import os

import pytest

try:  # pragma: no cover - optional dependency
    from sqlalchemy import create_engine, text
except ImportError:  # pragma: no cover
    pytest.skip(
        "Install the 'postgres' extra to run the Postgres adapter suite.",
        allow_module_level=True,
    )

from pharox.models import Proxy, ProxyPool
from pharox.storage.postgres import PostgresStorage
from pharox.storage.postgres.tables import pool_table, proxy_table
from pharox.tests.adapters import (
    StorageContractFixtures,
    storage_contract_suite,
)

POSTGRES_URL = os.getenv("PHAROX_TEST_POSTGRES_URL")
ENGINE = create_engine(POSTGRES_URL) if POSTGRES_URL else None

pytestmark = pytest.mark.skipif(
    ENGINE is None,
    reason=(
        "Install the 'postgres' extra and set PHAROX_TEST_POSTGRES_URL "
        "to run the Postgres storage contract suite."
    ),
)


def _make_storage() -> PostgresStorage:
    assert ENGINE is not None
    storage = PostgresStorage(engine=ENGINE)
    with ENGINE.begin() as conn:
        conn.execute(
            text(
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
    return storage


def _seed_pool(storage: PostgresStorage, pool: ProxyPool) -> ProxyPool:
    assert ENGINE is not None
    with ENGINE.begin() as conn:
        conn.execute(
            pool_table.insert().values(
                id=pool.id,
                name=pool.name,
                description=pool.description,
            )
        )
    return pool


def _seed_proxy(storage: PostgresStorage, proxy: Proxy) -> Proxy:
    assert ENGINE is not None
    with ENGINE.begin() as conn:
        conn.execute(
            proxy_table.insert().values(
                id=proxy.id,
                pool_id=proxy.pool_id,
                host=str(proxy.host),
                port=proxy.port,
                protocol=proxy.protocol,
                status=proxy.status,
                max_concurrency=proxy.max_concurrency,
                current_leases=0,
                country=proxy.country,
                source=proxy.source,
                city=proxy.city,
            )
        )
    return proxy


@pytest.mark.contract
def test_postgres_storage_contract():
    """Ensure the Postgres adapter satisfies the storage contract suite."""
    fixtures = StorageContractFixtures(
        make_storage=_make_storage,
        seed_pool=_seed_pool,
        seed_proxy=_seed_proxy,
    )
    storage_contract_suite(fixtures)
