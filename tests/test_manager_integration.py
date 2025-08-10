from datetime import datetime, timezone
from uuid import uuid4

import pytest

from lighthouse.manager import ProxyManager
from lighthouse.models import Client, Lease, Proxy, ProxyFilters, ProxyPool, ProxyStatus
from lighthouse.storage.in_memory import InMemoryStorage

# --- Test Cases ---


def test_acquire_and_release_flow(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_client_name: str,
    test_pool_name: str,
):
    """
    Test the complete lifecycle: acquire a proxy and then release it.

    This test verifies that the `current_leases` count is correctly
    incremented on acquisition and decremented on release.
    """
    # 1. SETUP: Create a client, pool, and proxy and add them to the storage
    client = Client(name=test_client_name, api_key_hash="some-hash")
    pool = ProxyPool(name=test_pool_name)
    storage.add_client(client)
    storage.add_pool(pool)
    proxy = Proxy(
        host="1.1.1.1",
        port=8080,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )
    storage.add_proxy(proxy)

    # 2. ACQUIRE: Get a lease for the proxy
    lease = manager.acquire_proxy(
        pool_name=test_pool_name, client_name=test_client_name
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


def test_concurrency_limit_is_respected(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_client_name: str,
    test_pool_name: str,
):
    """Test that a proxy with a limited concurrency cannot be over-leased."""
    # SETUP: A proxy that allows only 2 concurrent leases
    client = Client(name=test_client_name, api_key_hash="some-hash")
    pool = ProxyPool(name=test_pool_name)
    storage.add_client(client)
    storage.add_pool(pool)
    proxy = Proxy(
        host="2.2.2.2",
        port=8080,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
        max_concurrency=2,
    )
    storage.add_proxy(proxy)

    # ACQUIRE up to the limit
    lease1 = manager.acquire_proxy(
        pool_name=test_pool_name, client_name=test_client_name
    )
    lease2 = manager.acquire_proxy(
        pool_name=test_pool_name, client_name=test_client_name
    )
    assert lease1 is not None
    assert lease2 is not None

    # VERIFY state
    proxy_in_storage = storage.get_proxy_by_id(proxy.id)
    assert proxy_in_storage.current_leases == 2

    # ATTEMPT TO EXCEED LIMIT: This call should fail
    failed_lease = manager.acquire_proxy(
        pool_name=test_pool_name, client_name=test_client_name
    )
    assert failed_lease is None, (
        "Should not be able to acquire a proxy beyond its concurrency limit"
    )


def test_unlimited_concurrency(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_client_name: str,
    test_pool_name: str,
):
    """Test that a proxy with unlimited concurrency (`max_concurrency=None`).

    This test ensures that a proxy configured without a concurrency limit
    can be leased repeatedly without failure.
    """
    # SETUP: A proxy with no concurrency limit
    client = Client(name=test_client_name, api_key_hash="some-hash")
    pool = ProxyPool(name=test_pool_name)
    storage.add_client(client)
    storage.add_pool(pool)
    proxy = Proxy(
        host="3.3.3.3",
        port=8080,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
        max_concurrency=None,
    )
    storage.add_proxy(proxy)

    # ACQUIRE multiple times
    for i in range(10):
        lease = manager.acquire_proxy(
            pool_name=test_pool_name, client_name=test_client_name
        )
        assert lease is not None, f"Failed to acquire lease number {i+1}"

    # VERIFY state
    proxy_in_storage = storage.get_proxy_by_id(proxy.id)
    assert proxy_in_storage.current_leases == 10


def test_inactive_proxy_is_not_acquired(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_client_name: str,
    test_pool_name: str,
):
    """Test that a proxy marked as INACTIVE cannot be acquired."""
    # SETUP: An inactive proxy
    client = Client(name=test_client_name, api_key_hash="some-hash")
    pool = ProxyPool(name=test_pool_name)
    storage.add_client(client)
    storage.add_pool(pool)
    proxy = Proxy(
        host="4.4.4.4",
        port=8080,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.INACTIVE,
    )
    storage.add_proxy(proxy)

    # ATTEMPT ACQUISITION
    lease = manager.acquire_proxy(
        pool_name=test_pool_name, client_name=test_client_name
    )
    assert lease is None


def test_acquire_from_non_existent_pool_returns_none(
    manager: ProxyManager, test_client_name: str
):
    """Test that acquiring from a pool that doesn't exist returns None."""
    lease = manager.acquire_proxy(
        pool_name="non-existent-pool", client_name=test_client_name
    )
    assert lease is None


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
        client_id=uuid4(),
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
    test_client_name: str,
    test_pool_name: str,
):
    """
    Test that calling release_proxy multiple times for the same lease is safe.

    The `current_leases` count should only be decremented once.
    """
    # SETUP
    client = Client(name=test_client_name, api_key_hash="some-hash")
    pool = ProxyPool(name=test_pool_name)
    storage.add_client(client)
    storage.add_pool(pool)
    proxy = Proxy(
        host="7.7.7.7",
        port=8080,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )
    storage.add_proxy(proxy)
    lease = manager.acquire_proxy(
        pool_name=test_pool_name, client_name=test_client_name
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
    test_client_name: str,
    test_pool_name: str,
):
    """Test that acquiring from a pool where all proxies are busy returns None."""
    # SETUP: Two exclusive-use proxies in the same pool
    client = Client(name=test_client_name, api_key_hash="some-hash")
    pool = ProxyPool(name=test_pool_name)
    storage.add_client(client)
    storage.add_pool(pool)
    proxy1 = Proxy(
        host="8.8.8.8",
        port=8001,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )
    proxy2 = Proxy(
        host="8.8.8.8",
        port=8002,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
        max_concurrency=1,
    )
    storage.add_proxy(proxy1)
    storage.add_proxy(proxy2)

    # ACT: Acquire both proxies, filling up the pool
    assert (
        manager.acquire_proxy(pool_name=test_pool_name, client_name=test_client_name)
        is not None
    )
    assert (
        manager.acquire_proxy(pool_name=test_pool_name, client_name=test_client_name)
        is not None
    )

    # ASSERT: The next attempt should fail
    assert (
        manager.acquire_proxy(pool_name=test_pool_name, client_name=test_client_name)
        is None
    )


