from datetime import date

import pytest
from pydantic import ValidationError

from app.models.common import Category, LoyaltyTier, Source, stable_id
from app.models.member import MemberProfile, MemberProfileOutput, TravelHistoryItem
from app.models.partner_config import PartnerConfig
from app.models.recommendation import (
    Recommendation,
    RecommendationResponse,
    RemovedRecommendation,
    RuleMetadata,
)
from app.models.errors import (
    AuthorizationDeniedError,
    ErrorCode,
    ErrorResponse,
    MissingPartnerConfigError,
    UnknownMemberError,
)


def _history():
    return TravelHistoryItem(
        destination="Lisbon",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 5),
        booking_type=Category.HOTEL,
    )


def test_stable_id_is_deterministic():
    assert stable_id("Hotel", "Lisbon") == stable_id("Hotel", "Lisbon")
    assert stable_id("Hotel", "Lisbon") != stable_id("Flight", "Lisbon")


def test_member_profile_valid():
    m = MemberProfile(
        member_id="M1",
        partner_id="partner_capped",
        loyalty_tier=LoyaltyTier.GOLD,
        travel_history=[_history()],
    )
    assert m.loyalty_tier is LoyaltyTier.GOLD


def test_member_profile_rejects_more_than_five_history_items():
    with pytest.raises(ValidationError):
        MemberProfile(
            member_id="M1",
            partner_id="p",
            loyalty_tier=LoyaltyTier.GOLD,
            travel_history=[_history() for _ in range(6)],
        )


def test_member_profile_rejects_bad_tier():
    with pytest.raises(ValidationError):
        MemberProfile(
            member_id="M1",
            partner_id="p",
            loyalty_tier="Bronze",
            travel_history=[],
        )


def test_models_forbid_extra_fields():
    with pytest.raises(ValidationError):
        PartnerConfig(partner_id="p", excluded_categories=[], max_recommendations=3, surprise=1)


def test_partner_config_unlimited_defaults():
    c = PartnerConfig(partner_id="p")
    assert c.max_recommendations is None
    assert c.excluded_categories == []


def test_recommendation_response_round_trips():
    resp = RecommendationResponse(
        member_id="M1",
        partner_id="p",
        loyalty_tier=LoyaltyTier.SILVER,
        request_id="req-1",
        recommendations=[
            Recommendation(
                recommendation_id="r1",
                category=Category.HOTEL,
                title="Hotel in Lisbon",
                reason="because",
                score=0.9,
            )
        ],
        rule_metadata=RuleMetadata(
            applied_rules=["category_exclusion"],
            excluded_categories=[Category.CRUISE],
            removed_recommendations=[
                RemovedRecommendation(
                    recommendation_id="rx", category=Category.CRUISE, rule="category_exclusion"
                )
            ],
            candidate_count=2,
            final_count=1,
            max_allowed=None,
        ),
    )
    assert resp.rule_metadata.final_count == 1
    assert resp.recommendations[0].category is Category.HOTEL


def test_source_enum_values():
    assert Source.REST.value == "rest"
    assert Source.MCP.value == "mcp"
    assert Source.CLI.value == "cli"


def test_error_response_and_exceptions():
    err = ErrorResponse(error_code=ErrorCode.UNKNOWN_MEMBER, message="nope", request_id="r")
    assert err.error_code is ErrorCode.UNKNOWN_MEMBER
    assert UnknownMemberError("x").http_status == 404
    assert MissingPartnerConfigError("x").http_status == 404
    assert AuthorizationDeniedError("x").http_status == 403
    assert UnknownMemberError("x").error_code is ErrorCode.UNKNOWN_MEMBER
