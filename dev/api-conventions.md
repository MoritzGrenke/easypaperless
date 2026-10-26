# API Conventions

Developer conventions for the public API of `PaperlessClient` / `SyncPaperlessClient`.
They apply to all new and changed resource methods. When in doubt, copy the `users`
resource (#0035): it is the reference implementation.

---

## Resource-based API

The client exposes one resource object per paperless-ngx endpoint group. Methods are
called as `client.<resource>.<verb>()` (#0018):

```python
await client.tags.list(name_contains="inv")
await client.document_types.get(5)
await client.documents.notes.create(42, note="checked")
client.trash.restore([1, 2])          # SyncPaperlessClient
```

- Resource attribute names are the plural, snake_case form of the endpoint:
  `documents`, `tags`, `correspondents`, `document_types`, `storage_paths`,
  `custom_fields`, `users`, `groups`, `trash`.
- Sub-resources hang off their parent resource: `client.documents.notes`.
- Do not add flat method names such as `list_tags` or `get_tag` on the client.

### Method names

| Operation | Method | Example |
|-----------|--------|---------|
| List (auto-paginating) | `list()` | `client.tags.list()` |
| Fetch one | `get(id)` | `client.tags.get(3)` |
| Create | `create(*, ...)` | `client.tags.create(name="x")` |
| Update (PATCH) | `update(id, *, ...)` | `client.tags.update(3, name="y")` |
| Delete | `delete(id)` | `client.tags.delete(3)` |
| Bulk operation | `bulk_{action}(...)` | `client.tags.bulk_delete([1, 2])`, `client.documents.bulk_add_tag(...)` |
| Endpoint-specific action | plain verb / noun | `documents.download()`, `documents.thumbnail()`, `documents.upload()`, `documents.history()`, `documents.get_metadata()`, `trash.restore()`, `trash.empty()` |

Only implement the verbs the endpoint supports (e.g. `notes` has `list`, `create`,
`delete`; `trash` has `list`, `restore`, `empty`).

---

## Parameter names

### Primary key
Always `id`, never `tag_id`, `document_id`, etc.

```python
async def get(self, id: int) -> Tag: ...
async def update(self, id: int, *, name: str | Unset = UNSET) -> Tag: ...
```

### Sub-resource and multi-object keys
- In a sub-resource the parent key is `{parent_singular}_id`, the sub-resource's own key
  is `{resource_singular}_id`:
  ```python
  async def list(self, document_id: int, ...) -> PagedResult[DocumentNote]: ...
  async def delete(self, document_id: int, note_id: int) -> None: ...
  ```
- Bulk methods on documents and trash take `document_ids: list[int]`; bulk methods on
  the other resources take `ids: list[int]`.

### Keyword-only arguments
Everything except the primary/parent keys is keyword-only (`*`).

### Standard `list()` filter parameters

| Parameter | Meaning |
|-----------|---------|
| `ids` | Filter to specific IDs |
| `name_contains` | Case-insensitive substring match on `name` (`name__icontains`) |
| `name_exact` | Case-insensitive exact match on `name` (`name__iexact`) |
| `page` | Fetch a single page (disables auto-pagination) |
| `page_size` | Results per page |
| `ordering` | Field name to sort by |
| `descending` | Reverse sort direction (default `False`) |

Only include the filters the endpoint supports. Resources whose key field is not `name`
use the same pattern on that field (users: `username_contains`, `username_exact`).

### Document foreign-key filters

| Semantic | Pattern | Example |
|----------|---------|---------|
| Must match exactly one | `{resource_singular}` | `correspondent`, `document_type`, `storage_path` |
| Must match any of | `any_{resource_plural}` | `any_tags`, `any_storage_paths` |
| Must match none of | `exclude_{resource_plural}` | `exclude_correspondents`, `exclude_document_types` |

FK filters accept integer IDs or string names; names are resolved via `NameResolver`.
Known legacy exceptions that keep their singular form for backward compatibility:
`any_correspondent`, `any_document_type`. Use the plural form for anything new.

### Common field names

| Concept | Parameter name | Notes |
|---------|---------------|-------|
| Resource name | `name` | Never `title` for resource labels |
| Document title | `title` | Documents have `title`, not `name` |
| Document creation date | `date` | Mapped to the `created` field in the payload |
| Archive serial number | `archive_serial_number` | No abbreviation |
| Auto-match pattern | `match` | |
| Match algorithm | `matching_algorithm` | `MatchingAlgorithm` enum |
| Case-insensitive match | `is_insensitive` | |
| Owner user ID | `owner` | Nullable: `None` clears the owner |
| Permission set | `set_permissions` | `SetPermissions` model |

---

## `UNSET` vs `None` (#0019, #0028)

`UNSET` (type `Unset`, both exported from `easypaperless`) means "not provided": the
parameter is left out of the request. `None` means an explicit JSON `null`. Signatures
always use `Unset` (never the private `_Unset`) and `X | None`, never `Optional[X]`.

| Context | Type / default | Meaning |
|---------|----------------|---------|
| `create()` optional field where paperless has its own default | `X \| Unset = UNSET` | Omitted from the payload |
| `create()` / `update()` nullable field (e.g. `owner`) | `X \| None \| Unset = UNSET` | `None` sets the field to null |
| `update()` non-nullable field (e.g. `name`, `title`, `match`) | `X \| Unset = UNSET` | `None` is not allowed |
| `list()` filter where `None` just means "no filter" | `X \| None = None` | Filter not applied |
| `list()` filter that can filter *for* null (e.g. `correspondent`, `owner`) | `X \| None \| Unset = UNSET` | `None` filters for "is null" |
| `set_permissions` in `create()` / `update()` | `SetPermissions \| None \| Unset = UNSET` | `None` sends an empty permission set (clears it) |

Resources pass these values unchanged to `_ClientCore._create_resource()` /
`_update_resource()`, which drop `UNSET` values and translate `set_permissions`. Do not
put `set_permissions` conversion logic in resource files. New resources (e.g. `users`)
use `UNSET` defaults for all optional `list()` filters as well.

---

## Return types

- Every `list()` returns `PagedResult[Model]` (#0029). With `page` unset all pages are
  fetched and `next` / `previous` are `None`; with `page` set only that page is
  returned with the raw `next` / `previous` values. Endpoints that return a plain JSON
  array (e.g. notes, #0034) still get wrapped into a `PagedResult` by hand.
- `get`, `create` and `update` return the Pydantic model; `delete` and bulk operations
  return `None` unless the endpoint returns something useful.
- Binary endpoints (`download`, `thumbnail`, `bulk_download`) return `bytes`.

---

## Sync resources (#0016, #0026)

- Every async resource in `_internal/resources/<name>.py` has a sync mirror
  `Sync<Name>Resource` in `_internal/sync_resources/<name>.py` with identical method
  names, parameters, defaults and return types.
- The sync class gets the async resource and the client's `_run` callable in its
  constructor and only delegates (`self._run(self._async_x.method(...))`).
- Sync methods repeat the full docstring of the async method (summary, Args, Returns,
  Raises). Do not write "see the async version".

---

## Logging (#0030)

- Every module with resource or HTTP logic defines `logger = logging.getLogger(__name__)`.
- Every public async resource method logs one `logger.info(...)` line at the start,
  describing the operation and key identifiers (e.g. `"Getting user id=%d"`).
  Sync mirrors do not log; they delegate to the async method.
- Request/response details are logged at `DEBUG` in `_internal/http.py` only.
- The library never configures handlers, levels or formatters (only the `NullHandler`
  in `__init__.py`).

---

## Checklist: adding a new resource

Follow how `users` (#0035) and `trash` (#0036) were added:

1. **Model**: `src/easypaperless/models/<name>.py` (Pydantic v2); export it from
   `models/__init__.py` and from `easypaperless/__init__.py` (import + `__all__`).
2. **Async resource**: `src/easypaperless/_internal/resources/<name>.py` with
   `<Name>Resource(core)`, using the `_ClientCore` helpers (`_list_resource`,
   `_get_resource`, `_create_resource`, `_update_resource`, `_delete_resource`) where
   they fit; `logger.info` per public method; `UNSET` semantics as above.
3. **Sync resource**: `src/easypaperless/_internal/sync_resources/<name>.py` with
   `Sync<Name>Resource(async_resource, run)` and full docstrings.
4. **Client wiring**: class-level annotation and instantiation in `_ClientCore`
   (`client.py`) and in `SyncPaperlessClient` (`sync.py`); add the resource to the
   resource list in both client class docstrings.
5. **`resources.py`**: import both classes and add them to `__all__` (this is what pdoc
   renders).
6. **Tests**: `tests/test_client_<name>.py` covering async and sync; optional
   integration tests under `tests/integration/`.
7. **Docs**: entry in `CHANGELOG.md`; README if user-visible; regenerate pdoc (see
   `CLAUDE.md`).
8. **Issue index**: set the status in `dev/issues/0000-general-index.md`.

---

## 0.7.0 conventions

Binding decisions for the 0.7.0 milestone (#0043–#0052):

- **Tests**: new tests use the injectable `httpx.MockTransport` (`transport=` keyword,
  #0043) and the shared helper `tests/_transport.py` (`FakePaperless`), not respx.
  Existing respx tests stay.
- **No retry for creating requests**: `HttpSession.request()` / `post()` take an internal
  `retry: bool = True`. Requests that create something (`documents.upload`,
  `_create_resource` i.e. every `create()`, `notes.create`) pass `retry=False`, for both
  the built-in retry loop and `tenacity_retrying`. Other POSTs (bulk edits,
  bulk download, task acknowledge, trash actions) keep retrying.
- **Timeout naming**: `poll_interval` / `poll_timeout` for task polling (client defaults,
  `documents.upload(wait=True)`, `tasks.wait()`); `request_timeout` for the HTTP timeout
  of a single request (e.g. the upload POST). Never a bare `timeout` on methods that
  also poll.
