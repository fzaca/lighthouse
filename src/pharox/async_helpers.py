import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from .manager import ProxyManager
from .models import Lease, ProxyFilters


async def acquire_proxy_async(
    manager: ProxyManager,
    pool_name: str,
    consumer_name: Optional[str] = None,
    duration_seconds: int = 300,
    filters: Optional[ProxyFilters] = None,
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
    )
    try:
        yield lease
    finally:
        if lease is not None:
            await release_proxy_async(manager, lease)
