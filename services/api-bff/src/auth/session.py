"""Cookie-session handling for api-bff (T109).

Cookie is signed with HMAC-SHA256, marked HttpOnly, SameSite=Lax, Secure (in production).
Carries user identity, roles, MFA authentication timestamp, and a CSRF token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response

COOKIE_NAME = "mmi_session"
DEFAULT_TTL_MINUTES = 480  # 8 hours
MFA_FRESHNESS_SECONDS = 300  # 5 minutes


@dataclass
class SessionData:
    user_id: str
    email: str
    roles: list[str]
    mfa_auth_time: str  # ISO UTC
    csrf_token: str
    exp: int            # unix timestamp

    @property
    def mfa_datetime(self) -> datetime:
        return datetime.fromisoformat(self.mfa_auth_time)

    def is_mfa_fresh(self, max_age_seconds: int = MFA_FRESHNESS_SECONDS, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        diff = (current - self.mfa_datetime).total_seconds()
        return 0 <= diff <= max_age_seconds


MIN_SECRET_LENGTH = 32


def get_secret_key() -> bytes:
    """Production refuses to sign sessions with a missing or short secret; only development has a built-in value."""
    key = os.environ.get("MMI_SESSION_SECRET")
    if os.environ.get("MMI_ENV", "dev") == "prod":
        if not key or len(key) < MIN_SECRET_LENGTH:
            raise RuntimeError("MMI_SESSION_SECRET must be set to at least 32 characters in production")
        return key.encode("utf-8")
    return (key or "dev-insecure-session-secret-change-in-prod").encode("utf-8")


def sign_session(data: SessionData) -> str:
    raw_json = json.dumps(asdict(data)).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(raw_json).decode("utf-8")
    sig = hmac.new(get_secret_key(), b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{sig}"


def verify_session(cookie_val: str) -> SessionData | None:
    try:
        parts = cookie_val.split(".", 1)
        if len(parts) != 2:
            return None
        b64_payload, sig = parts
        expected_sig = hmac.new(get_secret_key(), b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload_bytes = base64.urlsafe_b64decode(b64_payload.encode("utf-8"))
        data_dict = json.loads(payload_bytes.decode("utf-8"))
        now_ts = int(datetime.now(UTC).timestamp())
        if data_dict.get("exp", 0) < now_ts:
            return None
        return SessionData(
            user_id=data_dict["user_id"],
            email=data_dict.get("email", ""),
            roles=data_dict.get("roles", []),
            mfa_auth_time=data_dict["mfa_auth_time"],
            csrf_token=data_dict["csrf_token"],
            exp=data_dict["exp"],
        )
    except Exception:
        return None


def create_session(
    user_id: str,
    email: str,
    roles: list[str],
    mfa_auth_time: datetime | None = None,
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
) -> SessionData:
    now = datetime.now(UTC)
    mfa_time = mfa_auth_time or now
    return SessionData(
        user_id=user_id,
        email=email,
        roles=roles,
        mfa_auth_time=mfa_time.isoformat(),
        csrf_token=secrets.token_urlsafe(32),
        exp=int((now + timedelta(minutes=ttl_minutes)).timestamp()),
    )


def set_session_cookie(response: Response, session: SessionData) -> None:
    cookie_value = sign_session(session)
    # Secure is true in production or if MMI_COOKIE_SECURE is explicitly true
    env = os.environ.get("MMI_ENV", "dev")
    secure = os.environ.get("MMI_COOKIE_SECURE", "true" if env == "prod" else "false").lower() == "true"
    response.set_cookie(
        key=COOKIE_NAME,
        value=cookie_value,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=DEFAULT_TTL_MINUTES * 60,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")


def get_current_session(request: Request) -> SessionData | None:
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        # Also check Authorization: Bearer for testing / programmatic clients if needed
        return None
    return verify_session(cookie)
