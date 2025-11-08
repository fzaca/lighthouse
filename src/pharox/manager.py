from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, Iterator, List, Optional

from .models import (
    AcquireEventPayload,
    Lease,
    ProxyFilters,
    ReleaseEventPayload,
)
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
            Callable[[AcquireEventPayload], None]
        ] = []
        self._release_callbacks: List[
            Callable[[ReleaseEventPayload], None]
        ] = []

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
        started_at = datetime.now(timezone.utc)

        if effective_consumer_name == self.DEFAULT_CONSUMER_NAME:
            self._storage.ensure_consumer(effective_consumer_name)

        self._storage.cleanup_expired_leases()

        proxy = self._storage.find_available_proxy(pool_name, filters)
        lease: Optional[Lease] = None
        if proxy:
            lease = self._storage.create_lease(
                proxy, effective_consumer_name, duration_seconds
            )
        completed_at = datetime.now(timezone.utc)

        self._notify_acquire(
            AcquireEventPayload(
                lease=lease,
                pool_name=pool_name,
                consumer_name=effective_consumer_name,
                filters=filters,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=max(
                    0,
                    int((completed_at - started_at).total_seconds() * 1000),
                ),
                pool_stats=self._storage.get_pool_stats(pool_name),
            )
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
        released_at = datetime.now(timezone.utc)
        lease.released_at = lease.released_at or released_at
        self._storage.release_lease(lease)
        pool_name = lease.pool_name
        pool_stats = (
            self._storage.get_pool_stats(pool_name) if pool_name else None
        )
        lease_duration_ms: Optional[int] = None
        if lease.released_at:
            lease_duration_ms = max(
                0,
                int(
                    (lease.released_at - lease.acquired_at).total_seconds()
                    * 1000
                ),
            )
        self._notify_release(
            ReleaseEventPayload(
                lease=lease,
                pool_name=pool_name,
                released_at=lease.released_at,
                lease_duration_ms=lease_duration_ms,
                pool_stats=pool_stats,
            )
        )

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
        self, callback: Callable[[AcquireEventPayload], None]
    ) -> None:
        """Register a callback invoked after attempting to acquire a proxy."""
        self._acquire_callbacks.append(callback)

    def register_release_callback(
        self, callback: Callable[[ReleaseEventPayload], None]
    ) -> None:
        """Register a callback invoked after releasing a proxy."""
        self._release_callbacks.append(callback)

    def _notify_acquire(self, payload: AcquireEventPayload) -> None:
        for callback in self._acquire_callbacks:
            callback(payload)

    def _notify_release(self, payload: ReleaseEventPayload) -> None:
        for callback in self._release_callbacks:
            callback(payload)
