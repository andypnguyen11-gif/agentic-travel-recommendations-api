import pytest

from app.models.common import LoyaltyTier
from app.models.errors import UnknownMemberError
from app.services.member_service import MemberService


def test_known_member_returns_profile():
    svc = MemberService()
    m = svc.get("M-plat-nocruise")
    assert m.loyalty_tier is LoyaltyTier.PLATINUM
    assert m.partner_id == "partner_no_cruise"
    assert len(m.travel_history) <= 5


def test_members_span_multiple_partners():
    svc = MemberService()
    partners = {svc.get(mid).partner_id for mid in svc.MEMBERS}
    assert {"partner_capped", "partner_unlimited", "partner_no_cruise"} <= partners


def test_unknown_member_raises():
    svc = MemberService()
    with pytest.raises(UnknownMemberError):
        svc.get("M-nope")
