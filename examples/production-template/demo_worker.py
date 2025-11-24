"""
Demo worker that seeds a pool, emits lease metrics, and runs health sweeps.

This script is intended to be run inside the docker-compose template.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from typing import List
from uuid import uuid4

from prometheus_client import start_http_server
from sqlalchemy import select
from sqlalchemy.engine import Engine, create_engine

from pharox import (
    HealthCheckOptions,
    HealthCheckOrchestrator,
    ProxyManager,
    ProxyProtocol,
    ProxyStatus,
    SelectorStrategy,
    register_prometheus_metrics,
)
from pharox.models import Proxy
from pharox.storage.postgres import PostgresStorage
from pharox.storage.postgres.tables import metadata, pool_table, proxy_table

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pharox.demo-worker")


DSN = os.getenv(
    "PHAROX_DSN",
    "postgresql+psycopg://pharox:pharox@db:5432/pharox",
)
POOL_NAME = os.getenv("PHAROX_POOL", "residential")
METRICS_PORT = int(os.getenv("PHAROX_METRICS_PORT", "8000"))
HEALTH_INTERVAL_SECONDS = int(os.getenv("PHAROX_HEALTH_INTERVAL", "60"))


def _get_engine() -> Engine:
    return create_engine(DSN, pool_pre_ping=True, pool_size=5, max_overflow=5)


def seed_pool(engine: Engine) -> None:
    """Ensure a pool and proxies exist for the demo worker."""
    metadata.create_all(engine)
    with engine.begin() as conn:
        pool_row = (
            conn.execute(
                select(pool_table.c.id).where(pool_table.c.name == POOL_NAME)
            )
            .mappings()
            .first()
        )
        if pool_row:
            pool_id = pool_row["id"]
        else:
            result = conn.execute(
                pool_table.insert().values(
                    id=uuid4(), name=POOL_NAME, description="Demo pool"
                )
            )
            pool_id = result.inserted_primary_key[0]
            logger.info("Created pool %s (%s)", POOL_NAME, pool_id)

        existing = conn.execute(
            select(proxy_table.c.id, proxy_table.c.host)
            .where(proxy_table.c.pool_id == pool_id)
        ).mappings()
        if list(existing):
            return

        proxies = [
            dict(
                id=uuid4(),
                host="10.0.0.1",
                port=8001,
                protocol=ProxyProtocol.HTTP.value,
                status=ProxyStatus.ACTIVE.value,
            ),
            dict(
                id=uuid4(),
                host="10.0.0.2",
                port=8002,
                protocol=ProxyProtocol.HTTP.value,
                status=ProxyStatus.ACTIVE.value,
            ),
            dict(
                id=uuid4(),
                host="10.0.0.3",
                port=8003,
                protocol=ProxyProtocol.HTTP.value,
                status=ProxyStatus.ACTIVE.value,
            ),
        ]
        for proxy in proxies:
            conn.execute(
            proxy_table.insert().values(pool_id=pool_id, **proxy)
        )
        logger.info("Seeded %s demo proxies into pool %s", len(proxies), POOL_NAME)


def _load_proxies(engine: Engine) -> List[Proxy]:
    with engine.begin() as conn:
        rows = conn.execute(
            select(proxy_table).select_from(proxy_table)
        ).mappings()
        return [Proxy.model_validate(dict(row)) for row in rows]


def _simulate_work(manager: ProxyManager) -> None:
    lease = manager.acquire_proxy(
        pool_name=POOL_NAME,
        consumer_name="demo-worker",
        selector=SelectorStrategy.ROUND_ROBIN,
    )
    if lease is None:
        logger.warning("No proxy available; backing off")
        time.sleep(0.5)
        return

    time.sleep(random.uniform(0.1, 0.4))
    manager.release_proxy(lease)


async def _health_sweep(
    engine: Engine, orchestrator: HealthCheckOrchestrator
) -> None:
    proxies = _load_proxies(engine)
    if not proxies:
        return
    options = HealthCheckOptions(
        target_url="https://httpbin.org/ip",
        timeout=5.0,
        slow_threshold_ms=2000,
    )
    async for result in orchestrator.stream_health_checks(
        proxies, options=options
    ):
        logger.info(
            "health.result",
            extra={
                "proxy": result.proxy_id,
                "status": result.status.value,
                "latency_ms": result.latency_ms,
            },
        )


async def main() -> None:
    engine = _get_engine()
    seed_pool(engine)

    storage = PostgresStorage(engine)
    manager = ProxyManager(storage=storage)
    register_prometheus_metrics(manager)
    orchestrator = HealthCheckOrchestrator(storage=storage)

    start_http_server(METRICS_PORT)
    logger.info("Metrics server listening on :%s", METRICS_PORT)

    last_health = time.time()
    while True:
        _simulate_work(manager)
        now = time.time()
        if now - last_health >= HEALTH_INTERVAL_SECONDS:
            await _health_sweep(engine, orchestrator)
            last_health = now


if __name__ == "__main__":
    asyncio.run(main())
