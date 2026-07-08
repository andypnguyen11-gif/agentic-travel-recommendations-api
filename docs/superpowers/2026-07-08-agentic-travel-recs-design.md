# Design Spec — Agentic Travel Recommendations Service (Lean MVP)

- **Date:** 2026-07-08
- **Owner:** Andy Nguyen
- **Status:** Pending human review, pre-implementation
- **Related:** `CLAUDE.md`, `questions/decision-log.md`, `PRD.md`, `Architecture.md`, `Tasks.md`

---

## 1. Purpose & framing

A lean, production-minded proof-of-concept for arrivia's **Agentic Travel
Recommendations API**: an internal service that lets an external AI agent (the
"AI Concierge") query a member's travel history, loyalty tier, and
partner-specific rules to produce personalized, **rule-compliant** travel
recommendations on a multi-tenant, white-label platform.

Scoped as a realistic **four-week first step** for one engineer. Optimizes for
the assignment rubric and constraint discipline, not maximal architecture.

### Core principles (design invariants)

1. **Deterministic backend is the source of truth.** Generator and rule engine
   are pure and deterministic. The LLM/AI agent **never** enforces partner rules,
   authorizes access, or invents member/travel facts.
2. **No live LLM call inside the service.** No API key needed to run, test, or
   demo. The MCP server is the *agentic surface*; the AI Concierge is the MCP
   **client**, living outside the service.
3. **Rule order is fixed:** category exclusions first, then recommendation caps.
4. **Partner config is READ-ONLY.** We respect whatever it returns.
5. **Fail closed** on missing context/config, unknown member, schema failure, or
   tenant mismatch → safe structured error. No stack traces or raw PII anywhere.
6. **REST and MCP share ONE service layer.** No duplicated business logic; MCP
   tools never bypass the rule engine.
7. **Multi-tenant isolation enforced in code**, not by prompt or convention.

### Non-goals / deferred to "later" (explicitly OUT of this build)

Live LLM orchestration/phrasing/ranking; citations + citation validation; agent
response-validation layer; LangSmith or any named third-party observability;
RAG/vector search; real DB persistence; real auth/SSO/RBAC UI; partner admin UI.
These are documented in the README "ships later" section.

---

## 2. Architecture

One Python service. One shared service layer. Three thin front doors (REST, MCP,
CLI). No LLM inside.

```
Caller (REST client / MCP agent / CLI)
        │  carries AgentContext (partner_id, agent_id, request_id, source)
        ▼
Front doors (thin adapters — build context, no business logic)
   • FastAPI:  POST /recommendations, GET /health
   • FastMCP (stdio):  get_member_profile, get_recommendations
   • CLI:  python -m cli.demo ...
        │
        ▼
RecommendationService.get_recommendations(ctx, member_id)   ← the single brain
   1. member  = MemberService.get(member_id)             # unknown → UNKNOWN_MEMBER
   2. TenantGuard.authorize(ctx, member)                 # mismatch → AUTHORIZATION_DENIED
   3. config  = PartnerConfigService.get(member.partner_id)  # missing → MISSING_PARTNER_CONFIG
   4. candidates = Generator.generate(member)            # deterministic, rule-unaware
   5. final, rule_metadata = RuleEngine.apply(candidates, config)  # exclusions → cap
   6. assemble RecommendationResponse (+ rule_metadata, request_id)
        │
        ▼  mock data providers (dict-backed)
   MemberService        PartnerConfigService (read-only)
```

**Order note:** member fetch precedes `TenantGuard.authorize` because the guard
compares `ctx.partner_id` against `member.partner_id`.

**Member profile lookups are ALSO guarded.** The MCP `get_member_profile` tool
must NOT call `MemberService.get()` directly — that would bypass tenant
isolation. It goes through a second guarded service method on the same shared
brain:

```
RecommendationService.get_member_profile(ctx, member_id) -> MemberProfileOutput
   1. member = MemberService.get(member_id)      # unknown → UNKNOWN_MEMBER
   2. TenantGuard.authorize(ctx, member)         # mismatch → AUTHORIZATION_DENIED
   3. return safe MemberProfileOutput(member)    # no cross-partner leakage
```

