"""
Configuration loader for Content Curation System.

Loads settings from config/settings.yaml and provides
typed access to configuration values.
"""

from pathlib import Path
from dataclasses import dataclass
import yaml


@dataclass
class DatabaseConfig:
    path: str


@dataclass
class ObsidianConfig:
    vault_path: str
    reading_list_folder: str

    @property
    def reading_list_path(self) -> Path:
        return Path(self.vault_path) / self.reading_list_folder


@dataclass
class FabricConfig:
    model: str
    pattern: str
    batch_size: int


@dataclass
class FetchConfig:
    days_back: int
    max_transcript_chars: int


@dataclass
class Settings:
    database: DatabaseConfig
    obsidian: ObsidianConfig
    fabric: FabricConfig
    fetch: FetchConfig


def load_settings(config_path: Path | None = None) -> Settings:
    """
    Load settings from YAML config file.

    Args:
        config_path: Path to settings.yaml. If None, uses default location.

    Returns:
        Settings object with all configuration values.
    """
    if config_path is None:
        # Default: config/settings.yaml relative to this file's parent
        config_path = Path(__file__).parent.parent / "config" / "settings.yaml"

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    return Settings(
        database=DatabaseConfig(**raw["database"]),
        obsidian=ObsidianConfig(**raw["obsidian"]),
        fabric=FabricConfig(**raw["fabric"]),
        fetch=FetchConfig(**raw["fetch"]),
    )


# Singleton instance - load once, use everywhere
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance (lazy-loaded)."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings
