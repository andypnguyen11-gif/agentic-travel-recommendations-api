# CLAUDE.md — Agentic Travel Recommendations Service

Guardrails for this repo. Read before making changes. These are non-negotiable
unless the human explicitly overrides them.

## What this project is

A lean, production-minded proof-of-concept for arrivia's **Agentic Travel
Recommendations API**: an internal service that lets an external AI agent (the
"AI Concierge") query a member's travel history, loyalty tier, and
partner-specific rules to produce personalized, rule-compliant recommendations
in a multi-tenant, white-label platform.

This is a **four-week first step**, scoped to what one engineer could realistically
ship — not a maximal architecture. Optimize for the assignment rubric and
constraint discipline, not for feature count.

## Core principles (the whole design hangs on these)

1. **Deterministic backend is the source of truth.** The recommendation
   generator and rule engine are deterministic and testable. The LLM/AI agent
   **never** enforces partner rules, authorizes data access, or invents member/
   travel facts.
2. **No live LLM call inside the service (first build).** The service generates
   candidates deterministically and enforces partner rules deterministically.
   The MCP server is the *agentic surface*; the AI Concierge lives **outside**
   the service as the MCP client. No API key is required to run, test, or demo.
3. **Rule order is fixed: category exclusions first, then recommendation caps.**
4. **Partner config is READ-ONLY.** We only read from the (mock) partner config
   service and must respect whatever it returns, even if suboptimal.
5. **Fail closed.** Missing context, missing config, unknown member, schema
   validation failure, or tenant mismatch → safe structured error, never a
   partial or guessed result. No stack traces or raw PII in responses/logs.
6. **REST and MCP share ONE service layer.** MCP tools must reuse the
   recommendation orchestration service — never duplicate business logic or
   bypass the rule engine.
7. **Multi-tenant isolation is enforced in code**, not by prompt or convention.
   A caller scoped to partner A can never read partner B's member or config.

## Constraints from the assignment (do not violate)

- **Existing infrastructure only.** No new third-party platforms. **No LangSmith.**
  Frame observability as AWS/Azure-native: structured JSON logs, CloudWatch /
  Application Insights, X-Ray / OpenTelemetry, correlation IDs.
- **Read-only partner config** (see principle 4).
- **Four-week scope.** README must state what ships first vs. later.
- **On-call ownership.** Design for 2am debuggability: correlation IDs,
  structured logs, clear failure classification, a runbook.

## Fixtures must match the assignment prompt exactly

- Loyalty tiers: **Silver / Gold / Platinum** only (no Bronze).
- Travel history: **last 5 bookings**, each with **destination, dates, booking type**.
- Partners: one **capped at 3**, one **unlimited**, one that **excludes cruises**.
- Recommendation categories include at least: Hotel, Flight, Cruise, Car Rental.

## MCP demo path

- **FastMCP over stdio** exposing two tools: `get_member_profile`,
  `get_recommendations`.
- Primary proof: **MCP Inspector** discovers the tools, shows input schema, and
  invokes `get_recommendations` for (a) the capped-at-3 partner and (b) the
  cruise-excluding partner.
- Fallback: a CLI script that runs the same end-to-end flow.
- Exact demo commands live in the README so the walkthrough is repeatable.

## Caller identity (auth is out of scope)

- Real auth is a non-goal. Caller identity comes from an **explicit mock
  `AgentContext`** built from trusted inputs (e.g. `x-partner-id` / `x-agent-id`
  headers for REST, args/env for CLI and MCP).
- Document clearly that production would replace this with signed service
  identity / JWT validation.

## Testing discipline

- **Every PR item ships with tests and is only checked off when its tests pass.**
- Prioritize tests that prove the rubric-critical behavior: cap enforcement,
  cruise exclusion, tenant/partner isolation, fail-closed on bad input,
  MCP-cannot-bypass-rule-engine.
- Tests must be deterministic and repeatable (no network, no LLM).

## Deferred to "later" (keep OUT of the first build)

Citations + citation validation, agent response validation layer, live LLM
orchestration/phrasing/re-ranking, LangSmith or any named third-party
observability, RAG/vector search, real DB persistence, real auth/RBAC UI,
partner admin UI. These belong in the README "ships later" section.

## Commit message conventions

- **Do NOT reference internal planning artifacts in commit messages.** No "PR 1",
  "PR 9", "M1", "M2", milestone numbers, or task-plan IDs. Those are scaffolding
  for us, not meaningful history for a reviewer.
- Write conventional, descriptive commits about *what changed and why*, e.g.
  `feat: add deterministic rule engine with exclusion-before-cap ordering`,
  `test: cover partner cruise exclusion and cap enforcement`.

## Process

- Decisions are logged in `questions/` as they are made — keep it current.
- Follow the Superpowers workflow: brainstorm → spec → plan → TDD implementation
  → verification before claiming done.
