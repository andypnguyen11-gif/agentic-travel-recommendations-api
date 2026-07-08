# Security Follow-ups (post-MVP hardening)

Deferred hardening items surfaced during review. None is a reachable exploit
with the current fixtures; each is captured here so it is a deliberate,
tracked decision rather than an oversight.

## SF-1 — Cross-tenant member-existence enumeration oracle

**Status:** Deferred (accepted for the four-week MVP; revisit before any
real multi-tenant traffic).

**What:** `RecommendationService.get_member_profile` and
`get_recommendations` fetch the member (which raises `UnknownMemberError` →
HTTP 404 / `UNKNOWN_MEMBER`) *before* running the tenant guard (which raises
`AuthorizationDeniedError` → HTTP 403 / `AUTHORIZATION_DENIED`). A caller
scoped to partner A therefore receives a **different** error for
"member exists but belongs to partner B" (403) versus "member does not
exist at all" (404). No profile data ever leaks — the tenant guard still
blocks every cross-partner data read — but the 403-vs-404 distinction lets an
authorized-for-A caller probe whether a given member ID *exists* under some
other partner.

**Why deferred:** Closing it means making not-found and not-authorized
**indistinguishable** to an unauthorized caller (e.g. return an identical
error for both, or run the tenant check before the existence check). That
changes the **public error contract** — the REST/MCP responses and the
`UNKNOWN_MEMBER` vs `AUTHORIZATION_DENIED` semantics — which the incident
runbook (README Section B) and several tests deliberately rely on for
2am debuggability. With no reachable exploit under the current mock fixtures
and the branch otherwise merge-ready, changing the contract right before
submission is unwarranted churn. It should be a deliberate design decision,
not a last-minute edit.

**Proposed fix (when scheduled):** Decide the desired contract explicitly
(unified "not accessible" error vs. distinct codes gated on caller scope),
then either (a) run `authorize` before the member existence check, or
(b) map both conditions to one caller-facing error while keeping the precise
reason in the (PII-safe, server-side) structured logs for debugging. Update
the affected REST/MCP/eval tests and the runbook to match the chosen contract.

**Evidence:** `app/services/recommendation_service.py` (fetch-then-authorize
order in both methods); `app/models/errors.py` (`UnknownMemberError` = 404,
`AuthorizationDeniedError` = 403).
