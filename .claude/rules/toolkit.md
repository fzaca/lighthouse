# Toolkit Rules

See the ecosystem-level rules at:
`pharox-ecosystem/.claude/rules/toolkit.md`

## Quick Reference

- No HTTP, no web frameworks, no auth — business logic only.
- Adding to `IStorage` requires implementing in ALL 4 adapters.
- New exceptions must subclass `PharoxError`.
- Public API lives in `src/pharox/__init__.py` — changes there are semver-breaking.
- `poetry run pytest` + `poetry run mypy src/pharox` must pass before every commit.
- Coverage threshold: 85% minimum.
- Release: `cz bump --no-verify` → `git push origin master --tags`.
