# [BUG] `notes.create()` May Return Another User's Note Under Concurrent Writes

## Summary
`documents.notes.create(document_id, note=...)` returns the *last* element of the note list that paperless-ngx sends back. If another note is added to the same document between paperless saving the caller's note and building the response, the method returns the other note — with the wrong ID — instead of the one the caller just created.

---

## Environment
- **Version / Branch:** easypaperless 0.7.0 (`main`)
- **paperless-ngx:** 2.18.2 (behaviour verified in #0050)
- **Client:** `PaperlessClient` and `SyncPaperlessClient` (sync delegates to async)

---

## Steps to Reproduce
1. Two clients (or two users) add a note to the same document at nearly the same time.
2. Client A calls `documents.notes.create(doc_id, note="from A")`.
3. paperless saves A's note, then B's note is saved before paperless serialises the response to A.
4. paperless answers A's POST with the full note list, oldest first, now ending with B's note.

---

## Expected Behavior
`notes.create()` returns the note that *this* call created (its text and ID), regardless of other notes added concurrently. If the created note cannot be identified unambiguously, the method says so (documented behaviour or a clear error) instead of silently returning a different note.

---

## Actual Behavior
`_internal/resources/notes.py` takes `data[-1]` from the returned list. Under concurrent writes this can be another user's note; the caller then stores a wrong note ID (e.g. for a later `notes.delete()`).

---

## Root Cause Analysis
paperless-ngx's `POST /api/documents/{id}/notes/` does not return the created note on its own, only the document's full note list (verified in #0050: oldest first, the new note is normally last). The client assumes "last element = mine", which only holds without concurrent writers.

Possible directions (to be decided in `/architecture`, not part of this bug report):
- Pick the newest note in the list that matches the caller's text and the token's user, instead of blindly the last element.
- Compare the note IDs before and after (requires an extra request).
- Document the remaining ambiguity (e.g. two identical notes from the same user at the same moment).

---

## Impact
**Low–Medium.** Only affects documents receiving notes from several writers at the same moment. Callers that store the returned note ID (e.g. to delete it later) would act on the wrong note.

---

## Acceptance Criteria
- [ ] With a response list whose last element is another user's note (and the caller's note earlier in the list), `notes.create()` returns the caller's note (correct ID, text and user).
- [ ] With a response list containing only the caller's new note at the end (normal case), behaviour is unchanged.
- [ ] If the created note cannot be identified unambiguously, the documented behaviour applies and is covered by a test.
- [ ] Async and sync clients behave identically.
- [ ] Tests use the injected transport (`FakePaperless`, tests/_transport.py) with response shapes recorded in #0050.

---

## Priority
`Low`

---

## Additional Notes
- Found during #0050 (live verification, "Left open").
- Check in the spike whether the note's `user` field in the response is an ID or a nested object in paperless-ngx 2.18, since identifying "my" note may rely on it.
- Related: #0017 (Document Notes), #0034 (notes response shape).
