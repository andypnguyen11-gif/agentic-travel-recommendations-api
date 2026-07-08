from app.models.errors import AuthorizationDeniedError
from app.models.member import MemberProfile
from app.security.context import AgentContext


def authorize(ctx: AgentContext, member: MemberProfile) -> None:
    """Fail closed if the caller's partner scope does not match the member's."""
    if ctx.partner_id != member.partner_id:
        raise AuthorizationDeniedError("Caller is not authorized for this member's partner.")
