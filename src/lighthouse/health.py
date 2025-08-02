import asyncio

import httpx

from .models import ProxyStatus
from .storage import IStorage


class HealthChecker:
    """Runs health checks on proxies."""

    def __init__(self, storage: IStorage, client: httpx.AsyncClient | None = None):
        self.storage = storage
        self.client = client or httpx.AsyncClient()
        self.test_url = "https://httpbin.org/ip"
        self.timeout = 5.0

    async def test_proxy(self, client, proxy):
        """Tests a single proxy and returns its status."""
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
