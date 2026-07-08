from app.models.common import Category
from app.models.partner_config import PartnerConfig
from app.models.recommendation import Recommendation
from app.rules.category_exclusion_rule import CategoryExclusionRule
from app.rules.max_recommendations_rule import MaxRecommendationsRule
from app.rules.rule_engine import RuleEngine


def _rec(rid, category, score=0.5):
    return Recommendation(
        recommendation_id=rid, category=category, title=rid, reason="r", score=score
    )


def _candidates():
    return [
        _rec("c1", Category.CRUISE),
        _rec("c2", Category.CRUISE),
        _rec("c3", Category.CRUISE),
        _rec("h1", Category.HOTEL),
        _rec("h2", Category.HOTEL),
        _rec("f1", Category.FLIGHT),
    ]


def test_cruise_exclusion_removes_all_cruises():
    cfg = PartnerConfig(partner_id="p", excluded_categories=[Category.CRUISE])
    final, meta = RuleEngine().apply(_candidates(), cfg)
    assert all(r.category is not Category.CRUISE for r in final)
    assert "category_exclusion" in meta.applied_rules
    assert {r.recommendation_id for r in meta.removed_recommendations} >= {"c1", "c2", "c3"}


def test_cap_limits_final_count():
    cfg = PartnerConfig(partner_id="p", max_recommendations=2)
    final, meta = RuleEngine().apply(_candidates(), cfg)
    assert len(final) == 2
    assert meta.final_count == 2
    assert "max_recommendations" in meta.applied_rules


def test_unlimited_partner_passes_everything():
    cfg = PartnerConfig(partner_id="p", max_recommendations=None)
    final, meta = RuleEngine().apply(_candidates(), cfg)
    assert len(final) == len(_candidates())
    assert "max_recommendations" not in meta.applied_rules


def test_exclusion_runs_before_cap():
    # 3 cruises first, then eligible hotels/flight. If cap ran first, the top 3
    # (all cruises) would fill the cap and then be removed, leaving 0. Exclusion
    # first means the cap applies only to eligible offers -> 3 non-cruise results.
    cfg = PartnerConfig(
        partner_id="p", excluded_categories=[Category.CRUISE], max_recommendations=3
    )
    final, meta = RuleEngine().apply(_candidates(), cfg)
    assert len(final) == 3
    assert all(r.category is not Category.CRUISE for r in final)
    assert meta.applied_rules == ["category_exclusion", "max_recommendations"]


def test_removed_records_carry_rule_reason():
    cfg = PartnerConfig(
        partner_id="p", excluded_categories=[Category.CRUISE], max_recommendations=1
    )
    _, meta = RuleEngine().apply(_candidates(), cfg)
    rules_used = {rr.rule for rr in meta.removed_recommendations}
    assert rules_used == {"category_exclusion", "max_recommendations"}


def test_new_rule_can_be_injected_without_touching_generator():
    # A no-op custom rule proves the engine composes an ordered rule list.
    class DropFlights:
        name = "drop_flights"

        def apply(self, candidates, config):
            from app.rules.base import RuleOutcome
            from app.models.recommendation import RemovedRecommendation

            kept, removed = [], []
            for c in candidates:
                if c.category is Category.FLIGHT:
                    removed.append(
                        RemovedRecommendation(
                            recommendation_id=c.recommendation_id, category=c.category, rule=self.name
                        )
                    )
                else:
                    kept.append(c)
            return RuleOutcome(kept, removed, bool(removed))

    engine = RuleEngine(rules=[DropFlights()])
    cfg = PartnerConfig(partner_id="p")
    final, meta = engine.apply(_candidates(), cfg)
    assert all(r.category is not Category.FLIGHT for r in final)
    assert "drop_flights" in meta.applied_rules
