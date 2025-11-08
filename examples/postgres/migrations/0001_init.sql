-- Baseline schema for the Pharox PostgreSQL adapter template.

CREATE TABLE IF NOT EXISTS proxy_pool (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS consumer (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS proxy (
    id UUID PRIMARY KEY,
    pool_id UUID NOT NULL REFERENCES proxy_pool(id),
    host TEXT NOT NULL,
    port INTEGER NOT NULL CHECK (port BETWEEN 1 AND 65535),
    protocol TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'inactive',
    credentials JSONB,
    source TEXT,
    country TEXT,
    city TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    isp TEXT,
    asn INTEGER,
    max_concurrency INTEGER CHECK (max_concurrency IS NULL OR max_concurrency > 0),
    current_leases INTEGER NOT NULL DEFAULT 0 CHECK (current_leases >= 0),
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proxy_pool_status
    ON proxy (pool_id, status);

CREATE INDEX IF NOT EXISTS idx_proxy_geo
    ON proxy USING GIST (point(longitude, latitude));

CREATE TABLE IF NOT EXISTS lease (
    id UUID PRIMARY KEY,
    proxy_id UUID NOT NULL REFERENCES proxy(id),
    pool_id UUID NOT NULL REFERENCES proxy_pool(id),
    consumer_id UUID NOT NULL REFERENCES consumer(id),
    pool_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    released_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_lease_active_expires
    ON lease (status, expires_at);
