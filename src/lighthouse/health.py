import asyncio
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Iterable, Optional

import httpx

from lighthouse.models import (
    HealthCheckOptions,
    HealthCheckResult,
    Proxy,
    ProxyProtocol,
    ProxyStatus,
)


class HealthCheckStrategy(ABC):
    """Defines the contract for executing protocol-specific health checks."""

    @abstractmethod
    async def check(
        self, proxy: Proxy, options: HealthCheckOptions
    ) -> HealthCheckResult:
        """Execute a health check using the provided proxy and options."""


class HTTPHealthCheckStrategy(HealthCheckStrategy):
    """Health check strategy for HTTP, HTTPS, and SOCKS proxies via HTTP requests."""

    async def check(
        self, proxy: Proxy, options: HealthCheckOptions
    ) -> HealthCheckResult:
        loop = asyncio.get_running_loop()
        last_error: Optional[str] = None
        status_code: Optional[int] = None
        latency_ms = int(options.timeout * 1000)

        target_url = str(options.target_url)

        async with httpx.AsyncClient(
            proxy=proxy.url, timeout=options.timeout
        ) as client:
            for attempt in range(1, options.attempts + 1):
                start_time = loop.time()
                try:
                    response = await client.get(
                        target_url,
                        headers=options.headers,
                        follow_redirects=options.allow_redirects,
                    )
                    status_code = response.status_code
                    latency_ms = int((loop.time() - start_time) * 1000)

                    if status_code in options.expected_status_codes:
                        status = (
                            ProxyStatus.ACTIVE
                            if latency_ms <= options.slow_threshold_ms
                            else ProxyStatus.SLOW
                        )
                        return HealthCheckResult(
                            proxy_id=proxy.id,
                            status=status,
                            latency_ms=latency_ms,
                            protocol=proxy.protocol,
                            attempts=attempt,
                            status_code=status_code,
                        )

                    last_error = (
                        f"Unexpected status code {status_code}; "
                        f"expected one of {options.expected_status_codes}"
                    )
                except httpx.TimeoutException as exc:
                    latency_ms = int(options.timeout * 1000)
                    last_error = f"Timeout while reaching {options.target_url}: {exc}"
                except httpx.HTTPError as exc:
                    latency_ms = int(options.timeout * 1000)
                    last_error = f"HTTP error while reaching {options.target_url}: {exc}"

        return HealthCheckResult(
            proxy_id=proxy.id,
            status=ProxyStatus.INACTIVE,
            latency_ms=latency_ms,
            protocol=proxy.protocol,
            attempts=options.attempts,
            status_code=status_code,
            error_message=last_error,
        )


class HealthChecker:
    """Protocol-aware proxy health checker suitable for any toolkit consumer."""

    def __init__(
        self,
        default_options: Optional[HealthCheckOptions] = None,
        protocol_options: Optional[Dict[ProxyProtocol, HealthCheckOptions]] = None,
        strategies: Optional[Dict[ProxyProtocol, HealthCheckStrategy]] = None,
    ) -> None:
        self._default_options = default_options or HealthCheckOptions()
        self._options_by_protocol: Dict[ProxyProtocol, HealthCheckOptions] = (
            protocol_options.copy() if protocol_options else {}
        )

        self._strategies: Dict[ProxyProtocol, HealthCheckStrategy] = (
            strategies.copy() if strategies else {}
        )
        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        http_strategy = self._strategies.get(ProxyProtocol.HTTP) or HTTPHealthCheckStrategy()
        self._strategies.setdefault(ProxyProtocol.HTTP, http_strategy)
        self._strategies.setdefault(ProxyProtocol.HTTPS, http_strategy)
        self._strategies.setdefault(ProxyProtocol.SOCKS4, http_strategy)
        self._strategies.setdefault(ProxyProtocol.SOCKS5, http_strategy)

    def register_strategy(
        self, protocol: ProxyProtocol, strategy: HealthCheckStrategy
    ) -> None:
        """Register or replace the strategy used for a given protocol."""

        self._strategies[protocol] = strategy

    def set_protocol_options(
        self, protocol: ProxyProtocol, options: HealthCheckOptions
    ) -> None:
        """Override the default options for a given protocol."""

        self._options_by_protocol[protocol] = options

    def _resolve_options(self, protocol: ProxyProtocol) -> HealthCheckOptions:
        return self._options_by_protocol.get(protocol, self._default_options)

    async def check_proxy(
        self,
        proxy: Proxy,
        options: Optional[HealthCheckOptions] = None,
    ) -> HealthCheckResult:
        """Execute a health check for the provided proxy."""

        strategy = self._strategies.get(proxy.protocol)
        if not strategy:
            raise ValueError(f"No health check strategy registered for {proxy.protocol}")

        effective_options = options or self._resolve_options(proxy.protocol)
        return await strategy.check(proxy, effective_options)

    async def stream_health_checks(
        self, proxies: Iterable[Proxy], options: Optional[HealthCheckOptions] = None
    ) -> AsyncGenerator[HealthCheckResult, None]:
        """Run health checks concurrently and yield results as they complete."""

        tasks = [self.check_proxy(proxy, options=options) for proxy in proxies]
        for future in asyncio.as_completed(tasks):
            yield await future
