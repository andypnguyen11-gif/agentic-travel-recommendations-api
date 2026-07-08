from app.models.partner_config import PartnerConfig
from app.models.recommendation import Recommendation, RemovedRecommendation, RuleMetadata
from app.rules.base import Rule
from app.rules.category_exclusion_rule import CategoryExclusionRule
from app.rules.max_recommendations_rule import MaxRecommendationsRule


class RuleEngine:
    """Ordered, deterministic rule pipeline. Exclusions run before caps."""

    def __init__(self, rules: list[Rule] | None = None) -> None:
        self.rules: list[Rule] = rules if rules is not None else [
            CategoryExclusionRule(),
            MaxRecommendationsRule(),
        ]

    def apply(
        self, candidates: list[Recommendation], config: PartnerConfig
    ) -> tuple[list[Recommendation], RuleMetadata]:
        applied_rules: list[str] = []
        removed_all: list[RemovedRecommendation] = []
        current = list(candidates)

        for rule in self.rules:
            outcome = rule.apply(current, config)
            current = outcome.kept
            removed_all.extend(outcome.removed)
            if outcome.applied:
                applied_rules.append(rule.name)

        meta = RuleMetadata(
            applied_rules=applied_rules,
            excluded_categories=list(config.excluded_categories),
            removed_recommendations=removed_all,
            candidate_count=len(candidates),
            final_count=len(current),
            max_allowed=config.max_recommendations,
        )
        return current, meta
