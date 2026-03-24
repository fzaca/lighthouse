"""Thread-safety stress tests for InMemoryStorage and ProxyManager."""

from __future__ import annotations

import threading
from typing import List, Optional

from pharox.manager import ProxyManager
from pharox.models import Lease, ProxyProtocol, ProxyStatus
from pharox.storage.in_memory import InMemoryStorage
from pharox.utils.bootstrap import bootstrap_pool, bootstrap_proxy


def _storage_with_proxy(
    pool_name: str,
    max_concurrency: Optional[int] = None,
) -> tuple[InMemoryStorage, ProxyManager]:
    storage = InMemoryStorage()
    pool = bootstrap_pool(storage, name=pool_name)
    bootstrap_proxy(
        storage,
        pool=pool,
        host="10.0.0.1",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        max_concurrency=max_concurrency,
    )
    return storage, ProxyManager(storage=storage)


def test_concurrent_acquire_respects_max_concurrency() -> None:
    """Only max_concurrency threads should succeed in acquiring a lease."""
    storage, manager = _storage_with_proxy("race-pool", max_concurrency=1)
    n_threads = 20
    results: List[Optional[Lease]] = [None] * n_threads

    def acquire(idx: int) -> None:
        results[idx] = manager.acquire_proxy(
            pool_name="race-pool", duration_seconds=300
        )

    threads = [threading.Thread(target=acquire, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    acquired = [r for r in results if r is not None]
    assert len(acquired) == 1, (
        f"Expected exactly 1 lease with max_concurrency=1, got {len(acquired)}"
    )


def test_concurrent_acquire_unlimited_concurrency_all_succeed() -> None:
    """With unlimited concurrency every thread should get a lease."""
    storage, manager = _storage_with_proxy("unlimited-pool", max_concurrency=None)
    n_threads = 10
    results: List[Optional[Lease]] = [None] * n_threads

    def acquire(idx: int) -> None:
        results[idx] = manager.acquire_proxy(
            pool_name="unlimited-pool", duration_seconds=300
        )

    threads = [threading.Thread(target=acquire, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    acquired = [r for r in results if r is not None]
    assert len(acquired) == n_threads


def test_concurrent_acquire_release_no_errors() -> None:
    """Rapid acquire/release cycles across threads should not raise."""
    storage, manager = _storage_with_proxy("cycle-pool", max_concurrency=1)
    errors: List[Exception] = []

    def cycle(_: int) -> None:
        try:
            with manager.with_lease(
                pool_name="cycle-pool", duration_seconds=60
            ):
                pass
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=cycle, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Unexpected errors during concurrent acquire/release: {errors}"


def test_concurrent_health_check_updates_no_data_race() -> None:
    """Applying health check results from multiple threads must not corrupt state."""
    from datetime import datetime, timezone

    from pharox.models import HealthCheckResult, ProxyStatus

    storage = InMemoryStorage()
    pool = bootstrap_pool(storage, name="health-pool")
    proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="10.0.0.2",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
    )

    errors: List[Exception] = []

    def apply_result(status: ProxyStatus) -> None:
        try:
            result = HealthCheckResult(
                proxy_id=proxy.id,
                status=status,
                latency_ms=10,
                protocol=proxy.protocol,
                checked_at=datetime.now(timezone.utc),
            )
            storage.apply_health_check_result(result)
        except Exception as exc:
            errors.append(exc)

    statuses = [ProxyStatus.ACTIVE, ProxyStatus.SLOW, ProxyStatus.INACTIVE] * 10
    threads = [
        threading.Thread(target=apply_result, args=(s,)) for s in statuses
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Data race detected: {errors}"
    # Final state must be one of the valid statuses (no corruption).
    updated = storage.get_proxy_by_id(proxy.id)
    assert updated is not None
    valid = {ProxyStatus.ACTIVE, ProxyStatus.SLOW, ProxyStatus.INACTIVE}
    assert updated.status in valid
