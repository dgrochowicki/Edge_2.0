"""OddsPapi v4 client with disk cache, request log and hard request limit (zlecenie B0).

- Key only from env ODDSPAPI_KEY or the repo-root .env; never written anywhere.
- Every network call is appended to scanner/data/api_usage.json (time, endpoint,
  params without the key, HTTP status, billable flag).
- Every response body is cached in scanner/data/raw/<endpoint>/<cache-key>.json;
  a cached request is never sent again.
- Hard limit: no billable call once BILLABLE_LIMIT billable calls are logged.
  /v4/historical-odds and /v4/account are not billed by OddsPapi
  (docs: Requests & Quota) and are logged with billable=false.

Stdlib only, so it runs before requirements are installed.
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://api.oddspapi.io/v4"
SCANNER_DIR = Path(__file__).resolve().parent
REPO_DIR = SCANNER_DIR.parent
DATA_DIR = SCANNER_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
USAGE_PATH = DATA_DIR / "api_usage.json"

BILLABLE_LIMIT = 200  # zlecenie B0: hard limit for etap 0 (250/month free, 50 reserve)
UNBILLED = {"historical-odds", "account"}
COOLDOWN_S = {"historical-odds": 5.0, "fixtures": 2.0}
DEFAULT_COOLDOWN_S = 1.0


class LimitExceeded(RuntimeError):
    pass


def load_key():
    key = os.environ.get("ODDSPAPI_KEY", "").strip()
    if key:
        return key
    env = REPO_DIR / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("ODDSPAPI_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        raise RuntimeError("ODDSPAPI_KEY not set (env or .env)")
    return key


def cache_key(endpoint, params):
    canon = json.dumps(sorted(params.items()), separators=(",", ":"))
    return hashlib.sha256(f"{endpoint}?{canon}".encode()).hexdigest()[:20]


def read_usage():
    if USAGE_PATH.exists():
        return json.loads(USAGE_PATH.read_text(encoding="utf-8"))
    return []


def billable_count():
    return sum(1 for u in read_usage() if u.get("billable"))


class Client:
    def __init__(self, max_calls=None):
        """max_calls: optional cap on network calls (billable or not) for this
        session, e.g. 10 for the B0 reconnaissance."""
        self._key = load_key()
        self._last_call = {}
        self.max_calls = max_calls
        self.session_calls = 0

    def get(self, endpoint, **params):
        """Return (body, from_cache). body is the parsed JSON (or None on error status)."""
        params = {k: v for k, v in params.items() if v is not None}
        ck = cache_key(endpoint, params)
        path = RAW_DIR / endpoint / f"{ck}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["body"], True

        billable = endpoint not in UNBILLED
        if billable and billable_count() >= BILLABLE_LIMIT:
            raise LimitExceeded(f"billable limit {BILLABLE_LIMIT} reached")
        if self.max_calls is not None and self.session_calls >= self.max_calls:
            raise LimitExceeded(f"session cap {self.max_calls} reached")

        wait = COOLDOWN_S.get(endpoint, DEFAULT_COOLDOWN_S) - (time.monotonic() - self._last_call.get(endpoint, -1e9))
        if wait > 0:
            time.sleep(wait)

        url = f"{BASE_URL}/{endpoint}?" + urllib.parse.urlencode({**params, "apiKey": self._key})
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        status, body = None, None
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                status = resp.status
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            status = e.code
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:
                body = None
        finally:
            self._last_call[endpoint] = time.monotonic()
            self.session_calls += 1
            self._log(endpoint, params, status, billable, ck)

        if status == 200:
            body = _redact(body, self._key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"endpoint": endpoint, "params": params,
                                        "fetched_at": _now(), "body": body},
                                       ensure_ascii=False), encoding="utf-8")
            return body, False
        raise RuntimeError(f"{endpoint} {params} -> HTTP {status}: {str(body)[:300]}")

    def _log(self, endpoint, params, status, billable, ck):
        usage = read_usage()
        usage.append({"time": _now(), "endpoint": endpoint, "params": params,
                      "status": status, "billable": billable, "cache_key": ck})
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        USAGE_PATH.write_text(json.dumps(usage, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _redact(body, key):
    """Drop the key from a response before it touches disk or a caller
    (/v4/account echoes it back as `api_key`)."""
    if isinstance(body, dict):
        return {k: _redact(v, key) for k, v in body.items() if k != "api_key"}
    if isinstance(body, list):
        return [_redact(v, key) for v in body]
    if isinstance(body, str) and key in body:
        return body.replace(key, "<redacted>")
    return body


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
