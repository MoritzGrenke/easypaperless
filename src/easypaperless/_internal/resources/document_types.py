"""Document types resource for PaperlessClient."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, List, cast

from easypaperless._internal.sentinel import UNSET, Unset
from easypaperless.models._base import MatchingAlgorithm
from easypaperless.models.document_types import DocumentType
from easypaperless.models.paged_result import PagedResult
from easypaperless.models.permissions import SetPermissions

if TYPE_CHECKING:
    from easypaperless.client import _ClientCore

logger = logging.getLogger(__name__)


class DocumentTypesResource:
    """Accessor for document types: ``client.document_types``."""

    def __init__(self, core: _ClientCore) -> None:
        self._core = core

    async def list(
        self,
        *,
        ids: List[int] | None = None,
        name_contains: str | None = None,
        name_exact: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        ordering: str | None = None,
        descending: bool = False,
        full_perms: bool = False,
    ) -> PagedResult[DocumentType]:
        """Return document types defined in paperless-ngx.

        When ``page`` is ``None`` (the default), all pages are fetched
        automatically and ``next`` / ``previous`` in the result are always
        ``None``.  When ``page`` is set, only that page is fetched and
        ``next`` / ``previous`` reflect the raw API values.

        Args:
            ids: Return only document types whose ID is in this list.
            name_contains: Case-insensitive substring filter on name.
            name_exact: Case-insensitive exact match on name.
            page: Return only this specific page (1-based).
            page_size: Number of results per page.
            ordering: Field to sort by.
            descending: When ``True``, reverses the sort direction.
            full_perms: When ``True``, paperless-ngx returns the full view/change
                permissions of every object, available as
                ``DocumentType.permissions``; ``user_can_change`` is then ``None``.
                Default: ``False``.

        Returns:
            :class:`~easypaperless.models.paged_result.PagedResult` of
            :class:`~easypaperless.models.document_types.DocumentType` objects.
        """
        logger.info("Listing document types")
        params: dict[str, Any] = {}
        if ids is not None:
            params["id__in"] = ",".join(str(i) for i in ids)
        if name_contains is not None:
            params["name__icontains"] = name_contains
        if name_exact is not None:
            params["name__iexact"] = name_exact
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size
        if ordering is not None:
            params["ordering"] = f"-{ordering}" if descending else ordering
        return cast(
            PagedResult[DocumentType],
            await self._core._list_resource(
                "document_types", DocumentType, params or None, full_perms=full_perms
            ),
        )

    async def get(self, id: int, *, full_perms: bool = False) -> DocumentType:
        """Fetch a single document type by its ID.

        Args:
            id: Numeric document-type ID.
            full_perms: When ``True``, paperless-ngx returns the full view/change
                permissions, available as ``DocumentType.permissions``;
                ``user_can_change`` is then ``None``. Default: ``False``.

        Returns:
            The :class:`~easypaperless.models.document_types.DocumentType` with the given ID.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document type exists with that ID.
        """
        logger.info("Getting document type id=%d full_perms=%s", id, full_perms)
        return cast(
            DocumentType,
            await self._core._get_resource(
                "document_types", id, DocumentType, full_perms=full_perms
            ),
        )

    async def create(
        self,
        *,
        name: str,
        match: str | Unset = UNSET,
        matching_algorithm: MatchingAlgorithm | Unset = UNSET,
        is_insensitive: bool = True,
        owner: int | None | Unset = UNSET,
        set_permissions: SetPermissions | None | Unset = UNSET,
    ) -> DocumentType:
        """Create a new document type.

        Args:
            name: Document-type name. Must be unique.
            match: Auto-matching pattern.
            matching_algorithm: Controls how ``match`` is applied.
                E.g. ``matching_algorithm=MatchingAlgorithm.REGEX`` for
                regular-expression matching.
            is_insensitive: When ``True``, ``match`` is case-insensitive.
                Defaults to ``True``, matching the paperless-ngx API default.
            owner: Numeric user ID to assign as owner.
            set_permissions: Explicit view/change permission sets.
                Pass ``None`` to create with empty permissions.

        Returns:
            The newly created :class:`~easypaperless.models.document_types.DocumentType`.
        """
        logger.info("Creating document type name=%r", name)
        return cast(
            DocumentType,
            await self._core._create_resource(
                "document_types",
                DocumentType,
                owner=owner,
                set_permissions=set_permissions,
                name=name,
                match=match,
                matching_algorithm=matching_algorithm,
                is_insensitive=is_insensitive,
            ),
        )

    async def update(
        self,
        id: int,
        *,
        name: str | Unset = UNSET,
        match: str | Unset = UNSET,
        matching_algorithm: MatchingAlgorithm | Unset = UNSET,
        is_insensitive: bool | Unset = UNSET,
        owner: int | None | Unset = UNSET,
        set_permissions: SetPermissions | None | Unset = UNSET,
    ) -> DocumentType:
        """Partially update a document type (PATCH semantics).

        Args:
            id: Numeric ID of the document type to update.
            name: Document-type name.
            match: Auto-matching pattern.
            matching_algorithm: Controls how ``match`` is applied.
                E.g. ``matching_algorithm=MatchingAlgorithm.REGEX`` for
                regular-expression matching.
            is_insensitive: When ``True``, ``match`` is case-insensitive.
            owner: Numeric user ID to assign as owner.
                Pass ``None`` to clear the owner.
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.
            set_permissions: Explicit view/change permission sets.
                Pass ``None`` to clear all permissions (overwrite with empty).
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.

        Returns:
            The updated :class:`~easypaperless.models.document_types.DocumentType`.
        """
        logger.info("Updating document type id=%d", id)
        return cast(
            DocumentType,
            await self._core._update_resource(
                "document_types",
                id,
                DocumentType,
                name=name,
                match=match,
                matching_algorithm=matching_algorithm,
                is_insensitive=is_insensitive,
                owner=owner,
                set_permissions=set_permissions,
            ),
        )

    async def delete(self, id: int) -> None:
        """Delete a document type.

        Args:
            id: Numeric ID of the document type to delete.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document type exists with that ID.
        """
        logger.info("Deleting document type id=%d", id)
        await self._core._delete_resource("document_types", id)

    async def bulk_delete(self, ids: List[int]) -> None:
        """Permanently delete multiple document types in a single request.

        Args:
            ids: List of document type IDs to delete.
        """
        logger.info("Bulk deleting %d document types", len(ids))
        await self._core._bulk_edit_objects("document_types", ids, "delete")

    async def bulk_set_permissions(
        self,
        ids: List[int],
        *,
        set_permissions: SetPermissions | Unset = UNSET,
        owner: int | None | Unset = UNSET,
        merge: bool = False,
    ) -> None:
        """Set permissions and/or owner on multiple document types.

        Args:
            ids: List of document type IDs to modify.
            set_permissions: Explicit view/change permission sets.
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.
            owner: Numeric user ID to assign as owner.
                Pass ``None`` to clear the owner.
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.
            merge: When ``True``, new permissions are merged with existing ones.
        """
        logger.info("Bulk setting permissions on %d document types", len(ids))
        params: dict[str, Any] = {"merge": merge}
        if not isinstance(set_permissions, Unset):
            params["permissions"] = set_permissions.model_dump()
        if not isinstance(owner, Unset):
            params["owner"] = owner
        await self._core._bulk_edit_objects("document_types", ids, "set_permissions", **params)
