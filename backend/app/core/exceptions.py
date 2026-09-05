"""
Centralized exception handling and error types for the AI Workflow Simulation Engine.

Provides clean, consistent error responses without exposing internal stack traces.
"""
from __future__ import annotations

import logging
import traceback
from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base application exception with HTTP status code and user-friendly message."""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        error_code: Optional[str] = None,
        details: Optional[dict] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppException):
    """Resource not found."""
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": str(identifier)},
        )


class UnauthorizedError(AppException):
    """Unauthorized access."""
    def __init__(self, message: str = "Unauthorized access"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
        )


class ForbiddenError(AppException):
    """Forbidden access - authenticated but not authorized."""
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN",
        )


class ValidationError(AppException):
    """Input validation error."""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            details=details,
        )


class InvalidStateError(AppException):
    """Invalid state transition or business rule violation."""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="INVALID_STATE",
            details=details,
        )


class DependencyBlockedError(AppException):
    """Task dependency not satisfied."""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="DEPENDENCY_BLOCKED",
            details=details,
        )


class FileError(AppException):
    """File-related errors (invalid, oversized, unsupported, storage failure)."""
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code="FILE_ERROR",
            details=details,
        )


class DuplicateSubmissionError(AppException):
    """Duplicate submission attempt."""
    def __init__(self, message: str = "Submission already exists"):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="DUPLICATE_SUBMISSION",
        )


class AIError(AppException):
    """AI service errors."""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="AI_ERROR",
            details=details,
        )


class MalformedAIResponseError(AppException):
    """AI response validation failed."""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="MALFORMED_AI_RESPONSE",
            details=details,
        )


class StorageError(AppException):
    """Storage system failure."""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="STORAGE_ERROR",
            details=details,
        )


class DatabaseError(AppException):
    """Database operation failure."""
    def __init__(self, message: str = "Database operation failed", details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DATABASE_ERROR",
            details=details,
        )


class WorkflowError(AppException):
    """Invalid workflow transition."""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="WORKFLOW_ERROR",
            details=details,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application."""
    
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            f"AppException: {exc.error_code} - {exc.message}",
            extra={"error_code": exc.error_code, "details": exc.details, "path": str(request.url)}
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        )
    
    @app.exception_handler(ValidationError)
    async def pydantic_validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        logger.warning(f"ValidationError: {exc.errors()}", extra={"path": str(request.url)})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()},
            },
        )
    
    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.error(f"IntegrityError: {exc.orig}", extra={"path": str(request.url)}, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "INTEGRITY_ERROR",
                "message": "Data integrity violation - duplicate or constraint violation",
                "details": {},
            },
        )
    
    @app.exception_handler(OperationalError)
    async def operational_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
        logger.error(f"OperationalError: {exc.orig}", extra={"path": str(request.url)}, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "DATABASE_UNAVAILABLE",
                "message": "Database temporarily unavailable",
                "details": {},
            },
        )
    
    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error(f"SQLAlchemyError: {exc}", extra={"path": str(request.url)}, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "DATABASE_ERROR",
                "message": "Database operation failed",
                "details": {},
            },
        )
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all handler - logs full traceback server-side, returns generic message to client."""
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {exc}",
            extra={"path": str(request.url)},
            exc_info=True
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {},
            },
        )