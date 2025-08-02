from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, IPvAnyAddress


class ProxyStatus(str, Enum):
    """Represents the operational status of a proxy."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SLOW = "slow"
    BANNED = "banned"


class LeaseStatus(str, Enum):
    """Represents the status of a proxy lease."""

    ACTIVE = "active"
    RELEASED = "released"


class ProxyCredentials(BaseModel):
    """Represents optional credentials for a proxy."""

    user: str
    password: str


class LifetimeStats(BaseModel):
    """Represents the lifetime usage statistics for a proxy."""

    total_bytes_up: int = Field(default=0, ge=0)
    total_bytes_down: int = Field(default=0, ge=0)


class SessionStats(BaseModel):
    """Represents the usage statistics for a single lease session."""

    bytes_up: int = Field(default=0, ge=0)
    bytes_down: int = Field(default=0, ge=0)
    request_count: int = Field(default=0, ge=0)


class Proxy(BaseModel):
    """Represents a network proxy."""

    id: UUID = Field(default_factory=uuid4)
    host: IPvAnyAddress
    port: int = Field(gt=0, le=65535)
    protocol: str
    pool_name: str
    status: ProxyStatus = ProxyStatus.INACTIVE
    last_checked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    credentials: Optional[ProxyCredentials] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    stats_lifetime: LifetimeStats = Field(default_factory=LifetimeStats)
    source: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    isp: Optional[str] = None
    asn: Optional[int] = None
    max_concurrency: Annotated[
        Optional[int],
        Field(
            default=None,
            gt=0,
            description=(
                "Maximum number of concurrent leases. "
                "If None, concurrency is unlimited."
            ),
        ),
    ] = None
    current_leases: Annotated[
        int,
        Field(
            default=0,
            ge=0,
            description=(
                "The current number of active leases. "
                "Managed by the storage layer."
            ),
        ),
    ] = 0


class ProxyPool(BaseModel):
    """Represents a collection of proxies with a shared configuration."""

    name: str
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class Lease(BaseModel):
    """Represents a lease on a proxy by a client."""

    id: UUID = Field(default_factory=uuid4)
    proxy_id: UUID
    client_id: UUID
    status: LeaseStatus = LeaseStatus.ACTIVE
    acquired_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    released_at: Optional[datetime] = None
    stats_session: SessionStats = Field(default_factory=SessionStats)


class Client(BaseModel):
    """Represents a client that consumes proxies."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    api_key_hash: str


class ProxyFilters(BaseModel):
    """Represents the filters to apply when finding an available proxy."""

    source: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    isp: Optional[str] = None
    asn: Optional[int] = None
    # For geo-proximity searches
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_km: Optional[int] = Field(
        None,
        gt=0,
        description="Search radius in kilometers for geo-proximity queries."
    )
