# Agentic Travel Recommendations Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lean, deterministic multi-tenant travel recommendation service exposed over REST and an MCP stdio server, where partner business rules are enforced in a deterministic backend that the LLM/agent can never bypass.

**Architecture:** One Python service with a single shared orchestration "brain" (`RecommendationService`) fronted by three thin adapters (FastAPI REST, FastMCP stdio, CLI). A deterministic generator produces candidate offers from member facts; a deterministic ordered rule engine applies partner category exclusions then recommendation caps. A tenant guard runs on every member access. No LLM call inside the service.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, pydantic-settings, MCP Python SDK (FastMCP), pytest, httpx (TestClient), Docker.

## Global Constraints

- **Python 3.11+** (uses `X | Y` unions, `list[T]`, `date`).
- **Deterministic backend is source of truth.** No LLM call inside the service. No API key required to run, test, or demo.
- **No third-party observability platform.** No LangSmith. Structured JSON logs only; production framing is AWS/Azure-native (CloudWatch/App Insights, X-Ray/OTel).
- **Partner config is READ-ONLY.**
- **Rule order is fixed:** category exclusions first, then recommendation caps.
- **Fail closed:** missing context/config, unknown member, schema failure, or tenant mismatch → safe structured error. No stack traces or raw PII in responses or logs.
- **REST and MCP share ONE service layer.** No duplicated business logic; MCP tools never bypass the rule engine or the tenant guard.
- **Loyalty tiers:** Silver / Gold / Platinum only.
- **Travel history:** max 5 items, each with destination, dates, booking type.
- **Partner fixtures:** one capped at 3, one unlimited, one excluding cruises.
- **All Pydantic models use `extra="forbid"`.**
- **Commit messages:** descriptive; NEVER reference "PR", "M1"/milestone numbers, or task IDs.
- **Every task ends green:** write tests first, watch them fail, implement, watch them pass, commit.

---

## File Structure

```
app/
  __init__.py
  main.py                     # FastAPI app, routers, exception handlers, logging init
  config.py                   # pydantic-settings Settings
  dependencies.py             # build/wire the shared RecommendationService
  logging_config.py           # JSON logging + safe_log_fields (PII-safe)
  api/
    __init__.py
    health.py                 # GET /health
    recommendations.py        # POST /recommendations
  mcp/
    __init__.py
    server.py                 # FastMCP stdio server, 2 tools, safe-error wrapper
  security/
    __init__.py
    context.py                # AgentContext + build_context  (SHARED)
    tenant_guard.py           # authorize(ctx, member)
  services/
    __init__.py
    member_service.py         # mock dict-backed member lookup
    partner_config_service.py # mock dict-backed read-only partner config
    recommendation_generator.py  # deterministic, rule-unaware
    recommendation_service.py    # orchestration brain (both guarded methods)
  rules/
    __init__.py
    base.py                   # Rule protocol + RuleOutcome
    category_exclusion_rule.py
    max_recommendations_rule.py
    rule_engine.py            # ordered pipeline + RuleMetadata
  models/
    __init__.py
    common.py                 # enums (LoyaltyTier, Category, Source) + stable_id
    member.py                 # TravelHistoryItem, MemberProfile, MemberProfileOutput
    partner_config.py         # PartnerConfig
    recommendation.py         # Recommendation, RemovedRecommendation, RuleMetadata,
                              #   RecommendationResponse, RecommendationRequest
    errors.py                 # ErrorCode, ErrorResponse, domain exceptions
cli/
  __init__.py
  demo.py
tests/
  __init__.py
  conftest.py                 # shared fixtures: context builder, service
  test_models.py
  test_member_service.py
  test_partner_config_service.py
  test_recommendation_generator.py
  test_rule_engine.py
  test_recommendation_service.py
  test_logging.py
  test_recommendations_api.py
  test_health.py
  test_mcp_tools.py
  evals/
    __init__.py
    test_tenant_isolation_eval.py
    test_cruise_exclusion_eval.py
    test_cap_enforcement_eval.py
    test_fail_closed_eval.py
Dockerfile
docker-compose.yml
requirements.txt
.env.example
.gitignore
pytest.ini
README.md
```

Fixtures (single source of truth, used by services and tests):
- Partners: `partner_capped` (max 3), `partner_unlimited` (None), `partner_no_cruise` (excludes Cruise, max None), plus `partner_missing` referenced by a member but absent from config → drives missing-config path.
- Members: `M-silver-capped` (Silver/partner_capped), `M-gold-unlimited` (Gold/partner_unlimited), `M-plat-nocruise` (Platinum/partner_no_cruise), `M-plat-capped` (Platinum/partner_capped), `M-orphan` (Silver/partner_missing). Unknown id: `M-nope` (absent).

---

### Task 1: Project skeleton + health endpoint

**Files:**
- Create: `requirements.txt`, `.gitignore`, `.env.example`, `pytest.ini`, `app/__init__.py`, `app/config.py`, `app/main.py`, `app/api/__init__.py`, `app/api/health.py`, `tests/__init__.py`, `tests/test_health.py`
- Test: `tests/test_health.py`

**Interfaces:**
- Produces: `app.main:app` (FastAPI instance); `GET /health` → `{"status": "ok"}`; `app.config.Settings` with `app_name: str`, `log_level: str`.

- [ ] **Step 1: Create `requirements.txt`**

```
fastapi>=0.110
uvicorn[standard]>=0.29
pydantic>=2.6
pydantic-settings>=2.2
mcp>=1.2
httpx>=0.27
pytest>=8.0
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
.venv/
venv/
.env
.pytest_cache/
*.egg-info/
.DS_Store
```

- [ ] **Step 3: Create `.env.example`**

```
APP_NAME=agentic-travel-recs
LOG_LEVEL=INFO
# MCP server caller identity (trusted launch context in the mock; replace with
# signed workload identity / JWT / gateway-injected tenant in production)
PARTNER_ID=partner_capped
AGENT_ID=agent-demo
```

- [ ] **Step 4: Create `pytest.ini`**

```
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -q
```

- [ ] **Step 5: Create empty `app/__init__.py` and `tests/__init__.py`**

Both files are empty.

- [ ] **Step 6: Create `app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "agentic-travel-recs"
    log_level: str = "INFO"


settings = Settings()
```

- [ ] **Step 7: Write the failing test `tests/test_health.py`**

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 8: Run test to verify it fails**

Run: `pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'` (or import error).

- [ ] **Step 9: Create `app/api/__init__.py` (empty) and `app/api/health.py`**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 10: Create `app/main.py`**

```python
from fastapi import FastAPI

from app.api import health
from app.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(health.router)
```

- [ ] **Step 11: Run test to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 12: Confirm the app boots**

Run: `python -c "from app.main import app; print(app.title)"`
Expected: prints `agentic-travel-recs`

- [ ] **Step 13: Commit**

```bash
git add requirements.txt .gitignore .env.example pytest.ini app tests
git commit -m "feat: add service skeleton with health endpoint and config"
```

---

### Task 2: Domain models + enums + errors

**Files:**
- Create: `app/models/__init__.py`, `app/models/common.py`, `app/models/member.py`, `app/models/partner_config.py`, `app/models/recommendation.py`, `app/models/errors.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `common.LoyaltyTier` = enum `SILVER="Silver"`, `GOLD="Gold"`, `PLATINUM="Platinum"`
  - `common.Category` = enum `HOTEL="Hotel"`, `FLIGHT="Flight"`, `CRUISE="Cruise"`, `CAR_RENTAL="CarRental"`
  - `common.Source` = enum `REST="rest"`, `MCP="mcp"`, `CLI="cli"`
  - `common.stable_id(*parts: str) -> str`
  - `member.TravelHistoryItem`, `member.MemberProfile` (`travel_history` max_length 5), `member.MemberProfileOutput`
  - `partner_config.PartnerConfig(partner_id, excluded_categories: list[Category], max_recommendations: int | None)`
  - `recommendation.Recommendation(recommendation_id, category, title, reason, score)`, `recommendation.RemovedRecommendation(recommendation_id, category, rule)`, `recommendation.RuleMetadata(...)`, `recommendation.RecommendationResponse(...)`, `recommendation.RecommendationRequest(member_id)`
  - `errors.ErrorCode`, `errors.ErrorResponse(error_code, message, request_id)`, exceptions `DomainError`, `UnknownMemberError`, `MissingPartnerConfigError`, `AuthorizationDeniedError` — each with class attrs `error_code: ErrorCode` and `http_status: int`.

- [ ] **Step 1: Write the failing test `tests/test_models.py`**

```python
from datetime import date

import pytest
from pydantic import ValidationError

from app.models.common import Category, LoyaltyTier, Source, stable_id
from app.models.member import MemberProfile, MemberProfileOutput, TravelHistoryItem
from app.models.partner_config import PartnerConfig
from app.models.recommendation import (
    Recommendation,
    RecommendationResponse,
    RemovedRecommendation,
    RuleMetadata,
)
from app.models.errors import (
    AuthorizationDeniedError,
    ErrorCode,
    ErrorResponse,
    MissingPartnerConfigError,
    UnknownMemberError,
)


