"""DocumentType Pydantic model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from easypaperless.models._base import MatchingAlgorithm
from easypaperless.models.permissions import SetPermissions


class DocumentType(BaseModel):
    """A paperless-ngx document type (e.g. Invoice, Receipt, Contract).

    Attributes:
        id: Unique document-type ID.
        name: Document-type name.
        document_count: Number of documents assigned to this document type.
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
    owner: int | None = None
    user_can_change: bool | None = None
    permissions: SetPermissions | None = None
