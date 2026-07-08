# Product Requirements Document (PRD) — Lean MVP

**Agentic Travel Recommendations Service**

- **Owner:** Andy Nguyen
- **Status:** Approved scope, pre-implementation
- **Audience:** implementation contributors, engineering + hiring reviewers
- **Authoritative design:** `docs/superpowers/2026-07-08-agentic-travel-recs-design.md`
- **Implementation plan:** `docs/superpowers/plans/2026-07-08-agentic-travel-recs.md`
- **Decision history:** `questions/decision-log.md`

> This PRD was scoped down from an earlier, much larger 22-work-item design to a
> lean four-week first step. See "Ships now vs. later" for what was deferred and
> `questions/decision-log.md` (D1) for why.

## 1. Summary

An internal service that lets an external AI agent (the "AI Concierge") query a
member's travel history, loyalty tier, and partner-specific rules to produce
personalized, **rule-compliant** travel recommendations on arrivia's
multi-tenant, white-label platform.

The design principle: **the deterministic backend is the source of truth.** The
LLM/AI agent may consume the service through MCP tools, but it never enforces
partner rules, authorizes data access, or invents member/travel facts. Those are
handled by deterministic backend code and validated before any response is
returned.

## 2. Problem

White-label travel platforms serve many partner brands, each with its own rules
for what may be shown to members (e.g. cap recommendations at 3, exclude cruises).
An agentic assistant that fetches member data and generates offers risks
hallucinated recommendations, cross-tenant data leakage, and rule bypass. The MVP
solves this with a small, production-minded service where every recommendation is
generated deterministically, filtered by partner rules, exposed over REST and MCP,
and validated with strict schemas.

## 3. Goals

- Deterministic FastAPI service returning personalized recommendations for known
  members.
- Partner-specific configuration: **category exclusions** and **max recommendation
  caps** (unlimited supported).
- **MCP stdio server** exposing two agent-discoverable tools: `get_member_profile`,
  `get_recommendations`, reusing the same service layer as REST.
- **Multi-tenant isolation** enforced in code via a tenant guard and an explicit
  mock `AgentContext`.
- Strict Pydantic schemas at every boundary; fail closed on bad input/output.
- Structured, PII-safe JSON logging with correlation IDs; AWS/Azure-native
  production framing (no third-party observability platform).
- Deterministic pytest **evals** for tenant isolation, cruise exclusion, cap
  enforcement, and fail-closed behavior.
- CLI demo, Docker support, and a README with Sections A, B, C.

## 4. Non-goals (deferred to "later")

- No live LLM call inside the service (no API key to run/test/demo).
- No citations / citation-validation layer, no separate agent-response-validation
  layer.
- No LLM orchestration / phrasing / re-ranking.
- No LangSmith or any named third-party observability platform.
- No RAG / vector search, no real DB persistence, no real auth / SSO / RBAC UI,
  no partner admin UI, no payment/booking/inventory.

## 5. Core principles

1. Deterministic backend is the source of truth; the LLM never enforces rules.
2. No LLM call inside the service.
3. Rule order is fixed: **category exclusions first, then caps.**
4. Partner config is **READ-ONLY**.
5. Fail closed on missing context/config, unknown member, schema failure, or
   tenant mismatch — safe structured error, never partial data, never PII/stack
   traces.
6. REST and MCP share ONE service layer; MCP never bypasses the guard or rule
   engine.
7. Multi-tenant isolation is enforced in code, not by prompt or convention.

## 6. Users

| Persona | Primary need |
|---|---|
| Travel Member | Relevant offers that respect partner rules; data isolated from others. |
| Partner Admin | Deterministic, auditable enforcement of exclusions and caps. |
| AI Agent | Discoverable MCP tools with strict schemas and safe errors. |
| Backend Engineer | Clean service boundaries, testability, one shared brain. |
| On-Call Engineer | Correlation IDs, rule metadata, clear failure classification. |
| Reviewer | Evidence of API design, MCP integration, multi-tenant safety, judgment. |

## 7. Functional requirements

### 7.1 REST API
- `GET /health` → `{"status": "ok"}`.
- `POST /recommendations` — body `{ "member_id": "..." }`; caller identity from
  `x-partner-id` / `x-agent-id` headers (`x-request-id` optional). Returns a
  schema-valid `RecommendationResponse` or a safe `ErrorResponse`.

### 7.2 Mock member service (dict-backed)
- `get(member_id)` → `MemberProfile` (member_id, partner_id, loyalty_tier,
  travel_history) or `UnknownMemberError`.
- Multiple members across multiple partners; loyalty tiers **Silver/Gold/Platinum**
  only; travel history = up to **5 bookings**, each with destination, dates,
  booking type.

### 7.3 Mock partner config service (read-only, dict-backed)
- `get(partner_id)` → `PartnerConfig` (excluded_categories, `max_recommendations:
  int | None` where None = unlimited) or `MissingPartnerConfigError`.
- Fixtures: one **capped at 3**, one **unlimited**, one that **excludes cruises**.

### 7.4 Deterministic recommendation generator
- Generates candidates from loyalty tier + travel history; categories include
  Hotel, Flight, Cruise, Car Rental. **Rule-unaware.** Platinum intentionally
  generates a Cruise candidate so the exclusion path is always exercised.
