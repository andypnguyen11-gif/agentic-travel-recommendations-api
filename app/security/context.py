import uuid

from pydantic import BaseModel, ConfigDict

from app.models.common import Source


class AgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    agent_id: str
    partner_id: str
    source: Source


def build_context(
    *,
    agent_id: str,
    partner_id: str,
    source: Source,
    request_id: str | None = None,
) -> AgentContext:
    return AgentContext(
        request_id=request_id or uuid.uuid4().hex,
        agent_id=agent_id,
        partner_id=partner_id,
        source=source,
    )
