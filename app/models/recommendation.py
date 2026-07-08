from pydantic import BaseModel, ConfigDict, Field

from app.models.common import Category, LoyaltyTier


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str
    category: Category
    title: str
    reason: str
    score: float


class RemovedRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str
    category: Category
    rule: str


class RuleMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applied_rules: list[str] = Field(default_factory=list)
    excluded_categories: list[Category] = Field(default_factory=list)
    removed_recommendations: list[RemovedRecommendation] = Field(default_factory=list)
    candidate_count: int
    final_count: int
    max_allowed: int | None


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: str
    partner_id: str
    loyalty_tier: LoyaltyTier
    request_id: str
    recommendations: list[Recommendation]
    rule_metadata: RuleMetadata


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: str
