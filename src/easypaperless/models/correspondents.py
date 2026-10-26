"""Correspondent Pydantic model."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from easypaperless.models._base import MatchingAlgorithm
from easypaperless.models.permissions import SetPermissions


class Correspondent(BaseModel):
    """A paperless-ngx correspondent (sender or recipient of a document).

    Attributes:
        id: Unique correspondent ID.
        name: Correspondent name.
        document_count: Number of documents assigned to this correspondent.
        last_correspondence: Date of the most recent document assigned here,
            or ``None``.
        permissions: View/change permissions (user and group IDs). ``None``
            unless fetched with ``full_perms=True``.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    slug: str | None = None
    match: str | None = None
    matching_algorithm: MatchingAlgorithm | None = None
    is_insensitive: bool | None = None
    document_count: int | None = None
    last_correspondence: date | None = None
    owner: int | None = None
    user_can_change: bool | None = None
    permissions: SetPermissions | None = None
