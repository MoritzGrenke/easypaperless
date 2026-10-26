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
        permissions: Permission codenames granted to the group, without the
            app label (e.g. ``"view_document"``), as paperless-ngx returns and
            accepts them.  :data:`~easypaperless.PaperlessPermission` holds the
            app-labelled form (``"documents.view_document"``); strip the
            prefix (``perm.split(".", 1)[1]``) before sending one here.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    permissions: list[str] | None = None