Both `get_recommendations` and `get_member_profile` run `MemberService.get` →
`TenantGuard.authorize` before returning anything. No front door (REST, MCP, CLI)
ever reaches `MemberService` without passing through the guard.

### Module layout

```
app/
  main.py                     # FastAPI app + dependency wiring
  config.py                   # pydantic-settings
  logging_config.py           # structured JSON logs + correlation id
  api/
    health.py                 # GET /health
    recommendations.py        # POST /recommendations (AgentContext from headers)
  mcp/
    server.py                 # FastMCP stdio server, 2 tools (no business logic)
  security/
    context.py                # AgentContext model + builder  (SHARED by REST/MCP/CLI)
    tenant_guard.py           # authorize(ctx, member)
  services/
    member_service.py         # mock, dict-backed
    partner_config_service.py # mock, read-only, dict-backed
    recommendation_generator.py  # deterministic, rule-unaware
    recommendation_service.py    # orchestration — the shared brain
  rules/
    base.py                   # Rule protocol (one apply() method)
    category_exclusion_rule.py
    max_recommendations_rule.py
    rule_engine.py            # ordered pipeline + RuleMetadata
  models/
    member.py  partner_config.py  recommendation.py  errors.py  common.py
cli/
  demo.py
tests/
  test_models.py test_member_service.py test_partner_config_service.py
  test_recommendation_generator.py test_rule_engine.py
  test_recommendation_service.py test_recommendations_api.py test_mcp_tools.py
  evals/
    test_tenant_isolation_eval.py test_cruise_exclusion_eval.py
    test_cap_enforcement_eval.py test_fail_closed_eval.py
Dockerfile  docker-compose.yml  requirements.txt  .env.example  pytest.ini
README.md
```

`AgentContext` lives in `security/context.py` (shared boundary), not under `mcp/`.

---

## 3. Data models

Pydantic v2. `extra="forbid"` (fail closed on unexpected fields); enums so bad
values fail at the boundary.

```python
# common.py
LoyaltyTier = Enum: "Silver" | "Gold" | "Platinum"          # exactly the brief
Category    = Enum: "Hotel" | "Flight" | "Cruise" | "CarRental"
BookingType = Enum: "Hotel" | "Flight" | "Cruise" | "CarRental"
Source      = Enum: "rest" | "mcp" | "cli"

# security/context.py
AgentContext:
    request_id: str        # generated per request/tool call if absent
    agent_id: str          # mock caller identity
    partner_id: str        # tenant/partner scope asserted by trusted caller context
    source: Source

# member.py
TravelHistoryItem:
    destination: str
    start_date: date
    end_date: date
    booking_type: BookingType
MemberProfile:
    member_id: str
    partner_id: str        # member's true partner; guard compares to ctx.partner_id
    loyalty_tier: LoyaltyTier
    travel_history: list[TravelHistoryItem]   # max_length = 5
MemberProfileOutput:       # safe profile returned by get_member_profile tool
    member_id: str
    partner_id: str
    loyalty_tier: LoyaltyTier
    travel_history: list[TravelHistoryItem]   # same shape; kept explicit so the
                                              # tool output contract can diverge
                                              # from the internal model later

# partner_config.py  (READ-ONLY)
PartnerConfig:
    partner_id: str
    excluded_categories: list[Category]       # e.g. [Cruise]
    max_recommendations: int | None           # None == unlimited (single source of truth)

# recommendation.py
Recommendation:
    recommendation_id: str    # deterministic stable id
    category: Category
    title: str
    reason: str               # deterministic template built from member facts
    score: float              # deterministic sort key (NOT AI "confidence")
RemovedRecommendation:
    recommendation_id: str
    category: Category
    rule: str                 # "category_exclusion" | "max_recommendations"
RuleMetadata:
    applied_rules: list[str]
    excluded_categories: list[Category]
    removed_recommendations: list[RemovedRecommendation]
    candidate_count: int
    final_count: int
    max_allowed: int | None
RecommendationResponse:
    member_id: str
    partner_id: str
    loyalty_tier: LoyaltyTier
    request_id: str
    recommendations: list[Recommendation]
    rule_metadata: RuleMetadata

# errors.py — safe structured errors (no stack traces / PII)
ErrorResponse: { error_code: str, message: str, request_id: str }
```

