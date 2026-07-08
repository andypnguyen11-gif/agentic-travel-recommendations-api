from app.models.common import Category, Source
from app.security.context import build_context
from app.dependencies import get_recommendation_service


def test_cruise_never_appears_for_excluding_partner_even_for_platinum():
    svc = get_recommendation_service()
    ctx = build_context(agent_id="a", partner_id="partner_no_cruise", source=Source.CLI)
    resp = svc.get_recommendations(ctx, "M-plat-nocruise")
    assert all(r.category is not Category.CRUISE for r in resp.recommendations)
    removed_cats = {rr.category for rr in resp.rule_metadata.removed_recommendations}
    assert Category.CRUISE in removed_cats  # it was generated, then removed
