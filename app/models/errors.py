from enum import Enum

from pydantic import BaseModel, ConfigDict


class ErrorCode(str, Enum):
    UNKNOWN_MEMBER = "UNKNOWN_MEMBER"
    MISSING_PARTNER_CONFIG = "MISSING_PARTNER_CONFIG"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: ErrorCode
    message: str
    request_id: str


class DomainError(Exception):
    """Base for safe, classified domain failures."""

    error_code: ErrorCode = ErrorCode.TOOL_EXECUTION_ERROR
    http_status: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnknownMemberError(DomainError):
    error_code = ErrorCode.UNKNOWN_MEMBER
    http_status = 404


class MissingPartnerConfigError(DomainError):
    error_code = ErrorCode.MISSING_PARTNER_CONFIG
    http_status = 404


class AuthorizationDeniedError(DomainError):
    error_code = ErrorCode.AUTHORIZATION_DENIED
    http_status = 403
