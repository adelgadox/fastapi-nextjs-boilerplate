from fastapi import HTTPException, status

_STATUS_CODE_MAP: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    402: "PAYMENT_REQUIRED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    410: "GONE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_ERROR",
    502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def api_error(
    code: str,
    message: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    field: str | None = None,
    meta: dict | None = None,
) -> HTTPException:
    """Return a structured HTTPException that the global handler converts to an error envelope."""
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "field": field, "meta": meta},
    )


def default_code(http_status: int) -> str:
    return _STATUS_CODE_MAP.get(http_status, "ERROR")
