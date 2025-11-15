"""Reusable contract suites for Pharox storage adapters."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from time import sleep
from typing import Callable, Iterator, Optional
from uuid import uuid4

from ..models import (
    HealthCheckResult,
    PoolStatsSnapshot,
    Proxy,
    ProxyFilters,
    ProxyPool,
    ProxyProtocol,
    ProxyStatus,
    SelectorStrategy,
)
from ..storage import IStorage

ProxySeeder = Callable[[IStorage, Proxy], Proxy]
PoolSeeder = Callable[[IStorage, ProxyPool], ProxyPool]
StorageFactory = Callable[[], IStorage]
StorageTeardown = Optional[Callable[[IStorage], None]]


@dataclass
class StorageContractFixtures:
    """
    Configuration required to run the storage adapter contract suite.

    Attributes
    ----------
    make_storage:
        Callable that returns a fresh `IStorage` implementation. The factory
        should guarantee isolation between invocations (e.g., truncate tables or
        spin up a transaction per call).
    seed_pool:
        Function that persists the provided `ProxyPool` in the storage backend
        and returns the stored copy.
    seed_proxy:
        Function that persists the provided `Proxy` in the storage backend and
        returns the stored copy.
    teardown_storage:
        Optional callable invoked after each scenario to dispose of resources
        (closing DB connections, rolling back transactions, etc.).
    """

    make_storage: StorageFactory
    seed_pool: PoolSeeder
    seed_proxy: ProxySeeder
    teardown_storage: StorageTeardown = None


def storage_contract_suite(fixtures: StorageContractFixtures) -> None:
    """
    Execute the canonical contract tests for an `IStorage` implementation.

    Parameters
    ----------
    fixtures:
        Adapter-specific hooks for provisioning storages and seeding pools /
        proxies. Each assertion raises `AssertionError` if the contract is not
        satisfied.
    """
    suite = _StorageContractSuite(fixtures)
    suite.run()


class _StorageContractSuite:
    def __init__(self, fixtures: StorageContractFixtures):
        self._fixtures = fixtures
        self._proxy_counter = 0

    def run(self) -> None:
        """Execute all contract scenarios."""
        self._consumer_roundtrip()
        self._finds_active_proxy()
        self._filters_proxies()
        self._composite_filters()
        self._enforces_concurrency_limits()
        self._least_used_selector_prefers_lowest_load()
        self._round_robin_selector_cycles()
        self._lease_release_cycle()
        self._cleans_up_expired_leases()
        self._applies_health_results()
        self._returns_pool_stats()

    def _consumer_roundtrip(self) -> None:
        with self._storage() as storage:
            consumer_name = self._unique_name("consumer")
            first_id = storage.ensure_consumer(consumer_name)
            second_id = storage.ensure_consumer(consumer_name)
            assert first_id == second_id

    def _finds_active_proxy(self) -> None:
        with self._storage() as storage:
            pool = self._make_pool(storage, "available")
            proxy = self._make_proxy(storage, pool)
            candidate = storage.find_available_proxy(pool.name)
            assert candidate is not None
            assert candidate.id == proxy.id

    def _filters_proxies(self) -> None:
        with self._storage() as storage:
            pool = self._make_pool(storage, "filters")
            self._make_proxy(
                storage,
                pool,
                country="AR",
                source="fast-provider",
                city="Buenos Aires",
            )
            target = self._make_proxy(
                storage,
                pool,
                country="CL",
                source="andina",
                city="Santiago",
            )

            filters = ProxyFilters(country="CL", source="andina", city="Santiago")
            candidate = storage.find_available_proxy(pool.name, filters=filters)
            assert candidate is not None
            assert candidate.id == target.id

    def _composite_filters(self) -> None:
        with self._storage() as storage:
            pool = self._make_pool(storage, "composite")
            self._make_proxy(
                storage,
                pool,
                host="10.10.0.10",
                country="AR",
                source="latam",
                city="Buenos Aires",
            )
            target = self._make_proxy(
                storage,
                pool,
                host="10.10.0.20",
                country="BR",
                source="andina",
                city="Sao Paulo",
            )
            self._make_proxy(
                storage,
                pool,
                host="10.10.0.30",
                country="CL",
                source="blocked",
                city="Forbidden",
            )

            filters = ProxyFilters(
                any_of=[
                    ProxyFilters(country="AR", source="latam"),
                    ProxyFilters(
                        all_of=[
                            ProxyFilters(country="BR"),
                            ProxyFilters(source="andina"),
                        ]
                    ),
                ],
                none_of=[ProxyFilters(city="Forbidden")],
                predicate=lambda proxy: str(proxy.host).endswith(".20"),
            )

            candidate = storage.find_available_proxy(pool.name, filters=filters)
            assert candidate is not None
            assert candidate.id == target.id

    def _enforces_concurrency_limits(self) -> None:
        with self._storage() as storage:
            pool = self._make_pool(storage, "concurrency")
            self._make_proxy(storage, pool, max_concurrency=1)
            consumer = self._consumer_name()

            first = self._acquire(storage, pool.name, consumer)
            assert first is not None

            second = storage.find_available_proxy(pool.name)
            assert (
                second is None
            ), "Proxy with depleted concurrency should not be returned"

    def _least_used_selector_prefers_lowest_load(self) -> None:
        with self._storage() as storage:
            pool = self._make_pool(storage, "least-used")
            idle = self._make_proxy(storage, pool, max_concurrency=5)
            busy = self._make_proxy(storage, pool, max_concurrency=5)
            consumers = [self._consumer_name() for _ in range(2)]
            for consumer in consumers:
                storage.ensure_consumer(consumer)
                lease = storage.create_lease(busy, consumer, duration_seconds=60)
                assert lease is not None

            candidate = storage.find_available_proxy(
                pool.name, selector=SelectorStrategy.LEAST_USED
            )
            assert candidate is not None
            assert (
                candidate.id == idle.id
            ), "Least-used selector should prioritize lowest load"

    def _round_robin_selector_cycles(self) -> None:
        with self._storage() as storage:
            pool = self._make_pool(storage, "round-robin")
            proxies = [
                self._make_proxy(storage, pool, host=f"10.0.0.{i}")
                for i in range(1, 4)
            ]

            expected_order = [proxy.id for proxy in sorted(proxies, key=lambda p: p.id)]
            sequence = []
            for _ in range(5):
                candidate = storage.find_available_proxy(
                    pool.name, selector=SelectorStrategy.ROUND_ROBIN
                )
                assert candidate is not None
                sequence.append(candidate.id)

            assert sequence[:3] == expected_order
            assert sequence[3] == expected_order[0]

    def _lease_release_cycle(self) -> None:
        with self._storage() as storage:
            pool = self._make_pool(storage, "release")
            self._make_proxy(storage, pool, max_concurrency=1)
            consumer = self._consumer_name()
            lease = self._acquire(storage, pool.name, consumer)
            assert lease is not None

            storage.release_lease(lease)
            replacement = storage.find_available_proxy(pool.name)
            assert replacement is not None, "Released proxy should become available"

    def _cleans_up_expired_leases(self) -> None:
        with self._storage() as storage:
            pool = self._make_pool(storage, "cleanup")
            self._make_proxy(storage, pool, max_concurrency=1)
            consumer = self._consumer_name()
            lease = self._acquire(storage, pool.name, consumer, duration_seconds=1)
            assert lease is not None

            sleep(1.1)
            cleaned = storage.cleanup_expired_leases()
            assert cleaned == 1

            replacement = storage.find_available_proxy(pool.name)
            assert replacement is not None

    def _applies_health_results(self) -> None:
        with self._storage() as storage:
            pool = self._make_pool(storage, "health")
            proxy = self._make_proxy(storage, pool, status=ProxyStatus.SLOW)

            result = HealthCheckResult(
                proxy_id=proxy.id,
                status=ProxyStatus.BANNED,
                latency_ms=1500,
                protocol=proxy.protocol,
                checked_at=datetime.now(timezone.utc),
                error_message="timeout",
            )
            updated = storage.apply_health_check_result(result)
            assert updated is not None
            assert updated.status == ProxyStatus.BANNED
            assert updated.checked_at == result.checked_at

    def _returns_pool_stats(self) -> None:
        with self._storage() as storage:
            pool = self._make_pool(storage, "stats")
            self._make_proxy(storage, pool, status=ProxyStatus.ACTIVE)
            active_leased = self._make_proxy(
                storage, pool, status=ProxyStatus.ACTIVE, max_concurrency=1
            )
            self._make_proxy(storage, pool, status=ProxyStatus.INACTIVE)

            consumer = self._consumer_name()
            lease = self._acquire(storage, pool.name, consumer, proxy=active_leased)
            assert lease is not None

            stats = storage.get_pool_stats(pool.name)
            assert isinstance(stats, PoolStatsSnapshot)
            assert stats.total_proxies == 3
            assert stats.active_proxies == 2
            assert stats.available_proxies == 1  # one active proxy still free
            assert stats.leased_proxies == 1
            assert stats.total_leases == 1

            storage.release_lease(lease)
            refreshed = storage.get_pool_stats(pool.name)
            assert refreshed is not None
            assert refreshed.leased_proxies == 0
            assert refreshed.total_leases == 0

    @contextmanager
    def _storage(self) -> Iterator[IStorage]:
        storage = self._fixtures.make_storage()
        try:
            yield storage
        finally:
            if self._fixtures.teardown_storage:
                self._fixtures.teardown_storage(storage)

    def _make_pool(self, storage: IStorage, suffix: str) -> ProxyPool:
        pool = ProxyPool(name=self._unique_name(f"pool-{suffix}"))
        return self._fixtures.seed_pool(storage, pool)

    def _make_proxy(
        self,
        storage: IStorage,
        pool: ProxyPool,
        *,
        status: ProxyStatus = ProxyStatus.ACTIVE,
        max_concurrency: Optional[int] = 1,
        host: Optional[str] = None,
        source: Optional[str] = None,
        country: Optional[str] = None,
        city: Optional[str] = None,
    ) -> Proxy:
        self._proxy_counter += 1
        proxy = Proxy(
            pool_id=pool.id,
            host=host or f"10.0.0.{self._proxy_counter}",
            port=8080,
            protocol=ProxyProtocol.HTTP,
            status=status,
            max_concurrency=max_concurrency,
            source=source,
            country=country,
            city=city,
        )
        return self._fixtures.seed_proxy(storage, proxy)

    def _acquire(
        self,
        storage: IStorage,
        pool_name: str,
        consumer: str,
        duration_seconds: int = 60,
        proxy: Optional[Proxy] = None,
    ):
        storage.ensure_consumer(consumer)
        candidate = proxy or storage.find_available_proxy(pool_name)
        if candidate is None:
            return None
        return storage.create_lease(candidate, consumer, duration_seconds)

    def _consumer_name(self) -> str:
        return self._unique_name("consumer")

    @staticmethod
    def _unique_name(prefix: str) -> str:
        return f"{prefix}-{uuid4().hex[:8]}"


__all__ = ["StorageContractFixtures", "storage_contract_suite"]
