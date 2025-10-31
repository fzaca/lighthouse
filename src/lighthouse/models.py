from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Dict, List, Optional, Union
from urllib.parse import quote_plus
from uuid import UUID, uuid4

from pydantic import AnyHttpUrl, BaseModel, Field, IPvAnyAddress, model_validator


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


class ProxyProtocol(str, Enum):
    """Enumeration for supported proxy protocols."""

    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class Proxy(BaseModel):
    """Represents a network proxy."""

    id: UUID = Field(default_factory=uuid4)
    host: Union[IPvAnyAddress, str]
    port: int = Field(gt=0, le=65535)
    protocol: ProxyProtocol
    pool_id: UUID
    status: ProxyStatus = ProxyStatus.INACTIVE
    checked_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    credentials: Optional[ProxyCredentials] = None
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

    @property
    def url(self) -> str:
        """
        Construct the full proxy URL, including credentials if they exist.

        Credentials are URL-encoded to handle special characters safely.
        """
        auth_part = ""
        if self.credentials:
            user = quote_plus(self.credentials.user)
            password = quote_plus(self.credentials.password)
            auth_part = f"{user}:{password}@"

        scheme = (
            self.protocol.value
            if isinstance(self.protocol, ProxyProtocol)
            else str(self.protocol)
        )

        host = str(self.host)
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"

        return f"{scheme}://{auth_part}{host}:{self.port}"


class ProxyPool(BaseModel):
    """Represents a collection of proxies with a shared configuration."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    description: Optional[str] = None


class Lease(BaseModel):
    """Represents a lease on a proxy by a client."""

    id: UUID = Field(default_factory=uuid4)
    proxy_id: UUID
    consumer_id: UUID
    status: LeaseStatus = LeaseStatus.ACTIVE
    acquired_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    released_at: Optional[datetime] = None


class Consumer(BaseModel):
    """Represents an entity that consumes proxies."""

    id: UUID = Field(default_factory=uuid4)
    name: str


class HealthCheckResult(BaseModel):
    """Represents the result of a single proxy health check."""

    proxy_id: UUID
    status: ProxyStatus
    latency_ms: int
    protocol: ProxyProtocol
    attempts: Annotated[int, Field(default=1, ge=1)] = 1
    status_code: Optional[int] = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: Optional[str] = None


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
    radius_km: Annotated[
        Optional[float],
        Field(
            None,
            gt=0,
            description="Search radius in kilometers for geo-proximity queries."
        )
    ] = None

    @model_validator(mode="after")
    def _validate_geo_filters(self) -> "ProxyFilters":
        """Ensure geographic filters are provided with the required context."""
        lat, lon = self.latitude, self.longitude
        if (lat is None) != (lon is None):
            raise ValueError("latitude and longitude must be provided together")
        if self.radius_km is not None and (lat is None or lon is None):
            raise ValueError(
                "latitude and longitude must be provided when radius_km is set"
            )
        return self


class HealthCheckOptions(BaseModel):
    """Configuration for executing a proxy health check."""

    target_url: AnyHttpUrl = Field(
        default="https://httpbin.org/ip",
        description="HTTP endpoint used to verify proxy connectivity.",
    )
    timeout: float = Field(default=5.0, gt=0, description="Request timeout in seconds.")
    attempts: Annotated[int, Field(default=1, ge=1, le=5)] = 1
    expected_status_codes: List[int] = Field(default_factory=lambda: [200])
    slow_threshold_ms: Annotated[int, Field(default=2000, ge=0)] = 2000
    allow_redirects: bool = True
    headers: Dict[str, str] = Field(default_factory=dict)
