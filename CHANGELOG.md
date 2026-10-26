# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **Injectable HTTP transport** (`PaperlessClient` / `SyncPaperlessClient`, #0043): New keyword-only `transport: httpx.AsyncBaseTransport | None = None` constructor parameter, passed to the internal `httpx.AsyncClient`. Use it with `httpx.MockTransport` for tests without global patching, or with a custom `httpx.AsyncHTTPTransport` (proxy, local address, TLS). Auth header, base URL, timeout, redirects and retries remain controlled by easypaperless. Using `SyncPaperlessClient` from a worker thread while another event loop runs in the main thread is now documented and tested.

### Fixed

- **Configured `timeout` is now applied to regular API requests** (#0043). Requests made without a per-call timeout previously passed `timeout=None` to httpx, which disabled the timeout entirely instead of using the client's configured `timeout` (default `30.0` s). Downloads were not affected.

---

## [0.6.0] - 2026-04-10

### Added

- **`documents.history(document_id)`** (`client.documents` / `sync_client.documents`): Fetches the full audit log for a document from `GET /documents/{id}/history/`. Returns `PagedResult[AuditLogEntry]`; each entry records the `timestamp`, `action` (e.g. `"create"`, `"update"`), `changes` dict, and `actor` (the user who performed the action, or `None` for system events). The `AuditLogEntry` and `AuditLogActor` models are exported from the top-level package.
- **Retry-with-backoff support** (`PaperlessClient` / `SyncPaperlessClient`): Three new constructor parameters enable automatic retries on transient errors: `retry_attempts` (max retries after the first failure; default `0` = disabled), `retry_backoff` (initial sleep in seconds between attempts, doubles on each retry; default `1.0`), and `retry_on` (tuple of exception types that trigger a retry; defaults to `ServerError`, `httpx.TimeoutException`, and `httpx.ConnectError`). When all attempts are exhausted a `RetryExhaustedError` is raised. Alternatively, pass a pre-configured `tenacity.AsyncRetrying` instance via `tenacity_retrying` to let tenacity drive the retry loop instead. `RetryExhaustedError` is exported from the top-level package.

---

## [0.5.1] - 2026-04-04

### Fixed

- **`documents.list()` single-value FK filters now send the correct query parameter keys** (#0040). Four parameters were sending wrong keys that Paperless-ngx silently ignored, returning all documents instead of filtered results:
  - `document_type=<id>` now sends `document_type__id` (was `document_type`)
  - `correspondent=<id>` now sends `correspondent__id` (was `correspondent__id__in` with a scalar)
  - `storage_path=<id>` now sends `storage_path__id` (was `storage_path__id__in` with a scalar)
  - `owner=<id>` now sends `owner__id` (was `owner__id__in` with a scalar)
  - Null-filter paths (`None` → `__isnull=true`) and multi-value `any_*` / `exclude_*` variants are unchanged. The sync client is fixed automatically as it delegates to the async implementation.

---

## [0.5.0] - 2026-03-31

### Added

- **`documents.thumbnail(id)`** (`client.documents` / `sync_client.documents`): Fetches the thumbnail image for a document as raw bytes from `GET /documents/{id}/thumb/`. Raises `NotFoundError` if the document does not exist and `ServerError` if the server returns an HTML page (e.g. an auth redirect) instead of image content.
- **`documents.bulk_download(document_ids, *, content, compression, follow_formatting)`** (`client.documents` / `sync_client.documents`): Downloads multiple documents as a single ZIP archive in one request via `POST /api/documents/bulk_download/`. `content` selects the file variant (`"archive"` *(default)*, `"originals"`, `"both"`); `compression` controls the ZIP algorithm (`"none"` *(default)*, `"deflated"`, `"bzip2"`, `"lzma"`); `follow_formatting` (default `False`) applies the configured paperless-ngx storage-path filename scheme to entries in the archive. Returns raw `bytes`.

---

## [0.4.1] - 2026-03-23

### Fixed

- `documents.download(id, original=True)` now correctly returns the original uploaded file instead of the archived PDF. The previous implementation routed `original=True` to `GET /documents/{id}/download/` and `original=False` to `GET /documents/{id}/archive/`, which no longer matches the current Paperless-ngx API. Both paths now use the single `GET /documents/{id}/download/` endpoint: omitting the query parameter returns the archived PDF (default), and appending `?original=true` returns the original file. Affects async and sync clients equally.

---

## [0.4.0] - 2026-03-20

### Added

- **Users resource** (`client.users` / `sync_client.users`): Full CRUD operations (`list`, `get`, `create`, `update`, `delete`) against the `/api/users/` endpoint. `list()` supports filtering by `username_contains` (case-insensitive substring) and `username_exact` (case-insensitive exact match), and returns `PagedResult[User]`.
- **`User` model** (`easypaperless.models.User`): Pydantic model with all fields from the API response, including `user_permissions` (directly assigned), `inherited_permissions` (read-only effective permissions), and `is_mfa_enabled` (read-only).
- **`PaperlessPermission` type alias** (`easypaperless.PaperlessPermission`): A `Literal[...]` type alias enumerating all 176 known Paperless permission strings. Use with standard `in` checks for type-safe, IDE-assisted permission inspection without relying on raw strings.
- **Trash resource** (`client.trash` / `sync_client.trash`): Manage the Paperless-ngx trash bin via three methods:
  - `list(page, page_size)` — returns `PagedResult[Document]` of all trashed documents.
  - `restore(document_ids)` — recovers the specified documents from the trash back to active status.
  - `empty(document_ids)` — **permanently and irreversibly** deletes the specified documents. A clear warning is included in the method docstring.

---

## [0.3.2] - 2026-03-18

### Fixed

- `documents.notes.list()` (async and sync) no longer crashes with `AttributeError: 'list' object has no attribute 'get'` on real paperless-ngx instances. The `/documents/{id}/notes/` endpoint returns a plain JSON array; the method now wraps it into a synthetic `PagedResult[DocumentNote]` (`count=len(notes)`, `next=None`, `previous=None`, `all=[<ids>] or None`) instead of incorrectly treating it as a paginated dict envelope.

---

## [0.3.1] - 2026-03-17

### Fixed

- `documents.notes.list()` now returns `PagedResult[DocumentNote]` instead of a plain `list`. The method signature, return type, and docstrings are now consistent with every other `list()` method in the library.
- Pagination no longer fails when a paperless-ngx instance is served behind a TLS-terminating reverse proxy that does not forward `X-Forwarded-Proto: https`. Previously, `get_all_pages` and `get_all_pages_paged` would follow `next` URLs verbatim from the API response, causing the proxy to reject plain-HTTP requests on its HTTPS port with a 400 error. Both methods now normalise the scheme of every `next` URL to match the scheme configured in `base_url` before issuing the request.

---

## [0.3.0] - 2026-03-17

### Breaking Changes

- `PaperlessClient` and `SyncPaperlessClient` constructor parameter renamed from `api_key` to `api_token`. Update any call site passing `api_key=` as a keyword argument.
- All `list()` methods now return `PagedResult[T]` instead of `list[T]`. Update call sites to access items via `.results` and the total count via `.count`.

### Added

- `PagedResult[T]` generic Pydantic model exported from `easypaperless`. All `list()` methods across every resource (async and sync) now return this model, providing access to the total item count (`.count`), raw pagination URLs (`.next`, `.previous`), all matching IDs (`.all`), and the result items (`.results`).
- `Unset` type alias and `UNSET` sentinel constant are now exported from the top-level `easypaperless` namespace. Use `UNSET` to signal "not provided" in optional parameters, distinct from explicit `None` (which clears a nullable field). Previously only available as an internal symbol; now fully public and documented.
- Structured logging throughout the library. Every resource method emits an `INFO`-level log record when called; the HTTP layer emits `DEBUG`-level request and response details. All loggers are children of the `easypaperless` logger — attach any standard Python `logging` handler to capture them. Auth tokens are never logged.

### Fixed

- `SyncTagsResource.create()`: `color` and `is_inbox_tag` parameters now correctly default to `UNSET` (was `None`). Previously, omitting these arguments would send `"color": null` and `"is_inbox_tag": null` to the API, silently overriding server-side defaults.
- `None` / `UNSET` semantics corrected across all async resource `create()` and `update()` methods. Parameters that cannot be `None` (e.g. `name`, `match`, `is_insensitive`) now use `UNSET` as their default and exclude `None` from their type. Nullable parameters (e.g. `owner`, `correspondent`) preserve `None` as the "clear this field" value.
- `CustomFieldsResource.update()` now accepts `owner` and `set_permissions` parameters, matching the API capabilities.
- `set_permissions` now supports three-way semantics in all `create()` and `update()` methods: `UNSET` — omit from payload; `None` — overwrite with empty permissions; `SetPermissions(...)` — overwrite with the provided value.

### Changed

- All `Optional[X]` usages in resource method signatures replaced with `X | None` for consistency with the modern Python union syntax.
- Sync resource methods no longer declare an unused `logger` variable. Logging is emitted by the async delegate under the `easypaperless._internal.resources.*` logger hierarchy.

---

## [0.2.1] - 2026-03-15

### Added

- `py.typed` marker file added to the package, making `easypaperless` PEP 561 compliant. Downstream projects running mypy will now receive full type information without needing `--ignore-missing-imports`.

### Fixed

- `Document.created` is now typed as `date | None` instead of `datetime | None`, matching the paperless-ngx v9+ API contract. Parsing documents returned by paperless-ngx v9+ no longer raises a Pydantic `ValidationError` for this field.
  - **Note:** Non-midnight datetime strings (e.g. `"2024-03-15T10:00:00Z"`) passed as `created` will now raise a validation error. If you are on a pre-v9 instance that returns non-midnight datetimes for `created`, pin to `0.2.0`.
  - `Document.created_date` is deprecated by paperless-ngx as of v9 and will be removed in a future API version; use `Document.created` instead.

### Changed

- Sync resource method docstrings (all classes in `_internal/sync_resources/`) now contain full, self-contained `Args`, `Returns`, and `Raises` sections. The previous pattern of deferring to the async counterpart via a cross-reference has been removed.

---

## [0.2.0] - 2026-03-14

### Breaking Changes

- `DocumentsResource.update()`: parameter `date` renamed to `created`; parameter `asn` renamed to `archive_serial_number`.
- `DocumentsResource.upload()`: parameter `asn` renamed to `archive_serial_number`.
- `DocumentsResource.list()`: default `search_mode` changed from `"title_or_text"` to `"title_or_content"`; map key `"title_or_text"` removed in favour of `"title_or_content"`.
- `client.bulk_edit_objects()` is now private (`_bulk_edit_objects`). It was an internal helper and was not intended for direct use.
- `client.documents.bulk_edit()` is now private (`_bulk_edit`). It was an internal helper and was not intended for direct use.
- `create()` methods on `TagsResource`, `CorrespondentsResource`, `DocumentTypesResource`, `StoragePathsResource`, and `CustomFieldsResource`: `is_insensitive` now defaults to `True` (was `False`), matching the paperless-ngx API default.
- The client API has been refactored from flat methods to a resource-based API.
  All resource operations are now accessed through resource objects on the client:

| Before (0.1) | After (0.2) |
|---|---|
| `client.list_documents(...)` | `client.documents.list(...)` |
| `client.get_document(id)` | `client.documents.get(id)` |
| `client.get_document_metadata(id)` | `client.documents.get_metadata(id)` |
| `client.update_document(id, ...)` | `client.documents.update(id, ...)` |
| `client.delete_document(id)` | `client.documents.delete(id)` |
| `client.download_document(id)` | `client.documents.download(id)` |
| `client.upload_document(...)` | `client.documents.upload(...)` |
| `client.get_notes(doc_id)` | `client.documents.notes.list(doc_id)` |
| `client.create_note(...)` | `client.documents.notes.create(...)` |
| `client.delete_note(...)` | `client.documents.notes.delete(...)` |
| `client.bulk_edit(...)` | `client.documents.bulk_edit(...)` |
| `client.bulk_add_tag(...)` | `client.documents.bulk_add_tag(...)` |
| `client.bulk_remove_tag(...)` | `client.documents.bulk_remove_tag(...)` |
| `client.bulk_modify_tags(...)` | `client.documents.bulk_modify_tags(...)` |
| `client.bulk_delete_documents(ids)` | `client.documents.bulk_delete(ids)` |
| `client.bulk_set_correspondent(...)` | `client.documents.bulk_set_correspondent(...)` |
| `client.bulk_set_document_type(...)` | `client.documents.bulk_set_document_type(...)` |
| `client.bulk_set_storage_path(...)` | `client.documents.bulk_set_storage_path(...)` |
| `client.bulk_modify_custom_fields(...)` | `client.documents.bulk_modify_custom_fields(...)` |
| `client.bulk_set_permissions(...)` | `client.documents.bulk_set_permissions(...)` |
| `client.list_tags(...)` | `client.tags.list(...)` |
| `client.get_tag(id)` | `client.tags.get(id)` |
| `client.create_tag(...)` | `client.tags.create(...)` |
| `client.update_tag(id, ...)` | `client.tags.update(id, ...)` |
| `client.delete_tag(id)` | `client.tags.delete(id)` |
| `client.bulk_delete_tags(ids)` | `client.tags.bulk_delete(ids)` |
| `client.bulk_set_permissions_tags(...)` | `client.tags.bulk_set_permissions(...)` |
| `client.list_correspondents(...)` | `client.correspondents.list(...)` |
| `client.get_correspondent(id)` | `client.correspondents.get(id)` |
| `client.create_correspondent(...)` | `client.correspondents.create(...)` |
| `client.update_correspondent(id, ...)` | `client.correspondents.update(id, ...)` |
| `client.delete_correspondent(id)` | `client.correspondents.delete(id)` |
| `client.list_document_types(...)` | `client.document_types.list(...)` |
| `client.get_document_type(id)` | `client.document_types.get(id)` |
| `client.create_document_type(...)` | `client.document_types.create(...)` |
| `client.update_document_type(id, ...)` | `client.document_types.update(id, ...)` |
| `client.delete_document_type(id)` | `client.document_types.delete(id)` |
| `client.list_storage_paths(...)` | `client.storage_paths.list(...)` |
| `client.get_storage_path(id)` | `client.storage_paths.get(id)` |
| `client.create_storage_path(...)` | `client.storage_paths.create(...)` |
| `client.update_storage_path(id, ...)` | `client.storage_paths.update(id, ...)` |
| `client.delete_storage_path(id)` | `client.storage_paths.delete(id)` |
| `client.list_custom_fields(...)` | `client.custom_fields.list(...)` |
| `client.get_custom_field(id)` | `client.custom_fields.get(id)` |
| `client.create_custom_field(...)` | `client.custom_fields.create(...)` |
| `client.update_custom_field(id, ...)` | `client.custom_fields.update(id, ...)` |
| `client.delete_custom_field(id)` | `client.custom_fields.delete(id)` |

The same changes apply to `SyncPaperlessClient`.

### Fixed

- `DocumentsResource.upload()` `created` parameter now also accepts a `date` object (previously only `str`).
- `SyncPaperlessClient` `create()` method signatures now consistently include `UNSET` as the default for optional nullable parameters, matching the async client.

### Removed

- All flat mixin-based methods on `PaperlessClient` and `SyncPaperlessClient`.
- Internal `_internal/mixins/` and `_internal/sync_mixins/` directories.

### Added

- Resource classes in `_internal/resources/` and `_internal/sync_resources/`.
- `client.documents`, `client.tags`, `client.correspondents`, `client.document_types`,
  `client.storage_paths`, `client.custom_fields` resource accessors.
- `client.documents.notes` sub-resource for document notes.

