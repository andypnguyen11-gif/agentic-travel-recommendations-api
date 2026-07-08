import logging

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from app.dependencies import get_recommendation_service
from app.logging_config import safe_log_fields
from app.models.common import Source
from app.models.errors import DomainError, ErrorResponse
from app.models.recommendation import RecommendationRequest
from app.security.context import build_context
from app.services.recommendation_service import RecommendationService

router = APIRouter()
logger = logging.getLogger("recommendations")


@router.post("/recommendations")
def post_recommendations(
    body: RecommendationRequest,
    x_partner_id: str = Header(...),
    x_agent_id: str = Header(...),
    x_request_id: str | None = Header(default=None),
    service: RecommendationService = Depends(get_recommendation_service),
):
    ctx = build_context(
        agent_id=x_agent_id, partner_id=x_partner_id, source=Source.REST, request_id=x_request_id
    )
    try:
        result = service.get_recommendations(ctx, body.member_id)
        logger.info(
            "recommendations",
            extra={
                "fields": safe_log_fields(
                    ctx,
                    tool_name="get_recommendations",
                    outcome="ok",
                    applied_rules=result.rule_metadata.applied_rules,
                    removed_count=len(result.rule_metadata.removed_recommendations),
                )
            },
        )
        return result
    except DomainError as exc:
        logger.warning(
            "recommendations_error",
            extra={
                "fields": safe_log_fields(
                    ctx,
                    tool_name="get_recommendations",
                    outcome="error",
                    failure_reason=exc.error_code.value,
                )
            },
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=ErrorResponse(
                error_code=exc.error_code, message=exc.message, request_id=ctx.request_id
            ).model_dump(mode="json"),
        )
