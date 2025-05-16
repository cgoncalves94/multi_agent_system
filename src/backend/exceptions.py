"""Custom exceptions for the chat application."""

from fastapi import HTTPException, status


class AppError(HTTPException):
    """Base class for application errors."""

    def __init__(self, detail: str, code: str):
        """Initialize the AppError.

        Args:
            detail: Human-readable error message
            code: Machine-readable error code
        """
        super().__init__(status_code=self.status_code, detail=detail)
        self.code = code


class NotFoundError(AppError):
    """Resource not found error."""

    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    """Resource conflict error."""

    status_code = status.HTTP_409_CONFLICT


class ValidationError(AppError):
    """Validation error."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class InternalServerError(AppError):
    """Internal server error."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
