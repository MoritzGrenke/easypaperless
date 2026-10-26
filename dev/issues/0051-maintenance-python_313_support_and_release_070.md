# [MAINTENANCE] Python 3.13 Support and 0.7.0 Release

## Summary
State Python 3.13 as supported, test it in CI, and release the 0.7.0 milestone (#0043–#0050) to PyPI so that downstream projects can pin it exactly.

---

## Task Description
- Add Python 3.13 to the package classifiers.
- **Create a CI workflow** that runs the test suite, `ruff check`, `ruff format --check` and `mypy` on Python 3.11, 3.12 and 3.13 (test matrix) on every push and pull request. Today only the two publish workflows exist; tests, lint and type check never run in CI.
- Fix any incompatibility found on 3.13.
- After #0043–#0050 are done: update CHANGELOG (calling out any breaking changes), docs and README, bump the version to 0.7.0, build and publish to PyPI, and tag the release.

---

## Motivation
The ThruCapture Backend runs on Python 3.13 and pins easypaperless exactly; it needs an official 0.7.0 release that is tested on its Python version.

---

## Scope

### In Scope
- Classifiers, new CI test workflow with matrix (3.11, 3.12, 3.13), 3.13 fixes.
- Integration tests (live instance) stay manual and are not part of CI.
- Release 0.7.0: changelog, docs (pdoc), version bump, PyPI publish, git tag.

### Out of Scope
- Dropping Python 3.11/3.12.
- Python 3.14.

---

## Acceptance Criteria
- [x] `pyproject.toml` lists Python 3.13 in its classifiers.
- [x] A CI workflow runs on every push and pull request and executes tests, ruff (check + format check) and mypy on 3.11, 3.12 and 3.13; all pass.
- [x] CHANGELOG has a 0.7.0 entry covering #0043–#0050, with breaking changes called out.
- [x] Version 0.7.0 is published on PyPI and installable with `pip install easypaperless==0.7.0` on Python 3.13.
- [x] A `v0.7.0` git tag exists.

---

## Dependencies & Constraints
- Release only after #0043–#0050 are deployed-ready.

---

## Priority
`High`

---

## Progress
- 2026-10-26: CI / Python 3.13 part done (branch `ci/0051-ci-py313`): 3.13 classifier added, `.github/workflows/ci.yml` created (push + PR, matrix 3.11/3.12/3.13: pytest, ruff check, ruff format --check, mypy), `tenacity` added to `[dev]` extras. Full gate green locally on Python 3.13 (Windows); no 3.13 incompatibilities found. The workflow has not yet run on GitHub (Linux).
- 2026-10-26: Release part done: ruff/mypy pinned after ruff 0.17 broke the CI format check, CHANGELOG 0.7.0, pdoc regenerated, version 0.7.0, PR #1 merged, tag `v0.7.0` pushed, published on PyPI (wheel + sdist).

---

## Additional Notes
- Requester: ThruCapture Backend, Must-items 12 and 13.
