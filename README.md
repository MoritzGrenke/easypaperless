# easypaperless 

[![PyPI version](https://img.shields.io/pypi/v/easypaperless.svg)](https://pypi.org/project/easypaperless/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

<div style="border: 2px solid #f39c12; padding: 12px; border-radius: 6px;">

**⚠️ Alpha Release**
This project is under active development. Breaking changes might occur, but will be documented in the changelog.
</div>
<br />


**easypaperless** is a high-level easy-to-use Python API wrapper for [Paperless-ngx](https://github.com/paperless-ngx/paperless-ngx). 

Unlike other wrappers that simply mirror REST endpoints, **easypaperless** is designed for humans. It provides a true abstraction layer, allowing you to interact with your document management system using intuitive Python methods and objects. You don't need to understand the underlying REST API to be productive.



---

## ✨ Key Features

* **True Abstraction:** Focus on your logic, not on HTTP methods or JSON payloads.
* **Developer Experience (DX):** Full Type Hinting support. Your IDE (VS Code, PyCharm, etc.) will provide perfect autocompletion and documentation as you type.
* **Extensive Coverage:** Currently covers a lot of essential workflows from document management to complex bulk operations.
* **Async-First with Sync Support:** Built on top of httpx, easypaperless is fully asynchronous by default for high-performance applications. But it also offers a synchronous wrapper for a classic blocking workflow.
* **Built-in Bulk Tools:** Easily manage hundreds of tags, correspondents, or documents with single-method calls.
* **Structured Logging:** The library emits structured log records under the `easypaperless` logger hierarchy. Attach any standard Python logging handler to capture API calls, responses, and errors.
* **Intuitive Error Hierarchy:** easypaperless provides descriptive, custom exceptions that tell you exactly what went wrong.

---

## 📋 Requirements

* Python: 3.11 or higher
* Paperless-ngx: 2.18 or higher (only tested with 2.18 so far)

### Core Dependencies: 

* httpx>=0.27 
* Pydantic>=2.0 

---

## 🚀 Installation

Install the package via pip:

```bash

pip install easypaperless

```

---

## 🛠 Quickstart

Get up and running in seconds. No API deep-dive required.

Create a API Authentification token in your paperless-ngx user profile and replace "YOUR_TOKEN" in following code examples by your actual token. Replace url with your actual url. Consider to create a dedicated paperless-ngx user for the api usage and limit the permissions to your needs.

### async Client

``` Python

import asyncio
from easypaperless import PaperlessClient

async def main():

    # create a paperless client
    # we encourage you to use .env files to store your credentials
    url = "http://localhost:8000"
    api_token = "YOUR_TOKEN"
    async with PaperlessClient(url=url, api_token=api_token) as client:
        # List documents — full-text search across title and OCR content, return the last 3 docs
        # list() returns a PagedResult; use .results for the items and .count for the total
        docs = await client.documents.list(
            search="test", max_results=3, ordering="added", descending=True
        )
        print(f"Total matching: {docs.count}")
        for doc in docs.results:
            print(f"Id: {doc.id} \nTitle: {doc.title} \nadded: {doc.added}\n")

        # Fetch a single document
        doc = await client.documents.get(id=1)
        print(doc.title, doc.created)

        # check if a "API_edited" tag already exists - otherwise create it.
        tags = await client.tags.list(name_exact="API_edited")
        if not tags.results:
            await client.tags.create(name="API_edited", color="#40bfb7")

        # Update metadata — string names are resolved to IDs automatically
        await client.documents.update(id=1, tags=["API_edited"])

        # Upload and wait for processing to complete
        # doc = await client.documents.upload("path/scan.pdf", title="your title here", wait=True)
        # print("Processed:", doc.id)


asyncio.run(main())

```

### sync Client

``` Python

from easypaperless import SyncPaperlessClient

# same example with the sync client:
# we encourage you to use .env files to store your credentials
url = "http://localhost:8000"
api_token = "YOUR_TOKEN"
with SyncPaperlessClient(url=url, api_token=api_token) as client:
    # List documents — full-text search across title and OCR content, return the last 3 docs
    # list() returns a PagedResult; use .results for the items and .count for the total
    docs = client.documents.list(search="test", max_results=3, ordering="added", descending=True)
    print(f"Total matching: {docs.count}")
    for doc in docs.results:
        print(f"Id: {doc.id} \nTitle: {doc.title} \nadded: {doc.added}\n")

    # Fetch a single document
    doc1 = client.documents.get(id=1)
    print(doc1.title, doc1.created)

    # check if a "API_edited" tag already exists - otherwise create it.
    tags = client.tags.list(name_exact="API_edited")
    if not tags.results:
        client.tags.create(name="API_edited", color="#40bfb7")

    # Update metadata — string names are resolved to IDs automatically
    doc_after_update = client.documents.update(id=1, tags=["API_edited"])
    print(doc_after_update.title, doc_after_update.created, doc_after_update.tags)

```

`SyncPaperlessClient` runs its own private event loop thread, so it can be used from a worker thread while another event loop (e.g. FastAPI/uvicorn) runs in the main thread. `close()` (or leaving the `with` block) stops and joins that thread and is safe to call twice. Do not call it directly from inside a running event loop (e.g. Jupyter) — use `PaperlessClient` there.

### Testing with an injected transport

Both clients accept a `transport` keyword (`httpx.AsyncBaseTransport`). It is handed to the internal `httpx.AsyncClient`, while easypaperless still controls the auth header, base URL, timeout and retries. This lets you test code that uses easypaperless with an `httpx.MockTransport`, without global patching:

``` Python
import httpx
from easypaperless import SyncPaperlessClient

def handler(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/api/tags/"
    return httpx.Response(200, json={"count": 0, "next": None, "previous": None, "results": []})

with SyncPaperlessClient(url="http://paperless.test", api_token="t",
                         transport=httpx.MockTransport(handler)) as client:
    assert client.tags.list().count == 0
```

With `SyncPaperlessClient` the handler runs on the client's internal loop thread. A custom `httpx.AsyncHTTPTransport(proxy=..., local_address=..., verify=...)` works the same way.

## ⚠️ Error Handling

Every exception raised by easypaperless derives from `PaperlessError` and is importable from `easypaperless`. Each one has a non-empty message and a `status_code` attribute (the HTTP status, or `None` when no response was received).

```
PaperlessError
├── AuthError
│   ├── AuthenticationError     401 – token missing or invalid
│   └── PermissionDeniedError   403 – token valid, permission missing
├── BadRequestError             400 – .field_errors, .non_field_errors
├── NotFoundError               404, or a name that could not be resolved
├── ValidationError             422
├── ServerError
│   ├── ServerResponseError     5xx response (status_code set)
│   └── TransportError          no response: connection refused, DNS, TLS, protocol error
│       └── TransportTimeoutError   connect/read/write/pool timeout
├── UploadError                 document processing task failed
├── TaskTimeoutError            upload polling exceeded poll_timeout
└── RetryExhaustedError         all retry attempts failed (last error chained as __cause__)
```

| Exception | Raised when | `status_code` |
|-----------|-------------|---------------|
| `AuthenticationError` | HTTP 401: the API token is missing or invalid | `401` |
| `PermissionDeniedError` | HTTP 403: the token is valid but lacks a permission; the message is paperless's `detail` text verbatim | `403` |
| `BadRequestError` | HTTP 400: paperless rejected the request data. `field_errors` maps field name → list of messages, `non_field_errors` holds the rest | `400` |
| `NotFoundError` | HTTP 404, or a tag/correspondent/... name could not be resolved | `404` / `None` |
| `ValidationError` | HTTP 422 | `422` |
| `ServerResponseError` | HTTP 5xx, or a download returned an HTML page instead of the file | the HTTP status |
| `TransportError` | paperless could not be reached: connection refused, DNS or TLS failure, broken connection. The original `httpx` exception is chained as `__cause__` | `None` |
| `TransportTimeoutError` | the request timed out (the operation may still have completed on the server) | `None` |
| `UploadError` | the processing task of an upload reports `FAILURE`/`REVOKED`, or succeeds without a document ID | `None` |
| `TaskTimeoutError` | `upload(wait=True)` did not finish within `poll_timeout` | `None` |
| `RetryExhaustedError` | all `retry_attempts` failed; `.attempts`, `.url`, last error as `__cause__` | `None` |
| `PaperlessError` | any other HTTP error status (e.g. 409, 429) | the HTTP status |

The classes are subclasses of the earlier ones, so existing `except AuthError` / `except ServerError` clauses keep working. Catching a more specific class lets you react differently:

```python
from easypaperless import (
    BadRequestError, PermissionDeniedError, AuthenticationError,
    ServerResponseError, TransportError,
)

try:
    await client.tags.create(name="")
except BadRequestError as err:
    print(err.field_errors)          # {"name": ["This field may not be blank."]}
except PermissionDeniedError as err:
    print(f"grant permission: {err}")
except AuthenticationError:
    print("check your API token")
except TransportError:
    print("paperless unreachable — retry later")
except ServerResponseError as err:
    print(f"paperless returned {err.status_code}")
```

The default `retry_on` contains `ServerError` and therefore retries both transport errors and 5xx responses; pass `retry_on=(TransportError,)` to retry only when paperless was unreachable.

## 📖 Functional Overview

All functionality is accessed through resource attributes on the client (e.g. `client.documents`, `client.tags`). Both `PaperlessClient` (async) and `SyncPaperlessClient` (sync) expose the same resources and methods.

All `list()` methods return a `PagedResult[T]` containing `.results` (the items), `.count` (total matches from the server), `.next` / `.previous` (raw page URLs when requesting a single page), and `.all` (all matching IDs when provided by the API).

The `UNSET` sentinel (importable from `easypaperless`) allows you to distinguish "not provided" from explicit `None` in optional parameters. Omitting a parameter or passing `UNSET` leaves the field unchanged; passing `None` explicitly clears a nullable field.

### Client

* **PaperlessClient / SyncPaperlessClient** Token-based authentication. Configurable timeout, poll interval, and poll timeout for slow instances. Optional built-in retry-with-exponential-backoff for transient errors (`retry_attempts`, `retry_backoff`, `retry_on`); also accepts a pre-configured `tenacity.AsyncRetrying` instance for advanced retry strategies. Optional injectable `httpx` transport (`transport=`) for mock-based testing or custom proxy/TLS settings.

### `client.documents` — Documents

* **list()** Search and filter documents by title, content, tags, dates, correspondent, and more. The workhorse of the wrapper.
* **get()** Fetch a single document's data; optionally includes extended file metadata.
* **get_metadata()** Retrieve file-level technical metadata (checksums, sizes, MIME types) for a specific document.
* **update()** Partially update document fields like title, tags, or dates using PATCH semantics. Supports `UNSET` to distinguish "not provided" from explicit `None`.
* **delete()** Permanently remove a document from your Paperless-ngx instance.
* **download()** Download the binary content of a document — either the archived PDF or the original file.
* **thumbnail()** Download the thumbnail image of a document as raw bytes.
* **upload()** Upload a new file to Paperless-ngx and optionally wait for the processing task to complete.
* **history()** Retrieve the full audit log for a document as a `PagedResult[AuditLogEntry]`, showing who changed what and when.

#### Document Bulk Operations

* **bulk_add_tag()** Add a single tag to a collection of documents in one request.
* **bulk_remove_tag()** Strip a specific tag from multiple documents simultaneously.
* **bulk_modify_tags()** Atomically add and remove multiple tags across a set of documents.
* **bulk_delete()** Permanently delete a list of documents in a single batch.
* **bulk_set_correspondent()** Assign or clear the correspondent for multiple documents at once.
* **bulk_set_document_type()** Change the document type for a group of documents in one go.
* **bulk_set_storage_path()** Update the storage path for multiple documents simultaneously.
* **bulk_modify_custom_fields()** Batch update or remove custom field values across multiple documents.
* **bulk_set_permissions()** Manage ownership and access permissions for a list of documents.
* **bulk_download()** Download multiple documents as a single ZIP archive. Supports choosing the file variant (`archive`, `originals`, or `both`), compression algorithm, and optional filename formatting.

### `client.documents.notes` — Document Notes

* **list()** Retrieve all text notes attached to a specific document.
* **create()** Add a new text note to an existing document.
* **delete()** Remove a specific note from a document.

### `client.tags` — Tags

* **list() / get() / create() / update() / delete()** Full CRUD for document tags, supporting colors and matching algorithms.
* **bulk_delete()** Batch delete tags.
* **bulk_set_permissions()** Batch update access control and ownership for tags.

### `client.correspondents` — Correspondents

* **list() / get() / create() / update() / delete()** Full CRUD for document authors, senders, or recipients.
* **bulk_delete()** Batch delete correspondents.
* **bulk_set_permissions()** Batch update access control and ownership for correspondents.

### `client.document_types` — Document Types

* **list() / get() / create() / update() / delete()** Full CRUD for categories like "Invoice," "Letter," or "Contract."
* **bulk_delete()** Batch delete document types.
* **bulk_set_permissions()** Batch update access control and ownership for document types.

### `client.storage_paths` — Storage Paths

* **list() / get() / create() / update() / delete()** Full CRUD for the physical directory structure where files are stored.
* **bulk_delete()** Batch delete storage paths.
* **bulk_set_permissions()** Batch update access control and ownership for storage paths.

### `client.custom_fields` — Custom Fields

* **list() / get() / create() / update() / delete()** Full CRUD for user-defined metadata fields for advanced document tracking.

### `client.users` — Users

* **list() / get() / create() / update() / delete()** Full CRUD for Paperless-ngx user accounts. Supports filtering by username and paginated results.
* Use `PaperlessPermission` (a typed `Literal` alias) for type-safe permission checks against `user.user_permissions` or `user.inherited_permissions`.

### `client.trash` — Trash

* **list()** List all documents currently in the Paperless-ngx trash bin. Returns `PagedResult[Document]`.
* **restore()** Recover one or more trashed documents back to active status.
* **empty()** Permanently and irreversibly delete trashed documents. **This operation cannot be undone.**


## 📚 Documentation

See the 👉 [Full API Reference (pdoc)](https://moritzgrenke.github.io/easypaperless/)

## 🤝 Contributing

Contributions are welcome! If you find a bug or have a feature request, please open an issue. 

## 📄 License

This project is licensed under the MIT License.