**Error codes → HTTP status:**

| error_code | HTTP | Meaning |
|---|---|---|
| `UNKNOWN_MEMBER` | 404 | Member id not found |
| `MISSING_PARTNER_CONFIG` | 404 | Partner config not found |
| `AUTHORIZATION_DENIED` | 403 | ctx.partner_id ≠ member.partner_id |
| `VALIDATION_ERROR` | 422 | Request/response schema invalid, or missing caller headers |
| `TOOL_EXECUTION_ERROR` | 500 | Unexpected internal failure, surfaced safely |

Modeling notes: `score` (not `confidence`) because nothing is AI-generated;
`rule_metadata` retained as the audit trail for on-call/runbook (citations
deferred); `PartnerConfig` uses only `max_recommendations` (None = unlimited) so
no contradictory state is representable.

---

## 4. Deterministic generator + rule engine (rubric-critical core)

Both are pure functions: same input → same output, no clock, no randomness, no
network.

### Generator (`recommendation_generator.py`) — knows member facts only

```
generate(member) -> list[Recommendation]:
  candidates = []
  # 1. History affinity: each past booking seeds a same-category offer
  for h in member.travel_history:
      candidates.append(offer(category=h.booking_type, seed=h.destination))
  # 2. Tier perks: deterministic per-tier catalog
  #    Silver   -> +Hotel
  #    Gold     -> +Hotel, +Flight
  #    Platinum -> +Hotel, +Flight, +Cruise    # intentionally surfaces a Cruise
  candidates += tier_catalog[member.loyalty_tier]
  # 3. Stable de-dupe by (category, title); deterministic score; stable sort
  return sorted(dedupe(candidates), key=lambda r: (-r.score, r.recommendation_id))
```

- **Platinum intentionally generates a Cruise candidate** so the cruise-exclusion
  path is always exercised end-to-end (a Platinum member on the cruise-excluding
  partner must have that cruise removed by the engine). Proves enforcement lives
  in the rule engine, not in generator "good behavior."
- `recommendation_id` is deterministic (stable hash of category+title+seed) so
  tests and `removed_recommendations` are reproducible.

### Rule engine (`rule_engine.py`) — knows partner config only; ordered pipeline

```
apply(candidates, config) -> (final, RuleMetadata):
  applied, removed = [], []
  # Rule 1: CategoryExclusionRule  (BEFORE cap)
  kept = [c for c in candidates if c.category not in config.excluded_categories]
  removed += [{id, category, rule:"category_exclusion"}
              for c in candidates if c.category in config.excluded_categories]
  if config.excluded_categories: applied.append("category_exclusion")
  # Rule 2: MaxRecommendationsRule
  if config.max_recommendations is not None:
      final = kept[:config.max_recommendations]
      removed += [{id, category, rule:"max_recommendations"}
                  for c in kept[config.max_recommendations:]]
      applied.append("max_recommendations")
  else:
      final = kept
  return final, RuleMetadata(applied, config.excluded_categories, removed,
                             candidate_count=len(candidates), final_count=len(final),
                             max_allowed=config.max_recommendations)
```

- **Exclusion-before-cap is explicit, tested (`test_exclusion_runs_before_cap`),
  and documented.** Rationale: if the cap ran first, the service could fill all 3
  slots with cruise offers, then remove them, returning fewer valid recommendations
  than the partner allows. Filtering excluded categories first means the cap
  applies only to eligible offers.
- Rules implement a minimal `Rule` protocol (single `apply()` method) held in the
  engine's ordered list. Adding a rule = new class + insert into the ordered list;
  no generator change. **Deliberately NOT a plugin framework** (YAGNI).

---

## 5. Front doors

Thin adapters over `RecommendationService`. Only real logic: build `AgentContext`
and enforce `TenantGuard`.

### Tenant guard (`security/tenant_guard.py`)
```
authorize(ctx, member):
    if ctx.partner_id != member.partner_id:
        raise AuthorizationDenied   # 403, fail closed
```
Called after member fetch, before config/generation. The multi-tenant isolation
boundary.

