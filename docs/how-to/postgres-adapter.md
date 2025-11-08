---
title: Build a PostgreSQL Adapter
description: Implement the IStorage contract using PostgreSQL and SQLAlchemy as an example backend.
---
# Build a PostgreSQL Adapter

Pharox ships with an in-memory adapter for tests and demos. This guide shows how
to create a PostgreSQL-backed implementation using SQLAlchemy. The same approach
applies to other ORMs or async drivers—swap libraries as needed.

!!! note "Scope"
    This is a reference implementation you can adapt to your organisation's
    standards. It focuses on the required `IStorage` methods and leaves schema
    migrations to tools like Alembic. A maintained template (code + migrations +
    Docker Compose) lives under `examples/postgres/` in the repository so you
    can clone it directly.

!!! info "Install optional dependencies"
    The toolkit exposes a `postgres` extra that bundles SQLAlchemy, psycopg, and
    Alembic. Install it via `pip install 'pharox[postgres]'` (or
    `poetry install --extras postgres`) before running the examples below.

## 1. Define the Schema

Create tables for pools, proxies, consumers, and leases. Below is a simplified
schema that captures the fields Pharox expects.

```sql
CREATE TABLE proxy_pool (
    id UUID PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE consumer (
    id UUID PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE proxy (
    id UUID PRIMARY KEY,
    pool_id UUID NOT NULL REFERENCES proxy_pool(id),
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    protocol TEXT NOT NULL,
    status TEXT NOT NULL,
    max_concurrency INTEGER NOT NULL DEFAULT 1,
    current_leases INTEGER NOT NULL DEFAULT 0,
    asn INTEGER,
    country TEXT,
    source TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE lease (
    id UUID PRIMARY KEY,
    proxy_id UUID NOT NULL REFERENCES proxy(id),
    consumer_id UUID NOT NULL REFERENCES consumer(id),
    status TEXT NOT NULL,
    acquired_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    released_at TIMESTAMPTZ
);
```

Add indexes that match your filter workloads (e.g., `proxy(pool_id, status)`,
geospatial indexes for latitude/longitude).

## 2. Implement the Adapter

Use SQLAlchemy's ORM or Core—below we use Core for clarity.

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

from pharox.models import HealthCheckResult, Lease, Proxy, ProxyFilters
from pharox.storage import IStorage

from .tables import consumer_table, lease_table, pool_table, proxy_table

class PostgresStorage(IStorage):
    def __init__(self, conn: Connection):
        self._conn = conn

    def find_available_proxy(
        self, pool_name: str, filters: Optional[ProxyFilters] = None
    ) -> Optional[Proxy]:
        query = (
            select(proxy_table)
            .join(pool_table, proxy_table.c.pool_id == pool_table.c.id)
            .where(
                pool_table.c.name == pool_name,
                proxy_table.c.status == "active",
                proxy_table.c.current_leases < proxy_table.c.max_concurrency,
            )
            .order_by(proxy_table.c.created_at.asc())
            .limit(1)
        )

        if filters:
            if filters.country:
                query = query.where(proxy_table.c.country == filters.country)
            if filters.source:
                query = query.where(proxy_table.c.source == filters.source)
            if filters.asn is not None:
                query = query.where(proxy_table.c.asn == filters.asn)

        row = self._conn.execute(query).m.fetchone()
        return Proxy.model_validate(row) if row else None

    def create_lease(
        self, proxy: Proxy, consumer_name: str, duration_seconds: int
    ) -> Lease:
        expires_at = datetime.now(UTC) + timedelta(seconds=duration_seconds)

        consumer_id = self.ensure_consumer(consumer_name)

        lease_id = uuid4()
        self._conn.execute(
            lease_table.insert().values(
                id=lease_id,
                proxy_id=proxy.id,
                consumer_id=consumer_id,
                status="active",
                acquired_at=datetime.now(UTC),
                expires_at=expires_at,
            )
        )
        self._conn.execute(
            update(proxy_table)
            .where(proxy_table.c.id == proxy.id)
            .values(current_leases=proxy.current_leases + 1)
        )

        return Lease(
            id=lease_id,
            proxy_id=proxy.id,
            consumer_id=consumer_id,
            status="active",
            acquired_at=datetime.now(UTC),
            expires_at=expires_at,
        )

    def ensure_consumer(self, consumer_name: str):
        stmt = (
            insert(consumer_table)
            .values(id=uuid4(), name=consumer_name)
            .on_conflict_do_nothing(index_elements=["name"])
            .returning(consumer_table.c.id)
        )
        result = self._conn.execute(stmt)
        row = result.fetchone()
        if row:
            return row.id

        query = select(consumer_table.c.id).where(consumer_table.c.name == consumer_name)
        return self._conn.execute(query).scalar_one()

    def release_lease(self, lease: Lease) -> None:
        self._conn.execute(
            update(lease_table)
            .where(lease_table.c.id == lease.id)
            .values(status="released", released_at=datetime.now(UTC))
        )
        self._conn.execute(
            update(proxy_table)
            .where(proxy_table.c.id == lease.proxy_id)
            .values(current_leases=proxy_table.c.current_leases - 1)
        )

    def cleanup_expired_leases(self) -> int:
        now = datetime.now(UTC)
        query = select(lease_table.c.id, lease_table.c.proxy_id).where(
            lease_table.c.status == "active",
            lease_table.c.expires_at <= now,
        )
        expired = list(self._conn.execute(query))
        for lease_id, proxy_id in expired:
            self._conn.execute(
                update(lease_table)
                .where(lease_table.c.id == lease_id)
                .values(status="expired", released_at=now)
            )
            self._conn.execute(
                update(proxy_table)
                .where(proxy_table.c.id == proxy_id)
                .values(current_leases=proxy_table.c.current_leases - 1)
            )
        return len(expired)

    def apply_health_check_result(
        self, result: HealthCheckResult
    ) -> Optional[Proxy]:
        self._conn.execute(
            update(proxy_table)
            .where(proxy_table.c.id == result.proxy_id)
            .values(
                status=result.status.value,
                checked_at=result.checked_at,
                last_latency_ms=result.latency_ms,
            )
        )
        refreshed = self._conn.execute(
            select(proxy_table).where(proxy_table.c.id == result.proxy_id)
        ).m.fetchone()
        return Proxy.model_validate(refreshed) if refreshed else None
```

The full implementation should guard against race conditions (e.g., using
`FOR UPDATE` locks) and handle geospatial filters. Start simple, then iterate
based on scale.

!!! tip "Health result contract"
    Align your `apply_health_check_result` with the guidance in
    [Storage › Best Practices](../storage.md#apply_health_check_result-best-practices)
    so every adapter exposes consistent status/latency data to the toolkit.

## 3. Run Contract Tests

Before adopting the adapter in production, reuse the storage contract suite
bundled with Pharox:

```python
import pytest
from sqlalchemy import create_engine, text

from pharox.storage.postgres import PostgresStorage
from pharox.models import Proxy, ProxyPool
from pharox.tests.adapters import (
    StorageContractFixtures,
    storage_contract_suite,
)

engine = create_engine("postgresql+psycopg://user:pass@localhost/pharox")


def make_storage() -> PostgresStorage:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE lease, proxy, consumer, proxy_pool RESTART IDENTITY"))
    return PostgresStorage(engine)


def seed_pool(storage: PostgresStorage, pool: ProxyPool) -> ProxyPool:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO proxy_pool (id, name, description) VALUES (:id, :name, :description)"
            ),
            {"id": str(pool.id), "name": pool.name, "description": pool.description},
        )
    return pool


def seed_proxy(storage: PostgresStorage, proxy: Proxy) -> Proxy:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO proxy (
                    id, pool_id, host, port, protocol, status, max_concurrency,
                    current_leases, country, source, city
                )
                VALUES (
                    :id, :pool_id, :host, :port, :protocol, :status,
                    :max_concurrency, 0, :country, :source, :city
                )
                """
            ),
            {
                "id": str(proxy.id),
                "pool_id": str(proxy.pool_id),
                "host": proxy.host,
                "port": proxy.port,
                "protocol": proxy.protocol.value,
                "status": proxy.status.value,
                "max_concurrency": proxy.max_concurrency,
                "country": proxy.country,
                "source": proxy.source,
                "city": proxy.city,
            },
        )
    return proxy


@pytest.mark.contract
def test_postgres_storage_contract():
    fixtures = StorageContractFixtures(
        make_storage=make_storage,
        seed_pool=seed_pool,
        seed_proxy=seed_proxy,
    )
    storage_contract_suite(fixtures)
```

Set `PHAROX_TEST_POSTGRES_URL` to point at a disposable database (e.g.,
`postgresql+psycopg://pharox:pharox@localhost:5439/pharox`) and run
`poetry run pytest tests/test_storage_contract_postgres.py` in this repo to see
the suite in action.

!!! tip "Spin up PostgreSQL fast"
    Use `docker compose up postgres` from the `/examples/postgres` directory
    (see below) to boot a development instance with migrations pre-applied.

## 4. Share as an Example

Pharox already ships `pharox.storage.postgres.PostgresStorage` plus the
`examples/postgres/` toolkit (docker-compose, migrations, and shims). Copy that
directory into your service to kick-start a production implementation, and send
improvements upstream (docs, migrations, tests) so the template keeps getting
better. If you need to publish an internal fork, keep the README up to date so
new teams can bootstrap quickly.
