# Pharox Toolkit

Pharox is the Python toolkit for building serious proxy orchestration systems.
It focuses on the business rules—leasing, storage contracts, health orchestration
and lifecycle hooks—so you can plug it into any application or service.

!!! tip "Just want to try it?"
    Head straight to the [Quickstart](getting-started/quickstart.md) for an
    end-to-end walkthrough you can run locally in under five minutes.

## Why Pharox

- **Battle-tested leasing logic** with concurrency caps, cleanup helpers and
  lifecycle callbacks ready for observability.
- **Storage abstraction that scales**: swap the in-memory adapter for your own
  datastore through the `IStorage` interface and shared contract tests.
- **Health orchestration** that aligns workers, services and SDKs behind the
  same `HealthCheckResult` semantics.
- **Modern Python ergonomics**: Pydantic v2 models, type hints, Ruff formatting,
  and context managers that reduce boilerplate.

## Choose Your Path

| If you want to… | Start here | Related reference |
| --- | --- | --- |
| Install, seed data, lease a proxy | [Quickstart](getting-started/quickstart.md) | [`ProxyManager`](reference/proxy-manager.md) |
| Embed Pharox in a worker or script | [Embed Pharox in a Worker](how-to/embed-worker.md) | [`pharox.utils.bootstrap`](reference/bootstrap.md) |
| Wire Pharox to a SQL datastore | [Build a PostgreSQL Adapter](how-to/postgres-adapter.md) | [`IStorage` contract](storage.md) |
| Run protocol health sweeps | [Run Health Checks at Scale](how-to/health-sweeps.md) | [Health Toolkit](health-checks.md) |

## Architecture Snapshot

The toolkit sits between your code and the storage layer:

1. Your automation, service or CLI drives `ProxyManager`.
2. `ProxyManager` delegates persistence to an `IStorage` implementation.
3. Health checks use `HealthChecker` / `HealthCheckOrchestrator` to enforce
   consistent classification.
4. Callbacks and metrics hooks let you surface events without forking the core.


## Community & Support

- GitHub issues and discussions: <https://github.com/fzaca/pharox>
- PyPI releases: <https://pypi.org/project/pharox/>
- Documentation source: this site, built with MkDocs Material—PRs welcome!
