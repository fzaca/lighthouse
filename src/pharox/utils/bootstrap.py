"""Bootstrap helpers for quickly preparing storage fixtures."""

from typing import Any, Optional, Union
from uuid import UUID, uuid4

from ..models import (
    Consumer,
    Proxy,
    ProxyPool,
    ProxyProtocol,
    ProxyStatus,
)
from ..storage import IStorage


def bootstrap_consumer(
    storage: IStorage,
    *,
    name: str = "default-consumer",
    consumer_id: Optional[UUID] = None,
) -> Consumer:
    """Ensure a consumer exists in the storage backend and return it."""
    consumer = Consumer(id=consumer_id or uuid4(), name=name)
    add_consumer = getattr(storage, "add_consumer", None)
    if callable(add_consumer):
        add_consumer(consumer)
        return consumer

    consumer_uuid = storage.ensure_consumer(name)
    return Consumer(id=consumer_uuid, name=name)


def bootstrap_pool(
    storage: IStorage,
    *,
    name: str = "default-pool",
    description: Optional[str] = None,
    pool_id: Optional[UUID] = None,
) -> ProxyPool:
    """Create a proxy pool inside the storage backend and return it."""
    pool = ProxyPool(id=pool_id or uuid4(), name=name, description=description)
    add_pool = getattr(storage, "add_pool", None)
    if not callable(add_pool):
        raise AttributeError("Storage backend does not support adding pools.")
    add_pool(pool)
    return pool


def bootstrap_proxy(
    storage: IStorage,
    *,
    pool: ProxyPool,
    host: Union[str, Any],
    port: int,
    protocol: ProxyProtocol = ProxyProtocol.HTTP,
    status: ProxyStatus = ProxyStatus.ACTIVE,
    proxy_id: Optional[UUID] = None,
    **extra_fields: Any,
) -> Proxy:
    """Create a proxy associated with the given pool and persist it to storage."""
    proxy = Proxy(
        id=proxy_id or uuid4(),
        host=host,
        port=port,
        protocol=protocol,
        pool_id=pool.id,
        status=status,
        **extra_fields,
    )
    add_proxy = getattr(storage, "add_proxy", None)
    if not callable(add_proxy):
        raise AttributeError("Storage backend does not support adding proxies.")
    add_proxy(proxy)

    get_proxy = getattr(storage, "get_proxy_by_id", None)
    if callable(get_proxy):
        stored_proxy = get_proxy(proxy.id)
        if stored_proxy is not None:
            return stored_proxy
    return proxy


__all__ = [
    "bootstrap_consumer",
    "bootstrap_pool",
    "bootstrap_proxy",
]
