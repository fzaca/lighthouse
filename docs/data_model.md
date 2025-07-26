# Abstract Data Model

This model is implementation agnostic.

```
// Entity: Proxy
Proxy {
    id: String (UUID)
    host: String
    port: Integer
    protocol: String
    credentials: { user, pass } (optional, encrypted)
    pool_name: String
    status: String
    last_checked_at: DateTime
    metadata: { country, isp, ... } (optional)
    stats_lifetime: { total_bytes_up, total_bytes_down }
}

// Entity: ProxyPool
ProxyPool {
    name: String (unique ID)
    description: String
    config: { rotation_strategy: String }
}

// Entity: Lease (the active “rental”)
Lease {
    id: String (UUID)
    proxy_id: String
    client_id: String
    status: String ('active', 'released')
    acquired_at: DateTime
    expires_at: DateTime
    released_at: DateTime (optional)
    stats_session: { bytes_up, bytes_down, request_count }
}

// Entity: Client (the user/service/company that consumes the proxies)
Client {
    id: String (UUID)
    name: String
    api_key: String (hash)
}
```