- Deterministic and testable without any LLM.

### 7.5 Rule engine
- Ordered pipeline: `CategoryExclusionRule` then `MaxRecommendationsRule`.
- Returns `RuleMetadata`: applied rules, excluded categories,
  `removed_recommendations` (each `{recommendation_id, category, rule}`),
  candidate/final counts, max_allowed.
- New rule *kinds* added by dropping a `Rule` class into the ordered list — no
  generator change. Not a plugin framework.

### 7.6 Orchestration service (shared brain)
- `get_recommendations(ctx, member_id)`: member fetch → tenant guard → partner
  config → generate → rules → assemble response.
- `get_member_profile(ctx, member_id)`: member fetch → tenant guard → safe
  `MemberProfileOutput`. **Never calls MemberService without the guard.**

### 7.7 MCP tools (FastMCP stdio)
- `get_member_profile(member_id)`, `get_recommendations(member_id)` — `member_id`
  is the only argument. Caller identity from server launch env (`PARTNER_ID`,
  `AGENT_ID`); `request_id` generated per call. One process = one partner session.
- Reuse the guarded service methods. Domain failures raise a safe `ToolError`
  carrying `{error_code, message, request_id}` — no stack traces/PII.

### 7.8 Security / multi-tenant isolation
- `AgentContext(request_id, agent_id, partner_id, source)` built from trusted
  input. Tenant guard denies when `ctx.partner_id != member.partner_id` (403 /
  safe MCP error). Production would replace mock identity with signed workload
  identity / JWT / gateway-injected tenant.

### 7.9 Observability
- Structured JSON logs, one line per request/tool call, allowlisted fields only.
  **Never** log full profiles, travel history, or recommendation reasons.
  Production framing: CloudWatch / Application Insights, X-Ray / OpenTelemetry.

### 7.10 Evals (deterministic pytest)
- Tenant isolation (both tools), cruise exclusion (even for Platinum), cap
  enforcement, fail-closed on unknown member / missing config.

## 8. Data models

`LoyaltyTier {Silver, Gold, Platinum}`, `Category {Hotel, Flight, Cruise,
CarRental}`, `Source {rest, mcp, cli}`. `MemberProfile`, `MemberProfileOutput`,
`TravelHistoryItem` (destination, start_date, end_date, booking_type),
`PartnerConfig` (excluded_categories, max_recommendations|None),
`Recommendation` (id, category, title, reason, `score` — a deterministic sort
key, not AI confidence), `RemovedRecommendation`, `RuleMetadata`,
`RecommendationResponse`, `ErrorResponse` + classified domain exceptions. All
models use `extra="forbid"`. Full field lists in the design spec §3.

## 9. Error contract

| error_code | HTTP | Meaning |
|---|---|---|
| `UNKNOWN_MEMBER` | 404 | Member id not found |
| `MISSING_PARTNER_CONFIG` | 404 | Partner config not found |
| `AUTHORIZATION_DENIED` | 403 | Caller partner ≠ member partner |
| `VALIDATION_ERROR` | 422 | Request/response schema invalid or missing caller headers |
| `TOOL_EXECUTION_ERROR` | 500 | Unexpected internal failure, surfaced safely |

MCP tools have no HTTP status; the same `error_code` values are delivered as a
safe `ToolError` payload.

## 10. Tech stack

Python 3.11+, FastAPI, Pydantic v2, pydantic-settings, MCP Python SDK (FastMCP),
pytest, httpx (TestClient), Docker + docker-compose. No LLM/API key required.

## 11. Ships now vs. later

| Ships now (four-week first step) | Deferred (later) |
|---|---|
| Deterministic generator + rule engine | LLM phrasing / ranking / orchestration |
| REST + MCP (2 tools) + CLI | Citations + citation validation |
| Tenant guard + multi-tenant evals | Real auth (signed identity / JWT) |
| Structured JSON logs (PII-safe) | CloudWatch / App Insights / X-Ray wiring |
| Mock member + partner config | Real DB persistence, partner admin UI |
| Docker + README (A/B/C) | RAG / vector search, feedback loops |

## 12. Acceptance criteria

- Service boots; `/health` returns ok; `POST /recommendations` returns
  schema-valid output for known members.
- Unknown member / missing config / cross-partner requests return safe structured
  errors (404 / 404 / 403).
- Cruise exclusions and max caps are always enforced; exclusion runs before cap.
- MCP tools reuse the guarded service and cannot bypass the rule engine;
  cross-partner `get_member_profile` returns a safe error with no profile leak.
- Deterministic eval suite passes (`pytest tests/evals`).
- Docker runs the API; README covers setup, architecture, trade-offs, runbook,
  AI usage log (B2 left for the human), and repeatable MCP Inspector demo commands.

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Cross-tenant data leakage | Tenant guard on every member access; isolation evals on both tools. |
| Rule bypass via MCP | MCP reuses the guarded shared service; no-bypass tests. |
| Stale partner config | Read config at request time; cap/exclusion changes apply on next request. |
| Sensitive logs | Allowlisted PII-safe log fields; production redaction/tokenization note. |
| Scope creep | Lean MVP; citations/LLM/observability platform deferred to "later". |
