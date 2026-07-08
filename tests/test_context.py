from app.models.common import Source
from app.security.context import AgentContext, build_context


def test_build_context_generates_request_id():
    ctx = build_context(agent_id="a", partner_id="p", source=Source.REST)
    assert ctx.request_id
    assert ctx.partner_id == "p"
    assert ctx.source is Source.REST


def test_build_context_keeps_provided_request_id():
    ctx = build_context(agent_id="a", partner_id="p", source=Source.MCP, request_id="req-9")
    assert ctx.request_id == "req-9"


def test_build_context_unique_ids_per_call():
    a = build_context(agent_id="a", partner_id="p", source=Source.MCP)
    b = build_context(agent_id="a", partner_id="p", source=Source.MCP)
    assert a.request_id != b.request_id


def test_context_is_frozen():
    ctx = AgentContext(request_id="r", agent_id="a", partner_id="p", source=Source.CLI)
    try:
        ctx.partner_id = "other"
        assert False, "expected frozen model to reject mutation"
    except Exception:
        pass
