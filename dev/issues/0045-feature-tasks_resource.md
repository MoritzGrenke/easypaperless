# [FEATURE] Tasks Resource (list, get, wait, acknowledge)

## Summary
Expose paperless-ngx's background tasks as a public `tasks` resource on both clients: list with filters, get a single task, wait for a task to finish, and acknowledge tasks. Upload errors and timeouts carry the task so that callers can classify failures and resume waiting.

Part of the 0.7.0 "Delivery Target" milestone requested by the ThruCapture Backend.

---

## Problem Statement
Task polling exists only as a private helper inside `documents.upload(wait=True)`. A caller that uploads with `wait=False` (e.g. to survive restarts) has no public way to look the task up later or to resume waiting. When processing fails, `UploadError` only contains a formatted message, so a caller cannot reliably tell a duplicate document from an OCR failure. `TaskTimeoutError` does not carry the task ID, so the task cannot be resumed. The paperless UI's task list (filtering, acknowledging) is also not reachable.

---

## Proposed Solution
- New `client.tasks` resource (async and sync):
  - `tasks.list(...)` with paperless's task filters (at least: task ID, status, task name, type, acknowledged) — returns the result in the same style as the other `list()` methods, as far as paperless's response shape allows (spike).
  - `tasks.get(task_id: str) -> Task` — raises `NotFoundError` if paperless does not know the task.
  - `tasks.wait(task_id: str, *, poll_interval: float | None = None, timeout: float | None = None) -> Task` — polls until the task reaches a terminal state and returns the final `Task`; per-call values override the client's defaults.
  - `tasks.acknowledge(task_ids: list[int]) -> ...` — marks tasks as acknowledged (as the paperless UI does).
