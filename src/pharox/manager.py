import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, Iterator, List, Optional

from .models import (
    AcquireEventPayload,
    Lease,
    ProxyFilters,
    ReleaseEventPayload,
    SelectorStrategy,
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
        selector: Optional[SelectorStrategy] = None,
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

        strategy = selector or SelectorStrategy.FIRST_AVAILABLE
        proxy = self._storage.find_available_proxy(
            pool_name, filters, strategy
        )
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
                selector=strategy,
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

    def acquire_proxy_with_retry(
        self,
        pool_name: str,
        consumer_name: Optional[str] = None,
        duration_seconds: int = 300,
        filters: Optional[ProxyFilters] = None,
        selector: Optional[SelectorStrategy] = None,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
        backoff_multiplier: float = 2.0,
        max_backoff_seconds: Optional[float] = None,
        sleep_fn: Optional[Callable[[float], None]] = None,
    ) -> Optional[Lease]:
        """
        Acquire a proxy with retry/backoff semantics.

        Parameters
        ----------
        max_attempts : int
            Total attempts before giving up. Must be >= 1.
        backoff_seconds : float
            Initial delay (in seconds) before retrying. Set to 0 for immediate retries.
        backoff_multiplier : float
            Factor applied to the delay after each attempt. Must be >= 1.
        max_backoff_seconds : Optional[float]
            Upper bound for the delay (helpful to prevent unbounded waits).
        sleep_fn : Optional[Callable[[float], None]]
            Custom sleep implementation (useful for tests). Defaults to ``time.sleep``.
        """
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative.")
        if backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least 1.")
        if max_backoff_seconds is not None and max_backoff_seconds <= 0:
            raise ValueError("max_backoff_seconds must be positive when provided.")

        sleep = sleep_fn or time.sleep
        lease: Optional[Lease] = None
        attempts = 0
        delay = backoff_seconds

        while attempts < max_attempts and lease is None:
            lease = self.acquire_proxy(
                pool_name=pool_name,
                consumer_name=consumer_name,
                duration_seconds=duration_seconds,
                filters=filters,
                selector=selector,
            )
            attempts += 1

            if lease is not None or attempts >= max_attempts:
                break

            wait = delay
            if max_backoff_seconds is not None:
                wait = min(wait, max_backoff_seconds)
            if wait > 0:
                sleep(wait)

            delay *= backoff_multiplier
            if max_backoff_seconds is not None:
                delay = min(delay, max_backoff_seconds)

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
        selector: Optional[SelectorStrategy] = None,
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
            selector=selector,
        )
        try:
            yield lease
        finally:
            if lease is not None:
                self.release_proxy(lease)

    @contextmanager
    def with_retrying_lease(
        self,
        pool_name: str,
        consumer_name: Optional[str] = None,
        duration_seconds: int = 300,
        filters: Optional[ProxyFilters] = None,
        selector: Optional[SelectorStrategy] = None,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
        backoff_multiplier: float = 2.0,
        max_backoff_seconds: Optional[float] = None,
        sleep_fn: Optional[Callable[[float], None]] = None,
    ) -> Iterator[Optional[Lease]]:
        """
        Context manager that retries acquisitions before yielding.

        Mirrors ``with_lease`` while adding configurable retry/backoff handling.
        """
        lease = self.acquire_proxy_with_retry(
            pool_name=pool_name,
            consumer_name=consumer_name,
            duration_seconds=duration_seconds,
            filters=filters,
            selector=selector,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            backoff_multiplier=backoff_multiplier,
            max_backoff_seconds=max_backoff_seconds,
            sleep_fn=sleep_fn,
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
