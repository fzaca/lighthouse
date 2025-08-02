from ipaddress import ip_address

import httpx
import pytest
from pytest_mock import MockerFixture

from lighthouse.health import HealthChecker
from lighthouse.models import Proxy, ProxyStatus
from tests.test_manager import MockStorage


@pytest.fixture
def mock_storage() -> MockStorage:
    """Provide a clean instance of MockStorage for each test."""
    return MockStorage()


@pytest.fixture
def health_checker(mock_storage: MockStorage) -> HealthChecker:
    """Provide a HealthChecker instance with a mock storage."""
    return HealthChecker(mock_storage)


@pytest.mark.asyncio
async def test_test_proxy_active(
    mocker: MockerFixture, health_checker: HealthChecker
):
    """Test that an active proxy is correctly identified."""
    proxy = Proxy(
        host=ip_address("1.1.1.1"), port=80, protocol="http", pool_name="test"
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_response_ok = mocker.MagicMock(spec=httpx.Response)
    mock_response_ok.status_code = 200
    mock_response_ok.raise_for_status.return_value = None

    mock_client.get.return_value = mock_response_ok

    proxy_id, status, latency = await health_checker.test_proxy(mock_client, proxy)

    assert proxy_id == proxy.id
    assert status == ProxyStatus.ACTIVE
    assert latency is not None
