# [MAINTENANCE] Python 3.13 Support and 0.7.0 Release

## Summary
State Python 3.13 as supported, test it in CI, and release the 0.7.0 milestone (#0043–#0050) to PyPI so that downstream projects can pin it exactly.

---

## Task Description
- Add Python 3.13 to the package classifiers.
- Run the test suite, lint and type check on Python 3.11, 3.12 and 3.13 in CI (test matrix).
- Fix any incompatibility found on 3.13.
- After #0043–#0050 are done: update CHANGELOG (including breaking changes such as the `TaskTimeoutError` constructor), docs and README, bump the version to 0.7.0, build and publish to PyPI, and tag the release.

---

## Motivation
The ThruCapture Backend runs on Python 3.13 and pins easypaperless exactly; it needs an official 0.7.0 release that is tested on its Python version.

---

## Scope

### In Scope
- Classifiers, CI matrix (3.11, 3.12, 3.13), 3.13 fixes.
- Release 0.7.0: changelog, docs (pdoc), version bump, PyPI publish, git tag.

### Out of Scope
- Dropping Python 3.11/3.12.
- Python 3.14.

---

## Acceptance Criteria
- [ ] `pyproject.toml` lists Python 3.13 in its classifiers.
- [ ] CI runs tests, ruff and mypy on 3.11, 3.12 and 3.13 and all pass.
- [ ] CHANGELOG has a 0.7.0 entry covering #0043–#0050, with breaking changes called out.
- [ ] Version 0.7.0 is published on PyPI and installable with `pip install easypaperless==0.7.0` on Python 3.13.
- [ ] A `v0.7.0` git tag exists.

---

## Dependencies & Constraints
- Release only after #0043–#0050 are deployed-ready.

---

## Priority
`High`

---

## Additional Notes
- Requester: ThruCapture Backend, Must-items 12 and 13.
