---
title: Production Deployment Checklist
description: Steps to harden a Pharox-based service before going live.
---
# Production Deployment Checklist

Work through this list before exposing a Pharox-backed service to production
traffic.

## Storage

- [ ] **Use `PostgresStorage`** — `InMemoryStorage` does not survive process
  restarts and is not safe across multiple workers.
- [ ] **Run Alembic migrations** before deploying a new version:
  ```bash
  alembic upgrade head
  ```
- [ ] **Connection pool sizing** — set `pool_size` and `max_overflow` on the
  SQLAlchemy engine to match your expected concurrency.  A safe starting point:
  `pool_size = <worker_threads>`, `max_overflow = 2`.
- [ ] **SSL/TLS** — pass `connect_args={"sslmode": "require"}` (or `verify-full`)
  to the engine when the database is on a separate host.

## Proxy Data

- [ ] Seed proxies via `add_proxies_bulk` for large initial loads — it uses a
  single transaction and avoids per-row round-trips.
- [ ] Set realistic `max_concurrency` on each pool; leaving it at `None`
  (unlimited) is only appropriate for dev/testing.
- [ ] Configure `expires_at` on leases so stale holds are cleaned up
  automatically by `cleanup_expired_leases`.

## Health Checks

- [ ] Run `HealthCheckOrchestrator` in a dedicated thread or process — it is
  blocking and CPU-light but I/O-heavy.
- [ ] Tune `HealthCheckOptions.interval_seconds` and `timeout_seconds` to your
  proxy SLA.  A common production setting: 60 s interval, 10 s timeout.
- [ ] Archive or truncate old health records periodically — see
  `docs/how-to/health-archival.md`.

## Observability

- [ ] Register `PrometheusMetricsRecorder` as acquire/release callbacks and
  expose the `/metrics` endpoint to Prometheus.
- [ ] Set alert rules on `pharox_acquire_total{status="miss"}` to detect pool
  exhaustion.
- [ ] Enable summaries (`enable_summaries=True`) and configure quantiles if
  p95/p99 latency SLOs are required.

## Retry / Resilience

- [ ] Pass an explicit `RetryConfig` to `acquire_proxy_with_retry` rather than
  relying on defaults — defaults are conservative and may not match your SLA.
- [ ] Cap `RetryConfig.max_backoff_seconds` to avoid unbounded blocking in
  synchronous workers.

## Security

- [ ] Store proxy credentials in a secrets manager (e.g. HashiCorp Vault, AWS
  Secrets Manager) — do not hard-code them or commit them to source control.
- [ ] Restrict database user to `SELECT`, `INSERT`, `UPDATE`, `DELETE` on
  Pharox tables only — no DDL grants in production.
- [ ] Rotate credentials via `update_proxy` rather than deleting and re-inserting
  to preserve lease history.

## Testing Before Go-Live

- [ ] Run `poetry run pytest` locally with the Postgres extra to confirm the
  adapter contract tests pass against a staging database.
- [ ] Run `poetry run mypy src/pharox` — zero errors expected.
- [ ] Run the production-template stack (`docs/how-to/production-template.md`)
  and verify metrics appear in Grafana before switching production traffic.

## Dependency Versions

- [ ] Pin `pharox` to a specific minor version in your service's lockfile —
  minor versions may add new abstract methods to `IStorage`.
- [ ] Review `CHANGELOG.md` on every upgrade for breaking changes.
