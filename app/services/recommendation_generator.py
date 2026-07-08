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
