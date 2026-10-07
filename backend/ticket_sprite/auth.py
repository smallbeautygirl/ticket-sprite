"""Login via Observ (ADR-0001) and the sprite's own session cookie.

The password is forwarded to Observ once and never stored. After that the
caller is identified only by a signed cookie that carries their email.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import Settings, get_settings

SESSION_COOKIE = "ts_session"


@dataclass(frozen=True)
class ObservIdentity:
    observ_id: int | None
    email: str
    display_name: str | None


class LoginFailed(Exception):
    pass


class ObservAuthClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._settings = settings
        self._transport = transport

    async def login(self, email: str, password: str) -> ObservIdentity:
        base = self._settings.observ_base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=15, transport=self._transport) as client:
            try:
                token_resp = await client.post(
                    f"{base}/apiserver/users/token", json={"email": email, "password": password}
                )
            except httpx.RequestError as exc:
                raise LoginFailed("Observ 無法連線") from exc
            if token_resp.status_code != 200:
                raise LoginFailed("帳號或密碼錯誤")
            token = token_resp.json().get("access_token")
            if not token:
                raise LoginFailed("Observ 回應缺少 access_token")

            me_resp = await client.get(
                f"{base}/auth/users/me",
                headers={
                    "Authorization": f"Bearer {token}",
                    "x-request-service-id": self._settings.observ_service_id,
                },
            )
        if me_resp.status_code != 200:
            # Token works but identity lookup failed; fall back to the typed email.
            return ObservIdentity(observ_id=None, email=email.lower(), display_name=None)
        data = me_resp.json()
        name = data.get("name") or " ".join(
            p for p in (data.get("first_name"), data.get("last_name")) if p
        ) or None
        return ObservIdentity(
            observ_id=data.get("id"), email=(data.get("email") or email).lower(), display_name=name
        )


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt="ticket-sprite-session")


def issue_session(settings: Settings, email: str) -> str:
    return _serializer(settings).dumps({"email": email})


def read_session(settings: Settings, token: str) -> str | None:
    try:
        data = _serializer(settings).loads(token, max_age=settings.session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("email")


def current_email(request: Request, settings: Settings = Depends(get_settings)) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    email = read_session(settings, token) if token else None
    if not email or not settings.may_log_in(email):
        # also drops sessions issued before someone was removed from the allowlist
        raise HTTPException(status_code=401, detail="請先登入")
    return email
