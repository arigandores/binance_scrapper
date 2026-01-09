from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

Metric = Dict[str, object]


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def _fmt_ratio(value: float) -> str:
    return f"{value:.2f}x"


def _format_metric(label: str, metric: Metric | None) -> str:
    if not metric:
        return f"{label}: n/a"
    return (
        f"{label}: long {_fmt_pct(metric['long_pct'])} / "
        f"short {_fmt_pct(metric['short_pct'])} "
        f"({_fmt_ratio(metric['ratio'])})"
    )


def build_message(run_dt: datetime, pairs: List[Dict[str, object]]) -> str:
    lines: List[str] = []
    utc_time = run_dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append("Binance Futures Long/Short (1d)")
    lines.append(f"Run: {utc_time}")

    for item in pairs:
        lines.append("")
        symbol = str(item["symbol"])
        lines.append(symbol)
        lines.append(_format_metric("Accounts 1d", item.get("accounts")))  # Top Trader Accounts
        lines.append(_format_metric("Positions 1d", item.get("positions")))  # Top Trader Positions
        lines.append(_format_metric("Global 1d", item.get("global")))  # Global accounts

    return "\n".join(lines)
