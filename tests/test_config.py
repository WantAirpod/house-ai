from pathlib import Path

from home_decision_ai.config import load_project_config


def test_load_project_config() -> None:
    config = load_project_config(Path("config"))

    assert config.user_profile["profile"]["purpose"] == "owner_occupied_purchase"
    assert config.wife_profile["profile"]["owner"] == "wife"
    assert len(config.regions) >= 1
    assert len(config.watchlist) >= 1
    assert "asking_price_change_percent" in config.alert_rules
