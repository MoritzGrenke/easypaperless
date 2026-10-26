# [FEATURE] Server Version Check and System Status

## Summary
Add a cheap, authenticated way to check the connection and read the paperless-ngx version (`client.server_version()`), and expose paperless's system status endpoint (`client.system_status()`).

Part of the 0.7.0 "Delivery Target" milestone requested by the ThruCapture Backend; extended with the system status to cover the server-information area.

---

## Problem Statement
A service configuring a paperless Delivery Target needs to verify URL and token before delivering anything ("test connection"), and wants to know which paperless version it talks to. Today there is no dedicated call; callers must issue an arbitrary request and interpret errors. A URL that points to some other web server is not reported as such. Administrators additionally want to see paperless's health (database, Redis, Celery, search index, storage), which paperless exposes under its status endpoint.

---

## Proposed Solution
- `client.server_version() -> str` (async and sync):
  - performs one cheap authenticated request (e.g. `GET /api/`),
  - returns the version from the `X-Version` response header,
  - raises the 401/403 `AuthError` subclass (#0046) for a refused token,
  - raises a dedicated error whose message says the server is not a paperless-ngx instance when the header is missing (e.g. `NotPaperlessError`, subclass of `PaperlessError`).
- `client.system_status() -> SystemStatus` (async and sync):
  - reads paperless's status endpoint and returns a typed model (version, install type, server OS, storage, database, tasks/Celery/Redis, index, classifier — as far as paperless provides them),
  - raises the 403 subclass when the token's user lacks the required (admin) permission.

---

## User Stories
- As a developer, I want `server_version()` so that a "test connection" button can verify URL and token with a single cheap call.
- As a developer, I want a clear "this is not a paperless instance" error so that a wrong URL is reported correctly instead of as a confusing parse or 404 error.
- As an administrator-tool developer, I want `system_status()` so that I can show paperless's health without parsing raw JSON.

---

## Scope

### In Scope
- `server_version()` and `system_status()` on both clients.
- Public `SystemStatus` model (tolerant to extra/missing fields).
- New "not a paperless" error class.
- Docs and tests via the injected transport (#0043).
- Spike: which endpoint is cheapest and reliably returns `X-Version` for an authenticated request; shape of the status response; permission required for status.

### Out of Scope
- Checking for newer paperless releases (remote version endpoint).
- Version-dependent feature switching inside easypaperless.

---

## Acceptance Criteria
- [ ] `server_version()` returns the value of the `X-Version` header (e.g. `"2.18.4"`).
- [ ] `server_version()` sends exactly one request and that request is authenticated.
- [ ] With a refused token (401) it raises the 401 `AuthError` subclass.
- [ ] When the response lacks `X-Version`, it raises the "not a paperless" error and the message says so.
- [ ] A 404 on the version request and a 200 HTML page without `X-Version` both raise the "not a paperless" error (not `NotFoundError`).
- [ ] A transport failure raises the transport `ServerError` subclass (#0046).
- [ ] `system_status()` returns a `SystemStatus` populated from a recorded paperless response; unknown extra fields do not cause errors.
- [ ] `system_status()` with a non-admin token raises the 403 subclass.
- [ ] Sync and async clients behave identically.

---

## Dependencies & Constraints
- Depends on the error classes of #0046 and the transport of #0043.
- **Detecting "not a paperless":** the generic status mapping would raise `NotFoundError` for a foreign server answering `/api/` with 404, before the header is ever checked. `server_version()` needs its own handling so that these cases raise the "not a paperless" error:
  - 404 on the version request,
  - 200 with an HTML page (e.g. a proxy or another web app) and no `X-Version` header,
  - any other successful response without `X-Version`.
  401 and 403 keep raising the `AuthError` subclasses.

---

## Priority
`High`

---

## Additional Notes
- Requester: ThruCapture Backend, Must-item 5 (version check). `system_status()` added to make the server-information area complete.

---

## Implementation Notes (assumptions, unverified)
The live test instance was unreachable when this was implemented (see the 0.7.0 spike findings), so the spike was not run. The only observation: an **anonymous** `GET /api/` on another paperless-ngx instance returned `302` to `schema/view/` without `X-Version`.

- `server_version()` sends an authenticated `GET /api/` and reads `X-Version`. Assumption: paperless-ngx's API version middleware sets `X-Version` on authenticated responses of the API root. The HTTP client follows redirects, so a foreign server's redirect to an HTML page ends as an HTML 200 without the header, which gives `NotPaperlessError`. A 404 is caught and re-raised as `NotPaperlessError` (`status_code=404`, `NotFoundError` as `__cause__`). 401/403 and transport errors keep their #0046 classes.
- `system_status()` reads `GET /api/status/`. The `SystemStatus` shape follows the paperless-ngx 2.x `SystemStatusView` source: `pngx_version` (exposed as `version`; a plain `version` key is accepted too), `server_os`, `install_type`, `storage {total, available}`, `database {type, url, status, error, migration_status {latest_migration, unapplied_migrations}}`, `tasks {redis_url, redis_status, redis_error, celery_status, celery_url, celery_error, index_status, index_last_modified, index_error, classifier_status, classifier_last_trained, classifier_error, sanity_check_status, sanity_check_last_run, sanity_check_error}`. Every field is optional and `extra="ignore"`. The test fixture is modelled on that source; it is not a captured response.
- Assumption: `/api/status/` requires an admin user (403 otherwise), as in the paperless source.
- Still open: verify the authenticated `X-Version` header, the status shape and the status permission against a live instance (spike #0050 / re-run of the 0.7.0 spikes).
