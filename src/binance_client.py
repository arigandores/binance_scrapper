from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://fapi.binance.com"


def _build_base_urls(base_url: Optional[str]) -> List[str]:
    env_list = os.getenv("BINANCE_BASE_URLS")
    if env_list:
        urls = [u.strip() for u in env_list.split(",") if u.strip()]
    else:
        single = base_url or os.getenv("BINANCE_BASE_URL")
        urls = [single] if single else []
    urls.append(BASE_URL)
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

        # Debug flag
        self.debug = os.getenv("BINANCE_DEBUG", "").lower() in ("1", "true", "yes")

        # Optional TLS verify control (not recommended in prod; use only if CA issues)
        tls_insecure = os.getenv("BINANCE_TLS_INSECURE", "").lower() in ("1", "true", "yes")
        if tls_insecure:
            self.session.verify = False
            self._dbg("TLS verification disabled (BINANCE_TLS_INSECURE)")

        # Optional proxy (e.g., BINANCE_PROXY or HTTPS_PROXY). Using env allows GH Actions/secrets.
        proxy = (
            os.getenv("BINANCE_PROXY")
            or os.getenv("HTTPS_PROXY")
            or os.getenv("https_proxy")
            or os.getenv("HTTP_PROXY")
            or os.getenv("http_proxy")
        )
        if proxy:
            self.session.proxies.update({"https": proxy, "http": proxy})
            self._dbg(f"Using static proxy from env: {proxy}")

        self._configure_retries()

        # Optional free proxy rotation (advanced.name public list)
        self.use_free_proxies = os.getenv("BINANCE_USE_FREE_PROXIES", "").lower() in ("1", "true", "yes")
        self.free_proxy_limit = int(os.getenv("BINANCE_FREE_PROXY_LIMIT", "20"))
        self.free_proxy_types = [
            t.strip() for t in os.getenv("BINANCE_FREE_PROXY_TYPES", "https").split(",") if t.strip()
        ]
        self.free_proxies: List[str] = []
        self.preferred_proxy: Optional[str] = None
        self.preferred_base: Optional[str] = None
        if self.use_free_proxies:
            try:
                self.free_proxies = self._load_free_proxies(limit=self.free_proxy_limit, types=self.free_proxy_types)
                self._dbg(f"Loaded {len(self.free_proxies)} free proxies")
            except Exception as exc:
                # Do not fail init on proxy list fetch errors; will continue without them
                self._dbg(f"Failed to load free proxies: {exc}")
                self.free_proxies = []

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

    def _configure_retries(self) -> None:
        """Configure HTTP retries for transient Binance/proxy hiccups."""
        retry_total = int(os.getenv("BINANCE_HTTP_RETRIES", "2"))
        if retry_total <= 0:
            return

        backoff = float(os.getenv("BINANCE_HTTP_BACKOFF", "0.5"))
        status_forcelist = (429, 500, 502, 503, 504)
        retry = Retry(
            total=retry_total,
            connect=retry_total,
            read=retry_total,
            status=retry_total,
            backoff_factor=backoff,
            status_forcelist=status_forcelist,
            allowed_methods=frozenset(["HEAD", "GET", "OPTIONS"]),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self._dbg(f"HTTP retries enabled: total={retry_total}, backoff={backoff}")

    def _request(self, path: str, params: Dict) -> Dict:
        last_error = None
        proxy_candidates: List[Optional[str]] = [None]
        if self.free_proxies:
            proxy_candidates.extend(self.free_proxies)

        max_attempts = max(1, int(os.getenv("BINANCE_MAX_ATTEMPTS", "1")))
        timeout_s = float(os.getenv("BINANCE_TIMEOUT", "4"))

        bases = list(self.base_urls)
        if self.preferred_base and self.preferred_base in bases:
            bases = [self.preferred_base] + [b for b in bases if b != self.preferred_base]

        for base in bases:
            url = f"{base}{path}"
            effective_proxies = proxy_candidates
            if self.preferred_proxy:
                effective_proxies = [self.preferred_proxy] + [p for p in proxy_candidates if p != self.preferred_proxy]

            for proxy in effective_proxies:
                proxies_dict = {"https": proxy, "http": proxy} if proxy else None
                for attempt in range(max_attempts):
                    try:
                        self._dbg(f"GET {url} attempt {attempt + 1} proxy={proxy}")
                        resp = self.session.get(url, params=params, timeout=timeout_s, proxies=proxies_dict)
                        if resp.status_code >= 400:
                            resp.raise_for_status()
                        try:
                            data = resp.json()
                        except ValueError as exc_json:
                            self._dbg(f"Invalid JSON from {url} proxy={proxy}: {exc_json}")
                            raise
                        self._dbg(f"Success {url} via proxy={proxy}")
                        if proxy:
                            self.preferred_proxy = proxy
                        self.preferred_base = base
                        return data
                    except Exception as exc:  # pylint: disable=broad-except
                        last_error = RuntimeError(f"{url} attempt {attempt + 1} proxy={proxy} failed: {exc}")
                        self._dbg(f"Error {url} attempt {attempt + 1} proxy={proxy}: {exc}")
                        # retry/backoff handled by HTTPAdapter; loop moves to next proxy/base
        raise last_error  # type: ignore[misc]

    def _proxy_test_url(self) -> str:
        base = self.preferred_base or (self.base_urls[0] if self.base_urls else BASE_URL)
        return f"{base}/fapi/v1/ping"

    def _is_proxy_alive(self, proxy: str, timeout: float) -> bool:
        test_url = self._proxy_test_url()
        try:
            resp = self.session.get(test_url, timeout=timeout, proxies={"https": proxy, "http": proxy})
            resp.raise_for_status()
            return True
        except Exception as exc:  # pylint: disable=broad-except
            self._dbg(f"Proxy check failed {proxy}: {exc}")
            return False

    def _load_free_proxies(self, limit: int = 20, types: List[str] | None = None) -> List[str]:
        types = types or ["https"]
        sources = {
            "http": "https://raw.githubusercontent.com/iplocate/free-proxy-list/refs/heads/main/protocols/http.txt",
            "https": "https://raw.githubusercontent.com/iplocate/free-proxy-list/refs/heads/main/protocols/https.txt",
        }
        custom_proxy_url = os.getenv("BINANCE_FREE_PROXY_URL")
        if custom_proxy_url:
            sources["https"] = custom_proxy_url
        validate = os.getenv("BINANCE_FREE_PROXY_VALIDATE", "1").lower() in ("1", "true", "yes")
        validate_timeout = float(os.getenv("BINANCE_FREE_PROXY_VALIDATE_TIMEOUT", "1.5"))
        seen = set()
        proxies: List[str] = []
        for t in types:
            url = sources.get(t)
            if not url:
                continue
            try:
                self._dbg(f"Fetch proxy list: {url}")
                resp = self.session.get(url, timeout=10)
                resp.raise_for_status()
            except Exception as exc:
                self._dbg(f"Proxy list fetch failed {url}: {exc}")
                continue
            # Each line is host:port
            candidates = [line.strip() for line in resp.text.splitlines() if ":" in line]
            self._dbg(f"Found {len(candidates)} raw proxies for type={t}")
            for p in candidates:
                if p in seen:
                    continue
                seen.add(p)
                proxy_url = f"http://{p}"
                if validate and not self._is_proxy_alive(proxy_url, timeout=validate_timeout):
                    continue
                proxies.append(proxy_url)
                if len(proxies) >= limit:
                    self._dbg(f"Collected proxy limit {len(proxies)}")
                    return proxies
        return proxies

    def _dbg(self, msg: str) -> None:
        if self.debug:
            print(f"[DEBUG][BinanceClient] {msg}")

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
