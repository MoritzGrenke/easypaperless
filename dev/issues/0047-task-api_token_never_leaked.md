# [TASK] Guarantee the API Token and Other Secrets Never Appear in Exceptions, Reprs or Logs

## Summary
Ensure and prove by tests that the API token — and other secrets passed through easypaperless, such as user passwords — never appear in an exception's message, an exception's repr, a log record, or the repr of a client, session or resource object.

Part of the 0.7.0 "Delivery Target" milestone requested by the ThruCapture Backend.

---

## Task Description
Audit every place where easypaperless creates exception messages, log records or object representations, and make sure secrets cannot leak — including indirect paths such as chained `httpx` exceptions, request objects attached to errors, debug logging of request/response data, and default `repr()` of objects that hold the token.

Current state (from code review): the token is only stored in the HTTP session and sent as a default header; no custom `__repr__` exposes it. For the token, this task is mainly about locking the behaviour in with tests. **However**, DEBUG logging writes complete JSON request bodies to the log, so e.g. the `password` passed to `users.create()` / `users.update()` ends up in log records today. This must be fixed.

---

## Motivation
The token grants full access to a paperless instance, and user passwords grant access to accounts. Services log exceptions and objects routinely (and may ship logs to third parties). A single leaked secret in a log line is a security incident.

---

## Scope

### In Scope
- `repr()` of `PaperlessClient`, `SyncPaperlessClient`, the internal HTTP session and resources does not contain the token (a masked form is acceptable).
- Messages and `repr()` of all easypaperless exceptions do not contain the token.
- Log records emitted by easypaperless at any level (including DEBUG) do not contain the token, neither in the message nor in its arguments.
- Debug logging never logs the `Authorization` header.
- Debug logging of request bodies masks secret fields (at least `password`; the full list of secret field names is decided in `/architecture`).
- Tests that set a distinctive token and password, trigger every error class and every log level, and assert the secrets are absent from messages, reprs and captured log records.
- A short note in the docs/security section.

### Out of Scope
- Redacting secrets that a caller puts into URLs, query parameters or free-text fields (e.g. note text) themselves.
- Logging done by `httpx` itself (document how to configure it instead).

---

## Acceptance Criteria
- [ ] `repr(PaperlessClient(url=..., api_token="SECRET-123"))` does not contain `SECRET-123`; same for `SyncPaperlessClient`.
- [ ] For each exception class raised by the HTTP layer (401, 403, 400, 404, 5xx, transport errors, retry exhausted, upload errors, task timeout), neither `str(err)` nor `repr(err)` contains the token.
- [ ] With logging captured at DEBUG for the `easypaperless` logger, a full request cycle including errors produces no record whose formatted message contains the token.
- [ ] With logging captured at DEBUG, `users.create(username="u", password="PW-SECRET-456")` and `users.update(id, password="PW-SECRET-456")` produce no record containing `PW-SECRET-456`; the other body fields are still logged.
- [ ] The tests above run in CI.

---

## Dependencies & Constraints
- Builds on the reworked exceptions of #0046 and the transport of #0043 (used to trigger errors in tests).

---

## Priority
`High`

---

## Additional Notes
- Requester: ThruCapture Backend, Must-item 8. Extended to other secrets (passwords) after code review found request bodies being logged at DEBUG level.
