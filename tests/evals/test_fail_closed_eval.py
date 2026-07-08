import pytest

from app.models.common import Source
from app.models.errors import MissingPartnerConfigError, UnknownMemberError
from app.security.context import build_context
from app.dependencies import get_recommendation_service


def _ctx(partner_id):
    return build_context(agent_id="a", partner_id=partner_id, source=Source.CLI)


def test_unknown_member_fails_closed():
    svc = get_recommendation_service()
    with pytest.raises(UnknownMemberError):
        svc.get_recommendations(_ctx("partner_capped"), "M-nope")


def test_missing_partner_config_fails_closed():
    svc = get_recommendation_service()
    with pytest.raises(MissingPartnerConfigError):
        svc.get_recommendations(_ctx("partner_missing"), "M-orphan")
