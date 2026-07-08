from app.models.partner_config import PartnerConfig
from app.models.recommendation import Recommendation, RemovedRecommendation
from app.rules.base import RuleOutcome


class MaxRecommendationsRule:
    name = "max_recommendations"

    def apply(self, candidates: list[Recommendation], config: PartnerConfig) -> RuleOutcome:
        if config.max_recommendations is None:
            return RuleOutcome(kept=list(candidates), removed=[], applied=False)

        limit = config.max_recommendations
        kept = candidates[:limit]
        removed = [
            RemovedRecommendation(
                recommendation_id=rec.recommendation_id, category=rec.category, rule=self.name
            )
            for rec in candidates[limit:]
        ]
        return RuleOutcome(kept=kept, removed=removed, applied=True)
