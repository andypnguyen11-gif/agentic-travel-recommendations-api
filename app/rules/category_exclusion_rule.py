from app.models.partner_config import PartnerConfig
from app.models.recommendation import Recommendation, RemovedRecommendation
from app.rules.base import RuleOutcome


class CategoryExclusionRule:
    name = "category_exclusion"

    def apply(self, candidates: list[Recommendation], config: PartnerConfig) -> RuleOutcome:
        if not config.excluded_categories:
            return RuleOutcome(kept=list(candidates), removed=[], applied=False)

        excluded = set(config.excluded_categories)
        kept: list[Recommendation] = []
        removed: list[RemovedRecommendation] = []
        for rec in candidates:
            if rec.category in excluded:
                removed.append(
                    RemovedRecommendation(
                        recommendation_id=rec.recommendation_id, category=rec.category, rule=self.name
                    )
                )
            else:
                kept.append(rec)
        return RuleOutcome(kept=kept, removed=removed, applied=True)
