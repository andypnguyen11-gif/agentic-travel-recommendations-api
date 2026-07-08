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
