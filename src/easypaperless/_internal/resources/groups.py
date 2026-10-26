"""Groups resource for PaperlessClient."""

from __future__ import annotations

import builtins
import logging
from typing import TYPE_CHECKING, Any, cast

from easypaperless._internal.sentinel import UNSET, Unset
from easypaperless.models.groups import Group
from easypaperless.models.paged_result import PagedResult

if TYPE_CHECKING:
    from easypaperless.client import _ClientCore

logger = logging.getLogger(__name__)


class GroupsResource:
    """Accessor for groups: ``client.groups``."""

    def __init__(self, core: _ClientCore) -> None:
        self._core = core

    async def list(
        self,
        *,
        name_contains: str | Unset = UNSET,
        name_exact: str | Unset = UNSET,
        ordering: str | Unset = UNSET,
        page: int | Unset = UNSET,
        page_size: int | Unset = UNSET,
    ) -> PagedResult[Group]:
        """Return groups defined in paperless-ngx.

        When ``page`` is ``UNSET`` (the default), all pages are fetched
        automatically and ``next`` / ``previous`` in the result are always
        ``None``.  When ``page`` is set, only that page is fetched and
        ``next`` / ``previous`` reflect the raw API values.

        Args:
            name_contains: Case-insensitive substring filter on the group name.
            name_exact: Case-insensitive exact match on the group name.
            ordering: Field to sort by.
            page: Return only this specific page (1-based).
            page_size: Number of results per page.

        Returns:
            :class:`~easypaperless.models.paged_result.PagedResult` of
            :class:`~easypaperless.models.groups.Group` objects.
        """
        logger.info("Listing groups")
        params: dict[str, Any] = {}
        if not isinstance(name_contains, Unset):
            params["name__icontains"] = name_contains
        if not isinstance(name_exact, Unset):
            params["name__iexact"] = name_exact
        if not isinstance(ordering, Unset):
            params["ordering"] = ordering
        if not isinstance(page, Unset):
            params["page"] = page
        if not isinstance(page_size, Unset):
            params["page_size"] = page_size
        return cast(
            PagedResult[Group],
            await self._core._list_resource("groups", Group, params or None),
        )

    async def get(self, id: int) -> Group:
        """Fetch a single group by its ID.

        Args:
            id: Numeric group ID.

        Returns:
            The :class:`~easypaperless.models.groups.Group` with the given ID.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no group exists with
                that ID.
        """
        logger.info("Getting group id=%d", id)
        return cast(Group, await self._core._get_resource("groups", id, Group))

    async def create(
        self,
        *,
        name: str,
        permissions: builtins.list[str] | Unset = UNSET,
    ) -> Group:
        """Create a new group.

        Args:
            name: Group name. Must be unique.
            permissions: Permission codename strings to grant the group
                (e.g. ``["documents.view_document"]``). See
                :data:`~easypaperless.PaperlessPermission`. Omitted from the
                request when not provided, so the group starts without
                permissions.

        Returns:
            The newly created :class:`~easypaperless.models.groups.Group`.
        """
        logger.info("Creating group name=%r", name)
        return cast(
            Group,
            await self._core._create_resource(
                "groups",
                Group,
                name=name,
                permissions=permissions,
            ),
        )

    async def update(
        self,
        id: int,
        *,
        name: str | Unset = UNSET,
        permissions: builtins.list[str] | Unset = UNSET,
    ) -> Group:
        """Partially update a group (PATCH semantics).

        Only fields with a non-:data:`~easypaperless.UNSET` value are included
        in the request body.  Omit a parameter (or pass
        :data:`~easypaperless.UNSET`) to leave it unchanged.

        Args:
            id: Numeric ID of the group to update.
            name: New group name.
            permissions: Replacement list of permission codename strings.
                Pass ``[]`` to remove all permissions.

        Returns:
            The updated :class:`~easypaperless.models.groups.Group`.
        """
        logger.info("Updating group id=%d", id)
        return cast(
            Group,
            await self._core._update_resource(
                "groups",
                id,
                Group,
                name=name,
                permissions=permissions,
            ),
        )

    async def delete(self, id: int) -> None:
        """Delete a group.

        Args:
            id: Numeric ID of the group to delete.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no group exists with
                that ID.
        """
        logger.info("Deleting group id=%d", id)
        await self._core._delete_resource("groups", id)
