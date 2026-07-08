# Decision Log

A running record of decisions made while scoping and building the Agentic Travel
Recommendations Service. Newest decisions appended at the bottom. Each entry
notes the question, the decision, and the reasoning so the repo tells one
consistent story.

---

## 2026-07-08 — Initial scoping session

### D1. Build scope: Lean MVP, not the full 22-PR system
**Decision:** Ship a lean MVP optimized for the assignment rubric and the
four-week first-step constraint. Scope:
- Mock member data service
- Mock partner config service (read-only)
- Deterministic recommendation generator
- Deterministic rule engine (exclusions first, caps second)
- Tenant/partner guard with explicit mock caller context
- REST API endpoint(s)
- MCP server with 2 discoverable tools: `get_member_profile`, `get_recommendations`
- Minimal CLI to demonstrate the flow end-to-end
- Focused tests/evals: caps, cruise exclusion, tenant guard, fail-closed
- README Sections A, B, C with a clear "ships first vs. later" split

**Why:** The 22-PR plan (agent orchestrator, citations, response validation,
LangSmith, full eval dashboards) far exceeds a realistic four-week single-engineer
step and risks reading as scope-creep to a reviewer who explicitly asked us to
scope tightly. A lean core + a credible "later" list scores better on Problem
Diagnosis & Judgment.

**Deferred to "later":** citations + citation validation, agent response
validation, advanced LLM orchestration, LangSmith-style eval dashboards, broader
observability, RAG, real DB, real auth.

### D2. Observability: no LangSmith — AWS/Azure-native framing
**Decision:** Drop LangSmith entirely from the first build and README. Use:
- Structured JSON logs with `request_id`, `member_id`, `partner_id`, `tool_name`,
  `rule_decisions`, `failure_reason`
- CloudWatch / Application Insights for logs & metrics
- X-Ray / OpenTelemetry for traces
- Metrics for requests, rule denials, upstream failures, latency, MCP tool errors

Any future "LLM observability" idea is phrased generically as "integrate with
arrivia-approved observability tooling," not a named third-party platform.

**Why:** The assignment forbids proposing a new third-party platform arrivia
doesn't already use. LangSmith would read as violating that constraint. Showing
constraint discipline is worth more than demo-only tooling.

### D3. MCP demo path: FastMCP stdio + MCP Inspector
**Decision:** Standard stdio MCP server exposing `get_member_profile` and
`get_recommendations`, reusing the same service layer as REST (no duplicated
business logic). Video demo: start the server via MCP Inspector, show tool
discovery + input schema, invoke `get_recommendations` for a capped-at-3 partner
and a cruise-excluding partner. Fallback CLI script for the same flow. Exact demo
commands documented in the README.

**Why:** Cleanest, most credible on-camera proof of genuine agent discovery +
invocation.

### D4. Caller identity: explicit mock AgentContext
**Decision:** Real auth is out of scope. Build an explicit mock `AgentContext`
from trusted inputs (`x-partner-id` / `x-agent-id` headers for REST; args/env for
CLI and MCP). Document that production would replace this with signed service
identity / JWT validation.

**Why:** Lets us demonstrate multi-tenant isolation and fail-closed authorization
without building an OAuth/SSO provider (a stated non-goal).

### D5. Fixtures aligned exactly to the assignment prompt
**Decision:**
- Loyalty tiers: Silver / Gold / Platinum only (drop Bronze from the PRD).
- Travel history: last 5 bookings, each with destination, dates, booking type.
- Partners: one capped at 3, one unlimited, one excluding cruises.

**Why:** Match the brief precisely so reviewers see fidelity to requirements.

### D6. Docs updated to match the lean MVP
**Decision:** Surgically revise PRD.md, Architecture.md, Tasks.md to reflect the
lean MVP before implementation. Remove/defer the 22-PR system, LangSmith,
advanced citation/response validation, and full agent orchestration. Keep docs
aligned around the lean-first / ships-later split.

**Why:** Avoid the repo telling two different stories (old maximal docs vs. actual
lean build), which reads as scope confusion.

### D7. Fully deterministic service; MCP is the only agentic surface
**Decision:** No live LLM call inside the recommendation service for the first
build. The service deterministically generates candidates from member profile,
loyalty tier, and travel history, then enforces partner rules via the rule
engine. The AI Concierge / LLM lives **outside** the service as the MCP client.

README will state explicitly:
- The LLM/AI Concierge is the MCP client, not part of the service.
- No API key is required to run or demo.
- Tests are deterministic and repeatable.
- LLM-based phrasing/ranking/orchestration is deferred to a later phase, after
  rule enforcement and observability are proven.

**Why:** Best fit for the rubric — it demonstrably shows the LLM never enforces
partner rules, authorizes access, or invents member/travel facts.

### D8. Process guardrails
**Decision:** Maintain a root `CLAUDE.md` capturing these principles; keep this
decision log current as new questions are answered; every work item ships with
tests and is only checked off when its tests pass.

