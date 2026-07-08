# Tasks — Agentic Travel Recommendations Service (Lean MVP)

Work-item checklist for the four-week first step. Each item is TDD (write the
failing test, watch it fail, implement, watch it pass) and ships with its own
tests — an item is checked off only when its tests are green.

- **Full step-by-step detail:** `docs/superpowers/plans/2026-07-08-agentic-travel-recs.md`
- **Design:** `docs/superpowers/2026-07-08-agentic-travel-recs-design.md`
- **Decisions:** `questions/decision-log.md`

> Reframed from an earlier 22-work-item plan to this lean scope (decision D1).
> Commit messages are descriptive and MUST NOT reference "PR N", "M1"/milestones,
> or task IDs (decision D8 / CLAUDE.md).

## Guardrails (apply to every item)

- Python 3.11+; all Pydantic models use `extra="forbid"`.
- Deterministic backend; no LLM call inside the service; no API key to run/test/demo.
- Partner config is read-only; rule order is exclusions → caps.
- Fail closed; never leak stack traces or PII in responses or logs.
- REST and MCP share one service layer; MCP never bypasses the guard/rule engine.
- Fixtures: tiers Silver/Gold/Platinum; travel history ≤5 (destination/dates/type);
  partners = capped-at-3, unlimited, cruise-excluding.

## Work items

- [ ] **1. Skeleton + health** — FastAPI app, `/health`, `config.py`
  (pydantic-settings), `requirements.txt`, `.gitignore`, `.env.example`,
  `pytest.ini`. Test: `/health` returns ok; app boots.

- [ ] **2. Domain models + errors** — enums (LoyaltyTier, Category, Source),
  `stable_id`, member models, `PartnerConfig` (`max_recommendations: int | None`),
  recommendation models, `ErrorResponse` + classified domain exceptions. Tests:
  valid pass; bad tier/category fail; `travel_history` > 5 fails; extra field fails.

- [ ] **3. Shared AgentContext** — `security/context.py` (`AgentContext` frozen +
  `build_context`, request_id generated per call); `tests/conftest.py`. Tests:
  request_id generated/kept/unique; frozen.

- [ ] **4. Mock member service** — dict-backed `get(member_id)`; members across
  partners; unknown → `UnknownMemberError`. Tests cover multi-partner + unknown.

- [ ] **5. Mock partner config service (read-only)** — capped/unlimited/cruise
  fixtures; missing → `MissingPartnerConfigError`. Tests for each fixture + missing.

- [ ] **6. Deterministic generator** — tier + history → candidates; rule-unaware;
  Platinum generates a Cruise. Tests: determinism, Platinum-cruise, sorted, no dups.

- [ ] **7. Rule engine** — `base` (Rule protocol + RuleOutcome), category
  exclusion, max recommendations, ordered engine + `RuleMetadata`. Tests: cruise
  removed, cap enforced, unlimited passes, `test_exclusion_runs_before_cap`,
  removed records carry rule reason, injectable new rule.

- [ ] **8. Tenant guard + orchestration service** — `authorize(ctx, member)`;
  `RecommendationService.get_recommendations` and `.get_member_profile` (both
  guarded); `dependencies.get_recommendation_service`. Tests: full flow, cruise
  excluded, cap enforced, both cross-partner denials, unknown member, missing config.

- [ ] **9. Structured logging (PII-safe)** — `configure_logging` + `safe_log_fields`
  (allowlist only). Tests: allowlist keys only; no PII keys leak.

- [ ] **10. REST endpoint** — `POST /recommendations` with header-built context;
  safe `ErrorResponse` bodies; 422 handler for missing headers. Tests:
  200 / 404 unknown / 403 cross-partner / 404 missing-config / 422 missing-headers /
  cruise-excluded-via-REST.

- [ ] **11. MCP stdio server** — FastMCP, two tools (`member_id` only), env-based
  identity, safe `ToolError` wrapper. Tests: returns dict, cannot bypass rule
  engine, safe profile, cross-partner safe error (no leak), unknown-member safe
  error, tools registered/discoverable.

- [ ] **12. Eval suite** — `tests/evals/`: tenant isolation (both tools), cruise
  exclusion (Platinum), cap enforcement, fail-closed. Run via `pytest tests/evals`.

- [ ] **13. CLI demo** — `cli/demo.py` end-to-end flow; prints tier/partner/recs/
  applied-rules/removed. Tests: happy path, cross-partner safe error, unknown member.

- [ ] **14. Docker + compose** — `Dockerfile`, `docker-compose.yml`; `/health` and
  `/recommendations` work in the container.

- [ ] **15. README (A/B/C)** — overview, setup, REST examples, **MCP Inspector demo
  commands**, CLI; Section A (Architecture & Trade-offs 300–500w), Section B
  (cruise-leak runbook; **B2 placeholder for the human, no AI**), Section C (AI
  usage log ≥3 interactions); ships-now-vs-later table; four-week plan; PII/logging
  and MCP-identity production notes.

- [ ] **16. Final verification sweep** — full `pytest`, evals alone, exercise all
  three front doors manually, confirm no banned commit language, fix + commit.

## Most valuable items for the assignment

Rule engine (7), orchestration + guard (8), MCP tools (11), and the eval suite
(12) carry the strongest signal: deterministic rule enforcement, clean service
boundaries, safe MCP integration, and eval-proven multi-tenant safety.
