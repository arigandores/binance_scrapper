from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

BASE_URL = "https://fapi.binance.com"
ALT_URL = "https://fapi.binance.me"  # часто работает при блоках


def _build_base_urls(base_url: Optional[str]) -> List[str]:
    env_list = os.getenv("BINANCE_BASE_URLS")
    if env_list:
        urls = [u.strip() for u in env_list.split(",") if u.strip()]
    else:
        single = base_url or os.getenv("BINANCE_BASE_URL")
        urls = [single] if single else []
    urls.append(BASE_URL)
    urls.append(ALT_URL)
    # preserve order, remove duplicates/empty
    seen = set()
    result = []
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        result.append(url)
    return result


class BinanceClient:
    def __init__(self, session: Optional[requests.Session] = None, base_url: Optional[str] = None) -> None:
        self.base_urls = _build_base_urls(base_url)
        self.session = session or requests.Session()
        # Mimic a real browser to reduce 451 blocks on some clouds
        browser_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "max-age=0",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Sec-CH-UA": '"Chromium";v="120", "Not A(Brand";v="24", "Google Chrome";v="120"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
        }
        # Do not override user-provided headers; only set if missing
        for key, value in browser_headers.items():
            self.session.headers.setdefault(key, value)

    def _request(self, path: str, params: Dict) -> Dict:
        last_error = None
        for base in self.base_urls:
            url = f"{base}{path}"
            for attempt in range(3):
                try:
                    resp = self.session.get(url, params=params, timeout=10)
                    if resp.status_code >= 400:
                        resp.raise_for_status()
                    return resp.json()
                except Exception as exc:  # pylint: disable=broad-except
                    last_error = exc
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
