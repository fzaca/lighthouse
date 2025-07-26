import asyncio

import httpx

from .models import ProxyStatus
from .storage import IStorage


class HealthChecker:
    """Runs health checks on proxies."""

    def __init__(self, storage: IStorage):
        self.storage = storage
        self.test_url = "https://httpbin.org/ip"
        self.timeout = 5.0

    async def run_check(self) -> None:
        """Fetch and test a batch of proxies."""
        proxies_to_test = self.storage.get_proxies_to_check()
        if not proxies_to_test:
            return

        async with httpx.AsyncClient() as client:
            tasks = [self._test_single_proxy(client, p) for p in proxies_to_test]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, tuple):
                proxy_id, status, latency = res
                self.storage.update_proxy_health(proxy_id, status, latency)

    async def _test_single_proxy(self, client, proxy):
        try:
            start_time = asyncio.get_event_loop().time()
            proxy_url = f"{proxy.protocol}://{proxy.host}:{proxy.port}"
            response = await client.get(
                self.test_url, proxy=proxy_url, timeout=self.timeout
            )
            response.raise_for_status()
            latency = (
                asyncio.get_event_loop().time() - start_time
            ) * 1000  # in milliseconds

            if response.status_code == 200:
                if latency > 2000:
                    status = ProxyStatus.SLOW
                else:
                    status = ProxyStatus.ACTIVE
            else:
                status = ProxyStatus.INACTIVE

            return (proxy.id, status, latency)
        except (httpx.ProxyError, httpx.ConnectError, httpx.TimeoutException):
            return (proxy.id, ProxyStatus.INACTIVE, self.timeout * 1000)
        except Exception:
            return (proxy.id, ProxyStatus.INACTIVE, self.timeout * 1000)
