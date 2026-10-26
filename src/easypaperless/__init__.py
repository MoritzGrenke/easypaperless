"""easypaperless — Python API wrapper for paperless-ngx."""

import importlib.metadata
import logging

__version__: str = importlib.metadata.version("easypaperless")

from easypaperless import resources as resources  # noqa: F401
from easypaperless._internal.sentinel import UNSET, Unset
from easypaperless.client import PaperlessClient
from easypaperless.exceptions import (
    AuthenticationError,
    AuthError,
    BadRequestError,
    NotFoundError,
    PaperlessError,
    PermissionDeniedError,
    RetryExhaustedError,
    ServerError,
    ServerResponseError,
    TaskTimeoutError,
    TransportError,
    TransportTimeoutError,
    UploadError,
    ValidationError,
)
from easypaperless.models import (
    AuditLogActor,
    AuditLogEntry,
    Correspondent,
    CustomField,
    CustomFieldValue,
    Document,
    DocumentMetadata,
    DocumentNote,
    DocumentType,
    FieldDataType,
    FileMetadataEntry,
    Group,
    MatchingAlgorithm,
    PagedResult,
    PaperlessPermission,
    PermissionSet,
    SearchHit,
    SetPermissions,
    StoragePath,
    Tag,
    Task,
    TaskStatus,
    User,
)
from easypaperless.sync import SyncPaperlessClient

logging.getLogger("easypaperless").addHandler(logging.NullHandler())

__all__ = [
    "__version__",
    # Clients
    "PaperlessClient",
    "SyncPaperlessClient",
    # Sentinel
    "UNSET",
    "Unset",
    # Models
    "MatchingAlgorithm",
    "PagedResult",
    "AuditLogActor",
    "AuditLogEntry",
    "Correspondent",
    "CustomField",
    "CustomFieldValue",
    "Document",
    "DocumentMetadata",
    "DocumentNote",
    "DocumentType",
    "FieldDataType",
    "FileMetadataEntry",
    "PermissionSet",
    "SearchHit",
    "SetPermissions",
    "StoragePath",
    "Tag",
    "Task",
    "TaskStatus",
    "User",
    "Group",
    "PaperlessPermission",
    # Exceptions
    "PaperlessError",
    "AuthError",
    "AuthenticationError",
    "PermissionDeniedError",
    "BadRequestError",
    "NotFoundError",
    "ValidationError",
    "ServerError",
    "ServerResponseError",
    "TransportError",
    "TransportTimeoutError",
    "UploadError",
    "TaskTimeoutError",
    "RetryExhaustedError",
]
