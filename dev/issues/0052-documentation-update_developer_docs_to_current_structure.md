# [DOCUMENTATION] Update Developer Docs and API Conventions to the Current Code Structure

## Summary
Bring `CLAUDE.md`, the API naming conventions and stale docstrings in line with the current code, so that contributors and the `/dev`, `/qa` and `/architecture` workflows follow the real structure and conventions when implementing the 0.7.0 issues (#0043–#0051).

---

## Background / Context
A code review before 0.7.0 found that the developer documentation describes an outdated state:
- `CLAUDE.md` shows the project structure with `_internal/mixins/` and `_internal/sync_mixins/`. Since the resource-based refactoring (#0018) the code uses `_internal/resources/` and `_internal/sync_resources/`, plus `resources.py`, `sentinel.py` and models such as `paged_result.py` and `users.py` that are not listed.
- `CLAUDE.md` references the naming conventions as `dev/api-conventions.md`; the file actually lives at `docs/api-conventions.md`, which is the *public* documentation folder.
- `docs/api-conventions.md` still describes the pre-#0018 flat method names (`list_tags`, `get_tag`, `create_document_type`, `get_notes`, `delete_note`) and `None` defaults instead of `UNSET` semantics (#0019, #0028), and does not mention `PagedResult` (#0029) or the sync-docstring rule (#0026).
- Docstrings in `exceptions.py` reference methods that no longer exist (e.g. `PaperlessClient.upload_document`) and parameter names that no longer exist (e.g. "API key" instead of API token, #0031).

---

## Type of Work
- [ ] Create new documentation
- [x] Update existing documentation
- [ ] Remove outdated documentation
- [x] Restructure / reorganize documentation

---

## Target Audience
Developers of / contributors to easypaperless, including AI agents working through the `/requirements` → `/architecture` → `/dev` → `/qa` workflow.

---

## Scope

### In Scope
- `CLAUDE.md`: project structure tree matches the actual `src/`, `tests/`, `dev/` and `docs/` layout; correct path to the conventions file.
- API conventions: move from `docs/` to `dev/` (developer documentation) or fix the reference — decide and apply consistently; remove it from the public pdoc output if it is moved.
- API conventions content updated to the resource-based API: `client.<resource>.<verb>()` naming, sub-resources (`client.documents.notes`), `id` / `{parent}_id` keys, `UNSET` vs `None` semantics, `PagedResult` return type for `list()`, sync resources mirroring async resources with full docstrings, logging conventions (#0030).
- A short "adding a new resource" checklist (model, async resource, sync resource, client/sync-client wiring and docstrings, `resources.py`, `models/__init__.py`, `__init__.py`, tests, CHANGELOG, pdoc).
- Stale docstrings in `exceptions.py` corrected.

### Out of Scope
- User-facing README and pdoc API docs for the new 0.7.0 features (handled within each feature issue and #0051).
- Changes to the skills in `.claude/skills/` (separate decision).

---

## Acceptance Criteria
- [ ] Documentation accurately reflects the current state of the system / product.
- [ ] Documentation is clear and understandable by the target audience.
- [ ] Every directory and module listed in the `CLAUDE.md` structure tree exists, and every module in `src/easypaperless/` is listed.
- [ ] The conventions file referenced in `CLAUDE.md` exists at the referenced path.
- [ ] The conventions describe only method names that exist on the current resources (no `list_tags`-style names remain).
- [ ] The conventions describe `UNSET` / `None` semantics and the `PagedResult` return type.
- [ ] The "adding a new resource" checklist is present and matches how `users` (#0035) and `trash` (#0036) were added.
- [ ] No docstring in `exceptions.py` references a non-existent method or parameter.

---

## Priority
`High` — should be done before implementing #0043–#0051, because the `/dev` workflow relies on these documents.

---

## Additional Notes
- Found during the code review preceding the 0.7.0 milestone.
