from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from math import asin, cos, isclose, radians, sin, sqrt
from typing import Annotated, Callable, Dict, List, Optional, Union
from urllib.parse import quote_plus
from uuid import UUID, uuid4

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    IPvAnyAddress,
    model_validator,
)


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


class SelectorStrategy(str, Enum):
    """Strategies that storage adapters can use to pick the next proxy."""

    FIRST_AVAILABLE = "first_available"
    LEAST_USED = "least_used"
    ROUND_ROBIN = "round_robin"


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
    pool_id: Optional[UUID] = None
    pool_name: Optional[str] = None
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

    model_config = ConfigDict(arbitrary_types_allowed=True)

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
    all_of: Optional[List["ProxyFilters"]] = None
    any_of: Optional[List["ProxyFilters"]] = None
    none_of: Optional[List["ProxyFilters"]] = None
    predicate: Optional[Callable[[Proxy], bool]] = None

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
        self.all_of = self._normalize_children(self.all_of)
        self.any_of = self._normalize_children(self.any_of)
        self.none_of = self._normalize_children(self.none_of)
        return self

    def matches(self, proxy: Proxy) -> bool:
        """Return True when the proxy satisfies all conditions."""
        if not self._matches_scalar_constraints(proxy):
            return False
        if self.predicate and not self.predicate(proxy):
            return False
        if self.all_of and not all(child.matches(proxy) for child in self.all_of):
            return False
        if self.any_of and not any(child.matches(proxy) for child in self.any_of):
            return False
        if self.none_of and any(child.matches(proxy) for child in self.none_of):
            return False
        return True

    def requires_python(self) -> bool:
        """Return True if this filter or nested clauses rely on a predicate."""
        if self.predicate is not None:
            return True
        return any(child.requires_python() for child in self._iter_children())

    def _iter_children(self) -> List["ProxyFilters"]:
        children: List["ProxyFilters"] = []
        if self.all_of:
            children.extend(self.all_of)
        if self.any_of:
            children.extend(self.any_of)
        if self.none_of:
            children.extend(self.none_of)
        return children

    def _normalize_children(
        self, candidates: Optional[List["ProxyFilters"]]
    ) -> Optional[List["ProxyFilters"]]:
        if not candidates:
            return None
        normalized = [child for child in candidates if child is not None]
        return normalized or None

    def _matches_scalar_constraints(self, proxy: Proxy) -> bool:
        if self.source and proxy.source != self.source:
            return False
        if self.country and proxy.country != self.country:
            return False
        if self.city and proxy.city != self.city:
            return False
        if self.isp and proxy.isp != self.isp:
            return False
        if self.asn is not None and proxy.asn != self.asn:
            return False
        if not self._matches_geo(proxy):
            return False
        return True

    def _matches_geo(self, proxy: Proxy) -> bool:
        if self.latitude is None or self.longitude is None:
            return True
        if proxy.latitude is None or proxy.longitude is None:
            return False
        if self.radius_km is None:
            return bool(
                isclose(proxy.latitude, self.latitude, abs_tol=1e-6)
                and isclose(proxy.longitude, self.longitude, abs_tol=1e-6)
            )
        return (
            self._haversine_distance_km(
                self.latitude,
                self.longitude,
                proxy.latitude,
                proxy.longitude,
            )
            <= self.radius_km
        )

    @staticmethod
    def _haversine_distance_km(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Compute the great-circle distance between two coordinates."""
        lat1_rad, lon1_rad = radians(lat1), radians(lon1)
        lat2_rad, lon2_rad = radians(lat2), radians(lon2)
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return 6371.0 * c


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


class PoolStatsSnapshot(BaseModel):
    """Aggregated stats for a specific proxy pool."""

    pool_name: str
    total_proxies: int = Field(ge=0, default=0)
    active_proxies: int = Field(ge=0, default=0)
    available_proxies: int = Field(ge=0, default=0)
    leased_proxies: int = Field(ge=0, default=0)
    total_leases: int = Field(ge=0, default=0)
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class AcquireEventPayload(BaseModel):
    """Callback payload describing a proxy acquisition attempt."""

    lease: Optional[Lease]
    pool_name: str
    consumer_name: str
    filters: Optional[ProxyFilters] = None
    selector: SelectorStrategy = SelectorStrategy.FIRST_AVAILABLE
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    pool_stats: Optional[PoolStatsSnapshot] = None


class ReleaseEventPayload(BaseModel):
    """Callback payload describing a proxy release operation."""

    lease: Lease
    pool_name: Optional[str] = None
    released_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    lease_duration_ms: Optional[int] = Field(default=None, ge=0)
    pool_stats: Optional[PoolStatsSnapshot] = None
