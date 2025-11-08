## 0.4.0 (2025-11-08)

### Feat

- **storage**: embed postgres adapter into package
- **tests**: add storage contract suite and postgres extra
- add postgres storage adapter template
- enrich proxy callbacks with telemetry payloads
- add async helpers for ProxyManager

## 0.3.0 (2025-11-02)

### Feat

- **utils**: add storage bootstrap helpers
- **manager**: add acquire and release callbacks
- **health,storage**: add health check orchestrator
- **manager,storage**: add lease context helper and allow zero ASN
- **manager**: validate lease duration input
- **manager**: auto-register default   consumer

### Fix

- **storage**: allow zero ASN filter
- **models**: bracket ipv6 hosts in proxy url

### Refactor

- rename package to pharox

## 0.2.0 (2025-10-25)

### Feat

- redesign health checking toolkit
- add geospatial filtering and toolkit exports
- **storage**: Implement thread-safe InMemoryStorage adapter
- **health**: Add error_message to HealthCheckResult for better diagnostics
- Implement stream_health_checks and its tests
- Add HealthChecker and update IStorage for health checks
- Implement asynchronous proxy health checker
- Add automated changelog generation with commitizen
- Implement concurrent proxy leasing
- Implement acquire_proxy method in ProxyManager
- Add ProxyManager and initial tests
- Add ProxyManager class skeleton
- Add Pydantic models and storage interface
- Add CI/CD workflows and project documentation files
- Configure project tools (ruff, pytest, mypy)

### Fix

- normalize proxy and target URLs
- **tests**: Adapt integration tests to architectural changes
- **tests**: Correctly mock httpx.AsyncClient in health checks
- **health**: Correct httpx proxy usage for async checks
- remove python 3.14 from test.yaml
- Correct syntax in GitHub Actions workflows

### Refactor

- remove duplicate storage state and unused stats
- **models**: Use Enum for proxy protocol validation
- **models**: Rename 'last_checked_at' to 'checked_at' for clarity
- **models**: Rename Client model to Consumer
- **models**: Decouple authentication logic from core models
- **api**: Use pool names in public API, while using IDs internally
- **models**: Use pool_id foreign key instead of pool_name
- **tests**: Remove obsolete mock-based tests in favor of integration tests
- **models**: Use Annotated for field validation syntax
- **storage**: Update to pydantic's model_copy method
- **storage**: Temporarily remove health check methods from IStorage
- **models**: Allow proxy host to be an IP or a hostname
- **proxy**: Add url property to handle auth and simplify usage
- **manager**: return Lease from acquire_proxy
