"""User Pydantic model and PaperlessPermission type alias."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

PaperlessPermission = Literal[
    "account.add_emailaddress",
    "account.add_emailconfirmation",
    "account.change_emailaddress",
    "account.change_emailconfirmation",
    "account.delete_emailaddress",
    "account.delete_emailconfirmation",
    "account.view_emailaddress",
    "account.view_emailconfirmation",
    "admin.add_logentry",
    "admin.change_logentry",
    "admin.delete_logentry",
    "admin.view_logentry",
    "auth.add_group",
    "auth.add_permission",
    "auth.add_user",
    "auth.change_group",
    "auth.change_permission",
    "auth.change_user",
    "auth.delete_group",
    "auth.delete_permission",
    "auth.delete_user",
    "auth.view_group",
    "auth.view_permission",
    "auth.view_user",
    "authtoken.add_token",
    "authtoken.add_tokenproxy",
    "authtoken.change_token",
    "authtoken.change_tokenproxy",
    "authtoken.delete_token",
    "authtoken.delete_tokenproxy",
    "authtoken.view_token",
    "authtoken.view_tokenproxy",
    "auditlog.add_logentry",
    "auditlog.change_logentry",
    "auditlog.delete_logentry",
    "auditlog.view_logentry",
    "contenttypes.add_contenttype",
    "contenttypes.change_contenttype",
    "contenttypes.delete_contenttype",
    "contenttypes.view_contenttype",
    "django_celery_results.add_chordcounter",
    "django_celery_results.add_groupresult",
    "django_celery_results.add_taskresult",
    "django_celery_results.change_chordcounter",
    "django_celery_results.change_groupresult",
    "django_celery_results.change_taskresult",
    "django_celery_results.delete_chordcounter",
    "django_celery_results.delete_groupresult",
    "django_celery_results.delete_taskresult",
    "django_celery_results.view_chordcounter",
    "django_celery_results.view_groupresult",
    "django_celery_results.view_taskresult",
    "documents.add_correspondent",
    "documents.add_customfield",
    "documents.add_customfieldinstance",
    "documents.add_document",
    "documents.add_documenttype",
    "documents.add_log",
    "documents.add_note",
    "documents.add_paperlesstask",
    "documents.add_savedview",
    "documents.add_savedviewfilterrule",
    "documents.add_sharelink",
    "documents.add_storagepath",
    "documents.add_tag",
    "documents.add_uisettings",
    "documents.add_workflow",
    "documents.add_workflowaction",
    "documents.add_workflowactionemail",
    "documents.add_workflowactionwebhook",
    "documents.add_workflowrun",
    "documents.add_workflowtrigger",
    "documents.change_correspondent",
    "documents.change_customfield",
    "documents.change_customfieldinstance",
    "documents.change_document",
    "documents.change_documenttype",
    "documents.change_log",
    "documents.change_note",
    "documents.change_paperlesstask",
    "documents.change_savedview",
    "documents.change_savedviewfilterrule",
    "documents.change_sharelink",
    "documents.change_storagepath",
    "documents.change_tag",
    "documents.change_uisettings",
    "documents.change_workflow",
    "documents.change_workflowaction",
    "documents.change_workflowactionemail",
    "documents.change_workflowactionwebhook",
    "documents.change_workflowrun",
    "documents.change_workflowtrigger",
    "documents.delete_correspondent",
    "documents.delete_customfield",
    "documents.delete_customfieldinstance",
    "documents.delete_document",
    "documents.delete_documenttype",
    "documents.delete_log",
    "documents.delete_note",
    "documents.delete_paperlesstask",
    "documents.delete_savedview",
    "documents.delete_savedviewfilterrule",
    "documents.delete_sharelink",
    "documents.delete_storagepath",
    "documents.delete_tag",
    "documents.delete_uisettings",
    "documents.delete_workflow",
    "documents.delete_workflowaction",
    "documents.delete_workflowactionemail",
    "documents.delete_workflowactionwebhook",
    "documents.delete_workflowrun",
    "documents.delete_workflowtrigger",
    "documents.view_correspondent",
    "documents.view_customfield",
    "documents.view_customfieldinstance",
    "documents.view_document",
    "documents.view_documenttype",
    "documents.view_log",
    "documents.view_note",
    "documents.view_paperlesstask",
    "documents.view_savedview",
    "documents.view_savedviewfilterrule",
    "documents.view_sharelink",
    "documents.view_storagepath",
    "documents.view_tag",
    "documents.view_uisettings",
    "documents.view_workflow",
    "documents.view_workflowaction",
    "documents.view_workflowactionemail",
    "documents.view_workflowactionwebhook",
    "documents.view_workflowrun",
    "documents.view_workflowtrigger",
    "guardian.add_groupobjectpermission",
    "guardian.add_userobjectpermission",
    "guardian.change_groupobjectpermission",
    "guardian.change_userobjectpermission",
    "guardian.delete_groupobjectpermission",
    "guardian.delete_userobjectpermission",
    "guardian.view_groupobjectpermission",
    "guardian.view_userobjectpermission",
    "mfa.add_authenticator",
    "mfa.change_authenticator",
    "mfa.delete_authenticator",
    "mfa.view_authenticator",
    "paperless.add_applicationconfiguration",
    "paperless.change_applicationconfiguration",
    "paperless.delete_applicationconfiguration",
    "paperless.view_applicationconfiguration",
    "paperless_mail.add_mailaccount",
    "paperless_mail.add_mailrule",
    "paperless_mail.add_processedmail",
    "paperless_mail.change_mailaccount",
    "paperless_mail.change_mailrule",
    "paperless_mail.change_processedmail",
    "paperless_mail.delete_mailaccount",
    "paperless_mail.delete_mailrule",
    "paperless_mail.delete_processedmail",
    "paperless_mail.view_mailaccount",
    "paperless_mail.view_mailrule",
    "paperless_mail.view_processedmail",
    "sessions.add_session",
    "sessions.change_session",
    "sessions.delete_session",
    "sessions.view_session",
    "socialaccount.add_socialaccount",
    "socialaccount.add_socialapp",
    "socialaccount.add_socialtoken",
    "socialaccount.change_socialaccount",
    "socialaccount.change_socialapp",
    "socialaccount.change_socialtoken",
    "socialaccount.delete_socialaccount",
    "socialaccount.delete_socialapp",
    "socialaccount.delete_socialtoken",
    "socialaccount.view_socialaccount",
    "socialaccount.view_socialapp",
    "socialaccount.view_socialtoken",
]
"""All known paperless-ngx permission strings, in the app-labelled form ``"<app>.<codename>"``.

