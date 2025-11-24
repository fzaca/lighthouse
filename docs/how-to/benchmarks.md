---
title: Run Benchmarks
description: Measure leasing and health-check throughput for Pharox adapters.
---

# Run Benchmarks

The toolkit ships a lightweight benchmark harness to compare adapters and
surface regressions in leasing/health persistence. It avoids network calls by
using synthetic health checks so results focus on storage performance.

## Quickstart (in-memory)

```bash
python -m pharox.benchmarks --adapter in-memory --iterations 500 --pool-size 32
```

This seeds a pool, acquires/releases proxies, then runs synthetic health checks
against the same storage. Output includes throughput and hit/miss counts.

## Benchmark PostgreSQL

Provide a DSN once the Postgres tables exist (or let the script create them):

```bash
python -m pharox.benchmarks \
  --adapter postgres \
  --dsn postgresql+psycopg://user:pass@localhost:5432/pharox \
  --iterations 2000 \
  --health-rounds 5
```

Install the postgres extra first:

```bash
pip install "pharox[postgres]"
```

## Tuning knobs

- `--iterations` and `--pool-size` tune leasing throughput checks.
- `--health-proxies`, `--health-rounds`, and `--latency-ms` adjust synthetic
  health checks to stress different code paths.
- Results are printed to stdout for easy capture in CI; wire them into your
  pipeline to guard against regressions.
