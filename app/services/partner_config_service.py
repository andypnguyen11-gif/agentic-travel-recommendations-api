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
