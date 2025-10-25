# Lighthouse Architecture Overview

Lighthouse is designed as a toolkit-centric ecosystem. The `lighthouse` library
provides the domain primitives, leasing logic, and storage contracts that every
other component builds upon. The surrounding projects compose this toolkit to
support different usage scenarios without duplicating business rules.

## Primary Components

- **Toolkit Library (`lighthouse-core`):** Pure business logic and data models
  for proxy lifecycle management. It talks to storage backends and exposes the
  public API (`ProxyManager`, `ProxyFilters`, etc.).
- **Storage Backends:** Implementations of the `IStorage` contract. The default
  in-memory adapter is bundled for development and testing. Production systems
  should supply adapters that persist proxy state in their own infrastructure.
- **SDK (`lighthouse-sdk`):** A lightweight client that orchestrates workflows
  for Python scripts and worker processes. The SDK depends on the toolkit to
  reuse validation and filtering logic locally while also speaking to the
  service API when needed.
- **Service (`lighthouse-service`):** A FastAPI application that exposes REST
  endpoints for managing proxies and leases. It composes the toolkit with a
  durable storage backend to provide shared state for browser clients.
- **Web Application (`lighthouse-frontend`):** A browser-based UI that talks to
  the FastAPI service.

## Interaction Flows

There are two primary paths users can take.

### 1. Automation & Worker Flow

```
End User (CLI / automation)
        ↓
  Python scripts / workers
        ↓
        SDK
     ↙      ↘
Toolkit   Service API (optional)
        ↓
     Storage
```

- Scripts can interact with the toolkit directly (e.g., running health checks
  or managing private proxy pools) when they have local access to storage.
- The same scripts can call into the FastAPI service through the SDK when they
  need shared, centralized state. The SDK reuses the toolkit models to keep both
  paths aligned.

### 2. Web Application Flow

```
End User (browser)
        ↓
    Web UI
        ↓
   FastAPI Service
        ↓
      Toolkit
        ↓
     Storage
```

- The web application always goes through the service boundary. The service
  mediates access control, auditing, and shared persistence, while delegating
  proxy lifecycle operations to the toolkit.

## Storage Responsibilities

The toolkit storage implementations only persist proxy-related entities
(proxies, pools, leases, consumers). User authentication, billing, analytics,
and any additional metadata belong to the surrounding applications (service or
custom integrations).

## Why This Separation Matters

- **Single Source of Truth:** The toolkit owns the core rules so that changes to
  leasing or filtering logic propagate consistently to every consumer without
  copy-paste.
- **Flexible Adoption:** Some teams may only need the toolkit for on-prem scripts
  or internal jobs; others can rely on the service + SDK for multi-tenant
  workloads. Both scenarios stay compatible.
- **Independent Deployment Cadence:** The SDK, service, and frontend can evolve
  on their own release cycles while depending on stable toolkit versions.

Refer to this document when planning new features to ensure each concern lands
in the right layer of the ecosystem.
