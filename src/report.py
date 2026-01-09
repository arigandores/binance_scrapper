from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

Metric = Dict[str, object]
HIGHLIGHT_THRESHOLD = 2.3


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def _fmt_ratio(value: float) -> str:
    return f"{value:.2f}x"


def _imbalance_value(metric: Metric | None) -> float:
    """Return symmetric imbalance factor (>=1) or 0 if unavailable."""
    if not metric:
        return 0.0
    try:
        ratio = float(metric["ratio"])
    except (KeyError, TypeError, ValueError):
        return 0.0
    if ratio <= 0:
        return 0.0
    return ratio if ratio >= 1 else 1 / ratio


def _format_metric(label: str, metric: Metric | None) -> str:
    if not metric:
        return f"<b>{label}</b>: n/a"
    imbalance = _imbalance_value(metric)
    highlight = imbalance > HIGHLIGHT_THRESHOLD
    content = (
        f"<b>{label}</b>: long {_fmt_pct(metric['long_pct'])} / "
        f"short {_fmt_pct(metric['short_pct'])} "
        f"({_fmt_ratio(metric['ratio'])})"
    )
    return f"⚠️ <b>{content}</b>" if highlight else content


def _pair_max_imbalance(item: Dict[str, object]) -> float:
    metrics = [item.get("accounts"), item.get("positions"), item.get("global")]
    return max((_imbalance_value(m) for m in metrics), default=0.0)


def build_message(run_dt: datetime, pairs: List[Dict[str, object]], errors: List[str] | None = None) -> str:
    lines: List[str] = []
    utc_time = run_dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append("⭐️ <b>Binance Futures Long/Short (1d)</b>")
    lines.append(f"<i>Run: {utc_time}</i>")

    sorted_pairs = sorted(pairs, key=_pair_max_imbalance, reverse=True)
    for item in sorted_pairs:
        lines.append("")
        symbol = str(item["symbol"])
        lines.append(f"<u><b>{symbol}</b></u>")
        lines.append(f"• {_format_metric('Accounts 1d', item.get('accounts'))}")  # Top Trader Accounts
        lines.append(f"• {_format_metric('Positions 1d', item.get('positions'))}")  # Top Trader Positions
        lines.append(f"• {_format_metric('Global 1d', item.get('global'))}")  # Global accounts

    if errors:
        lines.append("")
        lines.append("⚠️ <b>Warnings</b>:")
        for err in errors:
            lines.append(f"• {err}")

    return "\n".join(lines)
