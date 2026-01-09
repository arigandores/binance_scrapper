from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

import requests

BASE_URL = "https://fapi.binance.com"


class BinanceClient:
    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()

    def _get_latest(self, path: str, symbol: str) -> Dict:
        url = f"{BASE_URL}{path}"
        params = {"symbol": symbol, "period": "1d", "limit": 1}
        resp = self.session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            raise ValueError(f"No data returned for {symbol} at {path}")
        record = data[-1]
        return record

    @staticmethod
    def _parse_record(record: Dict) -> Dict:
        try:
            ratio = float(record["longShortRatio"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid record: {record}") from exc

        long_pct = (ratio / (1 + ratio)) * 100
        short_pct = 100 - long_pct

        timestamp_ms = record.get("timestamp")
        ts = (
            datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
            if isinstance(timestamp_ms, (int, float))
            else None
        )

        return {
            "ratio": ratio,
            "long_pct": long_pct,
            "short_pct": short_pct,
            "timestamp": ts,
        }

    def top_trader_accounts(self, symbol: str) -> Dict:
        record = self._get_latest("/futures/data/topLongShortAccountRatio", symbol)
        return self._parse_record(record)

    def top_trader_positions(self, symbol: str) -> Dict:
        record = self._get_latest("/futures/data/topLongShortPositionRatio", symbol)
        return self._parse_record(record)

    def global_long_short(self, symbol: str) -> Dict:
        record = self._get_latest("/futures/data/globalLongShortAccountRatio", symbol)
        return self._parse_record(record)
