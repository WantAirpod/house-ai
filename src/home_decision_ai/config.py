from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ProjectConfig:
    """Aggregated YAML configuration for research and decision workflows."""

    user_profile: dict[str, Any]
    wife_profile: dict[str, Any]
    regions: list[dict[str, Any]]
    watchlist: list[dict[str, Any]]
    alert_rules: dict[str, Any]


def read_yaml(path: Path) -> dict[str, Any]:
    """Read one YAML file and return a dictionary."""
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        msg = f"YAML root must be a mapping: {path}"
        raise ValueError(msg)

    return data


def load_project_config(config_dir: Path) -> ProjectConfig:
    """Load all project configuration files.

    TODO: Validate this with Pydantic models once the config schema stabilizes.
    """
    user_profile = read_yaml(config_dir / "user_profile.yaml")
    wife_profile = read_yaml(config_dir / "wife_profile.yaml")
    regions_data = read_yaml(config_dir / "regions.yaml")
    watchlist_data = read_yaml(config_dir / "watchlist.yaml")

    return ProjectConfig(
        user_profile=user_profile,
        wife_profile=wife_profile,
        regions=regions_data.get("regions", []),
        watchlist=watchlist_data.get("watchlist", []),
        alert_rules=watchlist_data.get("alert_rules", {}),
    )
