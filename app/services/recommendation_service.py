from app.models.member import MemberProfileOutput
from app.models.recommendation import RecommendationResponse
from app.security.context import AgentContext
from app.security.tenant_guard import authorize
from app.services.member_service import MemberService
from app.services.partner_config_service import PartnerConfigService
from app.services.recommendation_generator import RecommendationGenerator
from app.rules.rule_engine import RuleEngine


class RecommendationService:
    """The single shared brain. Every member access runs the tenant guard
    before any data is returned."""

    def __init__(
        self,
        member_service: MemberService,
        partner_config_service: PartnerConfigService,
        generator: RecommendationGenerator,
        rule_engine: RuleEngine,
    ) -> None:
        self._members = member_service
        self._configs = partner_config_service
        self._generator = generator
        self._rules = rule_engine

    def get_member_profile(self, ctx: AgentContext, member_id: str) -> MemberProfileOutput:
        member = self._members.get(member_id)          # unknown -> UnknownMemberError
        authorize(ctx, member)                         # mismatch -> AuthorizationDeniedError
        return MemberProfileOutput(
            member_id=member.member_id,
            partner_id=member.partner_id,
            loyalty_tier=member.loyalty_tier,
            travel_history=member.travel_history,
        )

    def get_recommendations(self, ctx: AgentContext, member_id: str) -> RecommendationResponse:
        member = self._members.get(member_id)          # unknown -> UnknownMemberError
        authorize(ctx, member)                         # mismatch -> AuthorizationDeniedError
        config = self._configs.get(member.partner_id)  # missing -> MissingPartnerConfigError
        candidates = self._generator.generate(member)
        final, meta = self._rules.apply(candidates, config)
        return RecommendationResponse(
            member_id=member.member_id,
            partner_id=member.partner_id,
            loyalty_tier=member.loyalty_tier,
            request_id=ctx.request_id,
            recommendations=final,
            rule_metadata=meta,
        )