### REST (`api/recommendations.py`)
```
POST /recommendations
  headers: x-partner-id (required), x-agent-id (required), x-request-id (optional)
  body:    { "member_id": "..." }
  -> build AgentContext(source="rest"); request_id generated if header absent
  -> RecommendationService.get_recommendations(ctx, member_id)
  -> 200 RecommendationResponse | safe ErrorResponse (404/403/422/500)
GET /health -> { "status": "ok" }
```
Missing/blank `x-partner-id` or `x-agent-id` → 422 (cannot build context → fail closed).

### MCP (`mcp/server.py`) — FastMCP over stdio
```
Tools (member_id is the ONLY argument; no partner_id argument):
  get_member_profile(member_id: str)  -> MemberProfileOutput
  get_recommendations(member_id: str) -> RecommendationResponse
```
- **Caller identity comes from server launch env/args:** `PARTNER_ID`, `AGENT_ID`
  (and optional base `REQUEST_ID`). **`request_id` is generated per tool call**,
  not once per process.
- **One MCP server process is scoped to one partner/agent session.** The agent can
  request recommendations but cannot choose or spoof its partner per call.
- Assumptions documented: in the mock/demo, MCP launch config is treated as
  trusted caller context; in production this is replaced by arrivia's approved
  service-identity mechanism (signed workload identity, JWT claims, or
  gateway-injected tenant context).
- Tool docstrings + typed signatures are what the agent **discovers** in MCP
  Inspector. Both tools build `AgentContext(source="mcp")` and call the **guarded**
  shared-service methods — `get_recommendations` → `RecommendationService.get_recommendations`,
  `get_member_profile` → `RecommendationService.get_member_profile`. Neither tool
  touches `MemberService` directly. ~10 lines each; no business logic.

**MCP error behavior (explicit).** MCP stdio tools have no HTTP status codes, so
domain failures are surfaced as **safe MCP tool errors**: a shared wrapper catches
known domain exceptions (`UnknownMember`, `MissingPartnerConfig`,
`AuthorizationDenied`, validation failures) and raises a FastMCP `ToolError` whose
message is a compact structured payload — `{error_code, message, request_id}` —
carrying the same `error_code` values as REST, with **no stack traces or PII**.
Unexpected errors map to `TOOL_EXECUTION_ERROR`. Both tools use the same wrapper so
behavior is consistent. Tested for unknown member and cross-partner access on both
tools (see §6).

### CLI (`cli/demo.py`) — fallback demo
```
python -m cli.demo --member-id M --partner-id P --agent-id A
  -> AgentContext(source="cli") -> service -> pretty-print tier, partner,
     recommendations, applied rules, removed offers
```

---

## 6. Testing & evals

Deterministic pytest only — no network, no LLM, no non-deterministic layer.
**Every work item ships with tests and is checked off only when its tests pass.**

### Unit / integration tests

| Layer | Tests |
|---|---|
| Models | valid pass; bad tier/category fail; `travel_history` > 5 fails; extra field fails |
| Member service | known → profile; unknown → `UNKNOWN_MEMBER` |
| Partner config | capped/unlimited/cruise-excluding fixtures load; missing → `MISSING_PARTNER_CONFIG` |
| Generator | deterministic (same in → same out); Platinum produces a Cruise candidate |
| Rule engine | cruise removed for excluding partner; cap of 3 enforced; unlimited passes all; `test_exclusion_runs_before_cap`; `removed_recommendations` records `{id, category, rule}` |
| Orchestration | full flow member→response; unknown member & missing config surface as errors |
| REST API | 200 happy path; 404 unknown; 403 cross-partner; 422 missing headers |
| MCP tools | both reuse the guarded shared service; output schema-valid; MCP path cannot bypass rule engine; `get_member_profile` for a cross-partner member raises a safe `ToolError` (`AUTHORIZATION_DENIED`), not a leaked profile; unknown member on both tools → safe `ToolError` (`UNKNOWN_MEMBER`); error payloads carry no stack traces/PII |

### Evals (`tests/evals/`, run via `pytest tests/evals`) — deterministic pytest checks

- `test_tenant_isolation_eval` — partner_b context requesting a partner_a member is
  denied on **both** `get_recommendations` and `get_member_profile` (REST 403 /
  MCP safe `ToolError`), with no profile data leaked
