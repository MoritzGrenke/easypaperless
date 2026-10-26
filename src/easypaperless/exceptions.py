"""Custom exception hierarchy for easypaperless.

Every exception has a non-empty message and a ``status_code`` attribute
(``None`` when no HTTP response was received)::

    PaperlessError
    ├── AuthError
    │   ├── AuthenticationError      401
    │   └── PermissionDeniedError    403
    ├── BadRequestError              400 (field_errors, non_field_errors)
    ├── NotFoundError                404 / unresolvable name
    ├── ValidationError              422
    ├── NotPaperlessError            URL is not a paperless-ngx instance
    ├── ServerError
    │   ├── ServerResponseError      5xx
    │   └── TransportError           connection, DNS, TLS, protocol errors
    │       └── TransportTimeoutError
    ├── UploadError
    ├── TaskTimeoutError
    └── RetryExhaustedError          last error chained as __cause__

Any other HTTP error status (e.g. 409, 429) raises a plain ``PaperlessError``.
"""

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
    authenticated user lacks permission for the requested operation. Catch
    :class:`AuthenticationError` (401) or :class:`PermissionDeniedError` (403)
    to tell the two cases apart.
    """


class AuthenticationError(AuthError):
    """Raised on 401 responses: the API token is missing or invalid."""


class PermissionDeniedError(AuthError):
    """Raised on 403 responses: the token is valid but lacks a permission."""


class BadRequestError(PaperlessError):
    """Raised on 400 responses: paperless-ngx rejected the request data.

    The message summarises all errors readably, e.g.
    ``"name: This field is required."``.

    Attributes:
        field_errors: Mapping of field name to the list of error messages
            paperless-ngx returned for that field.
        non_field_errors: Error messages not tied to a single field (the
            ``non_field_errors`` key, a ``detail`` message, or the items of a
            plain list body).
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = 400,
        *,
        field_errors: dict[str, list[str]] | None = None,
        non_field_errors: list[str] | None = None,
    ) -> None:
        """Create a BadRequestError.

        Args:
            message: Human-readable error description.
            status_code: HTTP status code. Default: ``400``.
            field_errors: Parsed per-field error messages. Default: empty.
            non_field_errors: Parsed messages not tied to a field. Default: empty.
        """
        super().__init__(message, status_code=status_code)
        self.field_errors: dict[str, list[str]] = dict(field_errors or {})
        self.non_field_errors: list[str] = list(non_field_errors or [])


class NotFoundError(PaperlessError):
    """Raised on 404 responses or when a name lookup fails."""


class ValidationError(PaperlessError):
    """Raised on 422 responses or bad input supplied by the caller."""


class NotPaperlessError(PaperlessError):
    """Raised when the configured URL does not point to a paperless-ngx instance.

    Raised by :meth:`~easypaperless.PaperlessClient.server_version` when the
    server answers the API root with 404, or with a successful response that
    lacks paperless's ``X-Version`` header (e.g. an HTML page from another web
    app or a reverse proxy). ``status_code`` holds the HTTP status of that
    response.
    """


class ServerError(PaperlessError):
    """Raised on 5xx responses or transport errors.

    Catch :class:`ServerResponseError` or :class:`TransportError` to tell the
    two cases apart.
    """


class ServerResponseError(ServerError):
    """Raised on HTTP 5xx responses; ``status_code`` holds the status."""


class TransportError(ServerError):
    """Raised when paperless-ngx could not be reached or the connection failed.

    Covers connection refused, DNS failures, TLS errors, protocol errors and
    timeouts. ``status_code`` is always ``None``; the original ``httpx``
    exception is chained as ``__cause__``.
    """

    def __init__(self, message: str) -> None:
        """Create a TransportError.

        Args:
            message: Human-readable error description.
        """
        super().__init__(message, status_code=None)


class TransportTimeoutError(TransportError):
    """Raised when a request times out (connect, read, write or pool timeout).

    The request may still have been processed by the server.
    """


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