def test_create_lease_raises_value_error_for_non_existent_proxy(
    storage: InMemoryStorage,
    test_client_name: str,
    test_pool_name: str,
):
    """
    Test that the storage layer raises ValueError for a non-existent proxy.

    This is a lower-level test directly on the storage to ensure it
    upholds its contract.
    """
    # SETUP: A proxy that exists in memory but NOT in the storage
    pool = ProxyPool(name=test_pool_name)
    storage.add_pool(pool)
    client = Client(name=test_client_name, api_key_hash="some-hash")
    storage.add_client(client)

    proxy_not_in_storage = Proxy(
        host="9.9.9.9", port=8080, protocol="http", pool_id=pool.id
    )

    # ACT & ASSERT
    with pytest.raises(ValueError, match="not found in storage"):
        storage.create_lease(
            proxy=proxy_not_in_storage,
            client_name=test_client_name,
            duration_seconds=60,
        )


# --- Integration Tests for Filtering Logic ---


def test_filtering_by_country_returns_correct_proxy(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_client_name: str,
    test_pool_name: str,
):
    """Test that acquiring a proxy can be successfully filtered by country."""
    # SETUP: Two proxies in the same pool but with different countries
    client = Client(name=test_client_name, api_key_hash="some-hash")
    pool = ProxyPool(name=test_pool_name)
    storage.add_client(client)
    storage.add_pool(pool)
    proxy_ar = Proxy(
        host="1.1.1.1",
        port=8001,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
        country="AR",
    )
    proxy_co = Proxy(
        host="2.2.2.2",
        port=8002,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
        country="CO",
    )
    storage.add_proxy(proxy_ar)
    storage.add_proxy(proxy_co)

    # ACT: Acquire a proxy with a filter for Argentina
    filters = ProxyFilters(country="AR")
    lease = manager.acquire_proxy(
        pool_name=test_pool_name, client_name=test_client_name, filters=filters
    )

    # ASSERT: The leased proxy must be the one from Argentina
    assert lease is not None
    assert lease.proxy_id == proxy_ar.id


