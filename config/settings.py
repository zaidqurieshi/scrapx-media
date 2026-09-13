"""Application settings and environment variable management."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from dotenv import load_dotenv

# Automatically locate and load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _to_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "y", "t", "on")


def parse_channel_target(target: str) -> Union[int, str]:
    """
    Normalizes a channel target representation.
    Handles:
      - Integer IDs: '-100123456789' -> -100123456789
      - Web links: 'https://t.me/channel_name' -> 'channel_name'
      - Usernames: '@channel_name' -> 'channel_name'
      - Raw handles: 'channel_name' -> 'channel_name'
    """
    target = str(target).strip()
    # Check if target is numeric channel ID
    try:
        return int(target)
    except ValueError:
        pass

    # Clean URL forms
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if target.startswith(prefix):
            target = target[len(prefix):]
            break

    # Strip leading @ if present for consistent Telethon lookup
    if target.startswith("@"):
        target = target[1:]

    return target


@dataclass
class Settings:
    # Telegram API Credentials
    telegram_api_id: int = field(
        default_factory=lambda: int(os.getenv("TELEGRAM_API_ID", "0"))
    )
    telegram_api_hash: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_API_HASH", "").strip()
    )
    telegram_session_name: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_SESSION_NAME", "scrapx_session").strip()
    )
    telegram_string_session: Optional[str] = field(
        default_factory=lambda: os.getenv("TELEGRAM_STRING_SESSION", "").strip() or None
    )

    # Channels
    first_squawk_channel: str = field(
        default_factory=lambda: os.getenv("FIRST_SQUAWK_CHANNEL", "@FirstSquawk").strip()
    )
    faytuks_network_channel: str = field(
        default_factory=lambda: os.getenv("FAYTUKS_NETWORK_CHANNEL", "@faytuks").strip()
    )
    scrapx_media_channel: str = field(
        default_factory=lambda: os.getenv("SCRAPX_MEDIA_CHANNEL", "@ScrapXMedia").strip()
    )

    # Source Toggles
    enable_first_squawk: bool = field(
        default_factory=lambda: _to_bool(os.getenv("ENABLE_FIRST_SQUAWK"), default=True)
    )
    enable_faytuks: bool = field(
        default_factory=lambda: _to_bool(os.getenv("ENABLE_FAYTUKS"), default=True)
    )

    # Operational Modes
    dry_run: bool = field(
        default_factory=lambda: _to_bool(os.getenv("DRY_RUN"), default=False)
    )
    media_group_debounce_seconds: float = field(
        default_factory=lambda: float(os.getenv("MEDIA_GROUP_DEBOUNCE_SECONDS", "1.5"))
    )
    database_path: str = field(
        default_factory=lambda: os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "scrapx_media.db"))
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )

    def validate(self) -> None:
        """Validates critical settings before startup."""
        errors = []
        if not self.telegram_api_id:
            errors.append("TELEGRAM_API_ID is missing or invalid in environment.")
        if not self.telegram_api_hash:
            errors.append("TELEGRAM_API_HASH is missing in environment.")
        if not self.scrapx_media_channel:
            errors.append("SCRAPX_MEDIA_CHANNEL destination channel is required.")
        if not self.enable_first_squawk and not self.enable_faytuks:
            errors.append("Both source channels are disabled. At least one must be enabled.")

        if errors:
            raise ValueError("Configuration Validation Failed:\n  - " + "\n  - ".join(errors))

    @property
    def parsed_first_squawk(self) -> Union[int, str]:
        return parse_channel_target(self.first_squawk_channel)

    @property
    def parsed_faytuks_network(self) -> Union[int, str]:
        return parse_channel_target(self.faytuks_network_channel)

    @property
    def parsed_scrapx_media(self) -> Union[int, str]:
        return parse_channel_target(self.scrapx_media_channel)


_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance

