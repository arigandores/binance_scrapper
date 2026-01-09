from __future__ import annotations

from typing import Optional

import requests


class TelegramClient:
    def __init__(self, bot_token: str, session: Optional[requests.Session] = None) -> None:
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.session = session or requests.Session()

    def send_message(self, chat_id: str, text: str, parse_mode: str | None = "HTML") -> dict:
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        resp = self.session.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise ValueError(f"Telegram API error: {data}")
        return data
