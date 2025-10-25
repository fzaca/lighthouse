# Migration Assessment: Toolkit vs Service vs SDK

This document captures the current evaluation of which pieces of the
`lighthouse` toolkit should remain in the core library and which concerns must
be handled by the FastAPI service or the SDK. The intention is to freeze the
boundaries before making implementation changes.

## Current Toolkit Surface

Component | Purpose | Recommendation
--------- | ------- | --------------
`lighthouse.models` | Domain entities, value objects, request options | **Stay** in toolkit. These are the shared contracts for every consumer.
`lighthouse.manager.ProxyManager` | Stateless orchestration of leasing logic | **Stay** in toolkit. Service and SDK both depend on this orchestration.
`lighthouse.storage.interface.IStorage` | Contract for persistence adapters | **Stay** in toolkit. Implementations live in surrounding projects.
`lighthouse.storage.in_memory` | Development-only adapter | **Stay** bundled. Useful for SDK tests and local scripts; production adapters belong to the service codebase.
`lighthouse.health` | Protocol-aware health checks | **Stay**. Both SDK workers and the FastAPI service need the same probing logic.
`drafts/` scripts | Manual testing playground | **Exclude** from the published package. These are developer utilities only.

## Responsibilities Outside the Toolkit

Concern | Target | Notes / Next Steps
------- | ------ | ------------------
Authentication, authorization, billing | **Service** | Already absent from the toolkit. Service must wrap toolkit calls with tenant/user context.
Proxy inventory ingestion pipelines | **Service** | Future features that fetch provider lists, rotate credentials, or reconcile stock should live with durable storage and auditing.
Bulk scheduling / orchestration of health sweeps | **Service** | Keep the probing logic in the toolkit, but the scheduler, retries, and alerting belong in the service or infrastructure.
Telemetry, metrics, logging sinks | **Service & SDK** | Toolkit should expose hooks/events only. Emission of logs/metrics should happen in the embedding application.
HTTP clients for remote control of the service | **SDK** | Any client for calling the FastAPI API (auth, retries, pagination) should remain in the SDK; core toolkit stays HTTP-agnostic besides health probes.
Command-line tooling for operators | **SDK** | CLI wrappers that orchestrate multiple toolkit calls are SDK territory.

## Guardrails for Future Work

1. **Toolkit remains stateless** beyond in-memory helpers. Anything needing
   durable or shared state moves to the service (or its storage adapters).
2. **Networking in the toolkit is limited to proxy health probes.** All other
   network I/O (API calls, provider ingestion) should be hosted by the service
   or SDK.
3. **SDK is the integration glue**: conversions between API payloads and toolkit
   models, retry policies, and client-side caching live there—not in the core.
4. **Service adds platform concerns** such as multi-tenancy, auth, reporting,
   and asynchronous orchestration using Celery/Arq/etc.

## Immediate Migration Actions

No modules require relocation today. The existing surface matches the desired
"toolkit" scope. Keep this document updated when new features are proposed so
that migrations can be planned before coding.
