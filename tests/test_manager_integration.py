from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from pharox.manager import ProxyManager
from pharox.models import (
    AcquireEventPayload,
    Lease,
    LeaseStatus,
    ProxyFilters,
    ProxyProtocol,
    ProxyStatus,
    ReleaseEventPayload,
)
from pharox.storage.in_memory import InMemoryStorage
from pharox.utils.bootstrap import (
    bootstrap_consumer,
    bootstrap_pool,
    bootstrap_proxy,
)

# --- Test Cases ---


def test_acquire_and_release_flow(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """
    Test the complete lifecycle: acquire a proxy and then release it.

    This test verifies that the `current_leases` count is correctly
    incremented on acquisition and decremented on release.
    """
    # 1. SETUP: Create a consumer, pool, and proxy and add them to the storage
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="1.1.1.1",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )

    # 2. ACQUIRE: Get a lease for the proxy
    lease = manager.acquire_proxy(
        pool_name=test_pool_name, consumer_name=test_consumer_name
    )
    assert lease is not None
    assert lease.proxy_id == proxy.id

    # 3. VERIFY ACQUISITION: Check the internal state of the storage
    proxy_in_storage = storage.get_proxy_by_id(proxy.id)
    assert proxy_in_storage is not None
    assert proxy_in_storage.current_leases == 1

    # 4. RELEASE: Release the lease
    manager.release_proxy(lease)

    # 5. VERIFY RELEASE: Check the state again
    proxy_in_storage_after_release = storage.get_proxy_by_id(proxy.id)
    assert proxy_in_storage_after_release is not None
    assert proxy_in_storage_after_release.current_leases == 0


def test_acquire_proxy_rejects_non_positive_duration(
    manager: ProxyManager, test_pool_name: str
):
    """Ensure acquire_proxy rejects non-positive durations."""
    with pytest.raises(ValueError, match="greater than zero"):
        manager.acquire_proxy(pool_name=test_pool_name, duration_seconds=0)

    with pytest.raises(ValueError, match="greater than zero"):
        manager.acquire_proxy(pool_name=test_pool_name, duration_seconds=-60)


def test_concurrency_limit_is_respected(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Test that a proxy with a limited concurrency cannot be over-leased."""
    # SETUP: A proxy that allows only 2 concurrent leases
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="2.2.2.2",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        max_concurrency=2,
    )

    # ACQUIRE up to the limit
    lease1 = manager.acquire_proxy(
        pool_name=test_pool_name, consumer_name=test_consumer_name
    )
    lease2 = manager.acquire_proxy(
        pool_name=test_pool_name, consumer_name=test_consumer_name
    )
    assert lease1 is not None
    assert lease2 is not None

    # VERIFY state
    proxy_in_storage = storage.get_proxy_by_id(proxy.id)
    assert proxy_in_storage.current_leases == 2

    # ATTEMPT TO EXCEED LIMIT: This call should fail
    failed_lease = manager.acquire_proxy(
        pool_name=test_pool_name, consumer_name=test_consumer_name
    )
    assert failed_lease is None, (
        "Should not be able to acquire a proxy beyond its concurrency limit"
    )


def test_unlimited_concurrency(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Test that a proxy with unlimited concurrency (`max_concurrency=None`).

    This test ensures that a proxy configured without a concurrency limit
    can be leased repeatedly without failure.
    """
    # SETUP: A proxy with no concurrency limit
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="3.3.3.3",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        max_concurrency=None,
    )

    # ACQUIRE multiple times
    for i in range(10):
        lease = manager.acquire_proxy(
            pool_name=test_pool_name, consumer_name=test_consumer_name
        )
        assert lease is not None, f"Failed to acquire lease number {i+1}"

    # VERIFY state
    proxy_in_storage = storage.get_proxy_by_id(proxy.id)
    assert proxy_in_storage.current_leases == 10


