from app.models.common import Category, LoyaltyTier
from app.services.member_service import MemberService
from app.services.recommendation_generator import RecommendationGenerator


def _gen(member_id):
    member = MemberService().get(member_id)
    return RecommendationGenerator().generate(member)


def test_generator_is_deterministic():
    a = _gen("M-gold-unlimited")
    b = _gen("M-gold-unlimited")
    assert [r.recommendation_id for r in a] == [r.recommendation_id for r in b]


def test_platinum_produces_a_cruise_candidate():
    cats = {r.category for r in _gen("M-plat-nocruise")}
    assert Category.CRUISE in cats  # generator is rule-unaware; engine removes it later


def test_generator_output_is_sorted_by_score_then_id():
    recs = _gen("M-gold-unlimited")
    keys = [(-r.score, r.recommendation_id) for r in recs]
    assert keys == sorted(keys)


def test_generator_has_no_duplicate_ids():
    recs = _gen("M-plat-capped")
    ids = [r.recommendation_id for r in recs]
    assert len(ids) == len(set(ids))


def test_silver_does_not_get_cruise_from_tier():
    cats = [r.category for r in _gen("M-silver-capped")]
    # Silver tier catalog has no cruise; and this member has no cruise history
    assert Category.CRUISE not in cats
