from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Dict, List

from .binance_client import BinanceClient
from .config_loader import load_settings
from .report import build_message
from .telegram_client import TelegramClient


def collect_metrics(client: BinanceClient, symbols: List[str]) -> List[Dict[str, object]]:
    results = []
    for symbol in symbols:
        accounts = client.top_trader_accounts(symbol)
        positions = client.top_trader_positions(symbol)
        global_ratio = client.global_long_short(symbol)
        results.append(
            {
                "symbol": symbol,
                "accounts": accounts,
                "positions": positions,
                "global": global_ratio,
            }
        )
    return results


def main() -> None:
    try:
        settings = load_settings()
        binance = BinanceClient()
        metrics = collect_metrics(binance, settings["pairs"])
        message = build_message(datetime.now(timezone.utc), metrics)

        telegram = TelegramClient(settings["telegram_bot_token"])
        telegram.send_message(settings["telegram_chat_id"], message)
        print("Report sent successfully")
    except Exception as exc:  # pragma: no cover - script entry
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
