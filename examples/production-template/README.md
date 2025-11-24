# Pharox Production Template

Docker Compose + scripts to run a Pharox worker with PostgreSQL storage,
Prometheus metrics, and a Grafana dashboard. The worker seeds a demo pool,
leases proxies in a loop, and runs periodic health sweeps to keep state fresh.

## Stack

- PostgreSQL 16 for leases, pools, and health data
- Worker container running Pharox with Prometheus metrics on port `8000`
- Prometheus scraping the worker
- Grafana with a pre-provisioned dashboard (http://localhost:3300, admin/admin)

## Quickstart

```bash
docker compose -f examples/production-template/docker-compose.yml up --build
```

Once the containers are healthy:

- Metrics endpoint: <http://localhost:8000/>
- Prometheus UI: <http://localhost:9090>
- Grafana dashboard: <http://localhost:3300/d/pharox-demo>

## What the worker does

- Seeds a pool (`PHAROX_POOL`, default `residential`) with three demo proxies.
- Registers Prometheus callbacks so acquire/release events become counters,
  histograms, and pool gauges.
- Continuously acquires/releases leases to generate telemetry.
- Runs a health sweep every `PHAROX_HEALTH_INTERVAL` seconds (default 60) using
  a synthetic health strategy (no external network required).

## Configuration

Environment variables on the worker service:

- `PHAROX_DSN`: Postgres DSN (default `postgresql+psycopg://pharox:pharox@db:5432/pharox`)
- `PHAROX_POOL`: Pool name to seed and target for leases.
- `PHAROX_METRICS_PORT`: Port exposed by `prometheus_client.start_http_server`.
- `PHAROX_HEALTH_INTERVAL`: Seconds between health sweeps.

## Adapting for real workloads

- Replace the demo proxies with your fleet (see `demo_worker.py:seed_pool`).
- Swap the health target URL or options to match your SLA.
- Point Prometheus/Grafana at your observability stack, or import the dashboard
  JSON into an existing Grafana instance.
- Build a proper worker image (instead of `pip install .`) that pins your
  dependencies and embeds your task code alongside the template.
