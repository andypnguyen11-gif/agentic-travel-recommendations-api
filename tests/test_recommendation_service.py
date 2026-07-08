import pytest

from app.models.common import Category, LoyaltyTier, Source
from app.models.errors import (
    AuthorizationDeniedError,
    MissingPartnerConfigError,
    UnknownMemberError,
)
from app.security.context import build_context
from app.dependencies import get_recommendation_service


def _ctx(partner_id):
    return build_context(agent_id="a", partner_id=partner_id, source=Source.CLI)


def test_full_recommendation_flow():
    svc = get_recommendation_service()
    resp = svc.get_recommendations(_ctx("partner_capped"), "M-silver-capped")
    assert resp.member_id == "M-silver-capped"
    assert resp.partner_id == "partner_capped"
    assert len(resp.recommendations) <= 3
    assert resp.request_id


def test_cruise_excluded_for_platinum_member():
    svc = get_recommendation_service()
    resp = svc.get_recommendations(_ctx("partner_no_cruise"), "M-plat-nocruise")
    assert all(r.category is not Category.CRUISE for r in resp.recommendations)
    assert "category_exclusion" in resp.rule_metadata.applied_rules


def test_cap_enforced_for_capped_partner():
    svc = get_recommendation_service()
    resp = svc.get_recommendations(_ctx("partner_capped"), "M-plat-capped")
    assert len(resp.recommendations) <= 3


def test_get_member_profile_authorized():
    svc = get_recommendation_service()
    prof = svc.get_member_profile(_ctx("partner_no_cruise"), "M-plat-nocruise")
    assert prof.member_id == "M-plat-nocruise"
    assert prof.loyalty_tier is LoyaltyTier.PLATINUM


def test_get_recommendations_cross_partner_denied():
    svc = get_recommendation_service()
    with pytest.raises(AuthorizationDeniedError):
        svc.get_recommendations(_ctx("partner_unlimited"), "M-plat-nocruise")


def test_get_member_profile_cross_partner_denied():
    svc = get_recommendation_service()
    with pytest.raises(AuthorizationDeniedError):
        svc.get_member_profile(_ctx("partner_unlimited"), "M-plat-nocruise")


def test_unknown_member_raises():
    svc = get_recommendation_service()
    with pytest.raises(UnknownMemberError):
        svc.get_recommendations(_ctx("partner_capped"), "M-nope")


def test_missing_partner_config_raises():
    svc = get_recommendation_service()
    with pytest.raises(MissingPartnerConfigError):
        svc.get_recommendations(_ctx("partner_missing"), "M-orphan")
