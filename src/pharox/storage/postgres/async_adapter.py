"""Async PostgreSQL adapter using SQLAlchemy Core + asyncpg."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Sequence
from uuid import UUID, uuid4

from sqlalchemy import (
    and_,
    case,
    func,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql import Select

from pharox.models import (
    HealthCheckResult,
    Lease,
    LeaseStatus,
    PoolStatsSnapshot,
    Proxy,
    ProxyFilters,
    ProxyStatus,
    SelectorStrategy,
)
from pharox.storage.async_interface import IAsyncStorage
from pharox.utils.geo import EARTH_RADIUS_KM

from .tables import (
    consumer_table,
    lease_table,
    pool_table,
    proxy_table,
    selector_state_table,
)


class AsyncPostgresStorage(IAsyncStorage):
    """
    Async SQLAlchemy implementation of ``IAsyncStorage`` backed by PostgreSQL.

    Requires an ``AsyncEngine`` configured with the ``asyncpg`` driver::

        from sqlalchemy.ext.asyncio import create_async_engine
        from pharox.storage.postgres import AsyncPostgresStorage

        engine = create_async_engine(
            "postgresql+asyncpg://user:pass@localhost/db",
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        storage = AsyncPostgresStorage(engine)

    Use this adapter when your application is fully async (FastAPI, aiohttp,
    asyncio workers). For synchronous callers use ``PostgresStorage`` instead.

    Notes
    -----
    The underlying table schema is identical to ``PostgresStorage``; both
    adapters can share the same database and Alembic migrations.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        """Initialise with an ``AsyncEngine`` using the asyncpg dialect."""
        self._engine = engine

    # ------------------------------------------------------------------
    # IAsyncStorage
    # ------------------------------------------------------------------

    async def find_available_proxy(
        self,
        pool_name: str,
        filters: Optional[ProxyFilters] = None,
        selector: Optional[SelectorStrategy] = None,
    ) -> Optional[Proxy]:
        """Return the next available proxy from the named pool."""
        async with self._engine.begin() as conn:
            pool_row = (
                await conn.execute(
                    select(pool_table.c.id).where(pool_table.c.name == pool_name)
                )
            ).mappings().first()
            if not pool_row:
                return None
            pool_id = pool_row["id"]

            base_availability = select(proxy_table).where(
                proxy_table.c.pool_id == pool_id,
                proxy_table.c.status == ProxyStatus.ACTIVE.value,
                or_(
                    proxy_table.c.max_concurrency.is_(None),
                    proxy_table.c.current_leases < proxy_table.c.max_concurrency,
                ),
            )
            availability = self._apply_filters(base_availability, filters)
            strategy = selector or SelectorStrategy.FIRST_AVAILABLE
            excluded_ids: List[UUID] = []

            while True:
                candidate_stmt = availability
                if excluded_ids:
                    candidate_stmt = candidate_stmt.where(
                        ~proxy_table.c.id.in_(excluded_ids)
                    )
                row = await self._run_selector(conn, pool_id, candidate_stmt, strategy)
                if not row:
                    return None
                proxy_row = Proxy.model_validate(dict(row))
                if not filters or filters.matches(proxy_row):
                    if strategy == SelectorStrategy.ROUND_ROBIN:
                        await self._set_selector_last_id(
                            conn, pool_id, strategy, proxy_row.id
                        )
                    return proxy_row
                excluded_ids.append(proxy_row.id)

    async def create_lease(
        self, proxy: Proxy, consumer_name: str, duration_seconds: int
    ) -> Lease:
        """Atomically claim a proxy for a consumer."""
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

        async with self._engine.begin() as conn:
            consumer_id = await self._ensure_consumer(conn, consumer_name)
            proxy_row = (
                await conn.execute(
                    select(
                        proxy_table.c.id,
                        proxy_table.c.pool_id,
                        proxy_table.c.current_leases,
                        proxy_table.c.max_concurrency,
                        pool_table.c.name.label("pool_name"),
                    )
                    .join(pool_table, proxy_table.c.pool_id == pool_table.c.id)
                    .where(proxy_table.c.id == proxy.id)
                    .with_for_update()
                )
            ).mappings().first()

            if not proxy_row:
                raise ValueError(f"Proxy {proxy.id} not found.")

            max_concurrency = proxy_row["max_concurrency"]
            if (
                max_concurrency is not None
                and proxy_row["current_leases"] >= max_concurrency
            ):
                raise RuntimeError(f"Proxy {proxy.id} is no longer available.")

            lease_id = uuid4()
            acquired_at = datetime.now(timezone.utc)
            await conn.execute(
                lease_table.insert().values(
                    id=lease_id,
                    proxy_id=proxy_row["id"],
                    pool_id=proxy_row["pool_id"],
                    consumer_id=consumer_id,
                    pool_name=proxy_row["pool_name"],
                    status=LeaseStatus.ACTIVE.value,
                    acquired_at=acquired_at,
                    expires_at=expires_at,
                )
            )
            await conn.execute(
                update(proxy_table)
                .where(proxy_table.c.id == proxy_row["id"])
                .values(current_leases=proxy_table.c.current_leases + 1)
            )

            return Lease(
                id=lease_id,
                proxy_id=proxy_row["id"],
                consumer_id=consumer_id,
                pool_id=proxy_row["pool_id"],
                pool_name=proxy_row["pool_name"],
                expires_at=expires_at,
                acquired_at=acquired_at,
            )

    async def ensure_consumer(self, consumer_name: str) -> UUID:
        """Upsert a consumer row and return its UUID."""
        async with self._engine.begin() as conn:
            return await self._ensure_consumer(conn, consumer_name)

    async def release_lease(self, lease: Lease) -> None:
        """Mark a lease as released and decrement the proxy counter."""
        released_at = lease.released_at or datetime.now(timezone.utc)
        async with self._engine.begin() as conn:
            db_lease = (
                await conn.execute(
                    select(
                        lease_table.c.id,
                        lease_table.c.proxy_id,
                        lease_table.c.status,
                    )
                    .where(lease_table.c.id == lease.id)
                    .with_for_update()
                )
            ).mappings().first()

            if not db_lease or db_lease["status"] != LeaseStatus.ACTIVE.value:
                return

            await conn.execute(
                update(lease_table)
                .where(lease_table.c.id == lease.id)
                .values(status=LeaseStatus.RELEASED.value, released_at=released_at)
            )
            await conn.execute(
                update(proxy_table)
                .where(proxy_table.c.id == db_lease["proxy_id"])
                .values(
                    current_leases=func.greatest(
                        0, proxy_table.c.current_leases - 1
                    )
                )
            )

    async def cleanup_expired_leases(self) -> int:
        """Release all expired leases and return the count."""
        now = datetime.now(timezone.utc)
        async with self._engine.begin() as conn:
            expired_rows = (
                await conn.execute(
                    select(lease_table.c.id, lease_table.c.proxy_id)
                    .where(
                        lease_table.c.status == LeaseStatus.ACTIVE.value,
                        lease_table.c.expires_at <= now,
                    )
                    .with_for_update()
                )
            ).mappings().all()

            if not expired_rows:
                return 0

            lease_ids = [row["id"] for row in expired_rows]
            await conn.execute(
                update(lease_table)
                .where(lease_table.c.id.in_(lease_ids))
                .values(status=LeaseStatus.RELEASED.value, released_at=now)
            )

            decrements = Counter(row["proxy_id"] for row in expired_rows)
            for proxy_id, count in decrements.items():
                await conn.execute(
                    update(proxy_table)
                    .where(proxy_table.c.id == proxy_id)
                    .values(
                        current_leases=func.greatest(
                            0, proxy_table.c.current_leases - count
                        )
                    )
                )

            return len(lease_ids)

    async def add_proxies_bulk(self, proxies: Sequence[Proxy]) -> int:
        """Insert multiple proxies in a single transaction."""
        if not proxies:
            return 0
        rows = [
            {
                "id": proxy.id,
                "pool_id": proxy.pool_id,
                "host": str(proxy.host),
                "port": proxy.port,
                "protocol": proxy.protocol.value,
                "status": proxy.status.value,
                "credentials": (
                    proxy.credentials.model_dump() if proxy.credentials else None
                ),
                "source": proxy.source,
                "country": proxy.country,
                "city": proxy.city,
                "latitude": proxy.latitude,
                "longitude": proxy.longitude,
                "isp": proxy.isp,
                "asn": proxy.asn,
                "max_concurrency": proxy.max_concurrency,
                "checked_at": proxy.checked_at,
            }
            for proxy in proxies
        ]
        async with self._engine.begin() as conn:
            await conn.execute(insert(proxy_table).values(rows))
        return len(rows)

    async def apply_health_check_result(
        self, result: HealthCheckResult
    ) -> Optional[Proxy]:
        """Persist a health-check outcome and return the updated proxy."""
        async with self._engine.begin() as conn:
            await conn.execute(
                update(proxy_table)
                .where(proxy_table.c.id == result.proxy_id)
                .values(status=result.status.value, checked_at=result.checked_at)
            )
            refreshed = (
                await conn.execute(
                    select(proxy_table).where(proxy_table.c.id == result.proxy_id)
                )
            ).mappings().first()
            return Proxy.model_validate(dict(refreshed)) if refreshed else None

    async def get_pool_stats(self, pool_name: str) -> Optional[PoolStatsSnapshot]:
        """Return aggregate counters for the named pool."""
        async with self._engine.begin() as conn:
            pool_row = (
                await conn.execute(
                    select(pool_table.c.id, pool_table.c.name).where(
                        pool_table.c.name == pool_name
                    )
                )
            ).mappings().first()
            if not pool_row:
                return None

            aggregates = (
                await conn.execute(
                    select(
                        func.count(proxy_table.c.id).label("total_proxies"),
                        self._sum_case(
                            proxy_table.c.status == ProxyStatus.ACTIVE.value
                        ).label("active_proxies"),
                        self._sum_case(
                            and_(
                                proxy_table.c.status == ProxyStatus.ACTIVE.value,
                                or_(
                                    proxy_table.c.max_concurrency.is_(None),
                                    proxy_table.c.current_leases
                                    < proxy_table.c.max_concurrency,
                                ),
                            )
                        ).label("available_proxies"),
                        self._sum_case(
                            proxy_table.c.current_leases > 0
                        ).label("leased_proxies"),
                        func.coalesce(
                            func.sum(proxy_table.c.current_leases), 0
                        ).label("total_leases"),
                    ).where(proxy_table.c.pool_id == pool_row["id"])
                )
            ).mappings().first()

            if aggregates is None:
                return PoolStatsSnapshot(pool_name=pool_row["name"])
            return PoolStatsSnapshot(
                pool_name=pool_row["name"],
                total_proxies=int(aggregates["total_proxies"] or 0),
                active_proxies=int(aggregates["active_proxies"] or 0),
                available_proxies=int(aggregates["available_proxies"] or 0),
                leased_proxies=int(aggregates["leased_proxies"] or 0),
                total_leases=int(aggregates["total_leases"] or 0),
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _run_selector(
        self,
        conn: AsyncConnection,
        pool_id: UUID,
        availability: Select,
        strategy: SelectorStrategy,
    ) -> Optional[Any]:
        if strategy == SelectorStrategy.LEAST_USED:
            stmt = availability.order_by(
                proxy_table.c.current_leases.asc(),
                proxy_table.c.checked_at.asc(),
                proxy_table.c.id.asc(),
            )
            return (
                await conn.execute(stmt.limit(1).with_for_update(skip_locked=True))
            ).mappings().first()

        if strategy == SelectorStrategy.ROUND_ROBIN:
            return await self._select_round_robin(conn, pool_id, availability)

        stmt = availability.order_by(
            proxy_table.c.checked_at.desc(),
            proxy_table.c.id.asc(),
        )
        return (
            await conn.execute(stmt.limit(1).with_for_update(skip_locked=True))
        ).mappings().first()

    async def _select_round_robin(
        self,
        conn: AsyncConnection,
        pool_id: UUID,
        availability: Select,
    ) -> Optional[Any]:
        last_proxy_id = await self._get_selector_last_id(
            conn, pool_id, SelectorStrategy.ROUND_ROBIN
        )
        orderings: List[Any] = []
        if last_proxy_id:
            orderings.append(
                case((proxy_table.c.id > literal(last_proxy_id), 0), else_=1)
            )
        orderings.append(proxy_table.c.id.asc())
        stmt = availability.order_by(*orderings)
        return (
            await conn.execute(stmt.limit(1).with_for_update(skip_locked=True))
        ).mappings().first()

    async def _get_selector_last_id(
        self,
        conn: AsyncConnection,
        pool_id: UUID,
        strategy: SelectorStrategy,
    ) -> Optional[UUID]:
        row = (
            await conn.execute(
                select(selector_state_table.c.last_proxy_id)
                .where(
                    selector_state_table.c.pool_id == pool_id,
                    selector_state_table.c.strategy == strategy.value,
                )
                .with_for_update(skip_locked=True)
            )
        ).mappings().first()
        if row is not None:
            return row["last_proxy_id"]

        await conn.execute(
            insert(selector_state_table)
            .values(pool_id=pool_id, strategy=strategy.value, last_proxy_id=None)
            .on_conflict_do_nothing(
                index_elements=[
                    selector_state_table.c.pool_id,
                    selector_state_table.c.strategy,
                ]
            )
        )
        return None

    async def _set_selector_last_id(
        self,
        conn: AsyncConnection,
        pool_id: UUID,
        strategy: SelectorStrategy,
        proxy_id: UUID,
    ) -> None:
        await conn.execute(
            insert(selector_state_table)
            .values(pool_id=pool_id, strategy=strategy.value, last_proxy_id=proxy_id)
            .on_conflict_do_update(
                index_elements=[
                    selector_state_table.c.pool_id,
                    selector_state_table.c.strategy,
                ],
                set_={"last_proxy_id": proxy_id, "updated_at": func.now()},
            )
        )

    def _apply_filters(self, stmt: Select, filters: Optional[ProxyFilters]) -> Select:
        if not filters:
            return stmt
        clause = self._build_filter_clause(filters)
        if clause is None:
            return stmt
        return stmt.where(clause)

    def _build_filter_clause(self, filters: ProxyFilters) -> Optional[Any]:
        clauses = []
        mapping = {
            "country": proxy_table.c.country,
            "source": proxy_table.c.source,
            "city": proxy_table.c.city,
            "isp": proxy_table.c.isp,
        }
        for attr, column in mapping.items():
            value = getattr(filters, attr)
            if value:
                clauses.append(column == value)
        if filters.asn is not None:
            clauses.append(proxy_table.c.asn == filters.asn)

        if filters.latitude is not None and filters.longitude is not None:
            clauses.append(proxy_table.c.latitude.is_not(None))
            clauses.append(proxy_table.c.longitude.is_not(None))
            if filters.radius_km is None:
                clauses.append(proxy_table.c.latitude == filters.latitude)
                clauses.append(proxy_table.c.longitude == filters.longitude)
            else:
                clauses.append(
                    self._distance_km(filters.latitude, filters.longitude)
                    <= filters.radius_km
                )

        for child in filters.all_of or []:
            child_clause = self._build_filter_clause(child)
            if child_clause is not None:
                clauses.append(child_clause)

        if filters.any_of:
            any_of_clauses: List[Any] = [
                c
                for child in filters.any_of
                if (c := self._build_filter_clause(child)) is not None
            ]
            if any_of_clauses:
                clauses.append(or_(*any_of_clauses))

        if filters.none_of:
            none_of_clauses: List[Any] = [
                c
                for child in filters.none_of
                if (c := self._build_filter_clause(child)) is not None
            ]
            if none_of_clauses:
                clauses.append(~or_(*none_of_clauses))

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return and_(*clauses)

    async def _ensure_consumer(
        self, conn: AsyncConnection, consumer_name: str
    ) -> UUID:
        insert_stmt = (
            insert(consumer_table)
            .values(id=uuid4(), name=consumer_name)
            .on_conflict_do_nothing(index_elements=[consumer_table.c.name])
            .returning(consumer_table.c.id)
        )
        inserted = (await conn.execute(insert_stmt)).scalar_one_or_none()
        if inserted:
            return inserted

        existing = (
            await conn.execute(
                select(consumer_table.c.id).where(
                    consumer_table.c.name == consumer_name
                )
            )
        ).scalars().first()
        if not existing:
            raise RuntimeError("Failed to load consumer row.")
        return existing

    def _sum_case(self, condition: Any) -> Any:
        return func.coalesce(func.sum(case((condition, 1), else_=0)), 0)

    def _distance_km(self, lat: float, lon: float) -> Any:
        lat1 = func.radians(lat)
        lon1 = func.radians(lon)
        lat2 = func.radians(proxy_table.c.latitude)
        lon2 = func.radians(proxy_table.c.longitude)
        sin_dlat = func.sin((lat2 - lat1) / 2)
        sin_dlon = func.sin((lon2 - lon1) / 2)
        a = (
            sin_dlat * sin_dlat
            + func.cos(lat1) * func.cos(lat2) * sin_dlon * sin_dlon
        )
        c = 2 * func.atan2(func.sqrt(a), func.sqrt(1 - a))
        return literal(EARTH_RADIUS_KM) * c