def _history():
    return TravelHistoryItem(
        destination="Lisbon",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 5),
        booking_type=Category.HOTEL,
    )


def test_stable_id_is_deterministic():
    assert stable_id("Hotel", "Lisbon") == stable_id("Hotel", "Lisbon")
    assert stable_id("Hotel", "Lisbon") != stable_id("Flight", "Lisbon")


def test_member_profile_valid():
    m = MemberProfile(
        member_id="M1",
        partner_id="partner_capped",
        loyalty_tier=LoyaltyTier.GOLD,
        travel_history=[_history()],
    )
    assert m.loyalty_tier is LoyaltyTier.GOLD


def test_member_profile_rejects_more_than_five_history_items():
    with pytest.raises(ValidationError):
        MemberProfile(
            member_id="M1",
            partner_id="p",
            loyalty_tier=LoyaltyTier.GOLD,
            travel_history=[_history() for _ in range(6)],
        )


def test_member_profile_rejects_bad_tier():
    with pytest.raises(ValidationError):
        MemberProfile(
            member_id="M1",
            partner_id="p",
            loyalty_tier="Bronze",
            travel_history=[],
        )


def test_models_forbid_extra_fields():
    with pytest.raises(ValidationError):
        PartnerConfig(partner_id="p", excluded_categories=[], max_recommendations=3, surprise=1)


def test_partner_config_unlimited_defaults():
    c = PartnerConfig(partner_id="p")
    assert c.max_recommendations is None
    assert c.excluded_categories == []


def test_recommendation_response_round_trips():
    resp = RecommendationResponse(
        member_id="M1",
        partner_id="p",
        loyalty_tier=LoyaltyTier.SILVER,
        request_id="req-1",
        recommendations=[
            Recommendation(
                recommendation_id="r1",
                category=Category.HOTEL,
                title="Hotel in Lisbon",
                reason="because",
                score=0.9,
            )
        ],
        rule_metadata=RuleMetadata(
            applied_rules=["category_exclusion"],
            excluded_categories=[Category.CRUISE],
            removed_recommendations=[
                RemovedRecommendation(
                    recommendation_id="rx", category=Category.CRUISE, rule="category_exclusion"
                )
            ],
            candidate_count=2,
            final_count=1,
            max_allowed=None,
        ),
    )
    assert resp.rule_metadata.final_count == 1
    assert resp.recommendations[0].category is Category.HOTEL


def test_source_enum_values():
    assert Source.REST.value == "rest"
    assert Source.MCP.value == "mcp"
    assert Source.CLI.value == "cli"


def test_error_response_and_exceptions():
    err = ErrorResponse(error_code=ErrorCode.UNKNOWN_MEMBER, message="nope", request_id="r")
    assert err.error_code is ErrorCode.UNKNOWN_MEMBER
    assert UnknownMemberError("x").http_status == 404
    assert MissingPartnerConfigError("x").http_status == 404
    assert AuthorizationDeniedError("x").http_status == 403
    assert UnknownMemberError("x").error_code is ErrorCode.UNKNOWN_MEMBER
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — import errors (`app.models` does not exist).

- [ ] **Step 3: Create `app/models/__init__.py` (empty) and `app/models/common.py`**

```python
import hashlib
from enum import Enum


class LoyaltyTier(str, Enum):
    SILVER = "Silver"
    GOLD = "Gold"
    PLATINUM = "Platinum"


class Category(str, Enum):
    HOTEL = "Hotel"
    FLIGHT = "Flight"
    CRUISE = "Cruise"
    CAR_RENTAL = "CarRental"


class Source(str, Enum):
    REST = "rest"
    MCP = "mcp"
    CLI = "cli"


def stable_id(*parts: str) -> str:
    """Deterministic short id from its parts. No randomness, no clock."""
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
```

- [ ] **Step 4: Create `app/models/member.py`**

```python
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import Category, LoyaltyTier


class TravelHistoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: str
    start_date: date
    end_date: date
    booking_type: Category


class MemberProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: str
    partner_id: str
    loyalty_tier: LoyaltyTier
    travel_history: list[TravelHistoryItem] = Field(default_factory=list, max_length=5)


class MemberProfileOutput(BaseModel):
    """Safe profile returned by the get_member_profile tool."""

    model_config = ConfigDict(extra="forbid")

    member_id: str
    partner_id: str
    loyalty_tier: LoyaltyTier
    travel_history: list[TravelHistoryItem] = Field(default_factory=list)
```

- [ ] **Step 5: Create `app/models/partner_config.py`**

```python
from pydantic import BaseModel, ConfigDict, Field

from app.models.common import Category


class PartnerConfig(BaseModel):
    """Read-only partner configuration. max_recommendations None == unlimited."""

    model_config = ConfigDict(extra="forbid")

    partner_id: str
    excluded_categories: list[Category] = Field(default_factory=list)
    max_recommendations: int | None = None
```

- [ ] **Step 6: Create `app/models/recommendation.py`**

```python
from pydantic import BaseModel, ConfigDict, Field

from app.models.common import Category, LoyaltyTier


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str
    category: Category
    title: str
    reason: str
    score: float


class RemovedRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str
    category: Category
    rule: str


class RuleMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    applied_rules: list[str] = Field(default_factory=list)
    excluded_categories: list[Category] = Field(default_factory=list)
    removed_recommendations: list[RemovedRecommendation] = Field(default_factory=list)
    candidate_count: int
    final_count: int
    max_allowed: int | None


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: str
    partner_id: str
    loyalty_tier: LoyaltyTier
    request_id: str
    recommendations: list[Recommendation]
    rule_metadata: RuleMetadata


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: str
```

- [ ] **Step 7: Create `app/models/errors.py`**

```python
from enum import Enum

from pydantic import BaseModel


class ErrorCode(str, Enum):
    UNKNOWN_MEMBER = "UNKNOWN_MEMBER"
    MISSING_PARTNER_CONFIG = "MISSING_PARTNER_CONFIG"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"


class ErrorResponse(BaseModel):
    error_code: ErrorCode
    message: str
    request_id: str


class DomainError(Exception):
    """Base for safe, classified domain failures."""

    error_code: ErrorCode = ErrorCode.TOOL_EXECUTION_ERROR
    http_status: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnknownMemberError(DomainError):
    error_code = ErrorCode.UNKNOWN_MEMBER
    http_status = 404


class MissingPartnerConfigError(DomainError):
    error_code = ErrorCode.MISSING_PARTNER_CONFIG
    http_status = 404


class AuthorizationDeniedError(DomainError):
    error_code = ErrorCode.AUTHORIZATION_DENIED
    http_status = 403
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (all tests)

- [ ] **Step 9: Commit**

```bash
git add app/models tests/test_models.py
git commit -m "feat: add typed domain models, enums, and classified domain errors"
```

---

### Task 3: Shared AgentContext + builder

**Files:**
- Create: `app/security/__init__.py`, `app/security/context.py`, `tests/conftest.py`
- Test: fixtures exercised later; add `tests/test_context.py`

**Interfaces:**
- Produces:
  - `security.context.AgentContext(request_id, agent_id, partner_id, source)` — frozen, `extra="forbid"`
  - `security.context.build_context(*, agent_id: str, partner_id: str, source: Source, request_id: str | None = None) -> AgentContext` — generates `request_id` (uuid4 hex) when not provided
  - `tests/conftest.py`: `make_context(partner_id="partner_capped", agent_id="agent-test", source=Source.CLI)` fixture

- [ ] **Step 1: Write the failing test `tests/test_context.py`**

```python
from app.models.common import Source
from app.security.context import AgentContext, build_context


def test_build_context_generates_request_id():
    ctx = build_context(agent_id="a", partner_id="p", source=Source.REST)
    assert ctx.request_id
    assert ctx.partner_id == "p"
    assert ctx.source is Source.REST


def test_build_context_keeps_provided_request_id():
    ctx = build_context(agent_id="a", partner_id="p", source=Source.MCP, request_id="req-9")
    assert ctx.request_id == "req-9"


def test_build_context_unique_ids_per_call():
    a = build_context(agent_id="a", partner_id="p", source=Source.MCP)
    b = build_context(agent_id="a", partner_id="p", source=Source.MCP)
    assert a.request_id != b.request_id


def test_context_is_frozen():
    ctx = AgentContext(request_id="r", agent_id="a", partner_id="p", source=Source.CLI)
    try:
        ctx.partner_id = "other"
        assert False, "expected frozen model to reject mutation"
    except Exception:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_context.py -v`
Expected: FAIL — `app.security.context` does not exist.

- [ ] **Step 3: Create `app/security/__init__.py` (empty) and `app/security/context.py`**

```python
import uuid

from pydantic import BaseModel, ConfigDict

from app.models.common import Source


class AgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    agent_id: str
    partner_id: str
    source: Source


def build_context(
    *,
    agent_id: str,
    partner_id: str,
    source: Source,
    request_id: str | None = None,
) -> AgentContext:
    return AgentContext(
        request_id=request_id or uuid.uuid4().hex,
        agent_id=agent_id,
        partner_id=partner_id,
        source=source,
    )