### D9. Orchestration order — fetch member before authorize
**Decision:** `RecommendationService` order is: member fetch → `TenantGuard.authorize(ctx, member)`
→ partner config → generate → rules → assemble. **Why:** the guard needs
`member.partner_id` to compare against `ctx.partner_id`.

### D10. AgentContext is shared, not MCP-specific
**Decision:** `AgentContext` lives in `security/context.py` and is used by REST,
MCP, and CLI. **Why:** it belongs to the shared service boundary, not the MCP layer.

### D11. `score` not `confidence`; keep `rule_metadata`; simplify PartnerConfig
**Decision:** Deterministic offers carry `score` (honest sort key), not
`confidence`. `RuleMetadata` retained for audit/on-call (citations deferred).
`PartnerConfig` uses only `max_recommendations: int | None` (None = unlimited);
dropped the unlimited boolean to make contradictory state unrepresentable.
`travel_history` capped at 5. `RecommendationResponse` includes member_id,
partner_id, request_id, recommendations, rule_metadata.

### D12. Generator/rule-engine split + Platinum-generates-Cruise
**Decision:** Generator knows member facts only; rule engine knows partner config
only. Platinum intentionally generates a Cruise candidate so the exclusion path is
always exercised end-to-end. Exclusion runs before cap (named test + README
rationale). `removed_recommendations` records `{recommendation_id, category, rule}`.
Rule protocol stays minimal — no plugin framework (YAGNI).

### D13. MCP caller identity from server launch env/args
**Decision:** MCP tools take `member_id` only. Caller identity (`PARTNER_ID`,
`AGENT_ID`) comes from server launch env/args; `request_id` generated per tool
call. One MCP process = one partner/agent session; the agent cannot spoof its
partner per call. Production replaces this with signed workload identity / JWT /
gateway-injected tenant. **Why:** stronger multi-tenant isolation story than a
per-call partner argument.

### D14. Testing/observability refinements
**Decision:** Evals are deterministic pytest checks (not LLM evals). Do not log
full member profiles, travel history, recommendation `reason`, or raw PII;
`member_id` acceptable for the mock, with a README note on production
redaction/tokenization. `request_id` generated per request/tool call, not once per
MCP process. Dockerfile + simple docker-compose. README Section C documents AI
usage incl. this design process; **Section B2 stays a placeholder** for the human
to answer without AI. Commit messages avoid "PR"/"M1"/milestone references.

### D15. Spec written
**Decision:** Design spec saved to
`docs/superpowers/2026-07-08-agentic-travel-recs-design.md` and self-reviewed
(resolved the one `partner_no_cruise` cap TBD: unlimited; exclusion-before-cap
interaction proven by an inline-config unit test).

### D16. Review fixes — guarded profile, MCP errors, status wording
**Decision (from human spec review):**
1. **Close tenant-isolation gap on `get_member_profile`.** Added a second guarded
   method `RecommendationService.get_member_profile(ctx, member_id)`: fetch member
   → `TenantGuard.authorize` → return safe `MemberProfileOutput`. The MCP tool must
   not call `MemberService` directly. Cross-partner profile access is tested (403 /
   safe MCP error, no leak).
2. **MCP error behavior made explicit.** MCP tools have no HTTP status; domain
   failures are raised as safe FastMCP `ToolError`s carrying a structured
   `{error_code, message, request_id}` payload (same error_code values as REST), no
   stack traces/PII. Shared wrapper for both tools; tested for unknown member and
   cross-partner.
3. **Status wording** changed from "Approved design" to "Pending human review,
   pre-implementation" until the human approves.
**Why:** `get_member_profile` bypassing the guard would leak cross-partner member
data — the exact multi-tenant failure the design exists to prevent.

### D17. Spec approved by human
**Decision:** Human approved the spec after the D16 fixes. Proceeding to
writing-plans, then revising PRD.md / Architecture.md / Tasks.md to match the lean
MVP before implementation.

### D18. Implementation plan written
**Decision:** TDD implementation plan saved to
`docs/superpowers/plans/2026-07-08-agentic-travel-recs.md` — 16 work items, each
with failing-test-first steps and real code, no placeholders except the required
human-only README B2. Self-reviewed for spec coverage, placeholders, and type
consistency.

### D19. Existing docs rewritten to lean MVP
**Decision:** Rewrote (not surgically patched) `Architecture.md`, `PRD.md`, and
`Tasks.md` to match the lean MVP. **Why rewrite:** the originals were deeply woven
around the 22-item / LangSmith / citations / agent-orchestrator system; surgical
edits would have left them internally inconsistent. All three now align on:
deterministic backend as source of truth, no LLM in the service, REST+MCP+CLI over
one shared guarded brain, read-only partner config, exclusions-before-caps,
env-scoped MCP identity, AWS/Azure-native observability, and a ships-now-vs-later
split. `Tasks.md` reframed to the 16 lean work items and stripped of "PR N"/
milestone framing per the commit conventions.
