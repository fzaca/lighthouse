"""Legacy import shim for the Postgres adapter tables."""

from pharox.storage.postgres.tables import (  # noqa: F401
    consumer_table,
    lease_table,
    metadata,
    pool_table,
    proxy_table,
    selector_state_table,
)

__all__ = [
    "metadata",
    "pool_table",
    "consumer_table",
    "proxy_table",
    "lease_table",
    "selector_state_table",
]
