"""HH OAuth helpers. Tokens are stored in source_configs.settings, not in git."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import SourceName
from app.core.timeutil import utc_now_naive
from app.models import SourceConfig

AUTHORIZE_URL = "https://hh.ru/oauth/authorize"
TOKEN_URL = "https://hh.ru/oauth/token"
HH_API = "https://api.hh.ru"


def hh_headers(access_token: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": settings.hh_user_agent,
        "HH-User-Agent": settings.hh_user_agent,
        "Accept": "application/json",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def resolve_access_token(source: SourceConfig | None = None) -> str:
    stored = ((source.settings or {}) if source else {}).get("access_token") or ""
    return stored or settings.hh_access_token


async def get_hh_source(session: AsyncSession) -> SourceConfig | None:
    result = await session.execute(select(SourceConfig).where(SourceConfig.name == SourceName.HH))
    return result.scalar_one_or_none()


def build_authorize_url() -> str:
    if not settings.hh_client_id:
        raise RuntimeError(
            "HH_CLIENT_ID is empty. After HH approves the app, paste Client ID and Client Secret into .env"
        )
    params = {
        "response_type": "code",
        "client_id": settings.hh_client_id,
        "redirect_uri": settings.hh_redirect_uri,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def _post_token(payload: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0, headers=hh_headers()) as client:
        response = await client.post(TOKEN_URL, data=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"HH token exchange failed ({response.status_code}): {response.text[:500]}")
        data = response.json()
        if not data.get("access_token"):
            raise RuntimeError("HH token exchange returned no access_token")
        return data


async def exchange_code(code: str) -> dict[str, Any]:
    if not settings.hh_client_id or not settings.hh_client_secret:
        raise RuntimeError("HH_CLIENT_ID / HH_CLIENT_SECRET are not set in .env")

    return await _post_token(
        {
            "grant_type": "authorization_code",
            "client_id": settings.hh_client_id,
            "client_secret": settings.hh_client_secret,
            "code": code,
            "redirect_uri": settings.hh_redirect_uri,
        }
    )


async def exchange_client_credentials() -> dict[str, Any]:
    if not settings.hh_client_id or not settings.hh_client_secret:
        raise RuntimeError("HH_CLIENT_ID / HH_CLIENT_SECRET are not set in .env")
    return await _post_token(
        {
            "grant_type": "client_credentials",
            "client_id": settings.hh_client_id,
            "client_secret": settings.hh_client_secret,
        }
    )


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    if not settings.hh_client_id or not settings.hh_client_secret:
        raise RuntimeError("HH_CLIENT_ID / HH_CLIENT_SECRET are not set in .env")
    return await _post_token(
        {
            "grant_type": "refresh_token",
            "client_id": settings.hh_client_id,
            "client_secret": settings.hh_client_secret,
            "refresh_token": refresh_token,
        }
    )


def _token_expired(stored: dict[str, Any], *, skew_seconds: int = 120) -> bool:
    raw = stored.get("expires_at")
    if not raw:
        return False
    try:
        from datetime import datetime

        exp = datetime.fromisoformat(str(raw))
    except ValueError:
        return False
    return exp <= utc_now_naive() + timedelta(seconds=skew_seconds)


async def save_tokens(session: AsyncSession, token_payload: dict[str, Any]) -> SourceConfig:
    source = await get_hh_source(session)
    if source is None:
        raise RuntimeError("HH source is not initialized")

    now = utc_now_naive()
    expires_in = int(token_payload.get("expires_in") or 0)
    expires_at = (now + timedelta(seconds=expires_in)).isoformat() if expires_in else None
    current = dict(source.settings or {})
    current["access_token"] = token_payload.get("access_token")
    if token_payload.get("refresh_token"):
        current["refresh_token"] = token_payload.get("refresh_token")
    if token_payload.get("token_type"):
        current["token_type"] = token_payload.get("token_type")
    current["expires_at"] = expires_at
    current["connected_at"] = now.isoformat()
    source.settings = current
    source.last_error = None
    source.status = "ready"
    await session.flush()
    return source


async def ensure_hh_token(session: AsyncSession) -> str:
    """Return a usable HH access token: stored → refresh → client_credentials → env."""
    source = await get_hh_source(session)
    stored = dict(source.settings or {}) if source else {}
    token = str(stored.get("access_token") or settings.hh_access_token or "")
    refresh = str(stored.get("refresh_token") or "")

    if token and refresh and _token_expired(stored):
        try:
            payload = await refresh_access_token(refresh)
            if source is not None:
                await save_tokens(session, payload)
            token = str(payload.get("access_token") or token)
        except Exception:  # noqa: BLE001
            token = token if not _token_expired(stored, skew_seconds=0) else ""

    if token:
        return token

    if settings.hh_client_id and settings.hh_client_secret:
        try:
            payload = await exchange_client_credentials()
            if source is not None:
                await save_tokens(session, payload)
            return str(payload.get("access_token") or "")
        except Exception:  # noqa: BLE001
            return ""
    return ""


async def probe_hh(access_token: str | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0, headers=hh_headers(access_token)) as client:
        response = await client.get(f"{HH_API}/vacancies", params={"text": "Python", "per_page": 1})
        body = (response.text or "")[:300]
        ok = response.status_code == 200
        found = None
        if ok:
            try:
                found = response.json().get("found")
            except Exception:  # noqa: BLE001
                found = None
        return {
            "ok": ok,
            "status_code": response.status_code,
            "found": found,
            "authenticated": bool(access_token),
            "detail": None if ok else body,
        }
