"""Async PostgreSQL adapter contract test.

Skipped unless PHAROX_TEST_ASYNC_POSTGRES_URL is set and the async extra
(asyncpg + greenlet) is installed.
"""
import os

import pytest

try:  # pragma: no cover - optional dependency
    from sqlalchemy import text as sa_text
    from sqlalchemy.ext.asyncio import create_async_engine
except ImportError:  # pragma: no cover
    pytest.skip(
        "Install the 'async' extra to run the async Postgres adapter suite.",
        allow_module_level=True,
    )

from pharox.models import Proxy, ProxyPool
from pharox.storage.postgres import AsyncPostgresStorage
from pharox.storage.postgres.tables import pool_table, proxy_table

ASYNC_POSTGRES_URL = os.getenv("PHAROX_TEST_ASYNC_POSTGRES_URL")
ENGINE = create_async_engine(ASYNC_POSTGRES_URL) if ASYNC_POSTGRES_URL else None

pytestmark = pytest.mark.skipif(
    ENGINE is None,
    reason=(
        "Install the 'async' extra and set PHAROX_TEST_ASYNC_POSTGRES_URL "
        "to run the async Postgres storage contract suite."
    ),
)


@pytest.fixture()
async def storage():
    """Provide a clean AsyncPostgresStorage for each test."""
    assert ENGINE is not None
    async with ENGINE.begin() as conn:
        await conn.execute(
            sa_text(
                """
                TRUNCATE TABLE
                    lease,
                    proxy,
                    consumer,
                    pool_selector_state,
                    proxy_pool
                RESTART IDENTITY CASCADE
                """
            )
        )
    return AsyncPostgresStorage(engine=ENGINE)


@pytest.fixture()
async def pool(storage: AsyncPostgresStorage) -> ProxyPool:
    """Insert a pool and return it."""
    from uuid import uuid4

    from pharox.models import ProxyPool

    p = ProxyPool(id=uuid4(), name="test-pool")
    async with ENGINE.begin() as conn:  # type: ignore[union-attr]
        await conn.execute(pool_table.insert().values(id=p.id, name=p.name))
    return p


@pytest.fixture()
async def proxy(pool: ProxyPool) -> Proxy:
    """Insert a proxy under the test pool and return it."""
    from uuid import uuid4

    from pharox.models import ProxyProtocol, ProxyStatus

    p = Proxy(
        id=uuid4(),
        host="10.0.0.1",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
    )
    async with ENGINE.begin() as conn:  # type: ignore[union-attr]
        await conn.execute(
            proxy_table.insert().values(
                id=p.id,
                pool_id=p.pool_id,
                host=str(p.host),
                port=p.port,
                protocol=p.protocol.value,
                status=p.status.value,
            )
        )
    return p


@pytest.mark.asyncio
async def test_find_available_proxy(storage, proxy, pool):
    """find_available_proxy returns an active proxy."""
    result = await storage.find_available_proxy(pool.name)
    assert result is not None
    assert result.id == proxy.id


@pytest.mark.asyncio
async def test_ensure_consumer_idempotent(storage):
    """ensure_consumer is idempotent."""
    id1 = await storage.ensure_consumer("bot")
    id2 = await storage.ensure_consumer("bot")
    assert id1 == id2


@pytest.mark.asyncio
async def test_create_and_release_lease(storage, proxy, pool):
    """Full acquire → release cycle persists correctly."""
    await storage.ensure_consumer("worker")
    lease = await storage.create_lease(proxy, "worker", duration_seconds=60)
    assert lease.proxy_id == proxy.id

    await storage.release_lease(lease)

    # Double-release should be a no-op
    await storage.release_lease(lease)


@pytest.mark.asyncio
async def test_cleanup_expired_leases(storage, proxy, pool):
    """cleanup_expired_leases removes leases with past expires_at."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import update as sa_update

    await storage.ensure_consumer("sweeper")
    lease = await storage.create_lease(proxy, "sweeper", duration_seconds=60)

    # Force the lease to appear expired
    async with ENGINE.begin() as conn:  # type: ignore[union-attr]
        from pharox.storage.postgres.tables import lease_table

        await conn.execute(
            sa_update(lease_table)
            .where(lease_table.c.id == lease.id)
            .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )

    count = await storage.cleanup_expired_leases()
    assert count == 1


@pytest.mark.asyncio
async def test_add_proxies_bulk(storage, pool):
    """add_proxies_bulk inserts all proxies."""
    from uuid import uuid4

    from pharox.models import ProxyProtocol, ProxyStatus

    proxies = [
        Proxy(
            id=uuid4(),
            host=f"10.0.1.{i}",
            port=8080,
            protocol=ProxyProtocol.HTTP,
            pool_id=pool.id,
            status=ProxyStatus.ACTIVE,
        )
        for i in range(1, 4)
    ]
    count = await storage.add_proxies_bulk(proxies)
    assert count == 3


@pytest.mark.asyncio
async def test_apply_health_check_result(storage, proxy):
    """apply_health_check_result persists status changes."""
    from pharox.models import HealthCheckResult, ProxyProtocol, ProxyStatus

    result = HealthCheckResult(
        proxy_id=proxy.id,
        status=ProxyStatus.INACTIVE,
        latency_ms=500,
        protocol=ProxyProtocol.HTTP,
    )
    updated = await storage.apply_health_check_result(result)
    assert updated is not None
    assert updated.status == ProxyStatus.INACTIVE


@pytest.mark.asyncio
async def test_get_pool_stats(storage, proxy, pool):
    """get_pool_stats returns correct aggregate counts."""
    stats = await storage.get_pool_stats(pool.name)
    assert stats is not None
    assert stats.total_proxies == 1
    assert stats.active_proxies == 1
