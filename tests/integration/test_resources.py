"""Integration tests: CRUD for tags, correspondents, document_types, storage_paths, custom_fields."""  # noqa: E501

from __future__ import annotations

from typing import Any

import pytest

from easypaperless import PaperlessClient, PermissionSet, SetPermissions


@pytest.mark.integration
async def test_tag_crud(client: PaperlessClient, uid: str) -> None:
    tag = await client.tags.create(name=f"__integration_tag_{uid}__")
    try:
        assert tag.name == f"__integration_tag_{uid}__"
        fetched = await client.tags.get(tag.id)
        assert fetched.id == tag.id
        updated = await client.tags.update(tag.id, name=f"__integration_tag_{uid}_updated__")
        assert updated.name == f"__integration_tag_{uid}_updated__"
        tags = await client.tags.list()
        ids = [t.id for t in tags.results]
        assert tag.id in ids
    finally:
        await client.tags.delete(tag.id)


@pytest.mark.integration
async def test_correspondent_crud(client: PaperlessClient, uid: str) -> None:
    corr = await client.correspondents.create(name=f"__integration_correspondent_{uid}__")
    try:
        assert corr.name == f"__integration_correspondent_{uid}__"
        fetched = await client.correspondents.get(corr.id)
        assert fetched.id == corr.id
        updated = await client.correspondents.update(
            corr.id, name=f"__integration_correspondent_{uid}_updated__"
        )
        assert updated.name == f"__integration_correspondent_{uid}_updated__"
        items = await client.correspondents.list()
        ids = [c.id for c in items.results]
        assert corr.id in ids
    finally:
        await client.correspondents.delete(corr.id)


@pytest.mark.integration
async def test_document_type_crud(client: PaperlessClient, uid: str) -> None:
    dt = await client.document_types.create(name=f"__integration_doctype_{uid}__")
    try:
        assert dt.name == f"__integration_doctype_{uid}__"
        fetched = await client.document_types.get(dt.id)
        assert fetched.id == dt.id
        updated = await client.document_types.update(
            dt.id, name=f"__integration_doctype_{uid}_updated__"
        )
        assert updated.name == f"__integration_doctype_{uid}_updated__"
        items = await client.document_types.list()
        ids = [d.id for d in items.results]
        assert dt.id in ids
    finally:
        await client.document_types.delete(dt.id)


@pytest.mark.integration
async def test_storage_path_crud(client: PaperlessClient, uid: str) -> None:
    sp = await client.storage_paths.create(
        name=f"__integration_storagepath_{uid}__", path="integration/{created}"
    )
    try:
        assert sp.name == f"__integration_storagepath_{uid}__"
        fetched = await client.storage_paths.get(sp.id)
        assert fetched.id == sp.id
        updated = await client.storage_paths.update(
            sp.id, name=f"__integration_storagepath_{uid}_updated__"
        )
        assert updated.name == f"__integration_storagepath_{uid}_updated__"
        items = await client.storage_paths.list()
        ids = [s.id for s in items.results]
        assert sp.id in ids
    finally:
        await client.storage_paths.delete(sp.id)


@pytest.mark.integration
async def test_custom_field_crud(client: PaperlessClient, uid: str) -> None:
    cf = await client.custom_fields.create(name=f"__integration_field_{uid}__", data_type="string")
    try:
        assert cf.name == f"__integration_field_{uid}__"
        fetched = await client.custom_fields.get(cf.id)
        assert fetched.id == cf.id
        updated = await client.custom_fields.update(
            cf.id, name=f"__integration_field_{uid}_updated__"
        )
        assert updated.name == f"__integration_field_{uid}_updated__"
        items = await client.custom_fields.list()
        ids = [f.id for f in items.results]
        assert cf.id in ids
    finally:
        await client.custom_fields.delete(cf.id)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("resource", "extra"),
    [
        ("tags", {}),
        ("correspondents", {}),
        ("document_types", {}),
        ("storage_paths", {"path": "integration/{created}"}),
    ],
)
async def test_full_perms_reads_back_permissions(
    client: PaperlessClient, uid: str, resource: str, extra: dict[str, Any]
) -> None:
    """#0053: permissions set on create are returned by get/list with full_perms=True."""
    group = await client.groups.create(name=f"__integration_perms_{resource}_{uid}")
    res = getattr(client, resource)
    perms = SetPermissions(
        view=PermissionSet(groups=[group.id]), change=PermissionSet(groups=[group.id])
    )
    obj = await res.create(name=f"__integration_perms_{uid}__", set_permissions=perms, **extra)
    try:
        assert (await res.get(obj.id, full_perms=True)).permissions == perms
        listed = await res.list(name_exact=obj.name, full_perms=True)
        assert [o.permissions for o in listed.results] == [perms]
        plain = await res.get(obj.id)
        assert plain.permissions is None
        assert plain.user_can_change is True
    finally:
        await res.delete(obj.id)
        await client.groups.delete(group.id)
