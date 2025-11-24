from pharox.benchmarks import (
    BenchmarkResult,
    run_health_benchmark,
    run_leasing_benchmark,
)
from pharox.storage.in_memory import InMemoryStorage


def test_leasing_benchmark_returns_result():
    """Leasing benchmark returns a populated result."""
    storage = InMemoryStorage()
    result = run_leasing_benchmark(
        storage,
        iterations=20,
        pool_size=4,
    )

    assert isinstance(result, BenchmarkResult)
    assert result.iterations == 20
    assert result.metadata["misses"] == 0
    assert result.ops_per_second > 0


def test_health_benchmark_uses_synthetic_strategy():
    """Health benchmark uses synthetic strategy and aggregates counts."""
    storage = InMemoryStorage()
    result = run_health_benchmark(
        storage,
        proxies=4,
        rounds=2,
        latency_ms=0,
    )

    assert isinstance(result, BenchmarkResult)
    assert result.iterations == 8
    assert result.metadata["proxies"] == 4
    assert result.metadata["rounds"] == 2
