from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.exceptions import ErrorDetail, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def _serialize_error(value):
    if isinstance(value, dict):
        return {key: _serialize_error(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_error(item) for item in value]
    if isinstance(value, ErrorDetail):
        return {"code": str(value.code), "message": str(value)}
    return {"code": "error", "message": str(value)}


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    if isinstance(exc, ValidationError):
        response.data = {
            "error": {
                "code": "validation_error",
                "message": _("Validation failed."),
                "fields": _serialize_error(response.data),
            }
        }
        return response

    detail = response.data.get("detail") if isinstance(response.data, dict) else None
    message = str(detail) if detail else _("Request failed.")
    error_code = str(getattr(detail, "code", "error")) if detail else "error"

    response.data = {
        "error": {
            "code": error_code,
            "message": message,
        }
    }

    if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        response.data["error"]["message"] = _("Internal server error.")

    return response
