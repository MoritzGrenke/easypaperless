"""UiSettings Pydantic models for ``GET /api/ui_settings/``.

paperless-ngx's web frontend loads this endpoint at startup. It is the only
endpoint that returns the token user's *effective* permissions (granted
directly and via groups), which makes it the basis for permission checks of
service users. Unknown fields are ignored at every level.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UiSettingsUser(BaseModel):
    """The user the API token belongs to.

    Attributes:
        id: User ID.
        username: Login name.
        is_staff: Whether the user is a staff member (paperless admin views,
            e.g. :meth:`~easypaperless.PaperlessClient.system_status`).
        is_superuser: Whether the user is a superuser (has every permission).
        groups: IDs of the groups the user belongs to.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    username: str
    is_staff: bool = False
    is_superuser: bool = False
    groups: list[int] = Field(default_factory=list)


class UiSettingsServerSettings(BaseModel):
    """Server-side settings paperless-ngx includes in the UI settings.

    Every field is optional; fields a paperless version does not send stay
    ``None``. Frontend preferences the user stored in the web UI may appear as
    additional keys and are ignored.

    Attributes:
        version: paperless-ngx version, e.g. ``"2.18.2"``.
        app_title: Custom application title, or ``None`` for the default.
        app_logo: URL of a custom application logo, or ``None``.
        trash_delay: Days before trashed documents are deleted for good.
        auditlog_enabled: Whether the audit log (document history) is enabled.
        email_enabled: Whether paperless-ngx can send e-mails.
        update_checking: Update-check configuration as paperless sends it,
            e.g. ``{"backend_setting": "default"}``.
    """

    model_config = ConfigDict(extra="ignore")

    version: str | None = None
    app_title: str | None = None
    app_logo: str | None = None
    trash_delay: int | None = None
    auditlog_enabled: bool | None = None
    email_enabled: bool | None = None
    update_checking: dict[str, Any] | bool | None = None


class UiSettings(BaseModel):
    """Current user, effective permissions and server settings.

    Returned by :meth:`~easypaperless.PaperlessClient.ui_settings`
    (``GET /api/ui_settings/``).

    Attributes:
        user: The user the API token belongs to.
        permissions: The user's effective permission codenames exactly as
            paperless-ngx returns them: bare codenames such as
            ``"add_document"`` or ``"view_paperlesstask"``, including
            permissions granted via groups. For a superuser paperless lists
            every permission. Note: codenames are bare (``"add_document"``),
            unlike the app-labelled ``PaperlessPermission`` form
            (``"documents.add_document"``).
        settings: Server-side settings (version, app title, trash delay, ...).
    """

    model_config = ConfigDict(extra="ignore")

    user: UiSettingsUser
    permissions: list[str] = Field(default_factory=list)
    settings: UiSettingsServerSettings = Field(default_factory=UiSettingsServerSettings)

    def has_permission(self, codename: str) -> bool:
        """Return whether the user has the permission ``codename``.

        Args:
            codename: Bare permission codename, e.g. ``"add_note"``.

        Returns:
            ``True`` if ``codename`` is in :attr:`permissions`, and always
            ``True`` for a superuser.

        Example:
            >>> settings.has_permission("add_document")
            True
        """
        return self.user.is_superuser or codename in self.permissions

    def missing_permissions(self, required: Iterable[str]) -> set[str]:
        """Return the codenames from ``required`` that the user lacks.

        Args:
            required: Bare permission codenames the caller needs, e.g.
                ``{"add_document", "add_note"}``.

        Returns:
            The subset of ``required`` that is not in :attr:`permissions`.
            Always an empty set for a superuser.

        Example:
            >>> settings.missing_permissions({"add_document", "add_note"})
            {'add_note'}
        """
        if self.user.is_superuser:
            return set()
        return set(required) - set(self.permissions)
