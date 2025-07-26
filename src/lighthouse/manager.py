from typing import Optional

from lighthouse.models import Lease, Proxy, ProxyFilters
from lighthouse.storage import IStorage


class ProxyManager:
    """
    Manages the lifecycle of proxies, including acquisition and release.

    Parameters
    ----------
    storage : IStorage
        The storage backend for proxy data.
    """

    def __init__(self, storage: IStorage):
        self._storage = storage

    def acquire_proxy(
        self, pool_name: str, client_id: str, filters: Optional[ProxyFilters] = None
    ) -> Optional[Proxy]:
        """
        Acquire a proxy from a given pool for a specific client.

        Optionally matching given filters.

        Parameters
        ----------
        pool_name : str
            The name of the proxy pool.
        client_id : str
            The ID of the client acquiring the proxy.
        filters : Optional[ProxyFilters], optional
            Filtering criteria for selecting a proxy, by default None.

        Returns
        -------
        Optional[Proxy]
            The acquired proxy, or None if no suitable proxy is available.
        """
        proxy = self._storage.find_available_proxy(pool_name, filters)
        if proxy:
            self._storage.create_lease(proxy, client_id)
            return proxy

        return None

    def release_proxy(self, lease: Lease) -> None:
        """
        Release a previously acquired proxy lease.

        Parameters
        ----------
        lease : Lease
            The lease to be released.
        """
        pass
