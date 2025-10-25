# Directives for Project: lighthouse-core

## 1. Core Identity & Objective

You act as an expert Python engineer supporting the development of the
**`lighthouse-core`** toolkit. The mission is to keep this library lean, modular,
and focused on proxy lifecycle business rules while enabling the rest of the
ecosystem (service, SDK, frontend) to compose it.

## 2. Architectural Context

Keep the toolkit focused on proxy lifecycle rules so it remains reusable across
different host projects (services, SDKs, standalone scripts).

### 2.1 Toolkit Layers

- **Models:** Pydantic schemas describing proxies, pools, leases, consumers, and
  health-check results.
- **ProxyManager:** Orchestrates leasing and release operations. Avoid adding
  transport or scheduling concerns here.
- **Storage (`IStorage` + adapters):** Persistence boundary for proxy data only.
  User accounts, billing, and analytics live outside this repo.
- **Utilities:** Focused helpers such as the health checker. Keep them stateless
  and reusable.

### 2.2 Ecosystem Flows

Two supported paths must remain compatible:

1. **Automation / Workers:** End users run Python scripts that depend on the
   SDK. The SDK can talk directly to the toolkit (local operations) and to the
   FastAPI service (shared state). Keep shared logic in the toolkit so both
   routes stay consistent.
2. **Web Experience:** End users access the browser UI → FastAPI service →
   toolkit → storage. Service-layer concerns (auth, rate limiting, orchestration)
   stay outside this repository.

Design changes must preserve this separation and avoid leaking service-specific
concepts into the toolkit.

## 3. Collaboration Norms

- **Language:** All code, docs, commits, and comments are written in English.
- **Comments:** Prefer self-explanatory code. Add comments only when conveying
  rationale that is not obvious from the implementation.
- **Conventional Commits:** Follow the spec for every commit message.

## 4. Delivery Workflow

- Work from feature branches with descriptive names.
- Accompany functional changes with tests. Run `poetry run pytest` (or the
  relevant subset) before merging.
- Use `commitizen` (`cz bump`) for releases, as described in `CONTRIBUTING.md`.

## 5. Reference Materials

Consult these files before making decisions:

- `README.md` for publicly visible messaging; keep it aligned with user-facing
  documentation.
- `pyproject.toml` for dependency management and tooling configuration.
- `CONTRIBUTING.md` for workflow expectations.
- `drafts/architecture-notes.md` for the internal ecosystem overview (context
  only; do not publish with the library docs).
