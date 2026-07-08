import json
import logging

from app.models.common import Source
from app.security.context import build_context
from app.logging_config import safe_log_fields, _JsonFormatter, configure_logging


def test_safe_log_fields_allowlist_only():
    ctx = build_context(agent_id="a", partner_id="p", source=Source.REST, request_id="r1")
    fields = safe_log_fields(
        ctx,
        tool_name="get_recommendations",
        outcome="ok",
        applied_rules=["category_exclusion"],
        removed_count=2,
        latency_ms=1.5,
    )
    assert fields["request_id"] == "r1"
    assert fields["partner_id"] == "p"
    assert fields["tool_name"] == "get_recommendations"
    assert fields["applied_rules"] == ["category_exclusion"]
    allowed = {
        "request_id", "source", "agent_id", "partner_id", "tool_name",
        "applied_rules", "removed_count", "outcome", "latency_ms", "failure_reason",
    }
    assert set(fields) <= allowed


def test_safe_log_fields_never_leaks_pii_keys():
    ctx = build_context(agent_id="a", partner_id="p", source=Source.REST)
    fields = safe_log_fields(ctx, tool_name="t", outcome="ok")
    for banned in ("travel_history", "reason", "recommendations", "preferences", "destination"):
        assert banned not in fields


def test_json_formatter_formats_record_with_fields():
    """Test _JsonFormatter directly: merges record fields into JSON payload."""
    formatter = _JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )
    record.fields = {"partner_id": "p", "outcome": "ok"}

    result = formatter.format(record)
    payload = json.loads(result)

    assert payload["level"] == "INFO"
    assert payload["message"] == "test message"
    assert payload["partner_id"] == "p"
    assert payload["outcome"] == "ok"


def test_configure_logging_sets_root_logger_state():
    """Test configure_logging: sets one handler with _JsonFormatter and correct level.

    Saves/restores root logger state to prevent pollution of other tests.
    """
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level

    try:
        configure_logging("DEBUG")

        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert isinstance(handler.formatter, _JsonFormatter)
        assert root.level == logging.DEBUG
    finally:
        root.handlers = original_handlers
        root.level = original_level
