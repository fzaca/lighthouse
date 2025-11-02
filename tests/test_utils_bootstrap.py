from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from pharox.storage.in_memory import InMemoryStorage
from pharox.utils.bootstrap import (
    bootstrap_consumer,
    bootstrap_pool,
    bootstrap_proxy,
)


class _EnsureOnlyStorage:
    """Minimal stub that only implements ensure_consumer."""

    def __init__(self) -> None:
        self._names: list[str] = []
        self._next_id = uuid4()

    def ensure_consumer(  # pragma: no cover - exercised in tests
        self, name: str
    ) -> UUID:
        """Record the ensured consumer and return a fixed UUID."""
        self._names.append(name)
        return self._next_id


class _ProxyOnlyStorage:
    """Stub lacking get_proxy_by_id to exercise bootstrap fallback."""

    def __init__(self) -> None:
        self.last_proxy = None

    def add_proxy(self, proxy) -> None:  # pragma: no cover - exercised in tests
        """Persist the proxy reference for inspection."""
        self.last_proxy = proxy


def test_bootstrap_consumer_uses_add_consumer_when_available() -> None:
    """InMemoryStorage add_consumer path should store the generated consumer."""
    storage = InMemoryStorage()
    consumer = bootstrap_consumer(storage, name="tenant")

    fetched = storage._consumer_name_to_id.get("tenant")  # type: ignore[attr-defined]
    assert fetched == consumer.id


def test_bootstrap_consumer_falls_back_to_ensure() -> None:
    """When add_consumer is absent, ensure_consumer() should be used."""
    storage = _EnsureOnlyStorage()
    consumer = bootstrap_consumer(storage, name="tenant-fallback")

    assert consumer.id == storage._next_id


def test_bootstrap_pool_requires_add_pool() -> None:
    """Storage without add_pool should raise AttributeError."""
    storage = object()
    with pytest.raises(AttributeError):
        bootstrap_pool(storage, name="missing")


def test_bootstrap_pool_adds_pool_in_inmemory_storage() -> None:
    """InMemoryStorage should register the new pool and expose its ID."""
    storage = InMemoryStorage()
    pool = bootstrap_pool(storage, name="workers")

    assert pool.id in storage._pool_name_to_id.values()  # type: ignore[attr-defined]


def test_bootstrap_proxy_returns_copy_if_get_available() -> None:
    """When get_proxy_by_id exists, the stored copy should be returned."""
    storage = InMemoryStorage()
    pool = bootstrap_pool(storage, name="geo")

    proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="5.5.5.5",
        port=3128,
    )

    stored = storage.get_proxy_by_id(proxy.id)
    assert stored is not None
    assert stored == proxy
    assert stored is not proxy


def test_bootstrap_proxy_returns_same_instance_when_get_missing() -> None:
    """If storage lacks get_proxy_by_id, the original proxy is returned."""
    storage = _ProxyOnlyStorage()
    pool = bootstrap_pool(InMemoryStorage(), name="temp")

    proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="6.6.6.6",
        port=8080,
    )

    assert proxy is storage.last_proxy


def test_bootstrap_proxy_requires_add_proxy() -> None:
    """Storage without add_proxy should raise AttributeError."""
    class _NoProxyMethods:
        pass

    pool = bootstrap_pool(InMemoryStorage(), name="temp2")

    with pytest.raises(AttributeError):
        bootstrap_proxy(_NoProxyMethods(), pool=pool, host="7.7.7.7", port=80)
