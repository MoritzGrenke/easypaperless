# [FEATURE] Upload Documents from Bytes and Per-Call Upload Timeout

## Summary
Extend `documents.upload()` so that a document can be uploaded from in-memory bytes with an explicit file name and content type, without writing a temporary file, and allow a per-call HTTP timeout for the upload request.

Part of the 0.7.0 "Delivery Target" milestone requested by the ThruCapture Backend.

---

## Problem Statement
`documents.upload()` only accepts a file path and reads the file from disk. Services that produce documents in memory (e.g. the ThruCapture Backend binding photographs into a PDF) must write a temporary file just to upload it. The file name sent to paperless is always derived from the path, and the content type cannot be set. Large uploads may also need a longer HTTP timeout than the client-wide default.

---

## Proposed Solution
- `documents.upload(file: str | Path | bytes, *, filename: str | None = None, content_type: str | None = None, timeout: float | None = None, ...)`, on both the async and the sync client.
- When `file` is `bytes`, `filename` is required; omitting it raises a clear local error before any request is sent.
- When `file` is a path, `filename` optionally overrides the name derived from the path.
- `filename` and `content_type` are sent to paperless exactly as given. When `content_type` is omitted, the existing behaviour applies.
- No temporary file is written in any case.
- `timeout` sets the HTTP timeout of the upload request itself, overriding the client's timeout for this call only. The existing `poll_interval` / `poll_timeout` parameters keep their meaning for `wait=True`.
- `wait=False` keeps returning the task ID; `wait=True` keeps returning the `Document`.
- **The upload request is never retried automatically**, regardless of the client's retry configuration (#0041). Today `post_document` runs through the retry loop: if a timeout occurs after paperless has already accepted the file, the retry uploads it a second time and creates a duplicate. A failed upload request must surface as an error so that the caller can decide (e.g. check by checksum, #0050) whether the document already exists. The same rule applies to other non-idempotent POST requests (to be listed in `/architecture`).

---

## User Stories
- As a developer generating PDFs in memory, I want to upload bytes directly so that I don't have to manage temporary files.
- As a developer, I want to control the file name and content type paperless receives so that the stored original has a meaningful name and is detected correctly.
- As a developer uploading large files over slow links, I want a per-call timeout so that one big upload does not force a long timeout on every request.

---

## Scope

### In Scope
- `bytes` support, `filename`, `content_type` and `timeout` parameters on async and sync `upload()`.
- Validation: `bytes` without `filename` raises a local error (no HTTP request).
- Excluding the upload request (and other non-idempotent POSTs) from automatic retries; docs of `retry_attempts` / `tenacity_retrying` updated accordingly.
- Docstring and user doc updates.
- Tests using the injected transport (#0043) that assert the multipart body contains the given file name, content type and bytes.

### Out of Scope
- File-like objects / streams (`BinaryIO`) — may be a follow-up.
- Automatic content type detection beyond the existing behaviour.
- Task handling changes (covered by #0045).

---

## Acceptance Criteria
- [ ] `upload(b"%PDF...", filename="capture.pdf")` sends a multipart request whose `document` part has filename `capture.pdf` and the given bytes.
- [ ] `upload(b"...", filename="x.pdf", content_type="application/pdf")` sends `application/pdf` as the part's content type.
- [ ] `upload(b"...")` without `filename` raises a local validation error and sends no request.
- [ ] `upload(Path("a.pdf"), filename="b.pdf")` sends `b.pdf` as the file name.
- [ ] `upload(path)` without new parameters behaves exactly as before.
- [ ] No temporary file is created during a bytes upload (verified by test).
- [ ] `upload(..., timeout=120)` uses 120 s for the upload request while other requests keep the client's timeout.
- [ ] The sync client offers the same parameters with identical behaviour.
- [ ] With `retry_attempts=3`, a transport error or timeout on the upload request results in exactly **one** request being sent and the error being raised (no retry). The same holds with `tenacity_retrying`.
- [ ] Retries for idempotent requests (e.g. GET) keep working as before.

---

## Dependencies & Constraints
- Tests should use the injected transport from #0043.
- **Naming must be decided before implementation:** `upload()` already has `poll_interval` / `poll_timeout` (task polling), this issue adds `timeout` (HTTP request), and #0045 adds `tasks.wait(timeout=...)` (total wait time). `timeout` would then mean different things in `upload()` and `tasks.wait()`. `/architecture` decides on consistent names for both issues together.
- The task polling used by `wait=True` is reworked in #0045; this issue must not change its results.

---

## Priority
`High`

---

## Additional Notes
- Requester: ThruCapture Backend, Must-items 2 and (partly) 11.
