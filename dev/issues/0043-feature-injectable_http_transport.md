# [FEATURE] Injectable HTTP Transport for PaperlessClient and SyncPaperlessClient

## Summary
Allow callers to inject an `httpx` transport into both clients so that requests can be routed through a custom or mock transport (e.g. `httpx.MockTransport`), while easypaperless keeps owning auth, base URL, timeouts and retries. Also make the worker-thread usage of `SyncPaperlessClient` an explicitly documented and tested scenario.

Part of the 0.7.0 "Delivery Target" milestone requested by the ThruCapture Backend (capture-hook, thru-capture-backend #407, #410).

---

## Problem Statement
Today the HTTP session builds its own `httpx.AsyncClient` and offers no hook to replace the transport. Downstream projects that test every integration through an injected `httpx` mock transport (as the ThruCapture Backend does) cannot test easypaperless the same way and have to fall back to global patching (respx). In addition, the ThruCapture Delivery Worker runs `SyncPaperlessClient` in a worker thread while FastAPI/uvicorn runs an event loop in the main thread; this scenario is not documented or tested.

---

## Proposed Solution
- Both `PaperlessClient` and `SyncPaperlessClient` accept an optional `transport` parameter (`httpx.AsyncBaseTransport | None`, default `None`).
- When given, the transport is passed into the `httpx.AsyncClient` that easypaperless builds. Auth header, base URL, timeout, redirect behaviour and retry configuration stay under easypaperless's control.
- When omitted, behaviour is unchanged.
- An `httpx.MockTransport` works through `SyncPaperlessClient` (its handler is invoked on the client's internal loop thread).
- `SyncPaperlessClient` is documented and tested as safe to construct and call from a worker thread while another event loop runs in the main thread; `close()` stops and joins its loop thread.

---

## User Stories
- As a developer of a service built on easypaperless, I want to inject an `httpx.MockTransport` so that my tests exercise easypaperless exactly like my other HTTP integrations, without global patching.
- As a developer, I want to pass a custom transport (e.g. with proxy, local address or custom TLS settings) without losing easypaperless's auth and timeout handling.
- As a developer of a FastAPI service, I want to use `SyncPaperlessClient` from a worker thread so that my synchronous delivery worker can run beside the main event loop.

---

## Scope

### In Scope
- `transport` parameter on `PaperlessClient` and `SyncPaperlessClient` constructors.
- Docstrings and user documentation for the parameter, with a `httpx.MockTransport` testing example.
- Documentation of the worker-thread usage of `SyncPaperlessClient` and of `close()` semantics.
- Tests: async client with `MockTransport`, sync client with `MockTransport`, sync client used from a worker thread while an event loop runs in the main thread, `close()` stops the loop thread.
- A reusable test fixture/helper based on the injected transport, intended to be used by the tests of the other 0.7.0 issues.

### Out of Scope
- Injecting a complete, pre-built `httpx.AsyncClient` (explicitly not preferred by the requester; may be revisited later).
- Migrating existing respx-based tests to the transport.
- Making `SyncPaperlessClient` usable from *inside* a running event loop (e.g. Jupyter) — the existing limitation remains.

---

## Acceptance Criteria
- [ ] `PaperlessClient(url=..., api_token=..., transport=httpx.MockTransport(handler))` routes every request through `handler`.
- [ ] `SyncPaperlessClient(url=..., api_token=..., transport=httpx.MockTransport(handler))` routes every request through `handler`.
- [ ] Requests going through an injected transport carry the `Authorization: Token ...` header, the configured base URL (`.../api/...`) and the configured timeout.
- [ ] Retry configuration (#0041) still applies when a transport is injected.
- [ ] Omitting `transport` results in exactly the previous behaviour (all existing tests pass unchanged).
- [ ] A test constructs and uses `SyncPaperlessClient` from a worker thread while an asyncio event loop is running in the main thread, and the calls succeed.
- [ ] After `SyncPaperlessClient.close()`, its internal loop thread is no longer alive; calling `close()` twice does not raise.
- [ ] The parameter and the worker-thread scenario are documented in docstrings and in the user docs.

---

## Dependencies & Constraints
- Other 0.7.0 issues (#0044–#0050) should write their new tests against the injected transport rather than respx, so that the features are proven the way their first user uses them.
- The transport type must be `httpx.AsyncBaseTransport`, because the sync client runs the async client internally.

---

## Priority
`High`

---

## Additional Notes
- Requester: ThruCapture Backend (capture-hook), milestone M21. Must-item 1 and the two "Should" items of the request.
