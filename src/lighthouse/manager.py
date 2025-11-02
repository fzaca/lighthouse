from contextlib import contextmanager
from typing import Iterator, Optional

from lighthouse.models import Lease, ProxyFilters
from lighthouse.storage import IStorage


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
        if proxy:
            lease = self._storage.create_lease(
                proxy, effective_consumer_name, duration_seconds
            )
            return lease

        return None

    def release_proxy(self, lease: Lease) -> None:
        """
        Release a previously acquired proxy lease.

        Parameters
        ----------
        lease : Lease
            The lease to be released.
        """
        self._storage.release_lease(lease)

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
