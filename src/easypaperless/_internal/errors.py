"""Single mapping point from HTTP responses to easypaperless exceptions.

paperless-ngx is a Django REST Framework app, so its error bodies follow the
DRF shapes: ``{"detail": "..."}``, a dict of field name to list of messages
(values may also be a plain string or nested dicts/lists), a
``non_field_errors`` key, or a plain JSON list. Anything that is not JSON
(e.g. an HTML page from a reverse proxy) is reduced to a short excerpt.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from easypaperless.exceptions import (
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PaperlessError,
    PermissionDeniedError,
    ServerResponseError,
    TransportError,
    TransportTimeoutError,
    ValidationError,
)

logger = logging.getLogger(__name__)

# Keys of a DRF error dict that do not name a model field.
_NON_FIELD_KEYS = ("non_field_errors", "detail")


def map_transport_error(exc: httpx.HTTPError, method: str, url: str) -> TransportError:
    """Translate an ``httpx`` exception into the matching easypaperless error.

    The caller raises the result ``from exc`` so the original exception stays
    available as ``__cause__``.
    """
    if isinstance(exc, httpx.TimeoutException):
        return TransportTimeoutError(
            f"Request timed out ({method.upper()} {url}). "
            "The operation may have completed on the server despite this error."
        )
    detail = str(exc) or type(exc).__name__
    return TransportError(f"{detail} ({method.upper()} {url})")


def _sanitise_body(body: str) -> str:
    """Return a safe representation of a response body.

    If the body looks like HTML, replaces it with a human-readable note and
    a short excerpt to avoid flooding logs or exception messages with raw HTML.
    """
    stripped = body.lstrip()
    if stripped.lower().startswith("<!") or stripped.lower().startswith("<html"):
        excerpt = body[:200]
        return (
            "response body appears to be an HTML page — this may indicate a "
            f"proxy or gateway error. Excerpt: {excerpt!r}"
        )
    return body


def _flatten(value: Any) -> list[str]:
    """Flatten a DRF error value (str, list, nested dict) into messages."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [msg for item in value for msg in _flatten(item)]
    if isinstance(value, dict):
        return [f"{key}: {msg}" for key, item in value.items() for msg in _flatten(item)]
    return [str(value)]


def _parse_body(response: httpx.Response) -> tuple[dict[str, list[str]], list[str]]:
    """Split an error body into ``(field_errors, non_field_errors)``."""
    try:
        body = response.json()
    except ValueError:
        text = _sanitise_body(response.text).strip()
        return {}, [text] if text else []

    if not isinstance(body, dict):
        return {}, _flatten(body) if body is not None else []

    field_errors: dict[str, list[str]] = {}
    non_field_errors: list[str] = []
    for key, value in body.items():
        if key in _NON_FIELD_KEYS:
            non_field_errors.extend(_flatten(value))
        else:
            field_errors[str(key)] = _flatten(value)
    return field_errors, non_field_errors


def _summarise(field_errors: dict[str, list[str]], non_field_errors: list[str]) -> str:
    """Build a readable one-line message from parsed errors."""
    parts = list(non_field_errors)
    parts += [f"{field}: {' '.join(msgs)}" for field, msgs in field_errors.items()]
    return "; ".join(parts)


def raise_for_status(response: httpx.Response, method: str, path: str) -> None:
    """Raise the easypaperless exception matching an unsuccessful response.

    Does nothing for 2xx responses. The message is paperless's ``detail``
    verbatim when present, otherwise a summary of the parsed body, otherwise
    ``"HTTP <status> <reason>"``.
    """
    if response.is_success:
        return
    status = response.status_code
    field_errors, non_field_errors = _parse_body(response)
    message = _summarise(field_errors, non_field_errors)
    if not message:
        message = f"HTTP {status} {response.reason_phrase}".strip()

    logger.warning("HTTP %s on %s %s — %s", status, method.upper(), path, message)
    if status == 400:
        raise BadRequestError(
            message,
            status_code=status,
            field_errors=field_errors,
            non_field_errors=non_field_errors,
        )
    if status == 401:
        raise AuthenticationError(message, status_code=status)
    if status == 403:
        raise PermissionDeniedError(message, status_code=status)
    if status == 404:
        raise NotFoundError(message, status_code=status)
    if status == 422:
        raise ValidationError(message, status_code=status)
    if status >= 500:
        raise ServerResponseError(message, status_code=status)
    raise PaperlessError(message, status_code=status)
