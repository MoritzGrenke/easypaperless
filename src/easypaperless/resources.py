"""Resource Classes

The following resource classes are _internal classes. Methods can be accessed via the instance of
`easypaperless.PaperlessClient` or `easypaperless.SyncPaperlessClient`

Example:
    async with PaperlessClient(url="http://localhost:8000", api_token="abc") as client:
        docs = await client.documents.list(max_results=10)

"""

# internal comment: the doc string above is also rendered in the pdoc documentation.
#
# original was:
#
# Public resource classes — for type annotations and IDE support.
#
# Re-exports all async and sync resource classes from the internal modules
# so that pdoc can document them as a full page with all methods.
#
# Example:
#    from easypaperless.resources import DocumentsResource

from easypaperless._internal.resources.correspondents import CorrespondentsResource
from easypaperless._internal.resources.custom_fields import CustomFieldsResource
from easypaperless._internal.resources.document_types import DocumentTypesResource
from easypaperless._internal.resources.documents import DocumentsResource
from easypaperless._internal.resources.groups import GroupsResource
from easypaperless._internal.resources.notes import NotesResource
from easypaperless._internal.resources.storage_paths import StoragePathsResource
from easypaperless._internal.resources.tags import TagsResource
from easypaperless._internal.resources.tasks import TasksResource
from easypaperless._internal.resources.trash import TrashResource
from easypaperless._internal.resources.users import UsersResource
from easypaperless._internal.sync_resources.correspondents import SyncCorrespondentsResource
from easypaperless._internal.sync_resources.custom_fields import SyncCustomFieldsResource
from easypaperless._internal.sync_resources.document_types import SyncDocumentTypesResource
from easypaperless._internal.sync_resources.documents import SyncDocumentsResource
from easypaperless._internal.sync_resources.groups import SyncGroupsResource
from easypaperless._internal.sync_resources.notes import SyncNotesResource
from easypaperless._internal.sync_resources.storage_paths import SyncStoragePathsResource
from easypaperless._internal.sync_resources.tags import SyncTagsResource
from easypaperless._internal.sync_resources.tasks import SyncTasksResource
from easypaperless._internal.sync_resources.trash import SyncTrashResource
from easypaperless._internal.sync_resources.users import SyncUsersResource

__all__ = [
    "CorrespondentsResource",
    "CustomFieldsResource",
    "DocumentTypesResource",
    "DocumentsResource",
    "NotesResource",
    "StoragePathsResource",
    "TagsResource",
    "SyncCorrespondentsResource",
    "SyncCustomFieldsResource",
    "SyncDocumentTypesResource",
    "SyncDocumentsResource",
    "SyncNotesResource",
    "SyncStoragePathsResource",
    "SyncTagsResource",
    "UsersResource",
    "SyncUsersResource",
    "GroupsResource",
    "SyncGroupsResource",
    "TrashResource",
    "SyncTrashResource",
    "TasksResource",
    "SyncTasksResource",
]
