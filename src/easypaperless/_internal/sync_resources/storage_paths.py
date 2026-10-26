"""Sync storage paths resource."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, cast

from easypaperless._internal.sentinel import UNSET, Unset
from easypaperless.models._base import MatchingAlgorithm
from easypaperless.models.paged_result import PagedResult
from easypaperless.models.permissions import SetPermissions
from easypaperless.models.storage_paths import StoragePath

if TYPE_CHECKING:
    from easypaperless._internal.resources.storage_paths import StoragePathsResource


class SyncStoragePathsResource:
    """Sync accessor for storage paths: ``client.storage_paths``."""

    def __init__(self, async_storage_paths: StoragePathsResource, run: Any) -> None:
        self._async_storage_paths = async_storage_paths
        self._run = run

    def list(
        self,
        *,
        ids: List[int] | None = None,
        name_contains: str | None = None,
        name_exact: str | None = None,
        path_contains: str | None = None,
        path_exact: str | None = None,
        page: int | None = None,
        page_size: int | None = None,
        ordering: str | None = None,
        descending: bool = False,
        full_perms: bool = False,
    ) -> PagedResult[StoragePath]:
        """Return storage paths defined in paperless-ngx.

        When ``page`` is ``None`` (the default), all pages are fetched
        automatically and ``next`` / ``previous`` in the result are always
        ``None``.  When ``page`` is set, only that page is fetched and
        ``next`` / ``previous`` reflect the raw API values.

        Args:
            ids: Return only storage paths whose ID is in this list.
            name_contains: Case-insensitive substring filter on name.
            name_exact: Case-insensitive exact match on name.
            path_contains: Case-insensitive substring filter on path template.
            path_exact: Case-insensitive exact match on path template.
            page: Return only this specific page (1-based).
            page_size: Number of results per page.
            ordering: Field to sort by.
            descending: When ``True``, reverses the sort direction.
            full_perms: When ``True``, paperless-ngx returns the full view/change
                permissions of every object, available as
                ``StoragePath.permissions``; ``user_can_change`` is then ``None``.
                Default: ``False``.

        Returns:
            :class:`~easypaperless.models.paged_result.PagedResult` of
            :class:`~easypaperless.models.storage_paths.StoragePath` objects.
        """
        return cast(
            PagedResult[StoragePath],
            self._run(
                self._async_storage_paths.list(
                    ids=ids,
                    name_contains=name_contains,
                    name_exact=name_exact,
                    path_contains=path_contains,
                    path_exact=path_exact,
                    page=page,
                    page_size=page_size,
                    ordering=ordering,
                    descending=descending,
                    full_perms=full_perms,
                )
            ),
        )

    def get(self, id: int, *, full_perms: bool = False) -> StoragePath:
        """Fetch a single storage path by its ID.

        Args:
            id: Numeric storage-path ID.
            full_perms: When ``True``, paperless-ngx returns the full view/change
                permissions, available as ``StoragePath.permissions``;
                ``user_can_change`` is then ``None``. Default: ``False``.

        Returns:
            The :class:`~easypaperless.models.storage_paths.StoragePath` with the given ID.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no storage path exists with that ID.
        """
        return cast(
            StoragePath, self._run(self._async_storage_paths.get(id, full_perms=full_perms))
        )

    def create(
        self,
        *,
        name: str,
        path: str | Unset = UNSET,
        match: str | Unset = UNSET,
        matching_algorithm: MatchingAlgorithm | Unset = UNSET,
        is_insensitive: bool = True,
        owner: int | None | Unset = UNSET,
        set_permissions: SetPermissions | None | Unset = UNSET,
    ) -> StoragePath:
        """Create a new storage path.

        Args:
            name: Storage-path name. Must be unique.
            path: Template string for the archive file path.
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
            The newly created :class:`~easypaperless.models.storage_paths.StoragePath`.
        """
        return cast(
            StoragePath,
            self._run(
                self._async_storage_paths.create(
                    name=name,
                    path=path,
                    match=match,
                    matching_algorithm=matching_algorithm,
                    is_insensitive=is_insensitive,
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
        path: str | Unset = UNSET,
        match: str | Unset = UNSET,
        matching_algorithm: MatchingAlgorithm | Unset = UNSET,
        is_insensitive: bool | Unset = UNSET,
        owner: int | None | Unset = UNSET,
        set_permissions: SetPermissions | None | Unset = UNSET,
    ) -> StoragePath:
        """Partially update a storage path (PATCH semantics).

        Args:
            id: Numeric ID of the storage path to update.
            name: Storage-path name.
            path: Template string for the archive file path.
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
            The updated :class:`~easypaperless.models.storage_paths.StoragePath`.
        """
        return cast(
            StoragePath,
            self._run(
                self._async_storage_paths.update(
                    id,
                    name=name,
                    path=path,
                    match=match,
                    matching_algorithm=matching_algorithm,
                    is_insensitive=is_insensitive,
                    owner=owner,
                    set_permissions=set_permissions,
                )
            ),
        )

    def delete(self, id: int) -> None:
        """Delete a storage path.

        Args:
            id: Numeric ID of the storage path to delete.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no storage path exists with that ID.
        """
        self._run(self._async_storage_paths.delete(id))

    def bulk_delete(self, ids: List[int]) -> None:
        """Permanently delete multiple storage paths in a single request.

        Args:
            ids: List of storage path IDs to delete.
        """
        self._run(self._async_storage_paths.bulk_delete(ids))

    def bulk_set_permissions(
        self,
        ids: List[int],
        *,
        set_permissions: SetPermissions | Unset = UNSET,
        owner: int | None | Unset = UNSET,
        merge: bool = False,
    ) -> None:
        """Set permissions and/or owner on multiple storage paths.

        Args:
            ids: List of storage path IDs to modify.
            set_permissions: Explicit view/change permission sets.
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.
            owner: Numeric user ID to assign as owner.
                Pass ``None`` to clear the owner.
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.
            merge: When ``True``, new permissions are merged with existing ones.
        """
        self._run(
            self._async_storage_paths.bulk_set_permissions(
                ids, set_permissions=set_permissions, owner=owner, merge=merge
            )
        )
