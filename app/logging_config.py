import json
import logging

from app.security.context import AgentContext


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "message": record.getMessage()}
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def safe_log_fields(
    ctx: AgentContext,
    *,
    tool_name: str,
    outcome: str,
    applied_rules: list[str] | None = None,
    removed_count: int = 0,
    latency_ms: float = 0.0,
    failure_reason: str | None = None,
) -> dict:
    """Allowlisted, PII-safe log fields. Member IDs, full profiles, travel history,
    and recommendation reasons are intentionally excluded from logs.
    Production would apply arrivia-approved redaction/tokenization."""
    return {
        "request_id": ctx.request_id,
        "source": ctx.source.value,
        "agent_id": ctx.agent_id,
        "partner_id": ctx.partner_id,
        "tool_name": tool_name,
        "applied_rules": applied_rules or [],
        "removed_count": removed_count,
        "outcome": outcome,
        "latency_ms": latency_ms,
        "failure_reason": failure_reason,
    }