def test_inactive_proxy_is_not_acquired(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Test that a proxy marked as INACTIVE cannot be acquired."""
    # SETUP: An inactive proxy
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    bootstrap_proxy(
        storage,
        pool=pool,
        host="4.4.4.4",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.INACTIVE,
    )

    # ATTEMPT ACQUISITION
    lease = manager.acquire_proxy(
        pool_name=test_pool_name, consumer_name=test_consumer_name
    )
    assert lease is None


def test_acquire_from_non_existent_pool_returns_none(
    manager: ProxyManager, test_consumer_name: str
):
    """Test that acquiring from a pool that doesn't exist returns None."""
    # SETUP
    storage = manager._storage
    bootstrap_consumer(storage, name=test_consumer_name)

    lease = manager.acquire_proxy(
        pool_name="non-existent-pool", consumer_name=test_consumer_name
    )
    assert lease is None


def test_acquire_proxy_with_default_consumer(
    manager: ProxyManager, storage: InMemoryStorage, test_pool_name: str
):
    """Test that a lease can be acquired without specifying a consumer."""
    # SETUP
    pool = bootstrap_pool(storage, name=test_pool_name)
    bootstrap_proxy(
        storage,
        pool=pool,
        host="5.5.5.5",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
    )

    # ACT: Call acquire_proxy without consumer_name
    lease = manager.acquire_proxy(pool_name=test_pool_name)

    # ASSERT
    assert lease is not None
    default_consumer_id = storage.ensure_consumer(manager.DEFAULT_CONSUMER_NAME)
    assert lease.consumer_id == default_consumer_id


def test_acquire_callbacks_are_invoked(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Registered acquire callbacks receive the lease and context."""
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    bootstrap_proxy(
        storage,
        pool=pool,
        host="10.10.10.10",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        country="AR",
    )

    captured: list[AcquireEventPayload] = []

    def on_acquire(payload: AcquireEventPayload):
        captured.append(payload)

    manager.register_acquire_callback(on_acquire)

    lease = manager.acquire_proxy(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
        filters=ProxyFilters(country="AR"),
    )

    assert lease is not None
    assert len(captured) == 1
    payload = captured[0]
    assert payload.lease == lease
    assert payload.pool_name == test_pool_name
    assert payload.consumer_name == test_consumer_name
    assert payload.filters is not None
    assert payload.filters.country == "AR"
    assert payload.duration_ms >= 0
    assert payload.pool_stats is not None
    assert payload.pool_stats.pool_name == test_pool_name


def test_acquire_callback_runs_on_miss(
    manager: ProxyManager, test_pool_name: str
):
    """Acquire callbacks execute even when no proxy is leased."""
    called: list[AcquireEventPayload] = []

    def on_acquire(payload: AcquireEventPayload):
        called.append(payload)

    manager.register_acquire_callback(on_acquire)

    result = manager.acquire_proxy(pool_name=test_pool_name)

    assert result is None
    assert len(called) == 1
    payload = called[0]
    assert payload.lease is None
    assert payload.pool_name == test_pool_name
    assert payload.consumer_name == ProxyManager.DEFAULT_CONSUMER_NAME
    assert payload.filters is None
    assert payload.pool_stats is None


def test_release_callbacks_are_invoked(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Registered release callbacks are executed after release."""
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    bootstrap_proxy(
        storage,
        pool=pool,
        host="11.11.11.11",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
    )

    captured: list[ReleaseEventPayload] = []

    def on_release(payload: ReleaseEventPayload):
        captured.append(payload)

    manager.register_release_callback(on_release)

    lease = manager.acquire_proxy(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
    )
    assert lease is not None
    manager.release_proxy(lease)

    assert len(captured) == 1
    payload = captured[0]
    assert payload.lease == lease
    assert payload.pool_name == test_pool_name
    assert payload.pool_stats is not None
    assert payload.lease_duration_ms is not None


def test_with_lease_context_manager_releases_proxy(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Ensure the with_lease helper releases proxies automatically."""
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="6.6.6.6",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )

    with manager.with_lease(
        pool_name=test_pool_name, consumer_name=test_consumer_name
    ) as lease:
        assert lease is not None
        proxy_in_storage = storage.get_proxy_by_id(proxy.id)
        assert proxy_in_storage is not None
        assert proxy_in_storage.current_leases == 1

    proxy_after_context = storage.get_proxy_by_id(proxy.id)
    assert proxy_after_context is not None
    assert proxy_after_context.current_leases == 0

    with pytest.raises(RuntimeError):
        with manager.with_lease(
            pool_name=test_pool_name, consumer_name=test_consumer_name
        ) as lease:
            assert lease is not None
            raise RuntimeError("forced error")

    proxy_after_exception = storage.get_proxy_by_id(proxy.id)
    assert proxy_after_exception is not None
    assert proxy_after_exception.current_leases == 0


# --- Additional test cases for robustness ---


def test_release_non_existent_lease_does_not_fail(
    manager: ProxyManager,
):
    """
    Test that releasing a lease that does not exist does not raise an error.

    This ensures the operation is idempotent and safe to call even with
    invalid data.
    """
    # SETUP: A fake lease that was never created in the storage
    fake_lease = Lease(
        proxy_id=uuid4(),
        consumer_id=uuid4(),
        expires_at=datetime.now(timezone.utc),
    )

    # ACT & ASSERT: The call should complete without raising an exception
    try:
        manager.release_proxy(fake_lease)
    except Exception as e:
        pytest.fail(f"Releasing a non-existent lease raised an exception: {e}")


def test_releasing_a_lease_twice_is_safe(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """
    Test that calling release_proxy multiple times for the same lease is safe.

    The `current_leases` count should only be decremented once.
    """
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="7.7.7.7",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )
    lease = manager.acquire_proxy(
        pool_name=test_pool_name, consumer_name=test_consumer_name
    )
    assert storage.get_proxy_by_id(proxy.id).current_leases == 1

    # ACT: Release the same lease twice
    manager.release_proxy(lease)
    assert storage.get_proxy_by_id(proxy.id).current_leases == 0

    manager.release_proxy(lease)

    # ASSERT: The count should not go below zero
    assert storage.get_proxy_by_id(proxy.id).current_leases == 0


def test_acquire_from_pool_with_no_available_proxies(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Test that acquiring from a pool where all proxies are busy returns None."""
    # SETUP: Two exclusive-use proxies in the same pool
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    bootstrap_proxy(
        storage,
        pool=pool,
        host="8.8.8.8",
        port=8001,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )
    bootstrap_proxy(
        storage,
        pool=pool,
        host="8.8.8.8",
        port=8002,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )

    # ACT: Acquire both proxies, filling up the pool
    assert (
        manager.acquire_proxy(
            pool_name=test_pool_name, consumer_name=test_consumer_name
        )
        is not None
    )
    assert (
        manager.acquire_proxy(
            pool_name=test_pool_name, consumer_name=test_consumer_name
        )
        is not None
    )

    # ASSERT: The next attempt should fail
    assert (
        manager.acquire_proxy(
            pool_name=test_pool_name, consumer_name=test_consumer_name
        )
        is None
    )


def test_create_lease_raises_value_error_for_non_existent_consumer(
    storage: InMemoryStorage,
    test_pool_name: str,
):
    """
    Test that the storage layer raises ValueError for a non-existent proxy.

    This is a lower-level test directly on the storage to ensure it
    upholds its contract.
    """
    # SETUP
    pool = bootstrap_pool(storage, name=test_pool_name)
    proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="9.9.9.9",
        port=8080,
        protocol=ProxyProtocol.HTTP,
    )

    # ACT & ASSERT
    with pytest.raises(ValueError, match="not found"):
        storage.create_lease(
            proxy=proxy,
            consumer_name="ghost-consumer",
            duration_seconds=60,
        )


# --- Integration Tests for Filtering Logic ---


def test_filtering_by_country_returns_correct_proxy(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Test that acquiring a proxy can be successfully filtered by country."""
    # SETUP: Two proxies in the same pool but with different countries
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    proxy_ar = bootstrap_proxy(
        storage,
        pool=pool,
        host="1.1.1.1",
        port=8001,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        country="AR",
    )
    bootstrap_proxy(
        storage,
        pool=pool,
        host="2.2.2.2",
        port=8002,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        country="CO",
    )

    # ACT: Acquire a proxy with a filter for Argentina
    filters = ProxyFilters(country="AR")
    lease = manager.acquire_proxy(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
        filters=filters
    )

    # ASSERT: The leased proxy must be the one from Argentina
    assert lease is not None
    assert lease.proxy_id == proxy_ar.id


def test_filtering_by_asn_zero_returns_proxy(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Ensure filters with ASN zero match proxies."""
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    proxy_zero = bootstrap_proxy(
        storage,
        pool=pool,
        host="3.3.3.3",
        port=9000,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        asn=0,
    )
    bootstrap_proxy(
        storage,
        pool=pool,
        host="4.4.4.4",
        port=9001,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        asn=64512,
    )

    lease = manager.acquire_proxy(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
        filters=ProxyFilters(asn=0),
    )

    assert lease is not None
    assert lease.proxy_id == proxy_zero.id


def test_filtering_returns_none_if_no_match(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Test that None is returned if no available proxy matches the filters."""
    # SETUP: Only one proxy from Argentina is available
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    bootstrap_proxy(
        storage,
        pool=pool,
        host="1.1.1.1",
        port=8001,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        country="AR",
    )

    # ACT: Try to acquire a proxy with a filter for Colombia
    filters = ProxyFilters(country="CO")
    lease = manager.acquire_proxy(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
        filters=filters
    )

    # ASSERT: No proxy should be found
    assert lease is None


def test_filtering_by_multiple_attributes(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Test that filtering works correctly when multiple criteria are provided."""
    # SETUP: A mix of proxies to test combined filters
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    proxy_ar_fast = bootstrap_proxy(
        storage,
        pool=pool,
        host="1.1.1.1",
        port=8001,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        country="AR",
        source="fast-provider",
    )
    bootstrap_proxy(
        storage,
        pool=pool,
        host="1.1.1.1",
        port=8002,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        country="AR",
        source="slow-provider",
    )

    # ACT: Filter by both country and source
    filters = ProxyFilters(country="AR", source="fast-provider")
    lease = manager.acquire_proxy(
        pool_name=test_pool_name, consumer_name=test_consumer_name, filters=filters
    )

    # ASSERT: Only the proxy matching both criteria should be returned
    assert lease is not None
    assert lease.proxy_id == proxy_ar_fast.id


def test_proxy_filters_require_coordinates_for_radius():
    """Radius-based filters without coordinates should be invalid."""
    with pytest.raises(ValueError):
        ProxyFilters(radius_km=10)


def test_proxy_filters_require_coordinate_pairs():
    """Latitude and longitude must be provided together."""
    with pytest.raises(ValueError):
        ProxyFilters(latitude=10)


def test_filtering_respects_concurrency_and_status(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Test that filtering skips unavailable proxies that match criteria."""
    # SETUP: Two proxies match the filter, but one is busy and one is inactive
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)
    bootstrap_proxy(
        storage,
        pool=pool,
        host="1.1.1.1",
        port=8001,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        country="AR",
        max_concurrency=1,
        current_leases=1,
    )
    bootstrap_proxy(
        storage,
        pool=pool,
        host="1.1.1.1",
        port=8002,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.INACTIVE,
        country="AR",
    )
    proxy_ar_available = bootstrap_proxy(
        storage,
        pool=pool,
        host="1.1.1.1",
        port=8003,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        country="AR",
        max_concurrency=1,
    )

    # ACT: Filter by country. The logic should skip the first two and find the third.
    filters = ProxyFilters(country="AR")
    lease = manager.acquire_proxy(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
        filters=filters
    )

    # ASSERT: The only truly available proxy should be leased
    assert lease is not None
    assert lease.proxy_id == proxy_ar_available.id


def test_filtering_by_geolocation(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Filtering with geographic radius returns the closest matching proxy."""
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)

    buenos_aires = bootstrap_proxy(
        storage,
        pool=pool,
        host="11.11.11.11",
        port=8001,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        latitude=-34.6037,
        longitude=-58.3816,
    )
    bootstrap_proxy(
        storage,
        pool=pool,
        host="22.22.22.22",
        port=8002,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        latitude=-33.4489,
        longitude=-70.6693,
    )

    filters = ProxyFilters(latitude=-34.6, longitude=-58.38, radius_km=50)
    lease = manager.acquire_proxy(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
        filters=filters,
    )

    assert lease is not None
    assert lease.proxy_id == buenos_aires.id


def test_filtering_by_radius_extremes(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Radius near zero requires exact matches; large radius reaches distant proxies."""
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)

    exact_proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="10.10.10.10",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        latitude=40.7128,
        longitude=-74.0060,
    )
    distant_proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="20.20.20.20",
        port=8080,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        latitude=51.5074,
        longitude=-0.1278,
    )

    # Near-zero radius should only match proxies at the exact coordinates.
    zero_radius_filters = ProxyFilters(
        latitude=40.7128,
        longitude=-74.0060,
        radius_km=0.0001,
    )
    first_lease = manager.acquire_proxy(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
        filters=zero_radius_filters,
    )
    assert first_lease is not None
    assert first_lease.proxy_id == exact_proxy.id
    manager.release_proxy(first_lease)

    # Mark the exact proxy as busy to force selection of the distant proxy.
    storage._pools[pool.id].proxies[exact_proxy.id].current_leases = 1
    storage._pools[pool.id].proxies[exact_proxy.id].max_concurrency = 1

    large_radius_filters = ProxyFilters(
        latitude=40.7128,
        longitude=-74.0060,
        radius_km=20000,
    )
    second_lease = manager.acquire_proxy(
        pool_name=test_pool_name,
        consumer_name=test_consumer_name,
        filters=large_radius_filters,
    )

    assert second_lease is not None
    assert second_lease.proxy_id == distant_proxy.id


def test_manager_reclaims_expired_leases(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_consumer_name: str,
    test_pool_name: str,
):
    """Expired leases are cleaned automatically when acquiring a proxy."""
    bootstrap_consumer(storage, name=test_consumer_name)
    pool = bootstrap_pool(storage, name=test_pool_name)

    proxy = bootstrap_proxy(
        storage,
        pool=pool,
        host="33.33.33.33",
        port=8003,
        protocol=ProxyProtocol.HTTP,
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )

    first_lease = manager.acquire_proxy(
        pool_name=test_pool_name, consumer_name=test_consumer_name, duration_seconds=10
    )
    assert first_lease is not None

    storage._leases[first_lease.id].expires_at = datetime.now(timezone.utc) - timedelta(
        seconds=1
    )

    second_lease = manager.acquire_proxy(
        pool_name=test_pool_name, consumer_name=test_consumer_name, duration_seconds=10
    )

    assert second_lease is not None
    assert second_lease.proxy_id == proxy.id
    assert storage._leases[first_lease.id].status == LeaseStatus.RELEASED
