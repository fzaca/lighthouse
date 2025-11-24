from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Dict, Optional

from pharox.health import HealthCheckOrchestrator, HealthCheckStrategy
from pharox.manager import ProxyManager
from pharox.models import (
    HealthCheckOptions,
    HealthCheckResult,
    ProxyProtocol,
    ProxyStatus,
    SelectorStrategy,
)
from pharox.storage import IStorage, InMemoryStorage
from pharox.utils import bootstrap_consumer, bootstrap_pool, bootstrap_proxy


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    name: str
    iterations: int
    elapsed_seconds: float
    ops_per_second: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class SyntheticHealthCheckStrategy(HealthCheckStrategy):
    """Synthetic strategy that simulates latency without network IO."""

    def __init__(self, latency_ms: float = 1.0) -> None:
        """Initialize with a fixed latency (milliseconds)."""
        self._latency_ms = latency_ms

    async def check(
        self, proxy, options: HealthCheckOptions
    ) -> HealthCheckResult:
        """Simulate a health check by sleeping for the configured latency."""
        await asyncio.sleep(self._latency_ms / 1000)
        return HealthCheckResult(
            proxy_id=proxy.id,
            status=ProxyStatus.ACTIVE,
            latency_ms=int(self._latency_ms),
            protocol=proxy.protocol,
        )


def run_leasing_benchmark(
    storage: IStorage,
    *,
    iterations: int = 1000,
    pool_size: int = 32,
    selector: SelectorStrategy = SelectorStrategy.ROUND_ROBIN,
) -> BenchmarkResult:
    """Measure acquisition/release throughput for a storage backend."""
    manager = ProxyManager(storage=storage)
    consumer_name = "benchmark-consumer"
    pool_name = "benchmark-pool"
    bootstrap_consumer(storage, name=consumer_name)
    pool = bootstrap_pool(storage, name=pool_name)
    for i in range(pool_size):
        bootstrap_proxy(
            storage,
            pool=pool,
            host=f"10.0.0.{i+1}",
            port=8000 + i,
            protocol=ProxyProtocol.HTTP,
            status=ProxyStatus.ACTIVE,
        )

    start = perf_counter()
    hits = 0
    for _ in range(iterations):
        lease = manager.acquire_proxy(
            pool_name=pool_name,
            consumer_name=consumer_name,
            selector=selector,
        )
        if lease:
            hits += 1
            manager.release_proxy(lease)
    elapsed = perf_counter() - start
    ops_per_second = iterations / elapsed if elapsed > 0 else float("inf")
    return BenchmarkResult(
        name="leasing",
        iterations=iterations,
        elapsed_seconds=elapsed,
        ops_per_second=ops_per_second,
        metadata={
            "hits": hits,
            "misses": iterations - hits,
            "pool_size": pool_size,
            "selector": selector.value,
        },
    )


def run_health_benchmark(
    storage: IStorage,
    *,
    proxies: int = 32,
    rounds: int = 3,
    latency_ms: float = 1.0,
) -> BenchmarkResult:
    """Measure health-check persistence throughput for a storage backend."""
    pool = bootstrap_pool(storage, name="health-benchmark")
    seeded_proxies = []
    for i in range(proxies):
        seeded_proxies.append(
            bootstrap_proxy(
                storage,
                pool=pool,
                host=f"172.16.0.{i+1}",
                port=9000 + i,
                protocol=ProxyProtocol.HTTP,
                status=ProxyStatus.ACTIVE,
            )
        )

    checker = SyntheticHealthCheckStrategy(latency_ms=latency_ms)
    orchestrator = HealthCheckOrchestrator(
        storage=storage,
        checker=None,
    )
    orchestrator.checker.register_strategy(ProxyProtocol.HTTP, checker)
    orchestrator.checker.register_strategy(ProxyProtocol.HTTPS, checker)
    orchestrator.checker.register_strategy(ProxyProtocol.SOCKS4, checker)
    orchestrator.checker.register_strategy(ProxyProtocol.SOCKS5, checker)
    options = HealthCheckOptions(timeout=max(latency_ms / 1000, 0.001))

    async def _run_checks():
        start = perf_counter()
        for _ in range(rounds):
            async for _ in orchestrator.stream_health_checks(
                seeded_proxies, options=options
            ):
                pass
        return perf_counter() - start

    elapsed = asyncio.run(_run_checks())
    total_checks = proxies * rounds
    ops_per_second = total_checks / elapsed if elapsed > 0 else float("inf")
    return BenchmarkResult(
        name="health-check",
        iterations=total_checks,
        elapsed_seconds=elapsed,
        ops_per_second=ops_per_second,
        metadata={
            "proxies": proxies,
            "rounds": rounds,
            "latency_ms": latency_ms,
        },
    )


def build_storage(
    adapter: str, dsn: Optional[str] = None, prepare_schema: bool = True
) -> IStorage:
    """Construct a storage adapter for benchmarking."""
    if adapter == "in-memory":
        return InMemoryStorage()
    if adapter == "postgres":
        try:
            from sqlalchemy import create_engine

            from pharox.storage.postgres import PostgresStorage
            from pharox.storage.postgres.tables import metadata
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "PostgreSQL benchmarks require the postgres extra "
                "`pip install pharox[postgres]`."
            ) from exc

        if not dsn:
            raise ValueError("A DSN is required when adapter='postgres'.")
        engine = create_engine(dsn)
        if prepare_schema:
            metadata.create_all(engine)
        return PostgresStorage(engine)

    raise ValueError(f"Unsupported adapter '{adapter}'.")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark Pharox leasing and health-check throughput."
    )
    parser.add_argument(
        "--adapter",
        choices=["in-memory", "postgres"],
        default="in-memory",
        help="Storage adapter to benchmark.",
    )
    parser.add_argument(
        "--dsn",
        help=(
            "Connection string for the Postgres adapter "
            "(required when adapter=postgres)."
        ),
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1000,
        help="Number of leasing iterations to run.",
    )
    parser.add_argument(
        "--pool-size",
        type=int,
        default=32,
        help="Proxies to seed in the leasing benchmark pool.",
    )
    parser.add_argument(
        "--health-proxies",
        type=int,
        default=32,
        help="Proxies to seed when running the health benchmark.",
    )
    parser.add_argument(
        "--health-rounds",
        type=int,
        default=3,
        help="Rounds of health checks to execute.",
    )
    parser.add_argument(
        "--latency-ms",
        type=float,
        default=1.0,
        help="Synthetic latency to simulate in health checks.",
    )
    args = parser.parse_args(argv)

    storage = build_storage(args.adapter, args.dsn)
    leasing = run_leasing_benchmark(
        storage,
        iterations=args.iterations,
        pool_size=args.pool_size,
    )
    health = run_health_benchmark(
        storage,
        proxies=args.health_proxies,
        rounds=args.health_rounds,
        latency_ms=args.latency_ms,
    )

    print(
        f"[leasing] {leasing.ops_per_second:.1f} ops/s "
        f"({leasing.iterations} iterations in {leasing.elapsed_seconds:.3f}s) "
        f"hits={leasing.metadata['hits']} misses={leasing.metadata['misses']}"
    )
    print(
        f"[health] {health.ops_per_second:.1f} checks/s "
        f"({health.iterations} checks in {health.elapsed_seconds:.3f}s) "
        f"proxies={health.metadata['proxies']} rounds={health.metadata['rounds']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - manual entry point
    raise SystemExit(main())