- `test_cruise_exclusion_eval` — cruise never appears for excluding partner, even Platinum
- `test_cap_enforcement_eval` — final count never exceeds partner max
- `test_fail_closed_eval` — missing context/config → safe structured error, never partial data

These are deterministic assertions, **not** LLM evals and not an AI evaluation
platform.

---

## 7. Observability (AWS/Azure-native — no LangSmith)

- Structured JSON logs, one line per request/tool call, fields: `request_id`,
  `source`, `agent_id`, `partner_id`, `member_id`, `tool_name`, `applied_rules`,
  `removed_count`, `outcome`, `latency_ms`, `failure_reason`.
- **PII discipline:** do **not** log full member profiles, travel history,
  recommendation `reason` text, or raw PII. Logging `member_id` is acceptable for
  the mock; README notes production would apply arrivia-approved
  redaction/tokenization rules.
- `request_id` generated per request/tool call if absent; threaded service →
  response → logs (the correlation-id spine for the runbook).
- README frames the production path: CloudWatch / Application Insights for
  logs+metrics; X-Ray / OpenTelemetry for traces; metrics for request volume,
  rule denials, upstream failures, latency, MCP tool errors. Future observability
  is phrased generically as "integrate with arrivia-approved observability
  tooling," never a named third-party platform.

---

## 8. Fixtures (aligned exactly to the assignment prompt)

- **Tiers:** Silver / Gold / Platinum only.
- **Travel history:** last 5 bookings, each with destination, dates, booking type.
- **Partners:**
  - `partner_capped` — `max_recommendations = 3`, no exclusions
  - `partner_unlimited` — `max_recommendations = None`, no exclusions
  - `partner_no_cruise` — excludes `Cruise`, `max_recommendations = None`
    (clean single-rule exclusion demo)
- **Exclusion-before-cap interaction** is proven by a unit test that constructs
  its own config inline (excludes `Cruise` **and** `max_recommendations = 3`),
  since that is the only place both rules must fire on the same request.
- **Members:** multiple across partners (incl. a Platinum member under
  `partner_no_cruise` to exercise cruise removal), plus one unknown-member case.

---

## 9. Deliverables & division of labor

**Produced by this build:**
1. Working code: REST + MCP + CLI + tests/evals; `Dockerfile`, simple
   `docker-compose.yml`, `requirements.txt`, `.env.example`, `pytest.ini`.
2. **README** with:
   - Section A — Architecture & Trade-offs (300–500 words)
   - Section B — Production Readiness: incident runbook (cruise-leak scenario);
     **B2 left as an explicit placeholder** for the human to answer without AI
   - Section C — AI Usage Log (documents this AI collaboration, incl. design process)
   - "Ships first vs. later" table; four-week plan; repeatable MCP Inspector demo
     commands; the deterministic/no-API-key/LLM-is-the-client statements
3. Revised `PRD.md`, `Architecture.md`, `Tasks.md` aligned to this lean MVP.

**NOT produced here (human's deliverables):** the video walkthrough, and README
Section B2 (must be answered without AI assistance).

---

## 10. Build sequencing (TDD; commits avoid "PR"/"M1" language)

1. Skeleton: FastAPI app, `/health`, config, logging, pytest — test app boots.
2. Domain models — validation tests.
3. Mock member service — tests.
4. Mock partner config service (read-only) — tests.
5. Deterministic generator — determinism + Platinum-cruise tests.
6. Rule engine — exclusion, cap, exclusion-before-cap, metadata tests.
7. Orchestration service + tenant guard — both guarded methods
   (`get_recommendations`, `get_member_profile`); flow + error + cross-partner
   isolation tests.
8. REST endpoint — API tests (200/404/403/422).
9. MCP stdio server + 2 tools + shared safe-error wrapper — reuse-guarded-service,
   no-bypass, cross-partner `get_member_profile` denial, and unknown-member error
   tests.
10. Evals suite — isolation, cruise, cap, fail-closed.
11. CLI demo.
12. Dockerfile + compose + `.env.example`.
13. README (A, B w/ B2 placeholder, C, ships-first-vs-later, demo commands).
14. Revise PRD/Architecture/Tasks to match.

Each step: write tests, implement, run green, check off, commit descriptively.
