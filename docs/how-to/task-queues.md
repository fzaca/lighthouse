---
title: Use Pharox with Task Queues
description: Combine ProxyManager with Celery, RQ, or Airflow using the PostgreSQL adapter.
---
# Use Pharox with Task Queues

This guide shows how to run Pharox-backed workers under Celery, RQ, or Airflow
while sharing state through the PostgreSQL adapter.

## 1) Build a shared manager

Create the storage and manager once per worker process so all tasks reuse the
same connection pool.

```python
from sqlalchemy import create_engine
from pharox import ProxyManager
from pharox.storage.postgres import PostgresStorage

engine = create_engine("postgresql+psycopg://user:pass@localhost:5432/pharox")
storage = PostgresStorage(engine)
manager = ProxyManager(storage=storage)
```

Register lifecycle callbacks here (e.g., Prometheus/structured logging) so every
task emits the same telemetry.

## 2) Celery example

Define the manager at module import time and use `with_retrying_lease` in tasks.

```python
from celery import Celery
from pharox import SelectorStrategy
from worker_core import process_job  # your app logic

app = Celery("scraper", broker="redis://localhost:6379/0")


@app.task(bind=True, max_retries=5)
def run_scrape(self, pool: str, payload: dict):
    with manager.with_retrying_lease(
        pool_name=pool,
        consumer_name="celery-worker",
        selector=SelectorStrategy.ROUND_ROBIN,
        max_attempts=3,
        backoff_seconds=0.5,
    ) as lease:
        if lease is None:
            raise self.retry(exc=RuntimeError("no proxy available"))
        proxy = storage.get_proxy_by_id(lease.proxy_id)
        process_job(proxy.url, payload)
```

Add a Celery beat task to run maintenance:

```python
@app.task
def sweep_pools():
    cleaned = manager.cleanup_expired_leases()
    return {"cleaned": cleaned}
```

## 3) RQ or Airflow pattern

The same manager works inside RQ jobs or Airflow tasks—initialise it in the
worker process and re-use it across tasks.

```python
# rq job
def rq_job(pool: str, payload: dict):
    with manager.with_lease(pool_name=pool, consumer_name="rq") as lease:
        if not lease:
            raise RuntimeError("no proxy available")
        proxy = storage.get_proxy_by_id(lease.proxy_id)
        process_job(proxy.url, payload)
```

For Airflow, place the manager in a module imported by tasks and call it inside
your PythonOperator or TaskFlow function.

## 4) Health sweeps on a schedule

Run periodic health checks from the same scheduler to keep pool state fresh:

```python
from pharox import HealthCheckOrchestrator

orchestrator = HealthCheckOrchestrator(storage=storage)

async def sweep_health(pool: str):
    proxies = storage.find_proxies(pool)  # implement on your adapter
    async for result in orchestrator.stream_health_checks(proxies):
        ...
```

Wire this to Celery beat, RQ scheduler, or an Airflow DAG to enforce SLAs and
quarantine unhealthy proxies.

## Tips

- Use dedicated consumers per queue (`consumer_name`) to segment metrics.
- Keep the manager singleton per worker; do not create one per task.
- Handle misses by retrying upstream (Celery retry, RQ requeue) instead of
sleeping inside tasks.
