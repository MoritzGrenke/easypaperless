# [FEATURE] Classifiable Error Hierarchy (401 vs 403, 400 Field Errors, Transport vs 5xx)

## Summary
Refine the exception hierarchy so that callers can classify every failure programmatically: authentication vs. permission errors, bad requests with parsed field errors, and transport failures vs. server 5xx responses — while keeping every existing `except` clause working.

Part of the 0.7.0 "Delivery Target" milestone requested by the ThruCapture Backend.

---

## Problem Statement
Today:
- 401 and 403 both raise `AuthError`, distinguishable only by `status_code`.
- A 400 response raises a bare `PaperlessError`; field errors returned by paperless (e.g. `{"title": ["This field is required."]}`) are not parsed, and the message falls back to the raw body because only `detail` is extracted.
- Transport errors (connection refused, DNS, TLS, timeout) and HTTP 5xx responses both raise `ServerError`; they can only be told apart by `status_code is None`.

A delivery worker must decide per error whether to retry, alert, or give up — this needs reliable classes.

---

## Proposed Solution
- `AuthError` gets two subclasses:
  - one for 401 (e.g. `AuthenticationError`: token missing/invalid),
  - one for 403 (e.g. `PermissionDeniedError`: token valid, permission missing).
  The message of a 403 keeps paperless's own words (e.g. which permission was missing).
- A 400 response raises its own class (e.g. `BadRequestError`, subclass of `PaperlessError`) that exposes the parsed field errors as a mapping of field name to list of messages, plus non-field errors. Its message summarises the field errors readably.
- `ServerError` gets two subclasses:
  - one for HTTP 5xx responses (with `status_code`),
  - one for transport errors (connection refused, DNS, TLS, timeout), with `status_code = None`. A timeout may be its own subclass of the transport error.
  The original `httpx` exception stays chained (`__cause__`).
- Every exception keeps `status_code` and the server's message.
- `RetryExhaustedError` keeps the last underlying error chained.
- Final class names are decided in `/architecture`; the names above are proposals.

---

## User Stories
- As a developer, I want to catch a permission error separately from an invalid token so that I can tell the user "grant permission X" instead of "check your token".
- As a developer, I want the field errors of a 400 as structured data so that I can show which field was rejected.
- As a developer of a retrying worker, I want to distinguish "paperless unreachable" from "paperless returned 500" so that I can choose different retry strategies.

---

## Scope

### In Scope
- New exception subclasses, exported from `easypaperless`.
- Mapping of HTTP status codes and transport errors to the new classes in the HTTP layer.
- Parsing of paperless's error body shapes (`detail`, field-error dicts, non-field errors, lists).
- Docs: an error-handling section listing all classes and when they are raised.
- Tests via the injected transport (#0043) for every class.

### Out of Scope
- Classes for other 4xx codes (409, 429, …) beyond what already exists — they keep raising `PaperlessError` with `status_code`.
- Token redaction (#0047).

---

## Acceptance Criteria
- [ ] A 401 raises the 401 subclass; `isinstance(err, AuthError)` is `True`; `err.status_code == 401`.
- [ ] A 403 raises the 403 subclass; `isinstance(err, AuthError)` is `True`; `str(err)` contains paperless's `detail` text verbatim.
- [ ] A 400 with body `{"title": ["This field is required."]}` raises the 400 class; its field errors equal `{"title": ["This field is required."]}`; `err.status_code == 400`.
- [ ] A 400 with `non_field_errors` or a plain list body is parsed without crashing and its messages are exposed.
- [ ] A 500/502/503 raises the 5xx subclass with the right `status_code`; `isinstance(err, ServerError)` is `True`.
- [ ] Connection refused, DNS failure, TLS failure and timeout raise the transport subclass with `status_code is None`; `err.__cause__` is the original `httpx` exception; `isinstance(err, ServerError)` is `True`.
- [ ] Every raised easypaperless exception exposes `status_code` and a non-empty message.
- [ ] All existing tests that catch `AuthError`, `ServerError`, `PaperlessError` still pass.
- [ ] The error-handling documentation lists every class.

---

## Dependencies & Constraints
- Must stay backward compatible: new classes are subclasses of the existing ones.
- **Single mapping point:** today the transport-error mapping is duplicated in four places in the HTTP layer (single request, download with redirects, and twice in the fetching of follow-up pages). Downloads and follow-up pages also bypass the retry loop. The mapping must be consolidated into one place so that every request path raises the same classes; whether downloads and follow-up pages should also be retried is decided in `/architecture`.
- Acceptance tests must cover all request paths: single request, download, and follow-up pages of a paginated list.
- Interacts with #0045 (`UploadError`, `TaskTimeoutError`) and #0041 (retry: the transport subclass must remain retryable by default).

---

## Priority
`High`

---

## Additional Notes
- Requester: ThruCapture Backend, Must-item 7.
