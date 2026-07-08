# Agentic Travel Recommendations Service

Internal service that lets an external AI agent (the "AI Concierge") fetch a
member's profile and generate partner-rule-compliant travel recommendations on
arrivia's multi-tenant, white-label platform. Deterministic backend; the LLM is
the MCP client, never the rule enforcer.

## How it works (at a glance)
- Deterministic generator turns member facts into candidate offers.
- Deterministic rule engine applies partner **category exclusions, then caps**.
- A tenant guard runs before any member data is returned.
- REST, MCP (stdio), and a CLI all call the same service brain.
- **No LLM call inside the service. No API key required to run, test, or demo.**

## Setup
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

## Run the REST API
    uvicorn app.main:app --reload
    curl -s localhost:8000/health
    curl -s -X POST localhost:8000/recommendations \
      -H "x-partner-id: partner_no_cruise" -H "x-agent-id: agent-demo" \
      -H "content-type: application/json" -d '{"member_id":"M-plat-nocruise"}'

## Run the MCP server (agent-discoverable)
Caller identity is the trusted launch context; one process = one partner session.

    PARTNER_ID=partner_no_cruise AGENT_ID=agent-demo python -m app.mcp.server

Discover + invoke with MCP Inspector:
    PARTNER_ID=partner_capped AGENT_ID=agent-demo \
      npx @modelcontextprotocol/inspector python -m app.mcp.server
Then: list tools -> inspect get_recommendations schema -> invoke with
{"member_id":"M-plat-capped"} (cap of 3) and, with a partner_no_cruise-scoped
server, {"member_id":"M-plat-nocruise"} (cruise removed).

## Run the CLI demo
    python -m cli.demo --member-id M-plat-nocruise --partner-id partner_no_cruise --agent-id a

## Tests and evals
    pytest            # full suite
    pytest tests/evals  # safety evals only

---

## Section A — Architecture & Trade-offs

The service has one shared brain, `RecommendationService`, and three thin
callers — REST (`app/api/recommendations.py`), an MCP stdio server
(`app/mcp/server.py`), and a CLI (`cli/demo.py`) — that all build an
`AgentContext` and delegate to it. Nothing about rule enforcement or data
access lives in any of the three callers, so there is no code path where an
agent talks directly to member or partner data. `get_recommendations` runs a
fixed pipeline: fetch the member from `MemberService`, authorize the caller
against that member's `partner_id` via `TenantGuard.authorize` (fail closed on
mismatch), read that partner's config from the read-only `PartnerConfigService`,
generate candidate offers from member facts alone
(`RecommendationGenerator`), and run the ordered `RuleEngine`
(`CategoryExclusionRule` then `MaxRecommendationsRule`) over those candidates.
`get_member_profile` runs the same fetch-then-authorize guard before returning
anything, so both tools share one authorization gate rather than each
reimplementing it.

**Trade-off 1 — deterministic rule engine vs. LLM enforcement.** An LLM could
read partner config and "decide" what to show, but that makes rule compliance
probabilistic and unauditable — exactly what a travel partner relationship
cannot tolerate. Keeping exclusion and cap logic in typed, unit-tested `Rule`
classes means every response is reproducible from the same inputs, and
`rule_metadata` gives on-call a literal trail (`applied_rules`,
`removed_recommendations`) instead of an LLM's self-report. The cost is that
the service can't yet handle a rule too nuanced to express as code — an
acceptable trade for a four-week first step.

**Trade-off 2 — env-scoped MCP identity vs. a per-call partner argument.** MCP
tools take only `member_id`; `partner_id` and `agent_id` come from the server's
launch environment (`PARTNER_ID`/`AGENT_ID`), not from tool arguments. A
per-call partner argument would let a compromised or careless agent claim any
partner scope it wants. Binding identity to the process that launched the
server means one MCP session is hard-scoped to one partner for its lifetime;
production replaces this launch context with signed workload identity, but the
one-session-one-partner shape stays.

**Config and rule changes.** `PartnerConfigService` is read at request time, so
if a partner's cap or excluded-category list changes upstream, the very next
`get_recommendations` call picks it up with zero code changes or redeploys —
the service never caches or writes config. Adding an entirely new *kind* of
rule (e.g. a minimum-tier gate) means writing one new `Rule` class and adding
it to the ordered list in `RuleEngine.__init__`; the pipeline, metadata shape,
and both callers are untouched.

## Section B — Production Readiness & Incident Response

### Incident Runbook: "AI Concierge shows cruises for a cruise-excluded partner"
1. Get `request_id`/`partner_id`/`member_id` from the report or logs.
2. Confirm partner config: does `partner_config` return `Cruise` in
   `excluded_categories`? If not, this is a config-source issue, not a service
   bug.
3. Reproduce deterministically: call `get_recommendations` for that member;
   inspect `rule_metadata.applied_rules` and `removed_recommendations` — was
   `category_exclusion` applied? Was a cruise in `removed_recommendations`?
4. If exclusion did not fire: check the rule order and the
   `CategoryExclusionRule`; check whether the client is calling our tool vs.
   rendering its own offers.
5. Resolve: fix + regression eval (`test_cruise_exclusion_eval`); if
   config-source, escalate to the partner-config owner since that service is
   read-only to us.

### B2 — Required Reasoning Question (answer WITHOUT AI assistance)
> **PLACEHOLDER — Andy to write by hand, no AI.** Describe a scenario where an AI
> coding assistant gives a plausible-but-wrong answer for enforcing partner rules,
> how you'd catch it, and what you'd verify before acting.

## Section C — AI Usage Log

This project was built with AI assistance throughout design and implementation,
under a rule that the deterministic backend and its enforcement logic are
human-reviewed line by line, and that Section B2 above is answered by a human
with no AI involvement. Three representative interactions, recorded in
`questions/decision-log.md`:

1. **Scope-down from a large multi-PR plan to a lean MVP.** The starting plan
   sized this as a large system (agent orchestrator, citations + citation
   validation, response validation layer, full eval dashboards). Asked to
   scope it to a realistic four-week, single-engineer first step, the AI
   proposed cutting to: mock member + partner config services, a deterministic
   generator, an ordered rule engine (exclusions then caps), a tenant guard,
   REST + MCP + CLI over one shared service, and a focused test/eval set —
   with the rest explicitly deferred to a "ships later" list. Kept as
   proposed: the cut lines up with what the assignment actually rewards
   (correctness and judgment under scope discipline, not feature count), and
   it left the repo with one honest story instead of an aspirational one it
   couldn't finish. See decision-log D1.
2. **Removing LangSmith to honor the "existing infrastructure only"
   constraint.** An early observability pass suggested LangSmith for
   LLM-specific tracing. Flagged in review as violating the assignment's
   explicit "no new third-party platforms" rule, the AI was asked to
   re-propose observability using only infrastructure arrivia already runs.
   The replacement — structured JSON logs with `request_id`/`member_id`/
   `partner_id`/`tool_name`/`rule_decisions`/`failure_reason`, framed as
   CloudWatch/Application Insights for logs and metrics and X-Ray/
   OpenTelemetry for traces — was kept, and any future LLM-observability idea
   is now phrased generically ("arrivia-approved observability tooling") so it
   can't reintroduce a named third-party tool by accident. See decision-log D2.
3. **`get_member_profile` tenant-guard gap caught in spec review.** During
   human review of the design spec, the drafted MCP `get_member_profile` tool
   called `MemberService` directly rather than going through
   `RecommendationService`, which meant it would return a member's profile
   without ever checking that the caller's `partner_id` matched the member's
   `partner_id` — the exact cross-tenant leak this whole design exists to
   prevent. Rejected the direct-call version; the AI's fix, accepted, added a
   guarded `RecommendationService.get_member_profile(ctx, member_id)` that
   runs fetch → `TenantGuard.authorize` → return, mirroring
   `get_recommendations`, with a cross-partner-access test added to prove the
   403/safe-MCP-error path. See decision-log D16.

---

## What ships first vs. later
| Ships now (four-week first step) | Deferred (later) |
|---|---|
| Deterministic generator + rule engine | LLM phrasing/ranking/orchestration |
| REST + MCP (2 tools) + CLI | Citations + citation validation |
| Tenant guard + multi-tenant evals | Real auth (signed identity / JWT) |
| Structured JSON logs (PII-safe) | CloudWatch/App Insights/X-Ray wiring |
| Mock member + partner config | Real DB persistence, partner admin UI |

## Four-week plan
This is the four-week first step; the table above bounds what ships now. Indicative week-by-week:

| Week | Focus |
|---|---|
| 1 | Domain models + fixtures (Silver/Gold/Platinum, last-5 bookings), mock member and read-only partner-config services, deterministic candidate generator. |
| 2 | Rule engine with fixed order (category exclusions → caps), tenant guard, shared recommendation service brain; unit tests for cap enforcement, cruise exclusion, and isolation. |
| 3 | REST endpoint, MCP stdio server (two tools), CLI demo — all sharing the one service layer; PII-safe structured JSON logging with correlation IDs. |
| 4 | Deterministic safety evals, Docker + compose, MCP Inspector walkthrough, README + incident runbook; buffer for hardening (non-root image, healthcheck) noted as later work. |

## Notes
- Logs never include full profiles, travel history, or recommendation reasons;
  production would apply arrivia-approved redaction/tokenization.
- MCP caller identity is a trusted launch context in the mock; production replaces
  it with signed workload identity / JWT claims / gateway-injected tenant.
