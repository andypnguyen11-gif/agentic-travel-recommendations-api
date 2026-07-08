import argparse
import sys

from app.dependencies import get_recommendation_service
from app.models.common import Source
from app.models.errors import DomainError
from app.security.context import build_context


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Agentic Travel Recommendations demo")
    parser.add_argument("--member-id", required=True)
    parser.add_argument("--partner-id", required=True)
    parser.add_argument("--agent-id", default="cli-demo")
    args = parser.parse_args(argv)

    ctx = build_context(agent_id=args.agent_id, partner_id=args.partner_id, source=Source.CLI)
    service = get_recommendation_service()

    try:
        resp = service.get_recommendations(ctx, args.member_id)
    except DomainError as exc:
        print(f"[error] {exc.error_code.value}: {exc.message} (request_id={ctx.request_id})")
        return 1

    print(f"Member:  {resp.member_id}")
    print(f"Partner: {resp.partner_id}")
    print(f"Tier:    {resp.loyalty_tier.value}")
    print(f"Applied rules: {', '.join(resp.rule_metadata.applied_rules) or 'none'}")
    print("Recommendations:")
    for rec in resp.recommendations:
        print(f"  - [{rec.category.value}] {rec.title} (score {rec.score})")
    print(f"Removed {len(resp.rule_metadata.removed_recommendations)} candidate(s):")
    for rr in resp.rule_metadata.removed_recommendations:
        print(f"  - {rr.recommendation_id} [{rr.category.value}] by {rr.rule}")
    return 0


def main() -> None:
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
