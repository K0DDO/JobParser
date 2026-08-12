"""Convert vacancy salaries to RUB using live CBR rates (with cache + fallback)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
from redis import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

CBR_DAILY_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
REDIS_KEY = "fx:rates:rub"
CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours
MEMORY_TTL_SECONDS = 30 * 60

# Used only if CBR/Redis are unavailable
FALLBACK_RATES_TO_RUB: dict[str, float] = {
    "RUB": 1.0,
    "RUR": 1.0,
    "USD": 83.0,
    "USDT": 83.0,
    "EUR": 96.0,
    "GBP": 112.0,
    "KZT": 0.18,
    "BYN": 28.0,
    "UAH": 1.86,
    "GEL": 32.0,
    "AMD": 0.23,
    "UZS": 0.007,
    "TRY": 1.74,
    "CNY": 12.3,
    "PLN": 22.3,
}

# Aliases mapped onto CBR codes
CURRENCY_ALIASES = {
    "RUR": "RUB",
    "USDT": "USD",
    "USDC": "USD",
}

_memory_rates: dict[str, float] = dict(FALLBACK_RATES_TO_RUB)
_memory_fetched_at: float | None = None
_memory_source: str = "fallback"
_memory_as_of: str | None = None


def normalize_currency(code: str | None) -> str | None:
    if not code:
        return None
    cur = code.strip().upper()
    return CURRENCY_ALIASES.get(cur, cur)


def _redis_client() -> Redis | None:
    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1.5)
        client.ping()
        return client
    except Exception:  # noqa: BLE001
        return None


def _parse_cbr_payload(payload: dict[str, Any]) -> dict[str, float]:
    rates: dict[str, float] = {"RUB": 1.0, "RUR": 1.0}
    valute = payload.get("Valute") or {}
    for code, item in valute.items():
        if not isinstance(item, dict):
            continue
        try:
            nominal = float(item.get("Nominal") or 1)
            value = float(item.get("Value") or 0)
        except (TypeError, ValueError):
            continue
        if nominal <= 0 or value <= 0:
            continue
        rates[str(code).upper()] = value / nominal
    # Stablecoins ≈ USD
    if "USD" in rates:
        rates["USDT"] = rates["USD"]
        rates["USDC"] = rates["USD"]
    return rates


async def fetch_cbr_rates() -> tuple[dict[str, float], str | None]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(CBR_DAILY_URL)
        response.raise_for_status()
        payload = response.json()
    rates = _parse_cbr_payload(payload)
    as_of = payload.get("Date") or payload.get("Timestamp")
    return rates, str(as_of) if as_of else None


def _store_rates(rates: dict[str, float], *, source: str, as_of: str | None) -> None:
    global _memory_rates, _memory_fetched_at, _memory_source, _memory_as_of
    merged = dict(FALLBACK_RATES_TO_RUB)
    merged.update(rates)
    merged["RUB"] = 1.0
    merged["RUR"] = 1.0
    _memory_rates = merged
    _memory_fetched_at = time.time()
    _memory_source = source
    _memory_as_of = as_of

    client = _redis_client()
    if client is None:
        return
    try:
        client.setex(
            REDIS_KEY,
            CACHE_TTL_SECONDS,
            json.dumps({"rates": merged, "source": source, "as_of": as_of, "fetched_at": _memory_fetched_at}),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to cache FX rates in Redis: %s", exc)


def _load_from_redis() -> dict[str, float] | None:
    client = _redis_client()
    if client is None:
        return None
    try:
        raw = client.get(REDIS_KEY)
        if not raw:
            return None
        payload = json.loads(raw)
        rates = payload.get("rates") or {}
        if not isinstance(rates, dict) or "USD" not in rates:
            return None
        global _memory_rates, _memory_fetched_at, _memory_source, _memory_as_of
        _memory_rates = {str(k).upper(): float(v) for k, v in rates.items()}
        _memory_fetched_at = float(payload.get("fetched_at") or time.time())
        _memory_source = str(payload.get("source") or "redis")
        _memory_as_of = payload.get("as_of")
        return _memory_rates
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read FX rates from Redis: %s", exc)
        return None


async def refresh_rates(*, force: bool = False) -> dict[str, Any]:
    """Refresh live FX rates from CBR. Safe to call on startup/scheduler."""
    if (
        not force
        and _memory_fetched_at is not None
        and _memory_source != "fallback"
        and (time.time() - _memory_fetched_at) < MEMORY_TTL_SECONDS
    ):
        return fx_status()

    try:
        rates, as_of = await fetch_cbr_rates()
        _store_rates(rates, source="cbr", as_of=as_of)
        logger.info("FX rates refreshed from CBR (%s currencies, as_of=%s)", len(rates), as_of)
        return fx_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("CBR FX refresh failed, keeping %s rates: %s", _memory_source, exc)
        if _load_from_redis() is None and _memory_source == "fallback":
            _store_rates(FALLBACK_RATES_TO_RUB, source="fallback", as_of=None)
        return {**fx_status(), "error": str(exc)}


def get_rates_to_rub() -> dict[str, float]:
    """Current RUB multipliers. Prefers memory → Redis → fallback."""
    if _memory_fetched_at is not None and _memory_source != "fallback":
        return _memory_rates
    cached = _load_from_redis()
    if cached:
        return cached
    return dict(FALLBACK_RATES_TO_RUB)


# Back-compat for older imports/tests
RATES_TO_RUB = FALLBACK_RATES_TO_RUB


def rate_to_rub(currency: str | None) -> float:
    cur = normalize_currency(currency) or "RUB"
    rates = get_rates_to_rub()
    return float(rates.get(cur, 1.0))


def to_rub(amount: int | None, currency: str | None) -> int | None:
    if amount is None:
        return None
    return int(round(amount * rate_to_rub(currency)))


def salary_in_rub(
    salary_from: int | None,
    salary_to: int | None,
    currency: str | None,
) -> tuple[int | None, int | None, str | None]:
    """Return (from, to, original_currency) with amounts converted to RUB."""
    original = normalize_currency(currency)
    if salary_from is None and salary_to is None:
        return None, None, original
    return to_rub(salary_from, original), to_rub(salary_to, original), original


def rub_rate_case(currency_column: Any) -> Any:
    """SQLAlchemy CASE expression: multiplier to convert currency column to RUB."""
    from sqlalchemy import case, func, literal

    rates = get_rates_to_rub()
    upper = func.upper(currency_column)
    whens = [(upper == code, literal(rate)) for code, rate in rates.items()]
    return case(*whens, else_=literal(1.0))


def fx_status() -> dict[str, Any]:
    rates = get_rates_to_rub()
    interesting = ("USD", "EUR", "GBP", "KZT", "BYN", "CNY", "PLN")
    return {
        "source": _memory_source,
        "as_of": _memory_as_of,
        "fetched_at": _memory_fetched_at,
        "currencies": len(rates),
        "rates": {code: rates.get(code) for code in interesting if code in rates},
    }
