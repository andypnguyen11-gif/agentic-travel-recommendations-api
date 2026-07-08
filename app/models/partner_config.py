from pydantic import BaseModel, ConfigDict, Field

from app.models.common import Category


class PartnerConfig(BaseModel):
    """Read-only partner configuration. max_recommendations None == unlimited."""

    model_config = ConfigDict(extra="forbid")

    partner_id: str
    excluded_categories: list[Category] = Field(default_factory=list)
    max_recommendations: int | None = None
