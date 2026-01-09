from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import List, Tuple

from .binance_client import BinanceClient
from .config_loader import load_settings
from .main import collect_metrics
from .report import HIGHLIGHT_THRESHOLD, _pair_max_imbalance, build_message
from .telegram_client import TelegramClient


def find_top_imbalances(
    client: BinanceClient, limit: int = 10, candidates: int = 120
) -> Tuple[List[dict], List[dict], List[str]]:
    # Pre-filter by highest quoteVolume to avoid thousands of requests
    symbols = client.list_top_volume_usdt_perpetual(limit=candidates)
    print(f"[info] Candidates by volume: {len(symbols)}")

    def _progress(idx: int, total: int, symbol: str, is_error: bool) -> None:
        status = "error" if is_error else "ok"
        print(f"[progress] {idx}/{total} {symbol} {status}")

    metrics, errors = collect_metrics(client, symbols, progress=_progress)
    sorted_pairs = sorted(metrics, key=_pair_max_imbalance, reverse=True)
    imbalanced = [m for m in sorted_pairs if _pair_max_imbalance(m) > HIGHLIGHT_THRESHOLD]
    return sorted_pairs[:limit], imbalanced, errors


def format_console_report(pairs: List[dict]) -> str:
    lines = ["Top long/short skews (USDT perpetual):"]
    for item in pairs:
        lines.append(
            f"- {item['symbol']}: max skew {_pair_max_imbalance(item):.2f}x "
            f"(accounts={item.get('accounts', {}).get('ratio')} "
            f"positions={item.get('positions', {}).get('ratio')} "
            f"global={item.get('global', {}).get('ratio')})"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Find symbols with biggest long/short imbalance")
    parser.add_argument("--limit", type=int, default=10, help="How many top symbols to print")
    parser.add_argument(
        "--candidates",
        type=int,
        default=120,
        help="How many top-volume symbols to scan (reduces total requests)",
    )
    args = parser.parse_args()

    client = BinanceClient()
    top_pairs, imbalanced_pairs, errors = find_top_imbalances(
        client, limit=args.limit, candidates=args.candidates
    )

    if errors:
        print("Partial errors:", *errors, sep="\n- ")

    if not top_pairs:
        raise SystemExit("No data collected")

    print(format_console_report(top_pairs))

    settings = load_settings()
    run_dt = datetime.now(timezone.utc)
    if not imbalanced_pairs:
        warn = [f"No symbols exceed {HIGHLIGHT_THRESHOLD:.1f}x among top {args.candidates} by volume"]
        message = build_message(run_dt, [], errors=warn)
        print(f"[info] {warn[0]}; sending warning message")
    else:
        # Split into batches to avoid Telegram message size/HTML issues
        batch_size = 10
        batches = [imbalanced_pairs[i : i + batch_size] for i in range(0, len(imbalanced_pairs), batch_size)]
        total_parts = len(batches)
        print(f"[info] Telegram payload symbols: {len(imbalanced_pairs)} (> {HIGHLIGHT_THRESHOLD:.1f}x), parts={total_parts}")

        telegram = TelegramClient(settings["telegram_bot_token"])
        for idx, batch in enumerate(batches, start=1):
            msg = build_message(run_dt, batch, errors=None)
            if total_parts > 1:
                lines = msg.split("\n")
                if lines:
                    lines[0] = f"{lines[0]} (part {idx}/{total_parts})"
                msg = "\n".join(lines)
            telegram.send_message(settings["telegram_chat_id"], msg)
            print(f"[info] Telegram part {idx}/{total_parts} sent ({len(batch)} symbols)")
        return

    telegram = TelegramClient(settings["telegram_bot_token"])
    telegram.send_message(settings["telegram_chat_id"], message)
    print("[info] Telegram sent")


if __name__ == "__main__":
    main()
