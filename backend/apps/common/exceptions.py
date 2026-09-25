"""
Consistent error envelope for every API error:

    {
      "error": {
        "code": "validation_error",
        "message": "Human readable summary.",
        "details": {"field": ["message", ...]}   # optional
      }
    }
"""

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class InvalidStateTransition(exceptions.APIException):
    """Raised when a business-state transition is not allowed."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "invalid_transition"
    default_detail = "This state transition is not allowed."


def _error(code, message, http_status, details=None, headers=None):
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return Response(body, status=http_status, headers=headers)


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(
            exc.message_dict if hasattr(exc, "error_dict") else exc.messages
        )
    elif isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception: log with traceback, never leak internals to the client.
        view = context.get("view")
        logger.exception("Unhandled API error in %s", view.__class__.__name__ if view else "?")
        return _error(
            "server_error",
            "An unexpected error occurred. Please try again later.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    headers = {
        k: v for k, v in response.headers.items() if k in ("Retry-After", "WWW-Authenticate")
    }

    if isinstance(exc, exceptions.ValidationError):
        details = exc.detail if isinstance(exc.detail, dict) else {"non_field_errors": exc.detail}
        return _error(
            "validation_error",
            "Some fields are invalid.",
            response.status_code,
            details=details,
            headers=headers,
        )

    detail = exc.detail if isinstance(exc, exceptions.APIException) else str(exc)
    code = getattr(detail, "code", None) or getattr(exc, "default_code", "error")
    return _error(code, str(detail), response.status_code, headers=headers)
