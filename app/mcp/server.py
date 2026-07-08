import json
import os
from typing import Callable

from mcp.server.fastmcp import FastMCP

try:  # SDK-provided tool error; fall back to a local type if unavailable.
    from mcp.server.fastmcp.exceptions import ToolError
except Exception:  # pragma: no cover - version-dependent import guard
    class ToolError(Exception):
        pass

from app.dependencies import get_recommendation_service
from app.models.common import Source
from app.models.errors import DomainError, ErrorCode, ErrorResponse
from app.security.context import AgentContext, build_context

mcp = FastMCP("agentic-travel-recs")
_service = get_recommendation_service()


def _context() -> AgentContext:
    # Caller identity comes from the trusted MCP launch environment. One server
    # process is scoped to one partner/agent session. request_id is per call.
    return build_context(
        agent_id=os.environ.get("AGENT_ID", "unknown-agent"),
        partner_id=os.environ.get("PARTNER_ID", ""),
        source=Source.MCP,
    )


def _run(tool_name: str, fn: Callable[[AgentContext], object]) -> dict:
    ctx = _context()
    try:
        return fn(ctx).model_dump(mode="json")
    except DomainError as exc:
        payload = ErrorResponse(
            error_code=exc.error_code, message=exc.message, request_id=ctx.request_id
        ).model_dump(mode="json")
        raise ToolError(json.dumps(payload)) from None
    except Exception:
        payload = ErrorResponse(
            error_code=ErrorCode.TOOL_EXECUTION_ERROR,
            message="Internal tool error.",
            request_id=ctx.request_id,
        ).model_dump(mode="json")
        raise ToolError(json.dumps(payload)) from None


def get_member_profile(member_id: str) -> dict:
    """Return a member's loyalty tier and travel history if the caller's partner
    scope is authorized for that member."""
    return _run("get_member_profile", lambda ctx: _service.get_member_profile(ctx, member_id))


def get_recommendations(member_id: str) -> dict:
    """Return partner-rule-compliant travel recommendations for a member, with
    rule metadata describing which offers were removed and why."""
    return _run("get_recommendations", lambda ctx: _service.get_recommendations(ctx, member_id))


# Register with FastMCP for agent discovery/invocation. Registration returns the
# original function, so the names above remain directly callable in tests.
mcp.tool()(get_member_profile)
mcp.tool()(get_recommendations)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
