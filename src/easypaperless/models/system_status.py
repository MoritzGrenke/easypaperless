"""SystemStatus Pydantic models for ``GET /api/status/``.

The shape follows paperless-ngx's ``SystemStatusView`` (paperless-ngx 2.x).
Every field is optional and unknown fields are ignored, because the response
differs between paperless versions and installs. Status values are the strings
paperless reports, typically ``"OK"``, ``"WARNING"`` or ``"ERROR"``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class SystemStatusStorage(BaseModel):
    """Disk space of the paperless-ngx media storage.

    Attributes:
        total: Total size of the storage in bytes.
        available: Free space in bytes.
    """

    model_config = ConfigDict(extra="ignore")

    total: int | None = None
    available: int | None = None


class SystemStatusMigrations(BaseModel):
    """Database migration state.

    Attributes:
        latest_migration: Name of the most recently applied migration.
        unapplied_migrations: Names of migrations not yet applied.
    """

    model_config = ConfigDict(extra="ignore")

    latest_migration: str | None = None
    unapplied_migrations: list[str] | None = None


class SystemStatusDatabase(BaseModel):
    """Database health.

    Attributes:
        type: Database engine (e.g. ``"postgresql"``, ``"sqlite"``).
        url: Database name or URL as reported by paperless-ngx.
        status: ``"OK"`` or ``"ERROR"``.
        error: Error message when the status is not OK.
        migration_status: Applied and unapplied migrations.
    """

    model_config = ConfigDict(extra="ignore")

    type: str | None = None
    url: str | None = None
    status: str | None = None
    error: str | None = None
    migration_status: SystemStatusMigrations | None = None


class SystemStatusTasks(BaseModel):
    """Health of the background services (Redis, Celery, index, classifier).

    Attributes:
        redis_url: Redis broker URL.
        redis_status: Redis status.
        redis_error: Redis error message, if any.
        celery_status: Celery worker status.
        celery_url: Name of the responding Celery worker.
        celery_error: Celery error message, if any.
        index_status: Search index status.
        index_last_modified: When the search index was last modified.
        index_error: Search index error message, if any.
        classifier_status: Status of the automatic matching classifier.
        classifier_last_trained: When the classifier was last trained.
        classifier_error: Classifier error message, if any.
        sanity_check_status: Status of the last sanity check.
        sanity_check_last_run: When the sanity check last ran.
        sanity_check_error: Sanity check error message, if any.
    """

    model_config = ConfigDict(extra="ignore")

    redis_url: str | None = None
    redis_status: str | None = None
    redis_error: str | None = None
    celery_status: str | None = None
    celery_url: str | None = None
    celery_error: str | None = None
    index_status: str | None = None
    index_last_modified: datetime | None = None
    index_error: str | None = None
    classifier_status: str | None = None
    classifier_last_trained: datetime | None = None
    classifier_error: str | None = None
    sanity_check_status: str | None = None
    sanity_check_last_run: datetime | None = None
    sanity_check_error: str | None = None


class SystemStatus(BaseModel):
    """paperless-ngx system status, as returned by ``GET /api/status/``.

    Returned by :meth:`~easypaperless.PaperlessClient.system_status`.

    Attributes:
        version: paperless-ngx version (paperless sends it as ``pngx_version``).
        server_os: Operating system of the server.
        install_type: How paperless-ngx is installed (e.g. ``"docker"``).
        storage: Media storage disk space.
        database: Database health and migrations.
        tasks: Redis, Celery, search index, classifier and sanity check health.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    version: str | None = Field(
        default=None, validation_alias=AliasChoices("pngx_version", "version")
    )
    server_os: str | None = None
    install_type: str | None = None
    storage: SystemStatusStorage | None = None
    database: SystemStatusDatabase | None = None
    tasks: SystemStatusTasks | None = None
