# ADR 001 — Callbacks over an event system

**Status:** Accepted
**Date:** 2025-11-02

## Context

`ProxyManager` needs to let callers plug in observability (logging, metrics) and
custom business logic (notifications, auditing) without hard-coding those concerns
into the core. Two common approaches were considered:

1. **Event bus / pub-sub** — a central dispatcher; handlers subscribe by event type.
2. **Callback lists** — callers register plain callables; the manager invokes them
   at defined lifecycle points (after acquire, after release).

## Decision

Use typed callback lists (`List[Callable[[Payload], None]]`) registered via
`register_acquire_callback` and `register_release_callback`.

## Rationale

- **Zero extra dependencies.** A callback list needs no third-party event library.
- **Explicit typing.** The payload types (`AcquireEventPayload`,
  `ReleaseEventPayload`) are Pydantic models — mypy can verify handler signatures.
- **Simple mental model.** Callbacks fire in registration order; there is no
  routing, priority, or async dispatch complexity.
- **Sufficient for the use cases on record** — metrics recording and structured
  logging only need the two lifecycle hooks.

An event bus would add value if many unrelated subsystems need to observe the
same events. For the current scope (one manager, a handful of optional callbacks),
the overhead is not justified.

## Consequences

- Adding a new lifecycle hook requires a new callback list and a new `register_*`
  method on `ProxyManager` — a small but explicit change.
- Callers that need async callbacks must wrap the synchronous call in
  `asyncio.to_thread` themselves; the manager remains sync-only.
