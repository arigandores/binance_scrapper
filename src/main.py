from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

from .binance_client import BinanceClient
from .config_loader import load_settings
from .report import build_message
from .telegram_client import TelegramClient


ProgressCb = Optional[Callable[[int, int, str, bool], None]]


def collect_metrics(
    client: BinanceClient, symbols: List[str], progress: ProgressCb = None
) -> Tuple[List[Dict[str, object]], List[str]]:
    results: List[Dict[str, object]] = []
    errors: List[str] = []
    total = len(symbols)
    for idx, symbol in enumerate(symbols, start=1):
        try:
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
            if progress:
                progress(idx, total, symbol, False)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(f"{symbol}: {exc}")
            if progress:
                progress(idx, total, symbol, True)
    return results, errors


def main() -> None:
    try:
        settings = load_settings()
        binance = BinanceClient()
        metrics, errors = collect_metrics(binance, settings["pairs"])
        if not metrics:
            raise RuntimeError(f"All symbol requests failed: {errors}")
        if errors:
            print("Partial errors:", *errors, sep="\n- ", file=sys.stderr)
        message = build_message(datetime.now(timezone.utc), metrics, errors=errors)

        telegram = TelegramClient(settings["telegram_bot_token"])
        telegram.send_message(settings["telegram_chat_id"], message)
        print("Report sent successfully")
    except Exception as exc:  # pragma: no cover - script entry
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
