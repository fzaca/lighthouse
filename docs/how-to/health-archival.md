# Design an Archival Strategy for Health Data

Health checks are high-volume and noisy. Pharox leaves persistence to storage
adapters so you can decide how much history to keep and how to compact it. Use
the playbook below to capture actionable history without letting raw events
grow unbounded.

## Goals

- Keep enough raw events to debug incidents and provider issues.
- Summarise old data into compact rollups that power dashboards and SLOs.
- Make retention explicit and automated so operators are not surprised by
  storage growth.

## Recommended Data Model

**Raw events (short retention)**

- Table keyed by `(checked_at, proxy_id)` with columns for `pool_id`, `status`,
  `latency_ms`, `status_code`, and `error_message`.
- Partition by day (or week) on `checked_at` to make drops cheap.
- Index on `(pool_id, checked_at)` for pool-level queries; add `(proxy_id,
  checked_at)` if you need per-proxy history.

**Rollups (long retention)**

- Hourly or daily grain keyed by `(window_start, pool_id)` and optionally
  `proxy_id`.
- Metrics to store: counts per status, success/error rate, p50/p95 latency,
  max latency, and most common error reason.
- Built from raw events and safe to regenerate if you need to change the
  aggregation logic.

## Retention Policy

1. Choose a raw retention window (7–30 days) that matches your debugging needs.
2. Drop old partitions on a schedule (cron/Airflow/RQ worker). Avoid ad hoc
   deletes on large tables.
3. Keep rollups for months since they are compact; expire them separately if
   needed.

## Rollup Job Sketch (PostgreSQL)

```sql
-- Materialise hourly rollups; run each hour after the window closes.
INSERT INTO health_check_rollup_hourly (
    window_start,
    pool_id,
    total,
    active,
    slow,
    inactive,
    error_rate,
    latency_p50_ms,
    latency_p95_ms,
    latency_max_ms
)
SELECT
    date_trunc('hour', checked_at) AS window_start,
    pool_id,
    count(*) AS total,
    count(*) FILTER (WHERE status = 'ACTIVE') AS active,
    count(*) FILTER (WHERE status = 'SLOW') AS slow,
    count(*) FILTER (WHERE status = 'INACTIVE') AS inactive,
    count(*) FILTER (WHERE status = 'INACTIVE')::float / NULLIF(count(*), 0) AS error_rate,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS latency_p50_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS latency_p95_ms,
    max(latency_ms) AS latency_max_ms
FROM health_check_event
WHERE checked_at >= date_trunc('hour', now()) - interval '1 hour'
  AND checked_at < date_trunc('hour', now())
GROUP BY 1, 2
ON CONFLICT (window_start, pool_id) DO UPDATE
SET
    total = EXCLUDED.total,
    active = EXCLUDED.active,
    slow = EXCLUDED.slow,
    inactive = EXCLUDED.inactive,
    error_rate = EXCLUDED.error_rate,
    latency_p50_ms = EXCLUDED.latency_p50_ms,
    latency_p95_ms = EXCLUDED.latency_p95_ms,
    latency_max_ms = EXCLUDED.latency_max_ms;
```

Notes:

- Use `ON CONFLICT` so reruns are idempotent.
- Replace `percentile_cont` with approximate quantiles if your adapter supports
  them (e.g., `tdigest` or `approx_percentile`).
- For multi-tenant systems, include `consumer_id` or `org_id` in the keys.

## Operational Checklist

- [ ] Schedule raw partition drops (e.g., keep 14 days) and monitor failures.
- [ ] Schedule rollup jobs after each window closes; alert on lag.
- [ ] Validate rollups feed your dashboards (Prometheus scraper can scrape
      rollup exporters or you can expose the rollup table via a metrics bridge).
- [ ] Document the windows and retention in your adapter README so downstream
      services know what is available.

## Adapter Integration Tips

- Keep archival logic in the adapter layer or a co-located worker; avoid baking
  it into `ProxyManager`.
- When exporting metrics, emit counters/histograms from rollups rather than raw
  rows to reduce Prometheus pressure.
- For cloud databases with native TTL/partitioning, use the managed features
  instead of custom jobs; the shape above still applies.
