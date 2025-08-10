# Lighthouse Core

[![Python Versions](https://img.shields.io/pypi/pyversions/lighthouse.svg)](https://pypi.org/project/lighthouse/)
[![PyPI Version](https://img.shields.io/pypi/v/lighthouse.svg)](https://pypi.org/project/lighthouse/)
[![CI Status](https://github.com/fzaca/lighthouse/actions/workflows/test.yml/badge.svg)](https://github.com/fzaca/lighthouse/actions/workflows/test.yml)
[![License](https://img.shields.io/pypi/l/lighthouse.svg)](https://github.com/fzaca/lighthouse/blob/main/LICENSE)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

The foundational Python toolkit for building robust proxy management systems.

`lighthouse` provides the pure, domain-agnostic business logic for managing the entire lifecycle of network proxies. It is the engine that powers the Lighthouse ecosystem, designed to be used as a direct dependency in your Python applications.

---

## Key Features

*   **Proxy Leasing System:** A powerful system to "lease" proxies to consumers, with support for exclusive, shared (concurrent), and unlimited usage.
*   **Pluggable Storage:** A clean interface (`IStorage`) that decouples the core logic from the database, allowing you to "plug in" any storage backend (e.g., in-memory, PostgreSQL, MongoDB).
*   **Health Checking Toolkit:** A flexible, asynchronous utility (`AsyncHealthChecker`) to test proxy health, latency, and compatibility.
*   **Modern & Type-Safe:** Built with Python 3.10+, Pydantic v2, and a 100% type-annotated codebase.
*   **Toolkit, Not a Framework:** Provides powerful, focused utilities, giving you the freedom to build your own application logic on top.

## Installation

You can install `lighthouse` directly from PyPI:

```bash
pip install lighthouse
```

## Quickstart Example

Here is a simple example of how to use `lighthouse` with the default `InMemoryStorage` to acquire and release a proxy.

```python
# Example of usage in code
```

## The Lighthouse Ecosystem

`lighthouse` is the central engine of a larger ecosystem. For a complete, deployable solution, check out the other projects:

*   **[lighthouse-service](https://github.com/fzaca/lighthouse-service):** A deployable FastAPI application and background workers that use this library to provide a proxy management API.
*   **[lighthouse-sdk](https://github.com/fzaca/lighthouse-sdk):** A lightweight Python client for easily interacting with the `lighthouse-service` API.

## Contributing

Contributions are welcome! Please see the `CONTRIBUTING.md` file for details on how to set up your development environment, run tests, and submit a pull request.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
