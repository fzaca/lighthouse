# Health Checking Toolkit

The health module provides reusable building blocks so every Lighthouse consumer
can evaluate proxy connectivity the same way.

## Components

- **`HealthCheckOptions`** (`lighthouse.models`): runtime configuration for a
  check (target URL, timeout, retries, expected status codes, latency threshold,
  headers, redirect policy).
- **`HealthChecker`** (`lighthouse.health`): orchestrates checks by selecting the
  appropriate strategy for a proxy protocol and returning a `HealthCheckResult`.
- **`HTTPHealthCheckStrategy`**: default strategy used for HTTP, HTTPS, SOCKS4,
  and SOCKS5 proxies. It performs real HTTP requests through the proxy and classifies
  the latency as `active`, `slow`, or `inactive`.

Custom strategies can be registered for any `ProxyProtocol` when a consumer needs
extra behaviour (e.g. verifying custom handshake semantics or accessing internal
metrics).

## Result Semantics

`HealthCheckResult` includes the proxy protocol, number of attempts, observed
status code (if any), timestamp, and an optional error message. Callers decide
how to persist or react to these results; the toolkit keeps the output portable
across services and scripts.

## Usage Guidelines

1. Configure defaults on the `HealthChecker` instance or pass `HealthCheckOptions`
   per call.
2. For repeated checks on the same protocol, set protocol-specific options via
   `set_protocol_options`.
3. Use `stream_health_checks` to evaluate multiple proxies concurrently when
   building worker pipelines.

Consumers that require authentication, quota enforcement, or storage should
perform those operations in their own layer (e.g. the FastAPI service) after
receiving the health results.
