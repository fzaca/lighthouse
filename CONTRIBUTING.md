# Contributing to Pharox

First off, thank you for considering contributing to Pharox! We welcome any contributions, from fixing a typo to implementing a new feature.

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
    Click the "Fork" button on the top right of the [GitHub repository page](https://github.com/fzaca/pharox).

2.  **Clone your fork:**
    ```bash
    git clone https://github.com/fzaca/pharox.git
    cd pharox
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
    All the library's source code is located in the `src/pharox` directory.

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

This project follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`) and uses [Commitizen](https://commitizen-tools.github.io/commitizen/) to automate versioning and changelog generation.

**Release Process:**

1.  **Ensure `main` is stable:**
    All tests must be passing on the `main` branch.

2.  **Create a new release:**
    The `cz bump` command automates the entire release process based on the commit history since the last tag. It will:
    *   Determine the correct version bump (`PATCH`, `MINOR`, or `MAJOR`).
    *   Update the version in `pyproject.toml`.
    *   Generate or update the `CHANGELOG.md` file.
    *   Create a new git tag for the release.

    ```bash
    # This single command handles everything
    cz bump
    ```

3.  **Generate release notes:**
    Use the helper script to extract the latest changelog entry (it defaults to the current Poetry version). Pipe it to a file that you can upload to GitHub releases or automate further.

    ```bash
    poetry run python scripts/generate_release_notes.py \
        --output dist/release-notes/v$(poetry version -s).md
    ```

    The command prints the destination file path. Use its contents as the body of the GitHub release or feed it into `gh release create`.

4.  **Push the changes and tags:**
    After the command completes, push the commit and the new tag to the remote repository. The GitHub Actions workflow will then publish the package to PyPI.

    ```bash
    git push --tags
    ```
