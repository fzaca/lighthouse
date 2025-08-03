import asyncio
from typing import AsyncGenerator, List

import httpx

from .models import HealthCheckResult, Proxy, ProxyStatus


class HealthChecker:
    """Runs health checks on proxies."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient()
        self.test_url = "https://httpbin.org/ip"
        self.timeout = 5.0

    async def check_proxy_health(self, proxy: Proxy) -> HealthCheckResult:
        """Test a single proxy and returns its status."""
        try:
            start_time = asyncio.get_event_loop().time()
            proxy_url = f"{proxy.protocol}://{proxy.host}:{proxy.port}"
            response = await self.client.get(
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

            return HealthCheckResult(
                proxy_id=proxy.id, status=status, latency_ms=int(latency)
            )
        except (httpx.ProxyError, httpx.ConnectError, httpx.TimeoutException):
            return HealthCheckResult(
                proxy_id=proxy.id,
                status=ProxyStatus.INACTIVE,
                latency_ms=int(self.timeout * 1000),
            )
        except Exception:
            return HealthCheckResult(
                proxy_id=proxy.id,
                status=ProxyStatus.INACTIVE,
                latency_ms=int(self.timeout * 1000),
            )

    async def stream_health_checks(
        self, proxies: List[Proxy]
    ) -> AsyncGenerator[HealthCheckResult, None]:
        """
        Test a list of proxies and yields HealthCheckResult objects as they complete.

        This method uses `asyncio.as_completed` to concurrently run health checks
        on the provided list of proxies. As each check finishes, it yields the
        result, allowing the caller to process results as they become available
        rather than waiting for all checks to complete.

        Args:
            proxies: A list of `Proxy` objects to be tested.

        Yields
        ------
            An `AsyncGenerator` that produces `HealthCheckResult` objects.
        """
        tasks = [self.check_proxy_health(proxy) for proxy in proxies]
        for future in asyncio.as_completed(tasks):
            result = await future
            yield result
