import asyncio
from ipaddress import ip_address

import httpx
import pytest
from pytest_mock import MockerFixture

from lighthouse.health import HealthChecker
from lighthouse.models import HealthCheckResult, Proxy, ProxyStatus


@pytest.fixture
def health_checker() -> HealthChecker:
    """Provide a HealthChecker instance."""
    return HealthChecker()


@pytest.mark.asyncio
async def test_test_proxy_active(
    mocker: MockerFixture, health_checker: HealthChecker
):
    """Test that an active proxy is correctly identified."""
    proxy = Proxy(
        host=ip_address("1.1.1.1"), port=80, protocol="http", pool_name="test"
    )

    mock_response_ok = mocker.MagicMock(spec=httpx.Response)
    mock_response_ok.status_code = 200
    mock_response_ok.raise_for_status.return_value = None

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response_ok

    mock_cm = mocker.AsyncMock()
    mock_cm.__aenter__.return_value = mock_client

    mocker.patch("httpx.AsyncClient", return_value=mock_cm)

    result = await health_checker.check_proxy_health(proxy)

    assert result.proxy_id == proxy.id
    assert result.status == ProxyStatus.ACTIVE
    assert result.latency_ms is not None


@pytest.mark.asyncio
async def test_stream_health_checks(
    mocker: MockerFixture, health_checker: HealthChecker
):
    """Test that streaming health checks yields results as they complete."""
    proxies = [
        Proxy(host=ip_address("1.1.1.1"), port=80, protocol="http", pool_name="test"),
        Proxy(host=ip_address("2.2.2.2"), port=8080, protocol="http", pool_name="test"),
    ]

    async def mock_check_proxy_health(proxy: Proxy):
        if proxy.host == ip_address("1.1.1.1"):
            await asyncio.sleep(0.02)  # Simulate a slower check
            return HealthCheckResult(
                proxy_id=proxy.id, status=ProxyStatus.ACTIVE, latency_ms=200
            )
        else:
            await asyncio.sleep(0.01)  # Simulate a faster check
            return HealthCheckResult(
                proxy_id=proxy.id, status=ProxyStatus.INACTIVE, latency_ms=5000
            )

    mocker.patch.object(
        health_checker, "check_proxy_health", side_effect=mock_check_proxy_health
    )

    results = []
    async for result in health_checker.stream_health_checks(proxies):
        results.append(result)

    assert len(results) == 2
    # The faster check should have returned first
    assert results[0].status == ProxyStatus.INACTIVE
    assert results[1].status == ProxyStatus.ACTIVE
