from dataclasses import dataclass, field
from typing import Any, Optional
from fastapi import HTTPException

class AppException(Exception):
    def __init__(self, message: str, error_code: str, status_code: int = 400, details: Optional[dict] = None):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "success": False,
            "data": None,
            "message": self.message,
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details
            }
        }

class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", error_code: str = "NOT_FOUND", details: Optional[dict] = None):
        super().__init__(message, error_code, 404, details)

class ValidationException(AppException):
    def __init__(self, message: str = "Validation error", error_code: str = "VALIDATION_ERROR", details: Optional[dict] = None):
        super().__init__(message, error_code, 422, details)

class AuthenticationException(AppException):
    def __init__(self, message: str = "Authentication required", error_code: str = "AUTHENTICATION_REQUIRED", details: Optional[dict] = None):
        super().__init__(message, error_code, 401, details)

class AuthorizationException(AppException):
    def __init__(self, message: str = "Insufficient permissions", error_code: str = "FORBIDDEN", details: Optional[dict] = None):
        super().__init__(message, error_code, 403, details)

class ConflictException(AppException):
    def __init__(self, message: str = "Resource already exists", error_code: str = "CONFLICT", details: Optional[dict] = None):
        super().__init__(message, error_code, 409, details)

class RateLimitException(AppException):
    def __init__(self, message: str = "Rate limit exceeded", error_code: str = "RATE_LIMIT_EXCEEDED", details: Optional[dict] = None):
        super().__init__(message, error_code, 429, details)

class ExternalServiceException(AppException):
    def __init__(self, message: str = "External service error", error_code: str = "EXTERNAL_SERVICE_ERROR", details: Optional[dict] = None):
        super().__init__(message, error_code, 503, details)

class VideoProcessingException(AppException):
    def __init__(self, message: str = "Video processing failed", error_code: str = "VIDEO_PROCESSING_ERROR", details: Optional[dict] = None):
        super().__init__(message, error_code, 500, details)

class PaymentException(AppException):
    def __init__(self, message: str = "Payment failed", error_code: str = "PAYMENT_ERROR", details: Optional[dict] = None):
        super().__init__(message, error_code, 402, details)

class WorkerException(AppException):
    def __init__(self, message: str = "Worker processing failed", error_code: str = "WORKER_ERROR", details: Optional[dict] = None):
        super().__init__(message, error_code, 500, details)
