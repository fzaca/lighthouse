from uuid import UUID, uuid4

import pytest

from lighthouse.manager import ProxyManager
from lighthouse.storage.in_memory import InMemoryStorage


@pytest.fixture
def storage() -> InMemoryStorage:
    """Provide a clean InMemoryStorage instance for each test."""
    return InMemoryStorage()


@pytest.fixture
def manager(storage: InMemoryStorage) -> ProxyManager:
    """Provide a ProxyManager instance configured with the in-memory storage."""
    return ProxyManager(storage=storage)


@pytest.fixture
def test_client_name() -> str:
    """Provide a consistent client name for tests."""
    return "test-client"


@pytest.fixture
def test_pool_name() -> str:
    """Provide a consistent pool name for tests."""
    return "test-pool"


@pytest.fixture
def test_pool_id() -> UUID:
    """Provide a consistent pool ID for tests."""
    return uuid4()
