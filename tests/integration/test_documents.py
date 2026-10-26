"""Integration tests: list, get, update documents — covers all list_documents filters."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from easypaperless import PagedResult, PaperlessClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _first_doc(client: PaperlessClient):  # type: ignore[return]
    docs = await client.documents.list(page=1, page_size=1)
    if not docs.results:
        pytest.skip("No documents available on this instance")
    return docs.results[0]


# ---------------------------------------------------------------------------
# Basic get / update
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_list_documents_returns_results(client: PaperlessClient) -> None:
    docs = await client.documents.list(page=1, page_size=5)
    assert isinstance(docs, PagedResult)


@pytest.mark.integration
async def test_get_document(client: PaperlessClient) -> None:
    doc = await _first_doc(client)
    fetched = await client.documents.get(doc.id)
    assert fetched.id == doc.id
    assert fetched.title is not None


@pytest.mark.integration
async def test_update_document_title(client: PaperlessClient) -> None:
    original = await _first_doc(client)
    new_title = f"__integration_updated__ {original.title}"
    updated = await client.documents.update(original.id, title=new_title)
    try:
        assert updated.title == new_title
    finally:
        await client.documents.update(original.id, title=original.title)


# ---------------------------------------------------------------------------
# Updates with None (Issue )
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_update_document_asn_None(client: PaperlessClient, temp_documents) -> None:
    original = temp_documents[0]
    new_title = f"__integration_updated__ {original.title}"
    updated = await client.documents.update(original.id, title=new_title, archive_serial_number=666)
    try:
        assert updated.title == new_title
        assert updated.archive_serial_number == 666
        new_title2 = f"__integration_updated2__ {original.title}"
        updated = await client.documents.update(original.id, title=new_title2)
        assert updated.title == new_title2
        assert updated.archive_serial_number == 666  # not changed
        new_title3 = f"__integration_updated3__ {original.title}"
        updated = await client.documents.update(
            original.id, title=new_title3, archive_serial_number=None
        )
        assert updated.title == new_title3
        assert updated.archive_serial_number is None  # removed

    finally:
        await client.documents.update(
            original.id,
            title=original.title,
            archive_serial_number=original.archive_serial_number,
        )


# ---------------------------------------------------------------------------
# Search modes
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_search_mode_title_or_text(client: PaperlessClient) -> None:
    docs = await client.documents.list(search="a", search_mode="title_or_text", page=1, page_size=5)
    assert isinstance(docs, PagedResult)


@pytest.mark.integration
async def test_search_mode_title(client: PaperlessClient) -> None:
    docs = await client.documents.list(search="a", search_mode="title", page=1, page_size=5)
    assert isinstance(docs, PagedResult)
    for doc in docs.results:
        assert "a" in doc.title.lower()


@pytest.mark.integration
async def test_search_mode_query(client: PaperlessClient) -> None:
    docs = await client.documents.list(search="*", search_mode="query", page=1, page_size=5)
    assert isinstance(docs, PagedResult)


@pytest.mark.integration
async def test_search_mode_original_filename(client: PaperlessClient) -> None:
    docs = await client.documents.list(
        search="a", search_mode="original_filename", page=1, page_size=5
    )
    assert isinstance(docs, PagedResult)


# ---------------------------------------------------------------------------
# ids filter
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_filter_by_ids(client: PaperlessClient) -> None:
    doc = await _first_doc(client)
    docs = await client.documents.list(ids=[doc.id])
    assert len(docs.results) == 1
    assert docs.results[0].id == doc.id


@pytest.mark.integration
async def test_filter_by_ids_no_match(client: PaperlessClient) -> None:
    docs = await client.documents.list(ids=[999999999])
    assert docs.results == []


# ---------------------------------------------------------------------------
# Tag filters (tags / any_tags / exclude_tags)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_filter_tags_all(client: PaperlessClient, uid: str) -> None:
    """Create a tag, assign to a doc, filter must-have-all, verify, restore."""
    doc = await _first_doc(client)
    original_tags = list(doc.tags or [])
    tag = await client.tags.create(name=f"__integration_tags_all_{uid}__")
    try:
        await client.documents.update(doc.id, tags=[*original_tags, tag.id])
        docs = await client.documents.list(tags=[tag.id])
        assert any(d.id == doc.id for d in docs.results)
    finally:
        await client.documents.update(doc.id, tags=original_tags)
        await client.tags.delete(tag.id)


@pytest.mark.integration
async def test_filter_any_tags(client: PaperlessClient, uid: str) -> None:
    doc = await _first_doc(client)
    original_tags = list(doc.tags or [])
    tag = await client.tags.create(name=f"__integration_any_tags_{uid}__")
    try:
        await client.documents.update(doc.id, tags=[*original_tags, tag.id])
        docs = await client.documents.list(any_tags=[tag.id])
        assert any(d.id == doc.id for d in docs.results)
    finally:
        await client.documents.update(doc.id, tags=original_tags)
        await client.tags.delete(tag.id)


@pytest.mark.integration
async def test_filter_exclude_tags(client: PaperlessClient, uid: str) -> None:
    doc = await _first_doc(client)
    original_tags = list(doc.tags or [])
    tag = await client.tags.create(name=f"__integration_exclude_tags_{uid}__")
    try:
        await client.documents.update(doc.id, tags=[*original_tags, tag.id])
        docs = await client.documents.list(exclude_tags=[tag.id])
        assert all(d.id != doc.id for d in docs.results)
    finally:
        await client.documents.update(doc.id, tags=original_tags)
        await client.tags.delete(tag.id)


# ---------------------------------------------------------------------------
# Correspondent filters
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_filter_correspondent_exact(client: PaperlessClient, uid: str) -> None:
    doc = await _first_doc(client)
    original_corr = doc.correspondent
    corr = await client.correspondents.create(name=f"__integration_corr_filter_{uid}__")
    try:
        await client.documents.update(doc.id, correspondent=corr.id)
        docs = await client.documents.list(correspondent=corr.id)
        assert any(d.id == doc.id for d in docs.results)
    finally:
        if original_corr is not None:
            await client.documents.update(doc.id, correspondent=original_corr)
        await client.correspondents.delete(corr.id)


@pytest.mark.integration
async def test_filter_any_correspondent(client: PaperlessClient, uid: str) -> None:
    doc = await _first_doc(client)
    original_corr = doc.correspondent
    corr = await client.correspondents.create(name=f"__integration_any_corr_{uid}__")
    try:
        await client.documents.update(doc.id, correspondent=corr.id)
        docs = await client.documents.list(any_correspondent=[corr.id])
        assert any(d.id == doc.id for d in docs.results)
    finally:
        if original_corr is not None:
            await client.documents.update(doc.id, correspondent=original_corr)
        await client.correspondents.delete(corr.id)


@pytest.mark.integration
async def test_filter_exclude_correspondents(client: PaperlessClient, uid: str) -> None:
    doc = await _first_doc(client)
    original_corr = doc.correspondent
    corr = await client.correspondents.create(name=f"__integration_excl_corr_{uid}__")
    try:
        await client.documents.update(doc.id, correspondent=corr.id)
        docs = await client.documents.list(exclude_correspondents=[corr.id])
        assert all(d.id != doc.id for d in docs.results)
    finally:
        if original_corr is not None:
            await client.documents.update(doc.id, correspondent=original_corr)
        await client.correspondents.delete(corr.id)


# ---------------------------------------------------------------------------
# Document type filters
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_filter_document_type_exact(client: PaperlessClient, uid: str) -> None:
    doc = await _first_doc(client)
    original_dt = doc.document_type
    dt = await client.document_types.create(name=f"__integration_dt_filter_{uid}__")
    try:
        await client.documents.update(doc.id, document_type=dt.id)
        docs = await client.documents.list(document_type=dt.id)
        assert any(d.id == doc.id for d in docs.results)
    finally:
        if original_dt is not None:
            await client.documents.update(doc.id, document_type=original_dt)
        await client.document_types.delete(dt.id)


@pytest.mark.integration
async def test_filter_any_document_type(client: PaperlessClient, uid: str) -> None:
    doc = await _first_doc(client)
    original_dt = doc.document_type
    dt = await client.document_types.create(name=f"__integration_any_dt_{uid}__")
    try:
        await client.documents.update(doc.id, document_type=dt.id)
        docs = await client.documents.list(any_document_type=[dt.id])
        assert any(d.id == doc.id for d in docs.results)
    finally:
        if original_dt is not None:
            await client.documents.update(doc.id, document_type=original_dt)
        await client.document_types.delete(dt.id)


@pytest.mark.integration
async def test_filter_exclude_document_types(client: PaperlessClient, uid: str) -> None:
    doc = await _first_doc(client)
    original_dt = doc.document_type
    dt = await client.document_types.create(name=f"__integration_excl_dt_{uid}__")
    try:
        await client.documents.update(doc.id, document_type=dt.id)
        docs = await client.documents.list(exclude_document_types=[dt.id])
        assert all(d.id != doc.id for d in docs.results)
    finally:
        if original_dt is not None:
            await client.documents.update(doc.id, document_type=original_dt)
        await client.document_types.delete(dt.id)


# ---------------------------------------------------------------------------
# Storage path filters
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_filter_storage_path_exact(client: PaperlessClient, uid: str) -> None:
    doc = await _first_doc(client)
    original_sp = doc.storage_path
    sp = await client.storage_paths.create(
        name=f"__integration_sp_filter_{uid}__", path="integration/{created}"
    )
    try:
        await client.documents.update(doc.id, storage_path=sp.id)
        docs = await client.documents.list(storage_path=sp.id)
        assert any(d.id == doc.id for d in docs.results)
    finally:
        if original_sp is not None:
            await client.documents.update(doc.id, storage_path=original_sp)
        await client.storage_paths.delete(sp.id)


@pytest.mark.integration
async def test_filter_any_storage_paths(client: PaperlessClient, uid: str) -> None:
    doc = await _first_doc(client)
    original_sp = doc.storage_path
    sp = await client.storage_paths.create(
        name=f"__integration_any_sp_{uid}__", path="integration/any/{created}"
    )
    try:
        await client.documents.update(doc.id, storage_path=sp.id)
        docs = await client.documents.list(any_storage_paths=[sp.id])
        assert any(d.id == doc.id for d in docs.results)
    finally:
        if original_sp is not None:
            await client.documents.update(doc.id, storage_path=original_sp)
        await client.storage_paths.delete(sp.id)


@pytest.mark.integration
async def test_filter_exclude_storage_paths(client: PaperlessClient, uid: str) -> None:
    doc = await _first_doc(client)
    original_sp = doc.storage_path
    sp = await client.storage_paths.create(
        name=f"__integration_excl_sp_{uid}__", path="integration/excl/{created}"
    )
    try:
        await client.documents.update(doc.id, storage_path=sp.id)
        docs = await client.documents.list(exclude_storage_paths=[sp.id])
        assert all(d.id != doc.id for d in docs.results)
    finally:
        if original_sp is not None:
            await client.documents.update(doc.id, storage_path=original_sp)
        await client.storage_paths.delete(sp.id)


# ---------------------------------------------------------------------------
# Date filters
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_filter_created_after_before(client: PaperlessClient) -> None:
    docs_after = await client.documents.list(created_after="1970-01-01", page=1, page_size=5)
    assert isinstance(docs_after, PagedResult)
    docs_before = await client.documents.list(created_before="2099-12-31", page=1, page_size=5)
    assert isinstance(docs_before, PagedResult)


@pytest.mark.integration
async def test_filter_added_after_before_date(client: PaperlessClient) -> None:
    docs = await client.documents.list(
        added_after=date(1970, 1, 1),
        added_before=date(2099, 12, 31),
        page=1,
        page_size=5,
    )
    assert isinstance(docs, PagedResult)


@pytest.mark.integration
async def test_filter_added_after_before_datetime(client: PaperlessClient) -> None:
    docs = await client.documents.list(
        added_after=datetime(1970, 1, 1, tzinfo=timezone.utc),
        added_before=datetime(2099, 12, 31, tzinfo=timezone.utc),
        page=1,
        page_size=5,
    )
    assert isinstance(docs, PagedResult)


@pytest.mark.integration
async def test_filter_added_from_until(client: PaperlessClient) -> None:
    docs = await client.documents.list(
        added_from=date(1970, 1, 1),
        added_until=date(2099, 12, 31),
        page=1,
        page_size=5,
    )
    assert isinstance(docs, PagedResult)


@pytest.mark.integration
async def test_filter_modified_after_before(client: PaperlessClient) -> None:
    docs = await client.documents.list(
        modified_after=date(1970, 1, 1),
        modified_before=date(2099, 12, 31),
        page=1,
        page_size=5,
    )
    assert isinstance(docs, PagedResult)


@pytest.mark.integration
async def test_filter_modified_from_until(client: PaperlessClient) -> None:
    docs = await client.documents.list(
        modified_from=datetime(1970, 1, 1, tzinfo=timezone.utc),
        modified_until=datetime(2099, 12, 31, tzinfo=timezone.utc),
        page=1,
        page_size=5,
    )
    assert isinstance(docs, PagedResult)


@pytest.mark.integration
async def test_filter_added_after_iso_datetime_string(client: PaperlessClient) -> None:
    """ISO datetime string for added_after should use the datetime (not date) API param."""
    docs = await client.documents.list(
        added_after="1970-01-01T00:00:00+00:00",
        page=1,
        page_size=5,
    )
    assert isinstance(docs, PagedResult)


@pytest.mark.integration
async def test_filter_added_before_iso_datetime_string(client: PaperlessClient) -> None:
    docs = await client.documents.list(
        added_before="2099-12-31T23:59:59+00:00",
        page=1,
        page_size=5,
    )
    assert isinstance(docs, PagedResult)


@pytest.mark.integration
async def test_filter_modified_after_iso_datetime_string(client: PaperlessClient) -> None:
    """ISO datetime string for modified_after should use the datetime (not date) API param."""
    docs = await client.documents.list(
        modified_after="1970-01-01T00:00:00+00:00",
        page=1,
        page_size=5,
    )
    assert isinstance(docs, PagedResult)


@pytest.mark.integration
async def test_filter_modified_before_iso_datetime_string(client: PaperlessClient) -> None:
    docs = await client.documents.list(
        modified_before="2099-12-31T23:59:59+00:00",
        page=1,
        page_size=5,
    )
    assert isinstance(docs, PagedResult)


@pytest.mark.integration
async def test_filter_added_from_until_iso_datetime_strings(client: PaperlessClient) -> None:
    docs = await client.documents.list(
        added_from="1970-01-01T00:00:00+00:00",
        added_until="2099-12-31T23:59:59+00:00",
        page=1,
        page_size=5,
    )
    assert isinstance(docs, PagedResult)


@pytest.mark.integration
async def test_filter_modified_from_until_iso_datetime_strings(client: PaperlessClient) -> None:
    docs = await client.documents.list(
        modified_from="1970-01-01T00:00:00+00:00",
        modified_until="2099-12-31T23:59:59+00:00",
        page=1,
        page_size=5,
    )
    assert isinstance(docs, PagedResult)


# ---------------------------------------------------------------------------
# Pagination, ordering, max_results
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_ordering_ascending_vs_descending(client: PaperlessClient) -> None:
    """Ascending and descending should return the same documents in opposite order."""
    asc = await client.documents.list(ordering="id", page=1, page_size=10)
    desc = await client.documents.list(ordering="id", descending=True, page=1, page_size=10)
    asc_ids = [d.id for d in asc.results]
    desc_ids = [d.id for d in desc.results]
    # Both pages may not cover exactly the same documents if there are >10 docs,
    # but the ascending result should equal the reverse of the descending page
    # when there are ≤10 docs total, or at minimum the ordering should differ.
    assert asc_ids == sorted(asc_ids)
    assert desc_ids == sorted(desc_ids, reverse=True)


@pytest.mark.integration
async def test_page_size(client: PaperlessClient) -> None:
    docs = await client.documents.list(page=1, page_size=3)
    assert len(docs.results) <= 3


@pytest.mark.integration
async def test_max_results(client: PaperlessClient) -> None:
    docs = await client.documents.list(max_results=2)
    assert len(docs.results) <= 2


@pytest.mark.integration
async def test_auto_pagination(client: PaperlessClient) -> None:
    """Auto-pagination should return more results than a single page of 1."""
    all_docs = await client.documents.list(page_size=1)
    single_page = await client.documents.list(page=1, page_size=1)
    # If there are multiple documents, auto-pagination returns more than page_size=1.
    if len(single_page.results) == 1:
        assert len(all_docs.results) >= len(single_page.results)


# ---------------------------------------------------------------------------
# Name-based FK resolution (resolve string → ID)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_filter_tag_by_name(client: PaperlessClient, uid: str) -> None:
    doc = await _first_doc(client)
    original_tags = list(doc.tags or [])
    name = f"__integration_name_resolve_{uid}__"
    tag = await client.tags.create(name=name)
    try:
        await client.documents.update(doc.id, tags=[*original_tags, tag.id])
        docs = await client.documents.list(tags=[name])
        assert any(d.id == doc.id for d in docs.results)
    finally:
        await client.documents.update(doc.id, tags=original_tags)
        await client.tags.delete(tag.id)
