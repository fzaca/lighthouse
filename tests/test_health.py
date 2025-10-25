import asyncio
from ipaddress import ip_address
from typing import List
from uuid import UUID

import httpx
import pytest
from pytest_mock import MockerFixture

from lighthouse.health import HealthChecker, HTTPHealthCheckStrategy
from lighthouse.models import (
    HealthCheckOptions,
    HealthCheckResult,
    Proxy,
    ProxyProtocol,
    ProxyStatus,
)


@pytest.fixture
def health_checker() -> HealthChecker:
    """Provide a HealthChecker instance."""
    return HealthChecker()


@pytest.fixture
def http_proxy(test_pool_id: UUID) -> Proxy:
    return Proxy(
        host=ip_address("1.1.1.1"),
        port=8080,
        protocol=ProxyProtocol.HTTP,
        pool_id=test_pool_id,
        status=ProxyStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_check_proxy_active(
    mocker: MockerFixture,
    health_checker: HealthChecker,
    http_proxy: Proxy,
):
    """An HTTP proxy returning an expected status code is marked active."""
    mock_response_ok = mocker.MagicMock(spec=httpx.Response)
    mock_response_ok.status_code = 204

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response_ok

    mock_cm = mocker.AsyncMock()
    mock_cm.__aenter__.return_value = mock_client

    mocker.patch("httpx.AsyncClient", return_value=mock_cm)

    options = HealthCheckOptions(
        target_url="https://example.com/status/204",
        expected_status_codes=[204],
    )

    result = await health_checker.check_proxy(http_proxy, options=options)

    assert result.proxy_id == http_proxy.id
    assert result.status == ProxyStatus.ACTIVE
    assert result.status_code == 204
    assert result.attempts == 1
    assert result.protocol == ProxyProtocol.HTTP


@pytest.mark.asyncio
async def test_check_proxy_slow(
    mocker: MockerFixture,
    health_checker: HealthChecker,
    http_proxy: Proxy,
):
    """A proxy exceeding the slow threshold is reported as slow."""
    mock_response_ok = mocker.MagicMock(spec=httpx.Response)
    mock_response_ok.status_code = 200

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response_ok

    mock_cm = mocker.AsyncMock()
    mock_cm.__aenter__.return_value = mock_client

    mocker.patch("httpx.AsyncClient", return_value=mock_cm)
    fake_loop = mocker.Mock()
    fake_loop.time.side_effect = [0.0, 0.01]
    mocker.patch("lighthouse.health.asyncio.get_running_loop", return_value=fake_loop)

    # Any latency will exceed this threshold since it's zero
    options = HealthCheckOptions(slow_threshold_ms=0)

    result = await health_checker.check_proxy(http_proxy, options=options)

    assert result.status == ProxyStatus.SLOW
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_check_proxy_inactive_after_retry(
    mocker: MockerFixture,
    health_checker: HealthChecker,
    http_proxy: Proxy,
):
    """Proxy becomes inactive after exhausting all attempts."""
    timeout_error = httpx.TimeoutException("request timed out")
    mock_response_fail = mocker.MagicMock(spec=httpx.Response)
    mock_response_fail.status_code = 503

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = [timeout_error, mock_response_fail]

    mock_cm = mocker.AsyncMock()
    mock_cm.__aenter__.return_value = mock_client

    mocker.patch("httpx.AsyncClient", return_value=mock_cm)

    options = HealthCheckOptions(expected_status_codes=[200], attempts=2)

    result = await health_checker.check_proxy(http_proxy, options=options)

    assert result.status == ProxyStatus.INACTIVE
    assert result.attempts == 2
    assert result.status_code == 503
    assert "Unexpected status code" in (result.error_message or "")


@pytest.mark.asyncio
async def test_stream_health_checks_preserves_completion_order(
    mocker: MockerFixture,
    health_checker: HealthChecker,
    http_proxy: Proxy,
    test_pool_id: UUID,
):
    """Streaming yields results as soon as individual checks finish."""
    faster_proxy = Proxy(
        host=ip_address("2.2.2.2"),
        port=9090,
        protocol=ProxyProtocol.HTTP,
        pool_id=test_pool_id,
        status=ProxyStatus.ACTIVE,
    )

    async def mock_check_proxy(proxy: Proxy, *_args, **_kwargs) -> HealthCheckResult:
        if proxy.host == http_proxy.host:
            await asyncio.sleep(0.02)
            return HealthCheckResult(
                proxy_id=proxy.id,
                status=ProxyStatus.ACTIVE,
                latency_ms=150,
                protocol=proxy.protocol,
            )
        await asyncio.sleep(0.01)
        return HealthCheckResult(
            proxy_id=proxy.id,
            status=ProxyStatus.INACTIVE,
            latency_ms=5000,
            protocol=proxy.protocol,
        )

    mocker.patch.object(health_checker, "check_proxy", side_effect=mock_check_proxy)

    results: List[HealthCheckResult] = []
    async for result in health_checker.stream_health_checks(
        [http_proxy, faster_proxy]
    ):
        results.append(result)

    assert len(results) == 2
    assert results[0].proxy_id == faster_proxy.id
    assert results[1].proxy_id == http_proxy.id


@pytest.mark.asyncio
async def test_custom_strategy_registration(
    health_checker: HealthChecker,
    http_proxy: Proxy,
):
    """Custom strategies can replace built-in behaviour."""

    class DummyStrategy(HTTPHealthCheckStrategy):
        async def check(
            self, proxy: Proxy, options: HealthCheckOptions
        ) -> HealthCheckResult:
            return HealthCheckResult(
                proxy_id=proxy.id,
                status=ProxyStatus.BANNED,
                latency_ms=0,
                protocol=proxy.protocol,
            )

    health_checker.register_strategy(ProxyProtocol.HTTP, DummyStrategy())

    result = await health_checker.check_proxy(http_proxy)

    assert result.status == ProxyStatus.BANNED
