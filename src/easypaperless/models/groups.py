"""Group Pydantic model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Group(BaseModel):
    """A paperless-ngx user group.

    Groups bundle permissions and can be granted object permissions
    (``set_permissions``) on documents and other resources.

    Attributes:
        id: Unique group ID (set by the API).
        name: Group name.
        permissions: Permission codename strings granted to the group
            (e.g. ``"documents.view_document"``). See
            :data:`~easypaperless.PaperlessPermission` for the known values.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    permissions: list[str] | None = None
