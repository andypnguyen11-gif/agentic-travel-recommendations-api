from app.models.common import Source
from app.security.context import build_context
from app.dependencies import get_recommendation_service


def test_final_count_never_exceeds_partner_max():
    svc = get_recommendation_service()
    ctx = build_context(agent_id="a", partner_id="partner_capped", source=Source.CLI)
    for member_id in ("M-silver-capped", "M-plat-capped"):
        resp = svc.get_recommendations(ctx, member_id)
        assert len(resp.recommendations) <= 3
        assert resp.rule_metadata.max_allowed == 3