- The `Task` model is public and contains at least: id, task ID, task name, file name, type, status, result (unaltered), acknowledged, related document, created/done timestamps, owner.
- `documents.upload(wait=True)` uses `tasks.wait()` internally; `upload(wait=False)` keeps returning the task ID string.
- `UploadError` carries the `Task` (task ID, status and paperless's `result` unaltered).
- `TaskTimeoutError` carries the task ID (and the timeout that was exceeded), so a caller can call `tasks.wait()` again.
- Starting system tasks (admin endpoint) is not part of this issue.

---

## User Stories
- As a developer of a delivery worker, I want to upload with `wait=False`, persist the task ID and later call `tasks.wait()` so that I can resume after a restart without uploading twice.
- As a developer, I want `UploadError` to expose paperless's original result so that I can distinguish "document is a duplicate" from "OCR failed" and react differently.
- As a developer, I want `TaskTimeoutError.task_id` so that I can keep waiting instead of re-uploading.
- As a developer building an admin tool, I want to list failed tasks and acknowledge them like in the paperless UI.

---

## Scope

### In Scope
- `TasksResource` and `SyncTasksResource` with `list`, `get`, `wait`, `acknowledge`.
- Public `Task` model (and `TaskStatus`), exported from `easypaperless` / `easypaperless.models` without breaking existing import paths.
- `UploadError.task` and `TaskTimeoutError.task_id` attributes.
- Refactoring `upload(wait=True)` onto `tasks.wait()`.
- Structured logging analogous to other resources (#0030).
- Tests via the injected transport (#0043).
- Spike: response shape of `GET /api/tasks/` (plain list vs. paginated), available filter names, acknowledge payload, behaviour of an unknown task ID.

### Out of Scope
- Running system tasks (e.g. index optimize, sanity check, train classifier).
- Task-related websocket/status streaming.

---

## Acceptance Criteria
- [ ] `tasks.get("<uuid>")` returns a `Task` with `status`, `result`, `related_document` and `task_file_name` populated from paperless's response.
- [ ] `tasks.get("<unknown>")` raises `NotFoundError`.
- [ ] `tasks.list(status=...)`, `tasks.list(acknowledged=False)` etc. send the corresponding paperless filter parameters.
- [ ] `tasks.wait(task_id)` returns the final `Task` when status becomes `SUCCESS`.
- [ ] `tasks.wait(task_id)` raises `UploadError` when status becomes `FAILURE` or `REVOKED`; `err.task.status` and `err.task.result` equal paperless's values unaltered.
- [ ] `tasks.wait(task_id, timeout=5)` raises `TaskTimeoutError` with `err.task_id == task_id` after ~5 s; the per-call `timeout` and `poll_interval` override client defaults.
- [ ] `tasks.acknowledge([1, 2])` sends the acknowledge request with those task IDs.
- [ ] `documents.upload(wait=False)` still returns the task ID string; `upload(wait=True)` still returns the `Document`, now via `tasks.wait()`.
- [ ] A duplicate-document failure and an OCR failure can be distinguished by inspecting `UploadError.task.result` (tested with recorded paperless responses).
- [ ] Existing imports of `Task`/`TaskStatus` keep working.
- [ ] The sync client provides the identical API.

---

## Dependencies & Constraints
- Uses the injected transport from #0043 for tests.
- Interacts with #0044 (upload) and #0046 (exception hierarchy); `UploadError` and `TaskTimeoutError` must fit into the reworked hierarchy.
- **Backward compatibility:** `TaskTimeoutError(message)` and `UploadError(message)` must keep working; `task_id` / `task` are added as optional keyword arguments, so this is not a breaking change.
- **Pagination:** `GET /api/tasks/` returns a plain list today (the current polling code reads `resp.json()[0]`), so the generic `_list_resource` helper does not fit. Since #0029 every `list()` returns a `PagedResult`; `tasks.list()` must build it itself, like `notes.list()` does (#0032, #0034).
- **Naming:** parameter names for `tasks.wait()` (`poll_interval` / `timeout` vs. `poll_timeout`) are decided together with #0044 in `/architecture`.
- **File size:** the tasks logic goes into its own resource modules (async and sync), and today's `_poll_task` moves out of `resources/documents.py` (already ~1100 lines). The `Task` / `TaskStatus` models move to their own model module and stay importable from `easypaperless.models.documents`.

---

## Priority
`High`

---

## Additional Notes
- Requester: ThruCapture Backend, Must-items 3 and (partly) 11. Extended to a complete resource (list, acknowledge) to cover the paperless tasks endpoint fully.

---

## Assumptions
The live instance was not reachable during implementation, so the spike was not run. The implementation rests on the following assumptions, taken from the previous polling code and the paperless-ngx docs/source. They should be verified against a live instance (e.g. in #0050):

> **Verified in #0050** against paperless-ngx 2.18.2: response shape, filters, unknown task ID, acknowledge and task fields hold as described. Corrections: `type` takes `auto_task`, `scheduled_task` or `manual_task` (not `file`). `status`, `task_name` and `type` are case-sensitive enums, and an invalid value answers 400. `RECEIVED` is a valid status. A duplicate `FAILURE` carries the existing document's ID in `related_document` (`null` if that document is in the trash). The failure texts below were replaced by the live ones in the tests.

- **Response shape:** `GET /api/tasks/` returns a plain JSON array (the old `_poll_task` read `resp.json()[0]`). `tasks.list()` wraps it into a `PagedResult` (`count = len(results)`, `next`/`previous` = `None`). A paginated envelope (`count`/`next`/`results`) is accepted defensively, and all of its pages are fetched.
- **Filters:** query parameters `task_id`, `status`, `task_name`, `type`, `acknowledged` (booleans sent as `true`/`false`). No `page` / `page_size` parameters, since the endpoint is not paginated.
- **Unknown task ID:** paperless answers `200 []` rather than 404. `tasks.get()` turns the empty result into `NotFoundError`. `tasks.wait()` keeps polling on an empty result, because a freshly uploaded task may not be listed yet.
- **Acknowledge:** `POST /api/tasks/acknowledge/` with body `{"tasks": [<numeric ids>]}`, answered with `{"result": <count>}`. If `result` is missing, the method returns `len(task_ids)`.
- **Task fields:** `id`, `task_id`, `task_name`, `task_file_name`, `type`, `status`, `result`, `acknowledged`, `related_document` (a string; an int is accepted and converted), `date_created`, `date_done`, `owner`. Unknown fields (e.g. `duplicate_documents`) are ignored.
- **Failure results used in tests** (the live texts from #0050): duplicate `"invoice.pdf: Not consuming invoice.pdf: It is a duplicate of Invoice 2026-10 (#12)."` (`related_document="12"`); duplicate of a trashed document: the same text plus `" Note: existing document is in the trash."` (`related_document=None`); consumption failure `"invoice.pdf: Error occurred while consuming document invoice.pdf: InputFileError: "`.

## Implementation Notes
- `tasks.wait()` uses `poll_interval` / `poll_timeout` rather than the `timeout` named in the acceptance criteria. This follows the binding naming decision shared with #0044 (see `dev/api-conventions.md`, "Timeout naming").
- `tasks.wait()` checks the task at least once, even when `poll_timeout` is 0.
- `upload(wait=True)` raises `UploadError(..., task=task)` itself when a successful task has no `related_document`.
- The non-retry flag for creating requests and bytes upload are left to #0044.
