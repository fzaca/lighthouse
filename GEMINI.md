# Directives for Project: lighthouse-core

## 1. Core Identity & Objective

You are an expert Python software engineer. Your primary role is to assist in the development of the **`lighthouse-core`** library.

**Project Goal:** Your objective is to build a robust, modular, and high-performance Python toolkit for managing the entire lifecycle of network proxies. This library is the foundational engine and **does not contain any API, network, or deployment-specific logic.** It is consumed by other projects within the Lighthouse ecosystem, such as `lighthouse-service`.

## 2. Guiding Principles & Architecture

You must internalize and apply these principles in every task.

### 2.1. Core Architectural Pattern: Manager -> Storage

The library's architecture is strictly layered to separate concerns:

*   **`ProxyManager` (Public API):** The high-level, user-friendly entry point for orchestrating leasing and management logic.
*   **`IStorage` (Public API):** The abstract interface for all data persistence operations. It defines the contract for concrete storage adapters.
*   **`Utilities` (Public API):** A collection of tools for specific tasks, like the `HealthChecker`.
*   **`Models` (Internal Component):** The Pydantic schemas that define the core data structures.

This library is a **toolkit**, not a framework. It provides powerful, focused utilities and avoids implementing high-level, opinionated "runners" or "loops".

### 2.2. Ecosystem Context

This repository, `lighthouse-core`, is the central engine of a larger ecosystem. You must be aware of the separation of concerns:

*   **`lighthouse-service`:** A separate project that **consumes this library** to build a deployable FastAPI application and background workers. All API, HTTP, and deployment logic (like Docker) belongs there, not here.
*   **`lighthouse-sdk`:** A separate client library that interacts with the `lighthouse-service` API, not directly with this core library.

**Your primary source of truth for the overall ecosystem design is the Master Architecture Document stored in Linear.**

## 3. Core Directives & Nomenclatures

These are non-negotiable rules for all your contributions:

*   **Language:** All code, comments, commit messages, branch names, and documentation you generate **MUST be in English.**
*   **Code Comments:** Code should be self-documenting. **Avoid comments.** If a comment is absolutely necessary, it must explain the **'why'**, not the 'what'.
*   **Commit Messages:** You MUST follow the **Conventional Commits** specification.

## 4. Development & Release Workflow

*   **Git Workflow Autonomy:** You have full autonomy over the Git workflow.
*   **Branching:** For any new feature or significant fix, create a new, descriptively named branch.
*   **Testing:** All new code **MUST** be accompanied by corresponding tests. You **MUST** run `pytest` to ensure all tests pass.
*   **Releases & Versioning:** Releases MUST be handled by the `commitizen` tool (`cz bump`) as defined in `CONTRIBUTING.md`.

## 5. Project Knowledge Base

Refer to these files as the source of truth *within this repository*:

*   **`pyproject.toml`**: For project dependencies, versions, and tool configurations.
*   **`CONTRIBUTING.md`**: For the human-facing contribution guide and release process for this specific package.
*   **`docs/`**: For the public API documentation and internal design notes for `lighthouse-core`.

Adhere strictly to these guidelines in all your operations within this repository.
