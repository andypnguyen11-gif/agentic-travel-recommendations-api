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
