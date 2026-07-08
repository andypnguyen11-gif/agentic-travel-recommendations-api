from functools import lru_cache

from app.rules.rule_engine import RuleEngine
from app.services.member_service import MemberService
from app.services.partner_config_service import PartnerConfigService
from app.services.recommendation_generator import RecommendationGenerator
from app.services.recommendation_service import RecommendationService


@lru_cache
def get_recommendation_service() -> RecommendationService:
    return RecommendationService(
        member_service=MemberService(),
        partner_config_service=PartnerConfigService(),
        generator=RecommendationGenerator(),
        rule_engine=RuleEngine(),
    )
