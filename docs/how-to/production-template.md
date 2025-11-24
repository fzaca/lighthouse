---
title: Production Template
description: Run Pharox with PostgreSQL, Prometheus, and Grafana via Docker Compose.
---
# Production Template

Use the template under `examples/production-template/` to start a Pharox worker
with PostgreSQL storage, Prometheus scraping, and a Grafana dashboard.

## Stack

- PostgreSQL for pools, leases, and health data.
- Worker container running `demo_worker.py` with Prometheus metrics on `:8000`.
- Prometheus scraping the worker and exporting data to Grafana.
- Grafana pre-provisioned with a basic dashboard (admin/admin).

## Quickstart

```bash
docker compose -f examples/production-template/docker-compose.yml up --build
```

- Metrics endpoint: <http://localhost:8000/>
- Prometheus UI: <http://localhost:9090>
- Grafana dashboard: <http://localhost:3300/d/pharox-demo>

## Customize

- Edit `demo_worker.py` to seed your pools/proxies and adjust health checks.
- Tune scrape intervals in `prometheus.yml` and extend the Grafana dashboard
  JSON under `examples/production-template/grafana/provisioning/dashboards/`.
- Swap the worker image for your own code once you wire the Pharox manager into
  your tasks or services.
