import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, Optional

from .manager import ProxyManager
from .models import Lease, ProxyFilters, SelectorStrategy


async def acquire_proxy_async(
    manager: ProxyManager,
    pool_name: str,
    consumer_name: Optional[str] = None,
    duration_seconds: int = 300,
    filters: Optional[ProxyFilters] = None,
    selector: Optional[SelectorStrategy] = None,
) -> Optional[Lease]:
    """
    Acquire a proxy without blocking the event loop.

    Runs ``ProxyManager.acquire_proxy`` in a worker thread via ``asyncio.to_thread``.
    """
    return await asyncio.to_thread(
        manager.acquire_proxy,
        pool_name,
        consumer_name,
        duration_seconds,
        filters,
        selector,
    )


async def release_proxy_async(manager: ProxyManager, lease: Lease) -> None:
    """
    Release a proxy lease from async code.

    Delegates to ``ProxyManager.release_proxy`` without blocking the loop.
    """
    await asyncio.to_thread(manager.release_proxy, lease)


@asynccontextmanager
async def with_lease_async(
    manager: ProxyManager,
    pool_name: str,
    consumer_name: Optional[str] = None,
    duration_seconds: int = 300,
    filters: Optional[ProxyFilters] = None,
    selector: Optional[SelectorStrategy] = None,
) -> AsyncIterator[Optional[Lease]]:
    """
    Async-compatible context manager mirroring ``ProxyManager.with_lease``.

    Useful when the storage backend is synchronous but callers need to use ``async``
    control flow.
    """
    lease = await acquire_proxy_async(
        manager=manager,
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
            await release_proxy_async(manager, lease)


async def acquire_proxy_with_retry_async(
    manager: ProxyManager,
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
    Async wrapper for ``ProxyManager.acquire_proxy_with_retry``.

    Runs the synchronous helper in a worker thread and keeps configurable retry
    behavior accessible to async callers.
    """
    return await asyncio.to_thread(
        manager.acquire_proxy_with_retry,
        pool_name,
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


@asynccontextmanager
async def with_retrying_lease_async(
    manager: ProxyManager,
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
) -> AsyncIterator[Optional[Lease]]:
    """Async context manager mirroring ``ProxyManager.with_retrying_lease``."""
    lease = await acquire_proxy_with_retry_async(
        manager=manager,
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
            await release_proxy_async(manager, lease)
