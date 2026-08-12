"""HH OAuth helpers. Tokens are stored in source_configs.settings, not in git."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import SourceName
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


async def exchange_code(code: str) -> dict[str, Any]:
    if not settings.hh_client_id or not settings.hh_client_secret:
        raise RuntimeError("HH_CLIENT_ID / HH_CLIENT_SECRET are not set in .env")

    payload = {
        "grant_type": "authorization_code",
        "client_id": settings.hh_client_id,
        "client_secret": settings.hh_client_secret,
        "code": code,
        "redirect_uri": settings.hh_redirect_uri,
    }
    async with httpx.AsyncClient(timeout=30.0, headers=hh_headers()) as client:
        response = await client.post(TOKEN_URL, data=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"HH token exchange failed ({response.status_code}): {response.text[:500]}")
        return response.json()


async def save_tokens(session: AsyncSession, token_payload: dict[str, Any]) -> SourceConfig:
    source = await get_hh_source(session)
    if source is None:
        raise RuntimeError("HH source is not initialized")

    expires_in = int(token_payload.get("expires_in") or 0)
    expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat() if expires_in else None
    current = dict(source.settings or {})
    current.update(
        {
            "access_token": token_payload.get("access_token"),
            "refresh_token": token_payload.get("refresh_token"),
            "token_type": token_payload.get("token_type"),
            "expires_at": expires_at,
            "connected_at": datetime.utcnow().isoformat(),
        }
    )
    source.settings = current
    source.last_error = None
    source.status = "ready"
    await session.flush()
    return source


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
