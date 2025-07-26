# Contributing to Lighthouse

First off, thank you for considering contributing to Lighthouse! We welcome any contributions, from fixing a typo to implementing a new feature.

This document provides a guide for making contributions to the project.

## Table of Contents

1.  [Getting Started: Your Development Environment](#getting-started-your-development-environment)
2.  [The Development Workflow](#the-development-workflow)
3.  [Running Tests](#running-tests)
4.  [Submitting Your Contribution](#submitting-your-contribution)
5.  [Versioning and Releases (For Maintainers)](#versioning-and-releases-for-maintainers)

---

## 1. Getting Started: Your Development Environment

To ensure a consistent development experience, we use [Poetry](https://python-poetry.org/) to manage dependencies and virtual environments.

**Prerequisites:**

*   [Git](https://git-scm.com/)
*   [Python](https://www.python.org/) 3.9+
*   [Poetry](https://python-poetry.org/docs/#installation)

**Setup Steps:**

1.  **Fork the repository:**
    Click the "Fork" button on the top right of the [GitHub repository page](https://github.com/fzaca/lighthouse).

2.  **Clone your fork:**
    ```bash
    git clone https://github.com/fzaca/lighthouse.git
    cd lighthouse
    ```

3.  **Install dependencies and activate the environment:**
    Poetry will create a virtual environment and install all required dependencies, including development tools like `pytest` and `ruff`.

    ```bash
    poetry install
    ```

4.  **Activate the virtual environment:**
    To use the installed tools, you need to be inside the project's virtual environment.

    ```bash
    poetry shell
    ```

5.  **Set up pre-commit hooks:**
    We use `pre-commit` to automatically lint and format your code before you commit it. This helps maintain a consistent code style.

    ```bash
    pre-commit install
    ```

You are now ready to start developing!

## 2. The Development Workflow

1.  **Create a new branch:**
    Work on a separate branch to keep your changes organized. Name it descriptively.

    ```bash
    # Example: git checkout -b feature/add-new-proxy-strategy
    # Example: git checkout -b fix/resolve-caching-bug
    git checkout -b <type>/<short-description>
    ```

2.  **Write your code:**
    All the library's source code is located in the `src/lighthouse` directory.

3.  **Write or update tests:**
    Tests are crucial! Make sure to add or update tests for any changes you make. Tests reside in the `tests/` directory.

4.  **Commit your changes:**
    When you're ready, stage and commit your files.

    ```bash
    git add .
    git commit -m "feat: Add new proxy rotation strategy"
    ```
    When you run `git commit`, `pre-commit` will automatically run `ruff` to format and lint your code. If it makes any changes, you'll need to `git add .` the modified files and run the commit command again.

## 3. Running Tests

To ensure your changes haven't broken anything, run the full test suite with `pytest`. We also check for test coverage.

```bash
# Make sure you are in the poetry shell
pytest
```

This command will run all tests in the `tests/` directory and print a coverage report to the terminal. Aim for high test coverage for any new code you add.

You can also run specific tests:

```bash
pytest tests/test_my_feature.py
```

## 4. Submitting Your Contribution

1.  **Push your branch to your fork:**
    ```bash
    git push origin <your-branch-name>
    ```

2.  **Open a Pull Request (PR):**
    Go to the original repository on GitHub. You should see a prompt to create a Pull Request from your recently pushed branch.

3.  **Fill out the PR template:**
    *   Provide a clear title and a concise description of your changes.
    *   Link to any relevant issues (e.g., "Closes #42").
    *   Explain your changes and why they are needed.

4.  **Wait for review:**
    A maintainer will review your PR. They may request changes. Once your PR is approved and all checks pass, it will be merged into the `main` branch.

## 5. Versioning and Releases (For Maintainers)

This project follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`). Releases are automated via GitHub Actions.

**Release Process:**

1.  **Ensure `master` is stable:**
    All tests must be passing on the `master` branch.

2.  **Bump the version:**
    Use `poetry` to update the version number in `pyproject.toml`.

    ```bash
    # Choose one depending on the changes
    poetry version patch  # For bugfixes (e.g., 0.1.0 -> 0.1.1)
    poetry version minor  # For new features (e.g., 0.1.1 -> 0.2.0)
    poetry version major  # For breaking changes (e.g., 0.2.0 -> 1.0.0)
    ```

3.  **Commit the version bump:**
    ```bash
    git add pyproject.toml
    git commit -m "chore: Bump version to vX.Y.Z"
    git push origin main
    ```

4.  **Create and push a git tag:**
    The GitHub Actions workflow is triggered by pushing a new tag that matches the `v*.*.*` pattern.

    ```bash
    git tag vX.Y.Z
    git push origin vX.Y.Z
    ```

This will trigger the `release.yml` workflow, which will build the package and publish it to PyPI.
