"""Users resource for PaperlessClient."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, List, cast

from easypaperless._internal.sentinel import UNSET, Unset
from easypaperless.models.paged_result import PagedResult
from easypaperless.models.users import User

if TYPE_CHECKING:
    from easypaperless.client import _ClientCore

logger = logging.getLogger(__name__)


class UsersResource:
    """Accessor for users: ``client.users``."""

    def __init__(self, core: _ClientCore) -> None:
        self._core = core

    async def list(
        self,
        *,
        username_contains: str | Unset = UNSET,
        username_exact: str | Unset = UNSET,
        ordering: str | Unset = UNSET,
        page: int | Unset = UNSET,
        page_size: int | Unset = UNSET,
    ) -> PagedResult[User]:
        """Return users defined in paperless-ngx.

        When ``page`` is ``UNSET`` (the default), all pages are fetched
        automatically and ``next`` / ``previous`` in the result are always
        ``None``.  When ``page`` is set, only that page is fetched and
        ``next`` / ``previous`` reflect the raw API values.

        Args:
            username_contains: Case-insensitive substring filter on username.
            username_exact: Case-insensitive exact match on username.
            ordering: Field to sort by.
            page: Return only this specific page (1-based).
            page_size: Number of results per page.

        Returns:
            :class:`~easypaperless.models.paged_result.PagedResult` of
            :class:`~easypaperless.models.users.User` objects.
        """
        logger.info("Listing users")
        params: dict[str, Any] = {}
        if not isinstance(username_contains, Unset):
            params["username__icontains"] = username_contains
        if not isinstance(username_exact, Unset):
            params["username__iexact"] = username_exact
        if not isinstance(ordering, Unset):
            params["ordering"] = ordering
        if not isinstance(page, Unset):
            params["page"] = page
        if not isinstance(page_size, Unset):
            params["page_size"] = page_size
        return cast(
            PagedResult[User],
            await self._core._list_resource("users", User, params or None),
        )

    async def get(self, id: int) -> User:
        """Fetch a single user by their ID.

        Args:
            id: Numeric user ID.

        Returns:
            The :class:`~easypaperless.models.users.User` with the given ID.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no user exists with
                that ID.
        """
        logger.info("Getting user id=%d", id)
        return cast(User, await self._core._get_resource("users", id, User))

    async def create(
        self,
        *,
        username: str,
        email: str | Unset = UNSET,
        password: str | Unset = UNSET,
        first_name: str | Unset = UNSET,
        last_name: str | Unset = UNSET,
        date_joined: datetime | Unset = UNSET,
        is_staff: bool | Unset = UNSET,
        is_active: bool | Unset = UNSET,
        is_superuser: bool | Unset = UNSET,
        groups: List[int] | Unset = UNSET,
        user_permissions: List[str] | Unset = UNSET,
    ) -> User:
        """Create a new user.

        Args:
            username: Login username. Must be unique.
            email: Email address.
            password: Password for the new account.
            first_name: Given name.
            last_name: Family name.
            date_joined: Account creation timestamp.
            is_staff: Grant staff (admin UI) access.
            is_active: Whether the account is active.
            is_superuser: Grant unrestricted superuser access.
            groups: IDs of groups to assign the user to.
            user_permissions: Directly assigned permission codenames, without
                the app label (e.g. ``["view_document"]``).  The app-labelled
                form ``"documents.view_document"`` is rejected by paperless-ngx
                with a :exc:`~easypaperless.exceptions.BadRequestError`.

        Returns:
            The newly created :class:`~easypaperless.models.users.User`.
        """
        logger.info("Creating user username=%r", username)
        return cast(
            User,
            await self._core._create_resource(
                "users",
                User,
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                date_joined=date_joined,
                is_staff=is_staff,
                is_active=is_active,
                is_superuser=is_superuser,
                groups=groups,
                user_permissions=user_permissions,
            ),
        )

    async def update(
        self,
        id: int,
        *,
        username: str | Unset = UNSET,
        email: str | Unset = UNSET,
        password: str | Unset = UNSET,
        first_name: str | Unset = UNSET,
        last_name: str | Unset = UNSET,
        date_joined: datetime | Unset = UNSET,
        is_staff: bool | Unset = UNSET,
        is_active: bool | Unset = UNSET,
        is_superuser: bool | Unset = UNSET,
        groups: List[int] | Unset = UNSET,
        user_permissions: List[str] | Unset = UNSET,
    ) -> User:
        """Partially update a user (PATCH semantics).

        Only fields with a non-:data:`~easypaperless.UNSET` value are included
        in the request body.  Omit a parameter (or pass
        :data:`~easypaperless.UNSET`) to leave it unchanged.

        Args:
            id: Numeric ID of the user to update.
            username: Login username.
            email: Email address.
            password: New password.
            first_name: Given name.
            last_name: Family name.
            date_joined: Account creation timestamp.
            is_staff: Grant or revoke staff access.
            is_active: Activate or deactivate the account.
            is_superuser: Grant or revoke superuser access.
            groups: IDs of groups to assign the user to.
            user_permissions: Directly assigned permission codenames, without
                the app label (e.g. ``["view_document"]``).  The app-labelled
                form ``"documents.view_document"`` is rejected by paperless-ngx
                with a :exc:`~easypaperless.exceptions.BadRequestError`.

        Returns:
            The updated :class:`~easypaperless.models.users.User`.
        """
        logger.info("Updating user id=%d", id)
        return cast(
            User,
            await self._core._update_resource(
                "users",
                id,
                User,
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                date_joined=date_joined,
                is_staff=is_staff,
                is_active=is_active,
                is_superuser=is_superuser,
                groups=groups,
                user_permissions=user_permissions,
            ),
        )

    async def delete(self, id: int) -> None:
        """Delete a user.

        Args:
            id: Numeric ID of the user to delete.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no user exists with
                that ID.
        """
        logger.info("Deleting user id=%d", id)
        await self._core._delete_resource("users", id)
