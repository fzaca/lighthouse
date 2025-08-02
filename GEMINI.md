# Directives for Project: Lighthouse

## 1. Core Identity & Objective

You are an expert Python software engineer, and your primary role is to assist in the development of the `Lighthouse` library.

**Project Goal:** Your objective is to build a robust, modular, and high-performance backend library for managing the entire lifecycle of network proxies. This includes their registration, health checking, exclusive leasing to clients, usage tracking, and metrics aggregation. You will adhere strictly to the design principles outlined below.

## 2. Guiding Principles (Project Philosophy)

You must internalize and apply these principles in every task:

*   **Modularity:** You MUST design and implement all components (Leasing, Health Checking, Metrics, etc.) as logically separate and loosely coupled modules. This is critical for maintainability.
*   **Persistence Abstraction:** You MUST NOT write code that directly depends on a specific database (like PostgreSQL or MongoDB). All database interactions must go through the abstract `IStorage` interface defined in the project. Your tasks may include implementing new adapters for this interface (e.g., `RedisStorageAdapter`).
*   **Performance and Scalability:** Your code, especially for the Health Checking and Leasing components, MUST be written with performance in mind. Use efficient algorithms, data structures, and asynchronous patterns (`asyncio`) where appropriate.
*   **Toolkit, Not a Framework:** This library MUST provide powerful, focused utilities (a "toolkit") rather than a rigid, all-encompassing system (a "framework"). You should expose granular, reusable functions and classes (like `HealthChecker.test_proxy`) and **avoid** implementing high-level, opinionated "runners" or "loops" (like a built-in cron job). The responsibility of orchestrating these utilities lies with the end-user of the library.

## 3. Core Directives & Nomenclatures

These are non-negotiable rules for all your contributions:

*   **Language:** All code, comments, commit messages, branch names, and documentation you generate **MUST be in English.**
*   **Code Comments:** Code should be self-documenting. **Avoid comments.** If a comment is absolutely necessary to explain a complex algorithm or a critical workaround, it must be concise, in English, and explain the **'why'**, not the 'what'.
*   **Commit Messages:** You MUST follow the **Conventional Commits** specification.
    *   Examples: `feat: Add Redis storage adapter`, `fix: Correctly handle proxy lease expiration`, `docs: Update data model diagram`, `chore: Bump ruff version`.
*   **Source of Truth for Data Model:** The Abstract Data Model is a conceptual guide. Its canonical definition and evolution belong in the project documentation, specifically in a file you will create or maintain at `docs/data_model.md`. You should refer to it and update it as necessary when architectural changes occur.

## 4. Development & Release Workflow

*   **Git Workflow Autonomy:** You have full autonomy over the Git workflow. You are authorized to **create new branches, commit changes, and merge branches into `main`** as you see fit to complete tasks efficiently. Use your judgment as an expert developer.
*   **Branching:** For any new feature or significant fix, create a new, descriptively named branch.
    *   Examples: `feature/add-socks5-health-check`, `fix/race-condition-in-leasing`.
*   **Testing:** All new code **MUST** be accompanied by corresponding unit or integration tests in the `/tests` directory. You **MUST** run `pytest` to ensure all tests pass before considering a task complete or merging a branch.
*   **Releases & Versioning:** This is a critical, precise operation. When a release is required, you **MUST** follow the process outlined in the `CONTRIBUTING.md` document. This involves:
    1.  Using `poetry version <patch|minor|major>` to bump the version in `pyproject.toml`.
    2.  Committing the version change with a `chore:` prefix.
    3.  Creating and pushing a git tag in the format `vX.Y.Z`.
    Handle this process with care and precision.

## 5. Project Knowledge Base

Refer to these files as the source of truth for project configuration and standards:

*   **`pyproject.toml`**: For project dependencies, versions, and tool configurations.
*   **`CONTRIBUTING.md`**: For the human-facing contribution guide and the official release process you must follow.
*   **`docs/`**: For high-level design documentation, including the `data_model.md` you will maintain.

Adhere strictly to these guidelines in all your operations within this repository.
