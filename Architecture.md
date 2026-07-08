# Architecture — Agentic Travel Recommendations Service (Lean MVP)

Deterministic backend is the source of truth. Three thin front doors (REST, MCP
stdio, CLI) share ONE orchestration brain. The LLM/AI agent is the MCP *client*,
never inside the service — it can request tools but can never enforce partner
rules, authorize access, or invent member facts.

```mermaid
flowchart TD
  RESTClient[REST API Client] --> API[FastAPI App]
  CLIUser[CLI Demo User] --> CLI[cli/demo.py]
  Agent[AI Agent / MCP Inspector] --> MCP[FastMCP stdio Server]

  API --> RecRoute[POST /recommendations]
  RecRoute --> Ctx1[Build AgentContext source=rest from headers]
  CLI --> Ctx2[Build AgentContext source=cli from args]
  MCP --> Tools[get_member_profile / get_recommendations]
  Tools --> Ctx3[Build AgentContext source=mcp from launch env]

  Ctx1 --> Service[RecommendationService — shared brain]
  Ctx2 --> Service
  Ctx3 --> Service

  Service --> Member[MemberService.get member_id]
  Member -->|unknown| ErrUnknown[UnknownMemberError 404]
  Member --> Guard[TenantGuard.authorize ctx, member]
  Guard -->|partner mismatch| ErrAuth[AuthorizationDeniedError 403]
  Guard --> Config[PartnerConfigService.get partner_id — READ ONLY]
  Config -->|missing| ErrConfig[MissingPartnerConfigError 404]
  Config --> Gen[RecommendationGenerator.generate — deterministic, rule-unaware]
  Gen --> Candidates[Candidate Recommendations incl. Platinum Cruise]
  Candidates --> Engine[RuleEngine.apply]

  Engine --> R1[1. CategoryExclusionRule]
  R1 --> R2[2. MaxRecommendationsRule]
  R2 --> Final[Final Recommendations + RuleMetadata]

  Final --> Resp[RecommendationResponse — Pydantic validated]
  Resp --> RecRoute
  Resp --> Tools
  Resp --> CLI

  Service --> Logs[Structured JSON logs — PII-safe fields]
  Tools -->|domain error| ToolErr[Safe MCP ToolError: error_code, message, request_id]

  MockMembers[(Mock Member Data)] --> Member
  MockConfig[(Mock Partner Config)] --> Config

  Tests[pytest unit + integration] --> Service
  Evals[pytest evals: isolation, cruise, cap, fail-closed] --> Service
  Evals --> Tools
```

## Key properties

- **One shared brain.** REST, MCP, and CLI all call `RecommendationService`. MCP
  tools are ~10 lines each and contain no business logic.
- **Guard on every member access.** Both `get_recommendations` and
  `get_member_profile` run `MemberService.get` → `TenantGuard.authorize` before
  returning anything. No front door reaches `MemberService` without the guard.
- **Fixed rule order:** category exclusions first, then caps. Proven by a named
  test (`test_exclusion_runs_before_cap`).
- **Fail closed:** unknown member, missing config, tenant mismatch, or schema
  failure → safe structured error. No stack traces or raw PII anywhere.
- **Deterministic:** no LLM, no clock, no randomness in the recommendation path.
  No API key needed to run, test, or demo.
- **Observability is AWS/Azure-native** (structured JSON logs; production framing
  = CloudWatch/App Insights, X-Ray/OpenTelemetry). No third-party platform.

See `docs/superpowers/2026-07-08-agentic-travel-recs-design.md` for the full
design and `docs/superpowers/plans/2026-07-08-agentic-travel-recs.md` for the
implementation plan.
