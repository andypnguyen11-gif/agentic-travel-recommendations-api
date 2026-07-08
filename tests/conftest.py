import pytest

from app.models.common import Source
from app.security.context import AgentContext, build_context


@pytest.fixture
def make_context():
    def _make(partner_id="partner_capped", agent_id="agent-test", source=Source.CLI) -> AgentContext:
        return build_context(agent_id=agent_id, partner_id=partner_id, source=source)

    return _make
