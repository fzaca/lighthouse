import asyncio
from typing import AsyncGenerator, List, Optional

import httpx

from .models import HealthCheckResult, Proxy, ProxyStatus


class HealthChecker:
    """A toolkit for performing various health and status checks on proxies."""

    def __init__(self, test_url: str = "https://httpbin.org/ip", timeout: float = 5.0):
        """
        Initialize the HealthChecker.

        Args:
            test_url: The URL to use for general health checks.
            timeout: The timeout in seconds for HTTP requests.
        """
        self.test_url = test_url
        self.timeout = timeout

    async def check_proxy_health(self, proxy: Proxy) -> HealthCheckResult:
        """
        Check the health of a single proxy by connecting to a test URL.

        Args:
            proxy: The Proxy object to test.

        Return:
            A HealthCheckResult object with the outcome of the check.
        """
        error_message: Optional[str] = None
        status: ProxyStatus
        try:
            start_time = asyncio.get_event_loop().time()
            async with httpx.AsyncClient(
                proxy=proxy.url, timeout=self.timeout
            ) as client:
                response = await client.get(self.test_url)
                response.raise_for_status()
            latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            if latency_ms > 2000:
                status = ProxyStatus.SLOW
            else:
                status = ProxyStatus.ACTIVE
        except (httpx.ProxyError, httpx.ConnectError, httpx.TimeoutException) as e:
            status = ProxyStatus.INACTIVE
            latency_ms = int(self.timeout * 1000)
            error_message = str(e)
        except Exception as e:
            status = ProxyStatus.INACTIVE
            latency_ms = int(self.timeout * 1000)
            error_message = f"An unexpected error occurred: {str(e)}"
        return HealthCheckResult(
            proxy_id=proxy.id,
            status=status,
            latency_ms=latency_ms,
            error_message=error_message,
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
