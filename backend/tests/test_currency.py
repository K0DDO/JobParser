import pytest

from app.services.currency import (
    FALLBACK_RATES_TO_RUB,
    _parse_cbr_payload,
    _store_rates,
    get_rates_to_rub,
    salary_in_rub,
    to_rub,
)


def test_parse_cbr_payload():
    payload = {
        "Date": "2026-08-13T11:30:00+03:00",
        "Valute": {
            "USD": {"Nominal": 1, "Value": 82.9977},
            "KZT": {"Nominal": 100, "Value": 17.8206},
        },
    }
    rates = _parse_cbr_payload(payload)
    assert rates["RUB"] == 1.0
    assert rates["USD"] == pytest.approx(82.9977)
    assert rates["USDT"] == pytest.approx(82.9977)
    assert rates["KZT"] == pytest.approx(0.178206)


def test_to_rub_uses_stored_live_rates():
    _store_rates({"USD": 80.0, "EUR": 90.0, "RUB": 1.0}, source="test", as_of="2026-08-13")
    assert to_rub(1000, "USD") == 80000
    assert to_rub(2000, "EUR") == 180000
    assert to_rub(200000, "RUB") == 200000
    assert to_rub(None, "USD") is None


def test_salary_in_rub_tuple():
    _store_rates({"EUR": 100.0, "RUB": 1.0}, source="test", as_of=None)
    low, high, original = salary_in_rub(2000, 3000, "EUR")
    assert original == "EUR"
    assert low == 200000
    assert high == 300000


def test_fallback_rates_available():
    rates = get_rates_to_rub()
    assert "USD" in rates
    assert FALLBACK_RATES_TO_RUB["RUB"] == 1.0
