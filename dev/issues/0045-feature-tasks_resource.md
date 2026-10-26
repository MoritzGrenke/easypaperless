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
- Changing the `TaskTimeoutError` constructor is acceptable but must be noted in the CHANGELOG.

---

## Priority
`High`

---

## Additional Notes
- Requester: ThruCapture Backend, Must-items 3 and (partly) 11. Extended to a complete resource (list, acknowledge) to cover the paperless tasks endpoint fully.
