import pytest

from pharox.manager import ProxyManager
from pharox.models import ProxyProtocol, ProxyStatus, RetryConfig
from pharox.storage.in_memory import InMemoryStorage
from pharox.utils.bootstrap import (
    bootstrap_consumer,
    bootstrap_pool,
    bootstrap_proxy,
)


def test_acquire_proxy_with_retry_eventually_succeeds(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
) -> None:
    """Ensure retries happen before success."""
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    recorded_delays = []
    seeded = {"done": False}

    def fake_sleep(delay: float) -> None:
        recorded_delays.append(delay)
        if not seeded["done"]:
            bootstrap_proxy(
                storage,
                pool=pool,
                host="10.10.0.1",
                port=8000,
                protocol=ProxyProtocol.HTTP,
                status=ProxyStatus.ACTIVE,
            )
            seeded["done"] = True

    lease = manager.acquire_proxy_with_retry(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
        max_attempts=3,
        backoff_seconds=0.1,
        sleep_fn=fake_sleep,
    )

    assert lease is not None
    assert recorded_delays == [0.1]


def test_acquire_proxy_with_retry_gives_up_after_max_attempts(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
) -> None:
    """Ensure the helper stops retrying after the configured attempts."""
    bootstrap_consumer(storage, name=test_consumer_name)
    bootstrap_pool(storage, name=test_pool_name)
    recorded_delays = []

    def fake_sleep(delay: float) -> None:
        recorded_delays.append(delay)

    lease = manager.acquire_proxy_with_retry(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
        max_attempts=2,
        backoff_seconds=0.1,
        sleep_fn=fake_sleep,
    )

    assert lease is None
    assert recorded_delays == [0.1]


def test_with_retrying_lease_releases_on_exit(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
) -> None:
    """Context manager should release even when retries were needed."""
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)

    seeded = {"done": False}

    def fake_sleep(_: float) -> None:
        if not seeded["done"]:
            bootstrap_proxy(
                storage,
                pool=pool,
                host="10.10.0.2",
                port=8001,
                protocol=ProxyProtocol.HTTP,
                status=ProxyStatus.ACTIVE,
                max_concurrency=1,
            )
            seeded["done"] = True

    with manager.with_retrying_lease(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
        max_attempts=2,
        backoff_seconds=0.1,
        sleep_fn=fake_sleep,
    ) as lease:
        assert lease is not None
        proxy_id = lease.proxy_id

    refreshed_proxy = storage.get_proxy_by_id(proxy_id)
    assert refreshed_proxy is not None
    assert refreshed_proxy.current_leases == 0


def test_acquire_proxy_with_retry_validates_arguments(
    manager: ProxyManager,
    test_pool_name: str,
) -> None:
    """Invalid retry arguments should raise helpful errors."""
    with pytest.raises(ValueError):
        manager.acquire_proxy_with_retry(
            pool_name=test_pool_name, max_attempts=0
        )
    with pytest.raises(ValueError):
        manager.acquire_proxy_with_retry(
            pool_name=test_pool_name, backoff_seconds=-1
        )
    with pytest.raises(ValueError):
        manager.acquire_proxy_with_retry(
            pool_name=test_pool_name, backoff_multiplier=0.5
        )
    with pytest.raises(ValueError):
        manager.acquire_proxy_with_retry(
            pool_name=test_pool_name, max_backoff_seconds=0
        )


def test_retry_config_validates_on_construction() -> None:
    """RetryConfig should raise ValueError for invalid parameters."""
    with pytest.raises(ValueError):
        RetryConfig(max_attempts=0)
    with pytest.raises(ValueError):
        RetryConfig(backoff_seconds=-1)
    with pytest.raises(ValueError):
        RetryConfig(backoff_multiplier=0.5)
    with pytest.raises(ValueError):
        RetryConfig(max_backoff_seconds=0)


def test_retry_config_overrides_individual_params(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
) -> None:
    """When retry_config is provided, individual params are ignored."""
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    bootstrap_proxy(
        storage,
        pool=pool,
        host="1.2.3.4",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
    )

    delays: list[float] = []

    config = RetryConfig(max_attempts=2, backoff_seconds=0.1)
    lease = manager.acquire_proxy_with_retry(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
        retry_config=config,
        sleep_fn=delays.append,
        # These should be ignored because retry_config is provided:
        max_attempts=99,
        backoff_seconds=99.0,
    )
    assert lease is not None
    assert delays == []  # succeeded on first attempt, no sleep


def test_with_retrying_lease_accepts_retry_config(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
) -> None:
    """with_retrying_lease should forward RetryConfig correctly."""
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    bootstrap_proxy(
        storage,
        pool=pool,
        host="5.6.7.8",
        port=3128,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
    )

    config = RetryConfig(max_attempts=1)
    with manager.with_retrying_lease(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
        retry_config=config,
    ) as lease:
        assert lease is not None