```

- [ ] **Step 4: Create `tests/conftest.py`**

```python
import pytest

from app.models.common import Source
from app.security.context import AgentContext, build_context


@pytest.fixture
def make_context():
    def _make(partner_id="partner_capped", agent_id="agent-test", source=Source.CLI) -> AgentContext:
        return build_context(agent_id=agent_id, partner_id=partner_id, source=source)

    return _make
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_context.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/security tests/conftest.py tests/test_context.py
git commit -m "feat: add shared AgentContext and context builder"
```

---

### Task 4: Mock member service

**Files:**
- Create: `app/services/__init__.py`, `app/services/member_service.py`
- Test: `tests/test_member_service.py`

**Interfaces:**
- Produces: `member_service.MemberService` with `get(member_id: str) -> MemberProfile` (raises `UnknownMemberError`). Class-level fixture dict `MemberService.MEMBERS`. Member ids and partner mapping per the File Structure fixtures.

- [ ] **Step 1: Write the failing test `tests/test_member_service.py`**

```python
import pytest

from app.models.common import LoyaltyTier
from app.models.errors import UnknownMemberError
from app.services.member_service import MemberService


def test_known_member_returns_profile():
    svc = MemberService()
    m = svc.get("M-plat-nocruise")
    assert m.loyalty_tier is LoyaltyTier.PLATINUM
    assert m.partner_id == "partner_no_cruise"
    assert len(m.travel_history) <= 5


def test_members_span_multiple_partners():
    svc = MemberService()
    partners = {svc.get(mid).partner_id for mid in svc.MEMBERS}
    assert {"partner_capped", "partner_unlimited", "partner_no_cruise"} <= partners


