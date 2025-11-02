from contextlib import contextmanager
from typing import Callable, Iterator, List, Optional

from .models import Lease, ProxyFilters
from .storage import IStorage


class ProxyManager:
    """
    Manages the lifecycle of proxies, including acquisition and release.

    Parameters
    ----------
    storage : IStorage
        The storage backend for proxy data.
    """

    DEFAULT_CONSUMER_NAME = "default"

    def __init__(self, storage: IStorage):
        self._storage = storage
        self._acquire_callbacks: List[
            Callable[[Optional[Lease], str, str, Optional[ProxyFilters]], None]
        ] = []
        self._release_callbacks: List[Callable[[Lease], None]] = []

    def acquire_proxy(
        self,
        pool_name: str,
        consumer_name: Optional[str] = None,
        duration_seconds: int = 300,
        filters: Optional[ProxyFilters] = None,
    ) -> Optional[Lease]:
        """
        Acquire a proxy from a named pool.

        If no consumer name is provided, the lease will be attributed to a
        default consumer.

        Parameters
        ----------
        pool_name : str
            The name of the proxy pool.
        consumer_name : str, optional
            The name of the consumer acquiring the proxy. Defaults to 'default'.
        duration_seconds : int, optional
            The duration of the lease in seconds, by default 300.
        filters : Optional[ProxyFilters], optional
            Filtering criteria for selecting a proxy, by default None.

        Returns
        -------
        Optional[Lease]
            The acquired lease, or None if no suitable proxy is found.
        """
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be greater than zero.")

        effective_consumer_name = consumer_name or self.DEFAULT_CONSUMER_NAME

        if effective_consumer_name == self.DEFAULT_CONSUMER_NAME:
            self._storage.ensure_consumer(effective_consumer_name)

        self._storage.cleanup_expired_leases()

        proxy = self._storage.find_available_proxy(pool_name, filters)
        lease: Optional[Lease] = None
        if proxy:
            lease = self._storage.create_lease(
                proxy, effective_consumer_name, duration_seconds
            )
        self._notify_acquire(
            lease=lease,
            pool_name=pool_name,
            consumer_name=effective_consumer_name,
            filters=filters,
        )
        return lease

    def release_proxy(self, lease: Lease) -> None:
        """
        Release a previously acquired proxy lease.

        Parameters
        ----------
        lease : Lease
            The lease to be released.
        """
        self._storage.release_lease(lease)
        self._notify_release(lease)

    def cleanup_expired_leases(self) -> int:
        """Trigger cleanup of expired leases in the storage backend."""
        return self._storage.cleanup_expired_leases()

    @contextmanager
    def with_lease(
        self,
        pool_name: str,
        consumer_name: Optional[str] = None,
        duration_seconds: int = 300,
        filters: Optional[ProxyFilters] = None,
    ) -> Iterator[Optional[Lease]]:
        """
        Context manager that acquires a lease and releases it automatically.

        Yields
        ------
        Optional[Lease]
            The acquired lease, or None if acquisition failed.
        """
        lease = self.acquire_proxy(
            pool_name=pool_name,
            consumer_name=consumer_name,
            duration_seconds=duration_seconds,
            filters=filters,
        )
        try:
            yield lease
        finally:
            if lease is not None:
                self.release_proxy(lease)

    def register_acquire_callback(
        self,
        callback: Callable[[Optional[Lease], str, str, Optional[ProxyFilters]], None],
    ) -> None:
        """Register a callback invoked after attempting to acquire a proxy."""
        self._acquire_callbacks.append(callback)

    def register_release_callback(
        self, callback: Callable[[Lease], None]
    ) -> None:
        """Register a callback invoked after releasing a proxy."""
        self._release_callbacks.append(callback)

    def _notify_acquire(
        self,
        lease: Optional[Lease],
        pool_name: str,
        consumer_name: str,
        filters: Optional[ProxyFilters],
    ) -> None:
        for callback in self._acquire_callbacks:
            callback(lease, pool_name, consumer_name, filters)

    def _notify_release(self, lease: Lease) -> None:
        for callback in self._release_callbacks:
            callback(lease)
