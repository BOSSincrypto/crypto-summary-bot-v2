import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Bot configuration loaded from environment variables."""

    # Telegram
    telegram_token: str = ""
    admin_password: str = "admin123"

    # API Keys
    coinmarketcap_api_key: str = ""
    openrouter_api_key: str = ""

    # Nitter instances (comma-separated, optional override)
    nitter_instances: str = ""

    # Database
    db_path: str = "bot.db"

    # Schedule (MSK = UTC+3)
    morning_hour_utc: int = 5   # 8:00 AM MSK
    morning_minute: int = 0
    evening_hour_utc: int = 20  # 11:00 PM MSK
    evening_minute: int = 0

    # EVM Support Address
    support_address: str = "0x5F4fe992a847e6B3cA07EBb379Ae02608D21BAb3"

    # AI Model
    ai_model: str = "google/gemma-3n-e4b-it"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            admin_password=os.getenv("ADMIN_PASSWORD", "admin123"),
            coinmarketcap_api_key=os.getenv("COINMARKETCAP_API_KEY", ""),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            nitter_instances=os.getenv("NITTER_INSTANCES", ""),
            db_path=os.getenv("DB_PATH", "bot.db"),
            support_address="0x5F4fe992a847e6B3cA07EBb379Ae02608D21BAb3",
            ai_model=os.getenv("AI_MODEL", "google/gemma-3n-e4b-it"),
        )
