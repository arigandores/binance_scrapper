from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Dict, Optional

import requests

BASE_URL = "https://fapi.binance.com"


class BinanceClient:
    def __init__(self, session: Optional[requests.Session] = None, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or os.getenv("BINANCE_BASE_URL", BASE_URL)
        self.session = session or requests.Session()
        # Binance may return 451 without a User-Agent from some clouds (e.g. GH Actions)
        self.session.headers.setdefault("User-Agent", "binance-ls-reporter/1.0 (+https://github.com)")

    def _request(self, path: str, params: Dict) -> Dict:
        url = f"{self.base_url}{path}"
        last_error = None
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=10)
                if resp.status_code >= 400:
                    resp.raise_for_status()
                data = resp.json()
                return data
            except Exception as exc:  # pylint: disable=broad-except
                last_error = exc
                # small linear backoff
                time.sleep(1 + attempt)
        raise last_error  # type: ignore[misc]

    def _get_latest(self, path: str, symbol: str) -> Dict:
        params = {"symbol": symbol, "period": "1d", "limit": 1}
        data = self._request(path, params)
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
