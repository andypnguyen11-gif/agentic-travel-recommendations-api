import json

import pytest

from app.models.common import Source
from app.models.errors import AuthorizationDeniedError
from app.security.context import build_context
from app.dependencies import get_recommendation_service
from app.mcp.server import ToolError, get_member_profile, get_recommendations


def _ctx(partner_id):
    return build_context(agent_id="a", partner_id=partner_id, source=Source.CLI)


def test_service_blocks_cross_partner_on_both_methods():
    svc = get_recommendation_service()
    for method in (svc.get_recommendations, svc.get_member_profile):
        with pytest.raises(AuthorizationDeniedError):
            method(_ctx("partner_unlimited"), "M-plat-nocruise")


def test_mcp_blocks_cross_partner_without_leaking_profile(monkeypatch):
    monkeypatch.setenv("PARTNER_ID", "partner_unlimited")  # wrong partner
    monkeypatch.setenv("AGENT_ID", "agent-mcp")
    for tool in (get_recommendations, get_member_profile):
        with pytest.raises(ToolError) as exc:
            tool("M-plat-nocruise")
        payload = json.loads(str(exc.value))
        assert payload["error_code"] == "AUTHORIZATION_DENIED"
        assert "loyalty_tier" not in payload  # no profile data leaked
