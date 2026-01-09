from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, TypedDict


class Settings(TypedDict):
    pairs: List[str]
    telegram_chat_id: str
    telegram_bot_token: str


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.json"


def _load_json_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _pairs_from_env() -> List[str] | None:
    raw = os.getenv("PAIRS")
    if not raw:
        return None
    pairs = [item.strip().upper() for item in raw.split(",") if item.strip()]
    return pairs or None


def load_settings() -> Settings:
    file_settings = _load_json_settings(CONFIG_PATH)

    pairs = _pairs_from_env() or file_settings.get("pairs")
    if not pairs or not isinstance(pairs, list):
        raise ValueError("Pairs are not configured. Set PAIRS env or config/settings.json")

    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID") or file_settings.get("telegram_chat_id")
    if not telegram_chat_id:
        raise ValueError("Telegram chat id is missing. Set TELEGRAM_CHAT_ID or config/settings.json")

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_bot_token:
        raise ValueError("Telegram bot token is missing. Set TELEGRAM_BOT_TOKEN environment variable")

    return {
        "pairs": [p.upper() for p in pairs],
        "telegram_chat_id": str(telegram_chat_id),
        "telegram_bot_token": telegram_bot_token,
    }
