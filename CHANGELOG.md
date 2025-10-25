## Unreleased

### Feat

- Add geospatial proxy filtering and automatic lease cleanup in manager
- Re-export public toolkit API from package root for easier consumption
- Implement concurrent proxy leasing
- Implement acquire_proxy method in ProxyManager
- Add ProxyManager and initial tests
- Add ProxyManager class skeleton
- Add Pydantic models and storage interface
- Add CI/CD workflows and project documentation files
- Configure project tools (ruff, pytest, mypy)

### Fix

- remove python 3.14 from test.yaml
- Correct syntax in GitHub Actions workflows

### Refactor

- **manager**: return Lease from acquire_proxy
