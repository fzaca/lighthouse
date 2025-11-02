from uuid import UUID, uuid4

import pytest

from pharox.manager import ProxyManager
from pharox.storage.in_memory import InMemoryStorage


@pytest.fixture
def storage() -> InMemoryStorage:
    """Provide a clean InMemoryStorage instance for each test."""
    return InMemoryStorage()


@pytest.fixture
def manager(storage: InMemoryStorage) -> ProxyManager:
    """Provide a ProxyManager instance configured with the in-memory storage."""
    return ProxyManager(storage=storage)


@pytest.fixture
def test_consumer_name() -> str:
    """Provide a consistent consumer name for tests."""
    return "test-entity"


@pytest.fixture
def test_pool_name() -> str:
    """Provide a consistent pool name for tests."""
    return "test-pool"


@pytest.fixture
def test_pool_id() -> UUID:
    """Provide a consistent pool ID for tests."""
    return uuid4()
