import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import health, recommendations
from app.config import settings
from app.logging_config import configure_logging
from app.models.errors import ErrorCode, ErrorResponse

configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name)
app.include_router(health.router)
app.include_router(recommendations.router)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed.",
            request_id=request_id,
        ).model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def unexpected_handler(request: Request, exc: Exception):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code=ErrorCode.TOOL_EXECUTION_ERROR,
            message="Internal server error.",
            request_id=request_id,
        ).model_dump(mode="json"),
    )
