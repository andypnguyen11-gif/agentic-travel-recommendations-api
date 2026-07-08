from dataclasses import dataclass
from typing import Protocol

from app.models.partner_config import PartnerConfig
from app.models.recommendation import Recommendation, RemovedRecommendation


@dataclass
class RuleOutcome:
    kept: list[Recommendation]
    removed: list[RemovedRecommendation]
    applied: bool


class Rule(Protocol):
    name: str

    def apply(self, candidates: list[Recommendation], config: PartnerConfig) -> RuleOutcome: ...
