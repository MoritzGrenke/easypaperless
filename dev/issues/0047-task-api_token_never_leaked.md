# [TASK] Guarantee the API Token Never Appears in Exceptions, Reprs or Logs

## Summary
Ensure and prove by tests that the API token never appears in an exception's message, an exception's repr, a log record, or the repr of a client, session or resource object.

Part of the 0.7.0 "Delivery Target" milestone requested by the ThruCapture Backend.

---

## Task Description
Audit every place where easypaperless creates exception messages, log records or object representations, and make sure the API token cannot leak — including indirect paths such as chained `httpx` exceptions, request objects attached to errors, debug logging of request/response data, and default `repr()` of objects that hold the token.

---

## Motivation
The token grants full access to a paperless instance. Services log exceptions and objects routinely (and may ship logs to third parties). A single leaked token in a log line is a security incident.

---

## Scope

### In Scope
- `repr()` of `PaperlessClient`, `SyncPaperlessClient`, the internal HTTP session and resources does not contain the token (a masked form is acceptable).
- Messages and `repr()` of all easypaperless exceptions do not contain the token.
- Log records emitted by easypaperless at any level (including DEBUG) do not contain the token, neither in the message nor in its arguments.
- Debug logging never logs the `Authorization` header.
- Tests that set a distinctive token, trigger every error class and every log level, and assert the token string is absent from messages, reprs and captured log records.
- A short note in the docs/security section.

### Out of Scope
- Redacting tokens that a caller puts into URLs or parameters themselves.
- Logging done by `httpx` itself (document how to configure it instead).

---

## Acceptance Criteria
- [ ] `repr(PaperlessClient(url=..., api_token="SECRET-123"))` does not contain `SECRET-123`; same for `SyncPaperlessClient`.
- [ ] For each exception class raised by the HTTP layer (401, 403, 400, 404, 5xx, transport errors, retry exhausted, upload errors, task timeout), neither `str(err)` nor `repr(err)` contains the token.
- [ ] With logging captured at DEBUG for the `easypaperless` logger, a full request cycle including errors produces no record whose formatted message contains the token.
- [ ] The tests above run in CI.

---

## Dependencies & Constraints
- Builds on the reworked exceptions of #0046 and the transport of #0043 (used to trigger errors in tests).

---

## Priority
`High`

---

## Additional Notes
- Requester: ThruCapture Backend, Must-item 8.