paperless-ngx uses this form only in :attr:`User.inherited_permissions`
(permissions a user gets from its groups).  :attr:`User.user_permissions` and
:attr:`~easypaperless.models.groups.Group.permissions` hold *bare* codenames
(``"view_document"``), both when paperless-ngx returns them and when you send
them; the app-labelled form is rejected there with a
:exc:`~easypaperless.exceptions.BadRequestError` (verified against
paperless-ngx 2.18.2).  Strip the app label with ``perm.split(".", 1)[1]``.

Example::

    from easypaperless import PaperlessPermission

    user = await client.users.get(1)
    perm: PaperlessPermission = "documents.view_document"
    codename = perm.split(".", 1)[1]                 # "view_document"
    can_view_docs = perm in (user.inherited_permissions or []) or codename in (
        user.user_permissions or []
    )
"""


class User(BaseModel):
    """A paperless-ngx user account.

    Attributes:
        id: Unique user ID (set by the API).
        username: Login username.
        email: Email address.
        password: Password field as returned by the API (write-only in practice).
        first_name: Given name.
        last_name: Family name.
        date_joined: Timestamp of account creation.
        is_staff: Whether the user has staff (admin UI) access.
        is_active: Whether the account is active.
        is_superuser: Whether the user has unrestricted superuser access.
        groups: IDs of groups the user belongs to.
        user_permissions: Directly assigned permission codenames, without the
            app label (e.g. ``"view_document"``).
        inherited_permissions: Permissions inherited from the user's groups,
            in the app-labelled form (e.g. ``"documents.view_document"``, see
            :data:`PaperlessPermission`). Read-only, not sent on create/update.
        is_mfa_enabled: Whether multi-factor authentication is enabled
            (read-only, not sent on create/update).
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    username: str
    email: str | None = None
    password: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    date_joined: datetime | None = None
    is_staff: bool | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    groups: list[int] | None = None
    user_permissions: list[str] | None = None
    inherited_permissions: list[str] | None = None
    is_mfa_enabled: bool | None = None
