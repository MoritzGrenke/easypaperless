"""Sync tags resource."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, cast

from easypaperless._internal.sentinel import UNSET, Unset
from easypaperless.models._base import MatchingAlgorithm
from easypaperless.models.paged_result import PagedResult
from easypaperless.models.permissions import SetPermissions
from easypaperless.models.tags import Tag

if TYPE_CHECKING:
    from easypaperless._internal.resources.tags import TagsResource


class SyncTagsResource:
    """Sync accessor for tags: ``client.tags``."""

    def __init__(self, async_tags: TagsResource, run: Any) -> None:
        self._async_tags = async_tags
        self._run = run

    def list(
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
    ) -> PagedResult[Tag]:
        """Return tags defined in paperless-ngx.

        When ``page`` is ``None`` (the default), all pages are fetched
        automatically and ``next`` / ``previous`` in the result are always
        ``None``.  When ``page`` is set, only that page is fetched and
        ``next`` / ``previous`` reflect the raw API values.

        Args:
            ids: Return only tags whose ID is in this list.
            name_contains: Case-insensitive substring filter on tag name.
            name_exact: Case-insensitive exact match on tag name.
            page: Return only this specific page (1-based).
            page_size: Number of results per page.
            ordering: Field to sort by.
            descending: When ``True``, reverses the sort direction.
            full_perms: When ``True``, paperless-ngx returns the full view/change
                permissions of every object, available as
                ``Tag.permissions``; ``user_can_change`` is then ``None``.
                Default: ``False``.

        Returns:
            :class:`~easypaperless.models.paged_result.PagedResult` of
            :class:`~easypaperless.models.tags.Tag` objects.
        """
        return cast(
            PagedResult[Tag],
            self._run(
                self._async_tags.list(
                    ids=ids,
                    name_contains=name_contains,
                    name_exact=name_exact,
                    page=page,
                    page_size=page_size,
                    ordering=ordering,
                    descending=descending,
                    full_perms=full_perms,
                )
            ),
        )

    def get(self, id: int, *, full_perms: bool = False) -> Tag:
        """Fetch a single tag by its ID.

        Args:
            id: Numeric tag ID.
            full_perms: When ``True``, paperless-ngx returns the full view/change
                permissions, available as ``Tag.permissions``;
                ``user_can_change`` is then ``None``. Default: ``False``.

        Returns:
            The :class:`~easypaperless.models.tags.Tag` with the given ID.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no tag exists with
                that ID.
        """
        return cast(Tag, self._run(self._async_tags.get(id, full_perms=full_perms)))

    def create(
        self,
        *,
        name: str,
        color: str | Unset = UNSET,
        is_inbox_tag: bool | Unset = UNSET,
        match: str | Unset = UNSET,
        matching_algorithm: MatchingAlgorithm | Unset = UNSET,
        is_insensitive: bool = True,
        parent: int | None | Unset = UNSET,
        owner: int | None | Unset = UNSET,
        set_permissions: SetPermissions | None | Unset = UNSET,
    ) -> Tag:
        """Create a new tag.

        Args:
            name: Tag name. Must be unique.
            color: Background colour as a CSS hex string.
            is_inbox_tag: When ``True``, newly ingested documents get this tag.
            match: Auto-matching pattern.
            matching_algorithm: Controls how ``match`` is applied.
                E.g. ``matching_algorithm=MatchingAlgorithm.REGEX`` for
                regular-expression matching.
            is_insensitive: When ``True``, ``match`` is case-insensitive.
                Defaults to ``True``, matching the paperless-ngx API default.
            parent: ID of parent tag for hierarchical trees.
            owner: Numeric user ID to assign as owner.
            set_permissions: Explicit view/change permission sets.
                Pass ``None`` to create with empty permissions.

        Returns:
            The newly created :class:`~easypaperless.models.tags.Tag`.
        """
        return cast(
            Tag,
            self._run(
                self._async_tags.create(
                    name=name,
                    color=color,
                    is_inbox_tag=is_inbox_tag,
                    match=match,
                    matching_algorithm=matching_algorithm,
                    is_insensitive=is_insensitive,
                    parent=parent,
                    owner=owner,
                    set_permissions=set_permissions,
                )
            ),
        )

    def update(
        self,
        id: int,
        *,
        name: str | Unset = UNSET,
        color: str | Unset = UNSET,
        is_inbox_tag: bool | Unset = UNSET,
        match: str | Unset = UNSET,
        matching_algorithm: MatchingAlgorithm | Unset = UNSET,
        is_insensitive: bool | Unset = UNSET,
        parent: int | None | Unset = UNSET,
        owner: int | None | Unset = UNSET,
        set_permissions: SetPermissions | None | Unset = UNSET,
    ) -> Tag:
        """Partially update a tag (PATCH semantics).

        Args:
            id: Numeric ID of the tag to update.
            name: Tag name.
            color: Background colour as a CSS hex string.
            is_inbox_tag: When ``True``, newly ingested documents get this tag.
            match: Auto-matching pattern.
            matching_algorithm: Controls how ``match`` is applied.
                E.g. ``matching_algorithm=MatchingAlgorithm.REGEX`` for
                regular-expression matching.
            is_insensitive: When ``True``, ``match`` is case-insensitive.
            parent: ID of parent tag.
                Pass ``None`` to clear (make root tag).
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.
            owner: Numeric user ID to assign as owner.
                Pass ``None`` to clear the owner.
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.
            set_permissions: Explicit view/change permission sets.
                Pass ``None`` to clear all permissions (overwrite with empty).
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.

        Returns:
            The updated :class:`~easypaperless.models.tags.Tag`.
        """
        return cast(
            Tag,
            self._run(
                self._async_tags.update(
                    id,
                    name=name,
                    color=color,
                    is_inbox_tag=is_inbox_tag,
                    match=match,
                    matching_algorithm=matching_algorithm,
                    is_insensitive=is_insensitive,
                    parent=parent,
                    owner=owner,
                    set_permissions=set_permissions,
                )
            ),
        )

    def delete(self, id: int) -> None:
        """Delete a tag.

        Args:
            id: Numeric ID of the tag to delete.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no tag exists with
                that ID.
        """
        self._run(self._async_tags.delete(id))

    def bulk_delete(self, ids: List[int]) -> None:
        """Permanently delete multiple tags in a single request.

        Args:
            ids: List of tag IDs to delete.
        """
        self._run(self._async_tags.bulk_delete(ids))

    def bulk_set_permissions(
        self,
        ids: List[int],
        *,
        set_permissions: SetPermissions | Unset = UNSET,
        owner: int | None | Unset = UNSET,
        merge: bool = False,
    ) -> None:
        """Set permissions and/or owner on multiple tags.

        Args:
            ids: List of tag IDs to modify.
            set_permissions: Explicit view/change permission sets.
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.
            owner: Numeric user ID to assign as owner.
                Pass ``None`` to clear the owner.
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.
            merge: When ``True``, new permissions are merged with existing ones.
        """
        self._run(
            self._async_tags.bulk_set_permissions(
                ids, set_permissions=set_permissions, owner=owner, merge=merge
            )
        )
