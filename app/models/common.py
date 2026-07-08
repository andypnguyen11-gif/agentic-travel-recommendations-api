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
