import json

import pytest

from app.mcp import server as mcp_server
from app.mcp.server import ToolError, get_member_profile, get_recommendations


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("PARTNER_ID", raising=False)
    monkeypatch.delenv("AGENT_ID", raising=False)


def _set_partner(monkeypatch, partner_id):
    monkeypatch.setenv("PARTNER_ID", partner_id)
    monkeypatch.setenv("AGENT_ID", "agent-mcp")


def test_get_recommendations_tool_returns_dict(monkeypatch):
    _set_partner(monkeypatch, "partner_capped")
    out = get_recommendations("M-silver-capped")
    assert out["partner_id"] == "partner_capped"
    assert len(out["recommendations"]) <= 3
    assert "rule_metadata" in out


def test_mcp_cannot_bypass_rule_engine(monkeypatch):
    _set_partner(monkeypatch, "partner_no_cruise")
    out = get_recommendations("M-plat-nocruise")
    cats = [r["category"] for r in out["recommendations"]]
    assert "Cruise" not in cats


def test_get_member_profile_tool_returns_safe_profile(monkeypatch):
    _set_partner(monkeypatch, "partner_no_cruise")
    out = get_member_profile("M-plat-nocruise")
    assert out["member_id"] == "M-plat-nocruise"
    assert out["loyalty_tier"] == "Platinum"


def test_get_member_profile_cross_partner_raises_safe_error(monkeypatch):
    _set_partner(monkeypatch, "partner_capped")  # wrong partner for this member
    with pytest.raises(ToolError) as exc:
        get_member_profile("M-plat-nocruise")
    payload = json.loads(str(exc.value))
    assert payload["error_code"] == "AUTHORIZATION_DENIED"
    assert "request_id" in payload


def test_unknown_member_raises_safe_error(monkeypatch):
    _set_partner(monkeypatch, "partner_capped")
    with pytest.raises(ToolError) as exc:
        get_recommendations("M-nope")
    payload = json.loads(str(exc.value))
    assert payload["error_code"] == "UNKNOWN_MEMBER"


def test_tools_are_registered_with_fastmcp():
    # discovery surface: both tool names exist on the server
    names = {t.name for t in mcp_server.mcp._tool_manager.list_tools()}
    assert {"get_member_profile", "get_recommendations"} <= names
