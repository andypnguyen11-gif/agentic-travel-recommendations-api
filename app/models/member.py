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
