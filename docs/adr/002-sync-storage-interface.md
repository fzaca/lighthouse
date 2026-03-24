# ADR 002 — Synchronous `IStorage` interface

**Status:** Accepted
**Date:** 2025-11-02

## Context

`IStorage` defines the persistence contract used by `ProxyManager` and
`HealthCheckOrchestrator`. Python has two concurrency models relevant here:

- **Sync / threading** — blocking I/O, standard with WSGI servers and
  `concurrent.futures`.
- **Async / asyncio** — non-blocking I/O, standard with ASGI servers and
  `asyncio`-based workers.

The choice of sync vs. async propagates through the entire call chain.

## Decision

`IStorage` is a synchronous (blocking) interface. All abstract methods return
values directly; none are coroutines.

## Rationale

- **Broader compatibility.** Sync adapters work inside both threaded and async
  runtimes (via `asyncio.to_thread`). An async-only interface would exclude
  threaded hosts without a wrapper.
- **Simpler adapter authoring.** SQLAlchemy Core with a synchronous engine is the
  most common production setup. Sync adapters avoid the complexity of
  `async_sessionmaker` and connection pool lifecycle management.
- **ProxyManager usage pattern.** Lease acquisition is typically short (sub-ms for
  in-memory, low-ms for Postgres). Blocking a thread for that duration is
  acceptable in most real-world scenarios.
- **Async helpers already exist.** `async_helpers.py` wraps `ProxyManager`
  operations in `asyncio.to_thread`, giving async callers a clean interface
  without requiring an async `IStorage`.

## Consequences

- High-throughput async services that want non-blocking storage access should
  use the async wrappers or implement `IAsyncStorage` separately (tracked in
  the backlog as a Sprint 4 item).
- SQLAlchemy async engine users will need a custom adapter; the provided
  `PostgresStorage` reference implementation uses a synchronous engine.
