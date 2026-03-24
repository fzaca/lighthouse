# ADR 003 — SQLAlchemy Core over ORM for the Postgres adapter

**Status:** Accepted
**Date:** 2025-11-08

## Context

The reference `PostgresStorage` adapter needs to issue SQL queries for proxy
lookup, lease creation, health-check updates, and pool statistics. SQLAlchemy
offers two layers:

- **ORM** — declares Python classes mapped to tables; rich relationship loading;
  session-based identity map.
- **Core** — table/column objects and composable SQL expression language; thin
  wrapper over the DBAPI.

## Decision

Use **SQLAlchemy Core** with explicit `Table` definitions (`tables.py`) and
parameterised `select`/`insert`/`update` statements.

## Rationale

- **No identity map overhead.** Proxy and lease objects are value objects — they
  are re-created from database rows on every read. An ORM session tracking
  identity is unnecessary and would add memory and lock-management overhead.
- **Explicit SQL.** Core statements are close to the generated SQL, making
  performance characteristics easy to reason about. `SKIP LOCKED`, window
  functions, and advisory locks are straightforward to express.
- **Pydantic owns validation.** Domain models (`Proxy`, `Lease`, etc.) are
  Pydantic models. Having a parallel set of ORM-mapped Python classes would
  create two representations of the same domain with synchronisation risk.
- **Alembic compatibility.** `MetaData` + `Table` definitions integrate cleanly
  with Alembic migrations regardless of whether ORM is used.

## Consequences

- Developers writing custom adapters for other databases follow the same
  Core pattern; there is no ORM base class to inherit from.
- Relationship traversal (e.g., joining pool → proxies → leases) must be
  written as explicit joins rather than relying on ORM `relationship()`.
