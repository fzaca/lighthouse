"""Reference PostgreSQL adapter using SQLAlchemy Core."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional
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
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.sql import Select

from pharox.models import (
    HealthCheckResult,
    Lease,
    LeaseStatus,
    PoolStatsSnapshot,
    Proxy,
    ProxyFilters,
    ProxyStatus,
)
from pharox.storage import IStorage

from .tables import consumer_table, lease_table, pool_table, proxy_table

EARTH_RADIUS_KM = 6371.0


class PostgresStorage(IStorage):
    """SQLAlchemy-powered implementation of the `IStorage` contract."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def find_available_proxy(
        self, pool_name: str, filters: Optional[ProxyFilters] = None
    ) -> Optional[Proxy]:
        """Return the next proxy that matches the filters for the given pool."""
        with self._engine.begin() as conn:
            stmt = (
                select(proxy_table)
                .join(pool_table, proxy_table.c.pool_id == pool_table.c.id)
                .where(
                    pool_table.c.name == pool_name,
                    proxy_table.c.status == ProxyStatus.ACTIVE.value,
                    or_(
                        proxy_table.c.max_concurrency.is_(None),
                        proxy_table.c.current_leases
                        < proxy_table.c.max_concurrency,
                    ),
                )
                .order_by(proxy_table.c.checked_at.desc(), proxy_table.c.id.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            stmt = self._apply_filters(stmt, filters)
            row = conn.execute(stmt).mappings().first()
            return Proxy.model_validate(dict(row)) if row else None

    def create_lease(
        self, proxy: Proxy, consumer_name: str, duration_seconds: int
    ) -> Lease:
        """Persist a lease for the specified proxy and consumer."""
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive.")

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

        with self._engine.begin() as conn:
            consumer_id = self._ensure_consumer(conn, consumer_name)
            proxy_row = (
                conn.execute(
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
                .mappings()
                .first()
            )
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
            conn.execute(
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
            conn.execute(
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

    def ensure_consumer(self, consumer_name: str) -> UUID:
        """Ensure a consumer row exists and return its ID."""
        with self._engine.begin() as conn:
            return self._ensure_consumer(conn, consumer_name)

    def release_lease(self, lease: Lease) -> None:
        """Mark the lease as released and decrement the proxy counter."""
        released_at = lease.released_at or datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            db_lease = (
                conn.execute(
                    select(
                        lease_table.c.id,
                        lease_table.c.proxy_id,
                        lease_table.c.status,
                    )
                    .where(lease_table.c.id == lease.id)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if not db_lease or db_lease["status"] != LeaseStatus.ACTIVE.value:
                return

            conn.execute(
                update(lease_table)
                .where(lease_table.c.id == lease.id)
                .values(
                    status=LeaseStatus.RELEASED.value,
                    released_at=released_at,
                )
            )
            conn.execute(
                update(proxy_table)
                .where(proxy_table.c.id == db_lease["proxy_id"])
                .values(
                    current_leases=func.greatest(
                        0, proxy_table.c.current_leases - 1
                    )
                )
            )

    def cleanup_expired_leases(self) -> int:
        """Release all expired leases and return how many rows were updated."""
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            expired_rows = (
                conn.execute(
                    select(lease_table.c.id, lease_table.c.proxy_id)
                    .where(
                        lease_table.c.status == LeaseStatus.ACTIVE.value,
                        lease_table.c.expires_at <= now,
                    )
                    .with_for_update()
                )
                .mappings()
                .all()
            )
            if not expired_rows:
                return 0

            lease_ids = [row["id"] for row in expired_rows]
            conn.execute(
                update(lease_table)
                .where(lease_table.c.id.in_(lease_ids))
                .values(
                    status=LeaseStatus.RELEASED.value,
                    released_at=now,
                )
            )

            decrements = Counter(row["proxy_id"] for row in expired_rows)
            for proxy_id, count in decrements.items():
                conn.execute(
                    update(proxy_table)
                    .where(proxy_table.c.id == proxy_id)
                    .values(
                        current_leases=func.greatest(
                            0, proxy_table.c.current_leases - count
                        )
                    )
                )

            return len(lease_ids)

    def apply_health_check_result(
        self, result: HealthCheckResult
    ) -> Optional[Proxy]:
        """Update a proxy row based on the latest health check."""
        with self._engine.begin() as conn:
            conn.execute(
                update(proxy_table)
                .where(proxy_table.c.id == result.proxy_id)
                .values(
                    status=result.status.value,
                    checked_at=result.checked_at,
                )
            )
            refreshed = (
                conn.execute(
                    select(proxy_table).where(proxy_table.c.id == result.proxy_id)
                )
                .mappings()
                .first()
            )
            return Proxy.model_validate(dict(refreshed)) if refreshed else None

    def get_pool_stats(self, pool_name: str) -> Optional[PoolStatsSnapshot]:
        """Produce aggregate counters for the named pool."""
        with self._engine.begin() as conn:
            pool_row = (
                conn.execute(
                    select(pool_table.c.id, pool_table.c.name).where(
                        pool_table.c.name == pool_name
                    )
                )
                .mappings()
                .first()
            )
            if not pool_row:
                return None

            aggregates = (
                conn.execute(
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
                            proxy_table.c.current_leases > 0,
                        ).label("leased_proxies"),
                        func.coalesce(
                            func.sum(proxy_table.c.current_leases), 0
                        ).label("total_leases"),
                    ).where(proxy_table.c.pool_id == pool_row["id"])
                )
                .mappings()
                .first()
            )

            return PoolStatsSnapshot(
                pool_name=pool_row["name"],
                total_proxies=int(aggregates["total_proxies"] or 0),
                active_proxies=int(aggregates["active_proxies"] or 0),
                available_proxies=int(aggregates["available_proxies"] or 0),
                leased_proxies=int(aggregates["leased_proxies"] or 0),
                total_leases=int(aggregates["total_leases"] or 0),
            )

    def _apply_filters(self, stmt: Select, filters: Optional[ProxyFilters]) -> Select:
        if not filters:
            return stmt

        if filters.country:
            stmt = stmt.where(proxy_table.c.country == filters.country)
        if filters.source:
            stmt = stmt.where(proxy_table.c.source == filters.source)
        if filters.city:
            stmt = stmt.where(proxy_table.c.city == filters.city)
        if filters.isp:
            stmt = stmt.where(proxy_table.c.isp == filters.isp)
        if filters.asn is not None:
            stmt = stmt.where(proxy_table.c.asn == filters.asn)

        if filters.latitude is not None and filters.longitude is not None:
            stmt = stmt.where(
                proxy_table.c.latitude.is_not(None),
                proxy_table.c.longitude.is_not(None),
            )
            if filters.radius_km is None:
                stmt = stmt.where(
                    proxy_table.c.latitude == filters.latitude,
                    proxy_table.c.longitude == filters.longitude,
                )
            else:
                stmt = stmt.where(
                    self._distance_km(filters.latitude, filters.longitude)
                    <= filters.radius_km
                )

        return stmt

    def _ensure_consumer(self, conn: Connection, consumer_name: str) -> UUID:
        insert_stmt = (
            insert(consumer_table)
            .values(id=uuid4(), name=consumer_name)
            .on_conflict_do_nothing(index_elements=[consumer_table.c.name])
            .returning(consumer_table.c.id)
        )
        inserted = conn.execute(insert_stmt).scalar_one_or_none()
        if inserted:
            return inserted

        existing = (
            conn.execute(
                select(consumer_table.c.id).where(
                    consumer_table.c.name == consumer_name
                )
            )
            .scalars()
            .first()
        )
        if not existing:
            raise RuntimeError("Failed to load consumer row.")
        return existing

    def _sum_case(self, condition):
        return func.coalesce(
            func.sum(case((condition, 1), else_=0)),
            0,
        )

    def _distance_km(self, lat: float, lon: float):
        lat1 = func.radians(lat)
        lon1 = func.radians(lon)
        lat2 = func.radians(proxy_table.c.latitude)
        lon2 = func.radians(proxy_table.c.longitude)
        sin_dlat = func.sin((lat2 - lat1) / 2)
        sin_dlon = func.sin((lon2 - lon1) / 2)
        a = sin_dlat * sin_dlat + func.cos(lat1) * func.cos(lat2) * sin_dlon * sin_dlon
        c = 2 * func.atan2(func.sqrt(a), func.sqrt(1 - a))
        return literal(EARTH_RADIUS_KM) * c