def test_filtering_returns_none_if_no_match(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_client_name: str,
    test_pool_name: str,
):
    """Test that None is returned if no available proxy matches the filters."""
    # SETUP: Only one proxy from Argentina is available
    client = Client(name=test_client_name, api_key_hash="some-hash")
    pool = ProxyPool(name=test_pool_name)
    storage.add_client(client)
    storage.add_pool(pool)
    proxy_ar = Proxy(
        host="1.1.1.1",
        port=8001,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
        country="AR",
    )
    storage.add_proxy(proxy_ar)

    # ACT: Try to acquire a proxy with a filter for Colombia
    filters = ProxyFilters(country="CO")
    lease = manager.acquire_proxy(
        pool_name=test_pool_name, client_name=test_client_name, filters=filters
    )

    # ASSERT: No proxy should be found
    assert lease is None


def test_filtering_by_multiple_attributes(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_client_name: str,
    test_pool_name: str,
):
    """Test that filtering works correctly when multiple criteria are provided."""
    # SETUP: A mix of proxies to test combined filters
    client = Client(name=test_client_name, api_key_hash="some-hash")
    pool = ProxyPool(name=test_pool_name)
    storage.add_client(client)
    storage.add_pool(pool)
    proxy_ar_fast = Proxy(
        host="1.1.1.1",
        port=8001,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
        country="AR",
        source="fast-provider",
    )
    proxy_ar_slow = Proxy(
        host="1.1.1.1",
        port=8002,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
        country="AR",
        source="slow-provider",
    )
    storage.add_proxy(proxy_ar_fast)
    storage.add_proxy(proxy_ar_slow)

    # ACT: Filter by both country and source
    filters = ProxyFilters(country="AR", source="fast-provider")
    lease = manager.acquire_proxy(
        pool_name=test_pool_name, client_name=test_client_name, filters=filters
    )

    # ASSERT: Only the proxy matching both criteria should be returned
    assert lease is not None
    assert lease.proxy_id == proxy_ar_fast.id


def test_filtering_respects_concurrency_and_status(
    manager: ProxyManager,
    storage: InMemoryStorage,
    test_client_name: str,
    test_pool_name: str,
):
    """Test that filtering skips unavailable proxies that match criteria."""
    # SETUP: Two proxies match the filter, but one is busy and one is inactive
    client = Client(name=test_client_name, api_key_hash="some-hash")
    pool = ProxyPool(name=test_pool_name)
    storage.add_client(client)
    storage.add_pool(pool)
    proxy_ar_busy = Proxy(
        host="1.1.1.1",
        port=8001,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
        country="AR",
        max_concurrency=1,
        current_leases=1,
    )
    proxy_ar_inactive = Proxy(
        host="1.1.1.1",
        port=8002,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.INACTIVE,
        country="AR",
    )
    proxy_ar_available = Proxy(
        host="1.1.1.1",
        port=8003,
        protocol="http",
        pool_id=pool.id,
        status=ProxyStatus.ACTIVE,
        country="AR",
        max_concurrency=1,
    )
    storage.add_proxy(proxy_ar_busy)
    storage.add_proxy(proxy_ar_inactive)
    storage.add_proxy(proxy_ar_available)

    # ACT: Filter by country. The logic should skip the first two and find the third.
    filters = ProxyFilters(country="AR")
    lease = manager.acquire_proxy(
        pool_name=test_pool_name, client_name=test_client_name, filters=filters
    )

    # ASSERT: The only truly available proxy should be leased
    assert lease is not None
    assert lease.proxy_id == proxy_ar_available.id
