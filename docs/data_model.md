# Data Models (Pydantic)

This document describes the Pydantic models that serve as the single source of truth for Lighthouse's data structures. These models provide automatic data validation and serialization.

---

### `Proxy`

Represents a network proxy.

```python
class Proxy(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    host: IPvAnyAddress
    port: int = Field(gt=0, le=65535)
    protocol: str
    pool_name: str
    status: ProxyStatus = ProxyStatus.INACTIVE
    last_checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
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
```

**Fields:**

*   `id`: A unique identifier (UUID) for the proxy.
*   `host`: The IP address of the proxy.
*   `port`: The port number of the proxy (must be between 1 and 65535).
*   `protocol`: The protocol of the proxy (e.g., `http`, `https`).
*   `pool_name`: The name of the pool this proxy belongs to.
*   `status`: The operational status of the proxy (`active`, `inactive`, `banned`).
*   `last_checked_at`: The timestamp of the last health check.
*   `credentials`: Optional credentials for the proxy.
*   `metadata`: A dictionary for storing arbitrary metadata.
*   `stats_lifetime`: Lifetime usage statistics for the proxy.
*   `source`: The source of the proxy (e.g., `datacenter-frankfurt-A`).
*   `country`: The country of the proxy.
*   `city`: The city of the proxy.
*   `latitude`: The latitude of the proxy.
*   `longitude`: The longitude of the proxy.
*   `isp`: The ISP of the proxy.
*   `asn`: The ASN of the proxy.

---

### `ProxyPool`

Represents a collection of proxies with a shared configuration.

```python
class ProxyPool(BaseModel):
    name: str
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
```

**Fields:**

*   `name`: A unique name for the pool.
*   `description`: An optional description of the pool.
*   `config`: A dictionary for storing pool-specific configuration.

---

### `Lease`

Represents a lease on a proxy by a client.

```python
class Lease(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    proxy_id: UUID
    client_id: UUID
    status: LeaseStatus = LeaseStatus.ACTIVE
    acquired_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    released_at: Optional[datetime] = None
    stats_session: SessionStats = Field(default_factory=SessionStats)
```

**Fields:**

*   `id`: A unique identifier (UUID) for the lease.
*   `proxy_id`: The ID of the leased proxy.
*   `client_id`: The ID of the client that acquired the lease.
*   `status`: The status of the lease (`active`, `released`).
*   `acquired_at`: The timestamp when the lease was acquired.
*   `expires_at`: The timestamp when the lease expires.
*   `released_at`: The timestamp when the lease was released.
*   `stats_session`: Usage statistics for the lease session.

---

### `Client`

Represents a client that consumes proxies.

```python
class Client(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    api_key_hash: str
```

**Fields:**

*   `id`: A unique identifier (UUID) for the client.
*   `name`: The name of the client.
*   `api_key_hash`: The hashed API key of the client.

---

### `ProxyFilters`

Represents the filters to apply when finding an available proxy.

```python
class ProxyFilters(BaseModel):
    source: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    isp: Optional[str] = None
    asn: Optional[int] = None
    # For geo-proximity searches
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_km: Optional[int] = Field(None, gt=0, description="Search radius in kilometers for geo-proximity queries.")
```

**Fields:**

*   `source`: Filter by the source of the proxy.
*   `country`: Filter by the country of the proxy.
*   `city`: Filter by the city of the proxy.
*   `isp`: Filter by the ISP of the proxy.
*   `asn`: Filter by the ASN of the proxy.
*   `latitude`: The latitude for geo-proximity searches.
*   `longitude`: The longitude for geo-proximity searches.
*   `radius_km`: The search radius in kilometers for geo-proximity queries.
