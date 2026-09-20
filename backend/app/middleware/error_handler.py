import logging
from uuid import uuid4
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from fastapi.responses import JSONResponse
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def error_handler_middleware(app):
    async def handle(request, exc):
        error_id = str(uuid4())
        status = 500
        message = "Something went wrong. Please try again."
        headers = None
        if isinstance(exc, HTTPException):
            status, message, headers = exc.status_code, str(exc.detail), exc.headers
        elif isinstance(exc, RequestValidationError):
            status, message = 422, "Invalid request. Check the field values."
        elif isinstance(exc, AppException):
            status, message = exc.status_code, exc.message
        else:
            logger.error("Request failed: %s %s error_id=%s", request.method, request.url.path, error_id, exc_info=(type(exc), exc, exc.__traceback__))
        return JSONResponse(status_code=status, headers=headers, content={"success": False, "data": None, "message": message, "error": {"code": str(status), "id": error_id}})
    for kind in (HTTPException, RequestValidationError, AppException, Exception):
        app.add_exception_handler(kind, handle)
