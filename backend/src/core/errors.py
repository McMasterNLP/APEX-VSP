"""Application error hierarchy and handlers."""

from typing import Any, Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error."""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(AppError):
    """Authentication failed error."""
    
    def __init__(self, message: str = "Authentication failed", details: Optional[dict[str, Any]] = None):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED, details)


class AuthorizationError(AppError):
    """Authorization failed error."""
    
    def __init__(self, message: str = "Not authorized", details: Optional[dict[str, Any]] = None):
        super().__init__(message, status.HTTP_403_FORBIDDEN, details)


class NotFoundError(AppError):
    """Resource not found error."""
    
    def __init__(self, message: str = "Resource not found", details: Optional[dict[str, Any]] = None):
        super().__init__(message, status.HTTP_404_NOT_FOUND, details)


class ValidationError(AppError):
    """Validation error."""
    
    def __init__(self, message: str = "Validation failed", details: Optional[dict[str, Any]] = None):
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class ConflictError(AppError):
    """Conflict error (e.g., duplicate resource)."""
    
    def __init__(self, message: str = "Resource conflict", details: Optional[dict[str, Any]] = None):
        super().__init__(message, status.HTTP_409_CONFLICT, details)


class ExternalServiceError(AppError):
    """External service error (LLM, TTS, etc.)."""
    
    def __init__(self, message: str = "External service error", details: Optional[dict[str, Any]] = None):
        super().__init__(message, status.HTTP_503_SERVICE_UNAVAILABLE, details)


class UsageLimitExceededError(AppError):
    """Raised when a metered action would exceed a per-user or global daily cap.

    Deliberately a plain AppError subclass (not a research-specific error like
    ResearchEvaluationRunServiceError) so every enforcement point -- chat
    turns, audio, and live evaluations alike -- surfaces the same error shape
    to the frontend.
    """

    def __init__(self, message: str = "Daily usage limit reached", details: Optional[dict[str, Any]] = None):
        super().__init__(message, status.HTTP_429_TOO_MANY_REQUESTS, details)


# Error handlers
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle application errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "message": exc.detail,
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
        },
    )

