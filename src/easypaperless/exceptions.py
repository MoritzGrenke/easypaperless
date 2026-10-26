"""Custom exception hierarchy for easypaperless."""

from __future__ import annotations


class PaperlessError(Exception):
    """Base exception for all easypaperless errors.

    Attributes:
        status_code: The HTTP status code associated with the error, or
            ``None`` for non-HTTP errors (e.g. timeouts, local validation).
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Create a PaperlessError.

        Args:
            message: Human-readable error description.
            status_code: HTTP status code, if applicable.
        """
        super().__init__(message)
        self.status_code = status_code


class AuthError(PaperlessError):
    """Raised on 401 or 403 responses.

    Indicates that the API token is missing or invalid, or that the
    authenticated user lacks permission for the requested operation.
    """


class NotFoundError(PaperlessError):
    """Raised on 404 responses or when a name lookup fails."""


class ValidationError(PaperlessError):
    """Raised on 422 responses or bad input supplied by the caller."""


class ServerError(PaperlessError):
    """Raised on 5xx responses or unrecoverable transport errors."""


class UploadError(PaperlessError):
    """Raised when file submission or document processing fails.

    Raised by ``client.documents.upload()`` (with ``wait=True``, see
    :meth:`~easypaperless.resources.DocumentsResource.upload`) when the
    paperless-ngx processing task reports ``FAILURE`` or ``REVOKED``, or
    succeeds without returning a document ID.
    """


class TaskTimeoutError(PaperlessError):
    """Raised when upload polling exceeds the configured timeout.

    Raised by ``client.documents.upload()`` (with ``wait=True``, see
    :meth:`~easypaperless.resources.DocumentsResource.upload`) when the
    document processing task does not reach a terminal state within
    ``poll_timeout`` seconds.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=None)


class RetryExhaustedError(PaperlessError):
    """Raised when all retry attempts are exhausted.

    Attributes:
        attempts: Total number of attempts made (initial + retries).
        url: The URL that was requested.
    """

    def __init__(self, message: str, attempts: int, url: str) -> None:
        """Create a RetryExhaustedError.

        Args:
            message: Human-readable error description.
            attempts: Total number of attempts made.
            url: The URL that was requested.
        """
        super().__init__(message, status_code=None)
        self.attempts = attempts
        self.url = url