def test_unknown_member_raises():
    svc = MemberService()
    with pytest.raises(UnknownMemberError):
        svc.get("M-nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_member_service.py -v`
Expected: FAIL — `app.services.member_service` does not exist.

- [ ] **Step 3: Create `app/services/__init__.py` (empty) and `app/services/member_service.py`**

```python
from datetime import date

from app.models.common import Category, LoyaltyTier
from app.models.errors import UnknownMemberError
from app.models.member import MemberProfile, TravelHistoryItem


def _h(dest: str, bt: Category, m: int) -> TravelHistoryItem:
    return TravelHistoryItem(
        destination=dest,
        start_date=date(2026, m, 1),
        end_date=date(2026, m, 6),
        booking_type=bt,
    )


class MemberService:
    """Mock, dict-backed member lookup. Returns Pydantic models, never dicts."""

    MEMBERS: dict[str, MemberProfile] = {
        "M-silver-capped": MemberProfile(
            member_id="M-silver-capped",
            partner_id="partner_capped",
            loyalty_tier=LoyaltyTier.SILVER,
            travel_history=[_h("Lisbon", Category.HOTEL, 1), _h("Rome", Category.FLIGHT, 2)],
        ),
        "M-gold-unlimited": MemberProfile(
            member_id="M-gold-unlimited",
            partner_id="partner_unlimited",
            loyalty_tier=LoyaltyTier.GOLD,
            travel_history=[
                _h("Tokyo", Category.HOTEL, 3),
                _h("Osaka", Category.CAR_RENTAL, 4),
                _h("Seoul", Category.FLIGHT, 5),
            ],
        ),
        "M-plat-nocruise": MemberProfile(
            member_id="M-plat-nocruise",
            partner_id="partner_no_cruise",
            loyalty_tier=LoyaltyTier.PLATINUM,
            travel_history=[_h("Miami", Category.HOTEL, 6), _h("Nassau", Category.CRUISE, 7)],
        ),
        "M-plat-capped": MemberProfile(
            member_id="M-plat-capped",
            partner_id="partner_capped",
            loyalty_tier=LoyaltyTier.PLATINUM,
            travel_history=[
                _h("Paris", Category.HOTEL, 8),
                _h("Nice", Category.FLIGHT, 9),
                _h("Cannes", Category.CAR_RENTAL, 10),
            ],
        ),
        "M-orphan": MemberProfile(
            member_id="M-orphan",
            partner_id="partner_missing",
            loyalty_tier=LoyaltyTier.SILVER,
            travel_history=[_h("Denver", Category.HOTEL, 11)],
        ),
    }

    def get(self, member_id: str) -> MemberProfile:
        member = self.MEMBERS.get(member_id)
        if member is None:
            raise UnknownMemberError(f"Member '{member_id}' not found.")
        return member.model_copy(deep=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_member_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/__init__.py app/services/member_service.py tests/test_member_service.py
git commit -m "feat: add mock member service with multi-partner fixtures"
```

---

### Task 5: Mock partner config service (read-only)

**Files:**
- Create: `app/services/partner_config_service.py`
- Test: `tests/test_partner_config_service.py`

**Interfaces:**
- Produces: `partner_config_service.PartnerConfigService` with `get(partner_id: str) -> PartnerConfig` (raises `MissingPartnerConfigError`). Fixtures: `partner_capped` (max 3), `partner_unlimited` (None), `partner_no_cruise` (excludes Cruise, None). `partner_missing` absent on purpose.

- [ ] **Step 1: Write the failing test `tests/test_partner_config_service.py`**

```python
import pytest

from app.models.common import Category
from app.models.errors import MissingPartnerConfigError
from app.services.partner_config_service import PartnerConfigService


def test_capped_partner():
    cfg = PartnerConfigService().get("partner_capped")
    assert cfg.max_recommendations == 3
    assert cfg.excluded_categories == []


def test_unlimited_partner():
    cfg = PartnerConfigService().get("partner_unlimited")
    assert cfg.max_recommendations is None


def test_cruise_excluding_partner():
    cfg = PartnerConfigService().get("partner_no_cruise")
    assert Category.CRUISE in cfg.excluded_categories


def test_missing_partner_raises():
    with pytest.raises(MissingPartnerConfigError):
        PartnerConfigService().get("partner_missing")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_partner_config_service.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create `app/services/partner_config_service.py`**

```python
from app.models.common import Category
from app.models.errors import MissingPartnerConfigError
from app.models.partner_config import PartnerConfig


class PartnerConfigService:
    """Mock, READ-ONLY partner config lookup. No write methods by design."""

    CONFIGS: dict[str, PartnerConfig] = {
        "partner_capped": PartnerConfig(partner_id="partner_capped", max_recommendations=3),
        "partner_unlimited": PartnerConfig(partner_id="partner_unlimited", max_recommendations=None),
        "partner_no_cruise": PartnerConfig(
            partner_id="partner_no_cruise",
            excluded_categories=[Category.CRUISE],
            max_recommendations=None,
        ),
    }

    def get(self, partner_id: str) -> PartnerConfig:
        cfg = self.CONFIGS.get(partner_id)
        if cfg is None:
            raise MissingPartnerConfigError(f"No configuration for partner '{partner_id}'.")
        return cfg.model_copy(deep=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_partner_config_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/partner_config_service.py tests/test_partner_config_service.py
git commit -m "feat: add read-only mock partner config service"
```

---

### Task 6: Deterministic recommendation generator

**Files:**
- Create: `app/services/recommendation_generator.py`
- Test: `tests/test_recommendation_generator.py`

**Interfaces:**
- Consumes: `MemberProfile`, `Category`, `LoyaltyTier`, `stable_id`, `Recommendation`.
- Produces: `recommendation_generator.RecommendationGenerator` with `generate(member: MemberProfile) -> list[Recommendation]`. Rule-unaware. Deterministic. Platinum always yields a Cruise candidate.

- [ ] **Step 1: Write the failing test `tests/test_recommendation_generator.py`**

```python
from app.models.common import Category, LoyaltyTier
from app.services.member_service import MemberService
from app.services.recommendation_generator import RecommendationGenerator


def _gen(member_id):
    member = MemberService().get(member_id)
    return RecommendationGenerator().generate(member)


def test_generator_is_deterministic():
    a = _gen("M-gold-unlimited")
    b = _gen("M-gold-unlimited")
    assert [r.recommendation_id for r in a] == [r.recommendation_id for r in b]


def test_platinum_produces_a_cruise_candidate():
    cats = {r.category for r in _gen("M-plat-nocruise")}
    assert Category.CRUISE in cats  # generator is rule-unaware; engine removes it later


def test_generator_output_is_sorted_by_score_then_id():
    recs = _gen("M-gold-unlimited")
    keys = [(-r.score, r.recommendation_id) for r in recs]
    assert keys == sorted(keys)


def test_generator_has_no_duplicate_ids():
    recs = _gen("M-plat-capped")
    ids = [r.recommendation_id for r in recs]
    assert len(ids) == len(set(ids))


def test_silver_does_not_get_cruise_from_tier():
    cats = [r.category for r in _gen("M-silver-capped")]
    # Silver tier catalog has no cruise; and this member has no cruise history
    assert Category.CRUISE not in cats
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_recommendation_generator.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create `app/services/recommendation_generator.py`**

```python
from app.models.common import Category, LoyaltyTier, stable_id
from app.models.member import MemberProfile
from app.models.recommendation import Recommendation

# Per-tier perk catalog (category, title-suffix). Platinum intentionally includes
# a Cruise so the exclusion path is always exercised end-to-end.
TIER_CATALOG: dict[LoyaltyTier, list[Category]] = {
    LoyaltyTier.SILVER: [Category.HOTEL],
    LoyaltyTier.GOLD: [Category.HOTEL, Category.FLIGHT],
    LoyaltyTier.PLATINUM: [Category.HOTEL, Category.FLIGHT, Category.CRUISE],
}

# Deterministic scores. History affinity ranks above generic tier perks.
_HISTORY_SCORE = 0.9
_TIER_SCORE = 0.6


class RecommendationGenerator:
    """Deterministic candidate generation. Knows member facts only; never
    partner rules."""

    def _offer(self, category: Category, seed: str, title: str, reason: str, score: float) -> Recommendation:
        return Recommendation(
            recommendation_id=stable_id(category.value, title, seed),
            category=category,
            title=title,
            reason=reason,
            score=score,
        )

    def generate(self, member: MemberProfile) -> list[Recommendation]:
        candidates: list[Recommendation] = []

        # 1. History affinity: each past booking seeds a same-category offer.
        for item in member.travel_history:
            title = f"{item.booking_type.value} deal in {item.destination}"
            reason = f"Based on your recent {item.booking_type.value} booking in {item.destination}."
            candidates.append(
                self._offer(item.booking_type, item.destination, title, reason, _HISTORY_SCORE)
            )

        # 2. Tier perks: deterministic per-tier catalog.
        tier = member.loyalty_tier
        for category in TIER_CATALOG[tier]:
            title = f"{tier.value} {category.value} perk"
            reason = f"Exclusive {category.value} offer for {tier.value} members."
            candidates.append(self._offer(category, tier.value, title, reason, _TIER_SCORE))

        # 3. De-dupe by (category, title), stable score-desc then id-asc sort.
        seen: set[tuple[str, str]] = set()
        deduped: list[Recommendation] = []
        for rec in candidates:
            key = (rec.category.value, rec.title)
            if key not in seen:
                seen.add(key)
                deduped.append(rec)

        return sorted(deduped, key=lambda r: (-r.score, r.recommendation_id))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_recommendation_generator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/recommendation_generator.py tests/test_recommendation_generator.py
git commit -m "feat: add deterministic rule-unaware recommendation generator"
```

---

### Task 7: Rule engine (exclusion → cap)

**Files:**
- Create: `app/rules/__init__.py`, `app/rules/base.py`, `app/rules/category_exclusion_rule.py`, `app/rules/max_recommendations_rule.py`, `app/rules/rule_engine.py`
- Test: `tests/test_rule_engine.py`

**Interfaces:**
- Consumes: `Recommendation`, `RemovedRecommendation`, `RuleMetadata`, `PartnerConfig`, `Category`.
- Produces:
  - `base.RuleOutcome(kept: list[Recommendation], removed: list[RemovedRecommendation], applied: bool)` (dataclass)
  - `base.Rule` protocol: attribute `name: str`, method `apply(candidates, config) -> RuleOutcome`
  - `category_exclusion_rule.CategoryExclusionRule` (`name="category_exclusion"`)
  - `max_recommendations_rule.MaxRecommendationsRule` (`name="max_recommendations"`)
  - `rule_engine.RuleEngine(rules=None)` with `apply(candidates, config) -> tuple[list[Recommendation], RuleMetadata]`; default ordered rules = `[CategoryExclusionRule(), MaxRecommendationsRule()]`.

- [ ] **Step 1: Write the failing test `tests/test_rule_engine.py`**

```python
from app.models.common import Category
from app.models.partner_config import PartnerConfig
from app.models.recommendation import Recommendation
from app.rules.category_exclusion_rule import CategoryExclusionRule
from app.rules.max_recommendations_rule import MaxRecommendationsRule
from app.rules.rule_engine import RuleEngine


def _rec(rid, category, score=0.5):
    return Recommendation(
        recommendation_id=rid, category=category, title=rid, reason="r", score=score
    )


def _candidates():
    return [
        _rec("c1", Category.CRUISE),
        _rec("c2", Category.CRUISE),
        _rec("c3", Category.CRUISE),
        _rec("h1", Category.HOTEL),
        _rec("h2", Category.HOTEL),
        _rec("f1", Category.FLIGHT),
    ]


def test_cruise_exclusion_removes_all_cruises():
    cfg = PartnerConfig(partner_id="p", excluded_categories=[Category.CRUISE])
    final, meta = RuleEngine().apply(_candidates(), cfg)
    assert all(r.category is not Category.CRUISE for r in final)
    assert "category_exclusion" in meta.applied_rules
    assert {r.recommendation_id for r in meta.removed_recommendations} >= {"c1", "c2", "c3"}


def test_cap_limits_final_count():
    cfg = PartnerConfig(partner_id="p", max_recommendations=2)
    final, meta = RuleEngine().apply(_candidates(), cfg)
    assert len(final) == 2
    assert meta.final_count == 2
    assert "max_recommendations" in meta.applied_rules


def test_unlimited_partner_passes_everything():
    cfg = PartnerConfig(partner_id="p", max_recommendations=None)
    final, meta = RuleEngine().apply(_candidates(), cfg)
    assert len(final) == len(_candidates())
    assert "max_recommendations" not in meta.applied_rules


def test_exclusion_runs_before_cap():
    # 3 cruises first, then eligible hotels/flight. If cap ran first, the top 3
    # (all cruises) would fill the cap and then be removed, leaving 0. Exclusion
    # first means the cap applies only to eligible offers -> 3 non-cruise results.
    cfg = PartnerConfig(
        partner_id="p", excluded_categories=[Category.CRUISE], max_recommendations=3
    )
    final, meta = RuleEngine().apply(_candidates(), cfg)
    assert len(final) == 3
    assert all(r.category is not Category.CRUISE for r in final)
    assert meta.applied_rules == ["category_exclusion", "max_recommendations"]


def test_removed_records_carry_rule_reason():
    cfg = PartnerConfig(
        partner_id="p", excluded_categories=[Category.CRUISE], max_recommendations=1
    )
    _, meta = RuleEngine().apply(_candidates(), cfg)
    rules_used = {rr.rule for rr in meta.removed_recommendations}
    assert rules_used == {"category_exclusion", "max_recommendations"}


def test_new_rule_can_be_injected_without_touching_generator():
    # A no-op custom rule proves the engine composes an ordered rule list.
    class DropFlights:
        name = "drop_flights"

        def apply(self, candidates, config):
            from app.rules.base import RuleOutcome
            from app.models.recommendation import RemovedRecommendation

            kept, removed = [], []
            for c in candidates:
                if c.category is Category.FLIGHT:
                    removed.append(
                        RemovedRecommendation(
                            recommendation_id=c.recommendation_id, category=c.category, rule=self.name
                        )
                    )
                else:
                    kept.append(c)
            return RuleOutcome(kept, removed, bool(removed))

    engine = RuleEngine(rules=[DropFlights()])
    cfg = PartnerConfig(partner_id="p")
    final, meta = engine.apply(_candidates(), cfg)
    assert all(r.category is not Category.FLIGHT for r in final)
    assert "drop_flights" in meta.applied_rules
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_rule_engine.py -v`
Expected: FAIL — `app.rules` modules do not exist.

- [ ] **Step 3: Create `app/rules/__init__.py` (empty) and `app/rules/base.py`**

```python
from dataclasses import dataclass
from typing import Protocol

from app.models.partner_config import PartnerConfig
from app.models.recommendation import Recommendation, RemovedRecommendation


@dataclass
class RuleOutcome:
    kept: list[Recommendation]
    removed: list[RemovedRecommendation]
    applied: bool


class Rule(Protocol):
    name: str

    def apply(self, candidates: list[Recommendation], config: PartnerConfig) -> RuleOutcome: ...
```

- [ ] **Step 4: Create `app/rules/category_exclusion_rule.py`**

```python
from app.models.partner_config import PartnerConfig
from app.models.recommendation import Recommendation, RemovedRecommendation
from app.rules.base import RuleOutcome


class CategoryExclusionRule:
    name = "category_exclusion"

    def apply(self, candidates: list[Recommendation], config: PartnerConfig) -> RuleOutcome:
        if not config.excluded_categories:
            return RuleOutcome(kept=list(candidates), removed=[], applied=False)

        excluded = set(config.excluded_categories)
        kept: list[Recommendation] = []
        removed: list[RemovedRecommendation] = []
        for rec in candidates:
            if rec.category in excluded:
                removed.append(
                    RemovedRecommendation(
                        recommendation_id=rec.recommendation_id, category=rec.category, rule=self.name
                    )
                )
            else:
                kept.append(rec)
        return RuleOutcome(kept=kept, removed=removed, applied=True)
```

- [ ] **Step 5: Create `app/rules/max_recommendations_rule.py`**

```python
from app.models.partner_config import PartnerConfig
from app.models.recommendation import Recommendation, RemovedRecommendation
from app.rules.base import RuleOutcome


class MaxRecommendationsRule:
    name = "max_recommendations"

    def apply(self, candidates: list[Recommendation], config: PartnerConfig) -> RuleOutcome:
        if config.max_recommendations is None:
            return RuleOutcome(kept=list(candidates), removed=[], applied=False)

        limit = config.max_recommendations
        kept = candidates[:limit]
        removed = [
            RemovedRecommendation(
                recommendation_id=rec.recommendation_id, category=rec.category, rule=self.name
            )
            for rec in candidates[limit:]
        ]
        return RuleOutcome(kept=kept, removed=removed, applied=True)
```

- [ ] **Step 6: Create `app/rules/rule_engine.py`**

```python
from app.models.partner_config import PartnerConfig
from app.models.recommendation import Recommendation, RemovedRecommendation, RuleMetadata
from app.rules.base import Rule
from app.rules.category_exclusion_rule import CategoryExclusionRule
from app.rules.max_recommendations_rule import MaxRecommendationsRule


class RuleEngine:
    """Ordered, deterministic rule pipeline. Exclusions run before caps."""

    def __init__(self, rules: list[Rule] | None = None) -> None:
        self.rules: list[Rule] = rules if rules is not None else [
            CategoryExclusionRule(),
            MaxRecommendationsRule(),
        ]

    def apply(
        self, candidates: list[Recommendation], config: PartnerConfig
    ) -> tuple[list[Recommendation], RuleMetadata]:
        applied_rules: list[str] = []
        removed_all: list[RemovedRecommendation] = []
        current = list(candidates)

        for rule in self.rules:
            outcome = rule.apply(current, config)
            current = outcome.kept
            removed_all.extend(outcome.removed)
            if outcome.applied:
                applied_rules.append(rule.name)

        meta = RuleMetadata(
            applied_rules=applied_rules,
            excluded_categories=list(config.excluded_categories),
            removed_recommendations=removed_all,
            candidate_count=len(candidates),
            final_count=len(current),
            max_allowed=config.max_recommendations,
        )
        return current, meta
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_rule_engine.py -v`
Expected: PASS (all, including `test_exclusion_runs_before_cap`)

- [ ] **Step 8: Commit**

```bash
git add app/rules tests/test_rule_engine.py
git commit -m "feat: add deterministic rule engine with exclusion-before-cap ordering"
```

---

### Task 8: Tenant guard + orchestration service (both guarded methods)

**Files:**
- Create: `app/security/tenant_guard.py`, `app/services/recommendation_service.py`, `app/dependencies.py`
- Test: `tests/test_recommendation_service.py`

**Interfaces:**
- Consumes: `AgentContext`, `MemberService`, `PartnerConfigService`, `RecommendationGenerator`, `RuleEngine`, `MemberProfileOutput`, `RecommendationResponse`, domain errors.
- Produces:
  - `tenant_guard.authorize(ctx: AgentContext, member: MemberProfile) -> None` (raises `AuthorizationDeniedError`)
  - `recommendation_service.RecommendationService(member_service, partner_config_service, generator, rule_engine)` with:
    - `get_member_profile(ctx, member_id) -> MemberProfileOutput`
    - `get_recommendations(ctx, member_id) -> RecommendationResponse`
  - `dependencies.get_recommendation_service() -> RecommendationService` (wires the default mocks)

- [ ] **Step 1: Write the failing test `tests/test_recommendation_service.py`**

```python
import pytest

from app.models.common import Category, LoyaltyTier, Source
from app.models.errors import (
    AuthorizationDeniedError,
    MissingPartnerConfigError,
    UnknownMemberError,
)
from app.security.context import build_context
from app.dependencies import get_recommendation_service


def _ctx(partner_id):
    return build_context(agent_id="a", partner_id=partner_id, source=Source.CLI)


def test_full_recommendation_flow():
    svc = get_recommendation_service()
    resp = svc.get_recommendations(_ctx("partner_capped"), "M-silver-capped")
    assert resp.member_id == "M-silver-capped"
    assert resp.partner_id == "partner_capped"
    assert len(resp.recommendations) <= 3
    assert resp.request_id


def test_cruise_excluded_for_platinum_member():
    svc = get_recommendation_service()
    resp = svc.get_recommendations(_ctx("partner_no_cruise"), "M-plat-nocruise")
    assert all(r.category is not Category.CRUISE for r in resp.recommendations)
    assert "category_exclusion" in resp.rule_metadata.applied_rules


def test_cap_enforced_for_capped_partner():
    svc = get_recommendation_service()
    resp = svc.get_recommendations(_ctx("partner_capped"), "M-plat-capped")
    assert len(resp.recommendations) <= 3


def test_get_member_profile_authorized():
    svc = get_recommendation_service()
    prof = svc.get_member_profile(_ctx("partner_no_cruise"), "M-plat-nocruise")
    assert prof.member_id == "M-plat-nocruise"
    assert prof.loyalty_tier is LoyaltyTier.PLATINUM


def test_get_recommendations_cross_partner_denied():
    svc = get_recommendation_service()
    with pytest.raises(AuthorizationDeniedError):
        svc.get_recommendations(_ctx("partner_unlimited"), "M-plat-nocruise")


def test_get_member_profile_cross_partner_denied():
    svc = get_recommendation_service()
    with pytest.raises(AuthorizationDeniedError):
        svc.get_member_profile(_ctx("partner_unlimited"), "M-plat-nocruise")


def test_unknown_member_raises():
    svc = get_recommendation_service()
    with pytest.raises(UnknownMemberError):
        svc.get_recommendations(_ctx("partner_capped"), "M-nope")


def test_missing_partner_config_raises():
    svc = get_recommendation_service()
    with pytest.raises(MissingPartnerConfigError):
        svc.get_recommendations(_ctx("partner_missing"), "M-orphan")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_recommendation_service.py -v`
Expected: FAIL — `app.dependencies` / service modules do not exist.

- [ ] **Step 3: Create `app/security/tenant_guard.py`**

```python
from app.models.errors import AuthorizationDeniedError
from app.models.member import MemberProfile
from app.security.context import AgentContext


def authorize(ctx: AgentContext, member: MemberProfile) -> None:
    """Fail closed if the caller's partner scope does not match the member's."""
    if ctx.partner_id != member.partner_id:
        raise AuthorizationDeniedError("Caller is not authorized for this member's partner.")
```

- [ ] **Step 4: Create `app/services/recommendation_service.py`**

```python
from app.models.member import MemberProfileOutput
from app.models.recommendation import RecommendationResponse
from app.security.context import AgentContext
from app.security.tenant_guard import authorize
from app.services.member_service import MemberService
from app.services.partner_config_service import PartnerConfigService
from app.services.recommendation_generator import RecommendationGenerator
from app.rules.rule_engine import RuleEngine


class RecommendationService:
    """The single shared brain. Every member access runs the tenant guard
    before any data is returned."""

    def __init__(
        self,
        member_service: MemberService,
        partner_config_service: PartnerConfigService,
        generator: RecommendationGenerator,
        rule_engine: RuleEngine,
    ) -> None:
        self._members = member_service
        self._configs = partner_config_service
        self._generator = generator
        self._rules = rule_engine

    def get_member_profile(self, ctx: AgentContext, member_id: str) -> MemberProfileOutput:
        member = self._members.get(member_id)          # unknown -> UnknownMemberError
        authorize(ctx, member)                         # mismatch -> AuthorizationDeniedError
        return MemberProfileOutput(
            member_id=member.member_id,
            partner_id=member.partner_id,
            loyalty_tier=member.loyalty_tier,
            travel_history=member.travel_history,
        )

    def get_recommendations(self, ctx: AgentContext, member_id: str) -> RecommendationResponse:
        member = self._members.get(member_id)          # unknown -> UnknownMemberError
        authorize(ctx, member)                         # mismatch -> AuthorizationDeniedError
        config = self._configs.get(member.partner_id)  # missing -> MissingPartnerConfigError
        candidates = self._generator.generate(member)
        final, meta = self._rules.apply(candidates, config)
        return RecommendationResponse(
            member_id=member.member_id,
            partner_id=member.partner_id,
            loyalty_tier=member.loyalty_tier,
            request_id=ctx.request_id,
            recommendations=final,
            rule_metadata=meta,
        )
```

- [ ] **Step 5: Create `app/dependencies.py`**

```python
from functools import lru_cache

from app.rules.rule_engine import RuleEngine
from app.services.member_service import MemberService
from app.services.partner_config_service import PartnerConfigService
from app.services.recommendation_generator import RecommendationGenerator
from app.services.recommendation_service import RecommendationService


@lru_cache
def get_recommendation_service() -> RecommendationService:
    return RecommendationService(
        member_service=MemberService(),
        partner_config_service=PartnerConfigService(),
        generator=RecommendationGenerator(),
        rule_engine=RuleEngine(),
    )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_recommendation_service.py -v`
Expected: PASS (all, including both cross-partner denials)

- [ ] **Step 7: Commit**

```bash
git add app/security/tenant_guard.py app/services/recommendation_service.py app/dependencies.py tests/test_recommendation_service.py
git commit -m "feat: add tenant guard and shared orchestration service"
```

---

### Task 9: Structured logging (PII-safe fields)

**Files:**
- Create: `app/logging_config.py`
- Test: `tests/test_logging.py`

**Interfaces:**
- Produces:
  - `logging_config.configure_logging(level: str) -> None`
  - `logging_config.safe_log_fields(ctx, *, tool_name, outcome, applied_rules=None, removed_count=0, latency_ms=0.0, failure_reason=None) -> dict` — returns ONLY allowlisted keys; never includes travel history, recommendation reasons, or full profiles.

- [ ] **Step 1: Write the failing test `tests/test_logging.py`**

```python
from app.models.common import Source
from app.security.context import build_context
from app.logging_config import safe_log_fields


def test_safe_log_fields_allowlist_only():
    ctx = build_context(agent_id="a", partner_id="p", source=Source.REST, request_id="r1")
    fields = safe_log_fields(
        ctx,
        tool_name="get_recommendations",
        outcome="ok",
        applied_rules=["category_exclusion"],
        removed_count=2,
        latency_ms=1.5,
    )
    assert fields["request_id"] == "r1"
    assert fields["partner_id"] == "p"
    assert fields["tool_name"] == "get_recommendations"
    assert fields["applied_rules"] == ["category_exclusion"]
    allowed = {
        "request_id", "source", "agent_id", "partner_id", "tool_name",
        "applied_rules", "removed_count", "outcome", "latency_ms", "failure_reason",
    }
    assert set(fields) <= allowed


def test_safe_log_fields_never_leaks_pii_keys():
    ctx = build_context(agent_id="a", partner_id="p", source=Source.REST)
    fields = safe_log_fields(ctx, tool_name="t", outcome="ok")
    for banned in ("travel_history", "reason", "recommendations", "preferences", "destination"):
        assert banned not in fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_logging.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create `app/logging_config.py`**

```python
import json
import logging

from app.security.context import AgentContext


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "message": record.getMessage()}
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def safe_log_fields(
    ctx: AgentContext,
    *,
    tool_name: str,
    outcome: str,
    applied_rules: list[str] | None = None,
    removed_count: int = 0,
    latency_ms: float = 0.0,
    failure_reason: str | None = None,
) -> dict:
    """Allowlisted, PII-safe log fields. member_id is acceptable for the mock;
    full profiles, travel history, and recommendation reasons are never logged.
    Production would apply arrivia-approved redaction/tokenization."""
    return {
        "request_id": ctx.request_id,
        "source": ctx.source.value,
        "agent_id": ctx.agent_id,
        "partner_id": ctx.partner_id,
        "tool_name": tool_name,
        "applied_rules": applied_rules or [],
        "removed_count": removed_count,
        "outcome": outcome,
        "latency_ms": latency_ms,
        "failure_reason": failure_reason,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_logging.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/logging_config.py tests/test_logging.py
git commit -m "feat: add PII-safe structured logging fields"
```

---

### Task 10: REST endpoint + safe error handling

**Files:**
- Modify: `app/main.py`
- Create: `app/api/recommendations.py`
- Test: `tests/test_recommendations_api.py`

**Interfaces:**
- Consumes: `get_recommendation_service`, `build_context`, `Source`, `RecommendationRequest`, `RecommendationResponse`, `DomainError`, `ErrorResponse`, `ErrorCode`, `safe_log_fields`.
- Produces: `POST /recommendations` (headers `x-partner-id`, `x-agent-id` required; `x-request-id` optional). Returns 200 `RecommendationResponse` or a safe `ErrorResponse` body with the mapped status. Missing headers → 422 `ErrorResponse(VALIDATION_ERROR)`.

- [ ] **Step 1: Write the failing test `tests/test_recommendations_api.py`**

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _headers(partner_id="partner_capped", agent_id="agent-test"):
    return {"x-partner-id": partner_id, "x-agent-id": agent_id}


def test_happy_path_returns_recommendations():
    resp = client.post("/recommendations", json={"member_id": "M-silver-capped"}, headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["partner_id"] == "partner_capped"
    assert len(body["recommendations"]) <= 3
    assert "rule_metadata" in body


def test_unknown_member_returns_404_error_shape():
    resp = client.post("/recommendations", json={"member_id": "M-nope"}, headers=_headers())
    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "UNKNOWN_MEMBER"
    assert "request_id" in body


def test_cross_partner_returns_403():
    resp = client.post(
        "/recommendations",
        json={"member_id": "M-plat-nocruise"},
        headers=_headers(partner_id="partner_capped"),
    )
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "AUTHORIZATION_DENIED"


def test_missing_partner_config_returns_404():
    resp = client.post(
        "/recommendations",
        json={"member_id": "M-orphan"},
        headers=_headers(partner_id="partner_missing"),
    )
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "MISSING_PARTNER_CONFIG"


def test_missing_headers_returns_422_error_shape():
    resp = client.post("/recommendations", json={"member_id": "M-silver-capped"})
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "VALIDATION_ERROR"


def test_cruise_never_appears_via_rest_for_excluding_partner():
    resp = client.post(
        "/recommendations",
        json={"member_id": "M-plat-nocruise"},
        headers=_headers(partner_id="partner_no_cruise"),
    )
    assert resp.status_code == 200
    cats = [r["category"] for r in resp.json()["recommendations"]]
    assert "Cruise" not in cats
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_recommendations_api.py -v`
Expected: FAIL — `/recommendations` route not found (404 for wrong reason / import error).

- [ ] **Step 3: Create `app/api/recommendations.py`**

```python
import logging

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from app.dependencies import get_recommendation_service
from app.logging_config import safe_log_fields
from app.models.common import Source
from app.models.errors import DomainError, ErrorResponse
from app.models.recommendation import RecommendationRequest
from app.security.context import build_context
from app.services.recommendation_service import RecommendationService

router = APIRouter()
logger = logging.getLogger("recommendations")


@router.post("/recommendations")
def post_recommendations(
    body: RecommendationRequest,
    x_partner_id: str = Header(...),
    x_agent_id: str = Header(...),
    x_request_id: str | None = Header(default=None),
    service: RecommendationService = Depends(get_recommendation_service),
):
    ctx = build_context(
        agent_id=x_agent_id, partner_id=x_partner_id, source=Source.REST, request_id=x_request_id
    )
    try:
        result = service.get_recommendations(ctx, body.member_id)
        logger.info(
            "recommendations",
            extra={
                "fields": safe_log_fields(
                    ctx,
                    tool_name="get_recommendations",
                    outcome="ok",
                    applied_rules=result.rule_metadata.applied_rules,
                    removed_count=len(result.rule_metadata.removed_recommendations),
                )
            },
        )
        return result
    except DomainError as exc:
        logger.warning(
            "recommendations_error",
            extra={
                "fields": safe_log_fields(
                    ctx,
                    tool_name="get_recommendations",
                    outcome="error",
                    failure_reason=exc.error_code.value,
                )
            },
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=ErrorResponse(
                error_code=exc.error_code, message=exc.message, request_id=ctx.request_id
            ).model_dump(mode="json"),
        )
```

- [ ] **Step 4: Modify `app/main.py` to wire the router, logging, and the validation handler**

Replace the entire file with:

```python
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import health, recommendations
from app.config import settings
from app.logging_config import configure_logging
from app.models.errors import ErrorCode, ErrorResponse

configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name)
app.include_router(health.router)
app.include_router(recommendations.router)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed.",
            request_id=request_id,
        ).model_dump(mode="json"),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_recommendations_api.py -v`
Expected: PASS (all)

- [ ] **Step 6: Run the full suite**

Run: `pytest -v`
Expected: PASS (everything so far)

- [ ] **Step 7: Commit**

```bash
git add app/api/recommendations.py app/main.py tests/test_recommendations_api.py
git commit -m "feat: expose recommendations REST endpoint with safe error responses"
```

---

### Task 11: MCP stdio server + two tools + safe-error wrapper

**Files:**
- Create: `app/mcp/__init__.py`, `app/mcp/server.py`
- Test: `tests/test_mcp_tools.py`
- Modify: `README.md` (append MCP run instructions — see Task 14; for now just create the server)

**Interfaces:**
- Consumes: `get_recommendation_service`, `build_context`, `Source`, `ErrorResponse`, `ErrorCode`, `DomainError`.
- Produces (all importable and directly callable in tests):
  - `server.get_member_profile(member_id: str) -> dict`
  - `server.get_recommendations(member_id: str) -> dict`
  - `server.mcp` (FastMCP instance named `agentic-travel-recs`)
  - On domain failure both tools raise a `ToolError` whose message is a JSON `ErrorResponse` payload (fields `error_code`, `message`, `request_id`); unexpected errors → `TOOL_EXECUTION_ERROR`. Caller identity read from env `PARTNER_ID` / `AGENT_ID`; `request_id` generated per call.

**Note on the `ToolError` import:** the MCP Python SDK exposes it at `mcp.server.fastmcp.exceptions.ToolError`. If the installed version differs, the fallback below defines a local `ToolError(Exception)` only when the import fails — verify against the installed `mcp` version during implementation.

- [ ] **Step 1: Write the failing test `tests/test_mcp_tools.py`**

```python
import json

import pytest

from app.mcp import server as mcp_server
from app.mcp.server import ToolError, get_member_profile, get_recommendations


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("PARTNER_ID", raising=False)
    monkeypatch.delenv("AGENT_ID", raising=False)


def _set_partner(monkeypatch, partner_id):
    monkeypatch.setenv("PARTNER_ID", partner_id)
    monkeypatch.setenv("AGENT_ID", "agent-mcp")


def test_get_recommendations_tool_returns_dict(monkeypatch):
    _set_partner(monkeypatch, "partner_capped")
    out = get_recommendations("M-silver-capped")
    assert out["partner_id"] == "partner_capped"
    assert len(out["recommendations"]) <= 3
    assert "rule_metadata" in out


def test_mcp_cannot_bypass_rule_engine(monkeypatch):
    _set_partner(monkeypatch, "partner_no_cruise")
    out = get_recommendations("M-plat-nocruise")
    cats = [r["category"] for r in out["recommendations"]]
    assert "Cruise" not in cats


def test_get_member_profile_tool_returns_safe_profile(monkeypatch):
    _set_partner(monkeypatch, "partner_no_cruise")
    out = get_member_profile("M-plat-nocruise")
    assert out["member_id"] == "M-plat-nocruise"
    assert out["loyalty_tier"] == "Platinum"


def test_get_member_profile_cross_partner_raises_safe_error(monkeypatch):
    _set_partner(monkeypatch, "partner_capped")  # wrong partner for this member
    with pytest.raises(ToolError) as exc:
        get_member_profile("M-plat-nocruise")
    payload = json.loads(str(exc.value))
    assert payload["error_code"] == "AUTHORIZATION_DENIED"
    assert "request_id" in payload


def test_unknown_member_raises_safe_error(monkeypatch):
    _set_partner(monkeypatch, "partner_capped")
    with pytest.raises(ToolError) as exc:
        get_recommendations("M-nope")
    payload = json.loads(str(exc.value))
    assert payload["error_code"] == "UNKNOWN_MEMBER"


def test_tools_are_registered_with_fastmcp():
    # discovery surface: both tool names exist on the server
    names = {t.name for t in mcp_server.mcp._tool_manager.list_tools()}
    assert {"get_member_profile", "get_recommendations"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mcp_tools.py -v`
Expected: FAIL — `app.mcp.server` does not exist.

- [ ] **Step 3: Create `app/mcp/__init__.py` (empty) and `app/mcp/server.py`**

```python
import json
import os
from typing import Callable

from mcp.server.fastmcp import FastMCP

try:  # SDK-provided tool error; fall back to a local type if unavailable.
    from mcp.server.fastmcp.exceptions import ToolError
except Exception:  # pragma: no cover - version-dependent import guard
    class ToolError(Exception):
        pass

from app.dependencies import get_recommendation_service
from app.models.common import Source
from app.models.errors import DomainError, ErrorCode, ErrorResponse
from app.security.context import AgentContext, build_context

mcp = FastMCP("agentic-travel-recs")
_service = get_recommendation_service()


def _context() -> AgentContext:
    # Caller identity comes from the trusted MCP launch environment. One server
    # process is scoped to one partner/agent session. request_id is per call.
    return build_context(
        agent_id=os.environ.get("AGENT_ID", "unknown-agent"),
        partner_id=os.environ.get("PARTNER_ID", ""),
        source=Source.MCP,
    )


def _run(tool_name: str, fn: Callable[[AgentContext], object]) -> dict:
    ctx = _context()
    try:
        return fn(ctx).model_dump(mode="json")
    except DomainError as exc:
        payload = ErrorResponse(
            error_code=exc.error_code, message=exc.message, request_id=ctx.request_id
        ).model_dump(mode="json")
        raise ToolError(json.dumps(payload)) from None
    except Exception:
        payload = ErrorResponse(
            error_code=ErrorCode.TOOL_EXECUTION_ERROR,
            message="Internal tool error.",
            request_id=ctx.request_id,
        ).model_dump(mode="json")
        raise ToolError(json.dumps(payload)) from None


def get_member_profile(member_id: str) -> dict:
    """Return a member's loyalty tier and travel history if the caller's partner
    scope is authorized for that member."""
    return _run("get_member_profile", lambda ctx: _service.get_member_profile(ctx, member_id))


def get_recommendations(member_id: str) -> dict:
    """Return partner-rule-compliant travel recommendations for a member, with
    rule metadata describing which offers were removed and why."""
    return _run("get_recommendations", lambda ctx: _service.get_recommendations(ctx, member_id))


# Register with FastMCP for agent discovery/invocation. Registration returns the
# original function, so the names above remain directly callable in tests.
mcp.tool()(get_member_profile)
mcp.tool()(get_recommendations)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mcp_tools.py -v`
Expected: PASS. If `test_tools_are_registered_with_fastmcp` fails due to an SDK API difference in listing tools, adjust that single assertion to the installed SDK's discovery call (e.g. `await mcp.list_tools()`), keeping the behavior tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add app/mcp tests/test_mcp_tools.py
git commit -m "feat: add MCP stdio server with two guarded, discoverable tools"
```

---

### Task 12: Eval suite (deterministic safety checks)

**Files:**
- Create: `tests/evals/__init__.py`, `tests/evals/test_tenant_isolation_eval.py`, `tests/evals/test_cruise_exclusion_eval.py`, `tests/evals/test_cap_enforcement_eval.py`, `tests/evals/test_fail_closed_eval.py`

**Interfaces:**
- Consumes: `get_recommendation_service`, `build_context`, MCP tools, domain errors. No new production code.

- [ ] **Step 1: Create `tests/evals/__init__.py` (empty) and write `tests/evals/test_tenant_isolation_eval.py`**

```python
import json

import pytest

from app.models.common import Source
from app.models.errors import AuthorizationDeniedError
from app.security.context import build_context
from app.dependencies import get_recommendation_service
from app.mcp.server import ToolError, get_member_profile, get_recommendations


def _ctx(partner_id):
    return build_context(agent_id="a", partner_id=partner_id, source=Source.CLI)


def test_service_blocks_cross_partner_on_both_methods():
    svc = get_recommendation_service()
    for method in (svc.get_recommendations, svc.get_member_profile):
        with pytest.raises(AuthorizationDeniedError):
            method(_ctx("partner_unlimited"), "M-plat-nocruise")


def test_mcp_blocks_cross_partner_without_leaking_profile(monkeypatch):
    monkeypatch.setenv("PARTNER_ID", "partner_unlimited")  # wrong partner
    monkeypatch.setenv("AGENT_ID", "agent-mcp")
    for tool in (get_recommendations, get_member_profile):
        with pytest.raises(ToolError) as exc:
            tool("M-plat-nocruise")
        payload = json.loads(str(exc.value))
        assert payload["error_code"] == "AUTHORIZATION_DENIED"
        assert "loyalty_tier" not in payload  # no profile data leaked
```

- [ ] **Step 2: Write `tests/evals/test_cruise_exclusion_eval.py`**

```python
from app.models.common import Category, Source
from app.security.context import build_context
from app.dependencies import get_recommendation_service


def test_cruise_never_appears_for_excluding_partner_even_for_platinum():
    svc = get_recommendation_service()
    ctx = build_context(agent_id="a", partner_id="partner_no_cruise", source=Source.CLI)
    resp = svc.get_recommendations(ctx, "M-plat-nocruise")
    assert all(r.category is not Category.CRUISE for r in resp.recommendations)
    removed_cats = {rr.category for rr in resp.rule_metadata.removed_recommendations}
    assert Category.CRUISE in removed_cats  # it was generated, then removed
```

- [ ] **Step 3: Write `tests/evals/test_cap_enforcement_eval.py`**

```python
from app.models.common import Source
from app.security.context import build_context
from app.dependencies import get_recommendation_service


def test_final_count_never_exceeds_partner_max():
    svc = get_recommendation_service()
    ctx = build_context(agent_id="a", partner_id="partner_capped", source=Source.CLI)
    for member_id in ("M-silver-capped", "M-plat-capped"):
        resp = svc.get_recommendations(ctx, member_id)
        assert len(resp.recommendations) <= 3
        assert resp.rule_metadata.max_allowed == 3
```

- [ ] **Step 4: Write `tests/evals/test_fail_closed_eval.py`**

```python
import pytest

from app.models.common import Source
from app.models.errors import MissingPartnerConfigError, UnknownMemberError
from app.security.context import build_context
from app.dependencies import get_recommendation_service


def _ctx(partner_id):
    return build_context(agent_id="a", partner_id=partner_id, source=Source.CLI)


def test_unknown_member_fails_closed():
    svc = get_recommendation_service()
    with pytest.raises(UnknownMemberError):
        svc.get_recommendations(_ctx("partner_capped"), "M-nope")


def test_missing_partner_config_fails_closed():
    svc = get_recommendation_service()
    with pytest.raises(MissingPartnerConfigError):
        svc.get_recommendations(_ctx("partner_missing"), "M-orphan")
```

- [ ] **Step 5: Run the eval suite to verify it passes**

Run: `pytest tests/evals -v`
Expected: PASS (all evals)

- [ ] **Step 6: Run the full suite**

Run: `pytest -v`
Expected: PASS (everything)

- [ ] **Step 7: Commit**

```bash
git add tests/evals
git commit -m "test: add deterministic safety evals for isolation, exclusion, cap, fail-closed"
```

---

### Task 13: CLI demo

**Files:**
- Create: `cli/__init__.py`, `cli/demo.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `get_recommendation_service`, `build_context`, `Source`, `DomainError`.
- Produces: `cli.demo.run(argv: list[str]) -> int` and `python -m cli.demo --member-id M --partner-id P --agent-id A`. Prints tier, partner, recommendations, applied rules, removed offers. Returns exit code 0 on success, 1 on handled domain error (prints safe error).

- [ ] **Step 1: Write the failing test `tests/test_cli.py`**

```python
from cli.demo import run


def test_cli_happy_path(capsys):
    code = run(["--member-id", "M-plat-nocruise", "--partner-id", "partner_no_cruise", "--agent-id", "a"])
    out = capsys.readouterr().out
    assert code == 0
    assert "partner_no_cruise" in out
    assert "Platinum" in out
    assert "Cruise" not in out.split("Removed")[0]  # no cruise among shown recs
    assert "category_exclusion" in out


def test_cli_cross_partner_prints_safe_error(capsys):
    code = run(["--member-id", "M-plat-nocruise", "--partner-id", "partner_capped", "--agent-id", "a"])
    out = capsys.readouterr().out
    assert code == 1
    assert "AUTHORIZATION_DENIED" in out


def test_cli_unknown_member_prints_safe_error(capsys):
    code = run(["--member-id", "M-nope", "--partner-id", "partner_capped", "--agent-id", "a"])
    out = capsys.readouterr().out
    assert code == 1
    assert "UNKNOWN_MEMBER" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `cli.demo` does not exist.

- [ ] **Step 3: Create `cli/__init__.py` (empty) and `cli/demo.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Manually verify the demo output**

Run: `python -m cli.demo --member-id M-plat-nocruise --partner-id partner_no_cruise --agent-id a`
Expected: prints Platinum member, partner_no_cruise, no Cruise among recommendations, `category_exclusion` applied, and a removed cruise candidate.

- [ ] **Step 6: Commit**

```bash
git add cli tests/test_cli.py
git commit -m "feat: add CLI demo of the end-to-end recommendation flow"
```

---

### Task 14: Docker + compose + local run

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`

**Interfaces:**
- Produces: a container running the REST API; `docker compose up` serves `/health` and `/recommendations`.

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create `docker-compose.yml`**

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_NAME=agentic-travel-recs
      - LOG_LEVEL=INFO
```

- [ ] **Step 3: Verify the image builds and health works**

Run: `docker compose up --build -d && sleep 3 && curl -s localhost:8000/health && docker compose down`
Expected: prints `{"status":"ok"}`.
(If Docker is unavailable in the environment, skip execution but keep the files; note it in the README.)

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "chore: add Docker and compose for local containerized run"
```

---

### Task 15: README (Sections A, B, C) + docs

**Files:**
- Modify: `README.md`

**Interfaces:** none (documentation). Must include: overview; architecture summary; setup/run; REST examples; **MCP Inspector demo commands**; CLI demo; Section A (Architecture & Trade-offs, 300–500 words); Section B (incident runbook for the cruise-leak; **B2 placeholder for the human**); Section C (AI Usage Log, ≥3 interactions incl. this design process); "ships first vs. later" table; four-week plan; the deterministic / no-API-key / LLM-is-the-client statements; PII-in-logs production note.

- [ ] **Step 1: Write `README.md`** with these sections (fill each with real content, not placeholders — except B2 which is intentionally a placeholder):

```markdown
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
(300–500 words. Cover: how recommendation service, MCP server, member data, and
partner config interact; ≥2 design trade-offs with rationale vs alternatives —
e.g. deterministic rule engine vs LLM enforcement, tool registry/guard vs direct
tool exposure, env-scoped MCP identity vs per-call partner arg; and how a partner
changing their cap or adding an exclusion is handled — config is read at request
time from the partner config service, so a cap/exclusion change is picked up on
the next request with no code change; adding a brand-new KIND of rule means adding
one Rule class to the engine's ordered list.)

## Section B — Production Readiness & Incident Response

### Incident Runbook: "AI Concierge shows cruises for a cruise-excluded partner"
(Walk diagnose -> confirm -> resolve using correlation ids and rule_metadata:
1. Get request_id/partner_id/member_id from the report or logs.
2. Confirm partner config: does partner_config return Cruise in excluded_categories?
   If not, this is a config-source issue, not a service bug.
3. Reproduce deterministically: call get_recommendations for that member; inspect
   rule_metadata.applied_rules and removed_recommendations — was category_exclusion
   applied? Was a cruise in removed_recommendations?
4. If exclusion did not fire: check the rule order and the CategoryExclusionRule;
   check whether the client is calling our tool vs rendering its own offers.
5. Resolve: fix + regression eval (test_cruise_exclusion_eval); if config-source,
   escalate to the partner-config owner since that service is read-only to us.)

### B2 — Required Reasoning Question (answer WITHOUT AI assistance)
> **PLACEHOLDER — Andy to write by hand, no AI.** Describe a scenario where an AI
> coding assistant gives a plausible-but-wrong answer for enforcing partner rules,
> how you'd catch it, and what you'd verify before acting.

## Section C — AI Usage Log
(≥3 interactions: what was asked, what the AI produced, what was kept/changed/
rejected and why. Include: the scope-down from a 22-PR plan to a lean MVP; the
LangSmith removal for the "existing infrastructure only" constraint; and the
get_member_profile tenant-guard gap caught in spec review.)

---

## What ships first vs. later
| Ships now (four-week first step) | Deferred (later) |
|---|---|
| Deterministic generator + rule engine | LLM phrasing/ranking/orchestration |
| REST + MCP (2 tools) + CLI | Citations + citation validation |
| Tenant guard + multi-tenant evals | Real auth (signed identity / JWT) |
| Structured JSON logs (PII-safe) | CloudWatch/App Insights/X-Ray wiring |
| Mock member + partner config | Real DB persistence, partner admin UI |

## Notes
- Logs never include full profiles, travel history, or recommendation reasons;
  production would apply arrivia-approved redaction/tokenization.
- MCP caller identity is a trusted launch context in the mock; production replaces
  it with signed workload identity / JWT claims / gateway-injected tenant.
```

- [ ] **Step 2: Fill Sections A and C with real prose** (A is 300–500 words; C documents at least three real interactions from `questions/decision-log.md`). Leave B2 as the placeholder.

- [ ] **Step 3: Verify no accidental AI content in B2**

Run: `grep -n "PLACEHOLDER" README.md`
Expected: the B2 placeholder line is present and clearly marks human-only work.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add README with architecture, runbook, AI usage log, and demo commands"
```

---

### Task 16: Final verification sweep

**Files:** none (verification + any small fixes)

- [ ] **Step 1: Run the full suite**

Run: `pytest -v`
Expected: PASS, no skips other than Docker-gated manual checks.

- [ ] **Step 2: Run the evals alone**

Run: `pytest tests/evals -v`
Expected: PASS.

- [ ] **Step 3: Exercise all three front doors manually**

Run:
```bash
uvicorn app.main:app &
sleep 2
curl -s -X POST localhost:8000/recommendations -H "x-partner-id: partner_capped" -H "x-agent-id: a" -H "content-type: application/json" -d '{"member_id":"M-plat-capped"}'
kill %1
python -m cli.demo --member-id M-plat-nocruise --partner-id partner_no_cruise --agent-id a
PARTNER_ID=partner_capped AGENT_ID=a python -c "from app.mcp.server import get_recommendations; print(get_recommendations('M-plat-capped'))"
```
Expected: REST returns ≤3 recs; CLI shows cruise removed; MCP tool returns ≤3 recs.

- [ ] **Step 4: Confirm no banned commit language**

Run: `git log --oneline | grep -Ei "\\bPR ?[0-9]|\\bM[0-9]\\b" || echo "clean"`
Expected: prints `clean`.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "chore: final verification pass"
```

---

## Self-Review

**Spec coverage:** every spec section maps to a task —
§2 architecture → Tasks 1,3,8,10,11,13; §3 models → Task 2; §4 generator+engine →
Tasks 6,7; §5 front doors + guarded profile + MCP errors → Tasks 8,10,11; §6
tests/evals → embedded per task + Task 12; §7 observability → Task 9 + README;
§8 fixtures → Tasks 4,5; §9 deliverables → Tasks 14,15; §10 sequencing → task order.

**Placeholder scan:** the only intentional placeholder is README **B2**, which the
assignment REQUIRES the human to answer without AI. No other placeholders.

**Type consistency:** `AgentContext(request_id, agent_id, partner_id, source)`,
`RuleOutcome(kept, removed, applied)`, `RuleEngine.apply -> (list, RuleMetadata)`,
`RecommendationService.get_recommendations/get_member_profile`, and the MCP tool
signatures (`member_id` only) are used identically across tasks.
```
