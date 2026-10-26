"""Tag Pydantic model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from easypaperless.models._base import MatchingAlgorithm
from easypaperless.models.permissions import SetPermissions


class Tag(BaseModel):
    """A paperless-ngx tag.

    Attributes:
        id: Unique tag ID.
        name: Tag name.
        color: Hex colour code used in the UI (e.g. ``"#ff0000"``).
        is_inbox_tag: If ``True``, newly ingested documents receive this tag
            automatically until they are processed.
        document_count: Number of documents currently assigned to this tag.
        parent: ID of the parent tag for hierarchical tag trees, or ``None``.
        children: IDs of child tags, or ``None``.
        permissions: View/change permissions (user and group IDs). ``None``
            unless fetched with ``full_perms=True``.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    slug: str | None = None
    color: str | None = None
    text_color: str | None = None
    match: str | None = None
    matching_algorithm: MatchingAlgorithm | None = None
    is_insensitive: bool | None = None
    is_inbox_tag: bool | None = None
    document_count: int | None = None
    owner: int | None = None
    user_can_change: bool | None = None
    permissions: SetPermissions | None = None
    parent: int | None = None
    children: list[int] | None = None
