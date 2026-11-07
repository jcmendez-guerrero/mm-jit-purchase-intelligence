"""Local-only token issuer for Compose. Refuses to start unless MMI_ENV=dev. Never deployed."""

import os
import re
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from mmi_common.auth import DevIssuer
from pydantic import BaseModel

USER_SUBJECT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@:-]{0,119}")


class TokenRequest(BaseModel):
    subject: str
    audience: str
    roles: list[str] = []
    user: bool = False                 # an end-user token issued on the user's behalf (the BFF's on-behalf-of stand-in)
    auth_time: int | None = None       # epoch seconds of the user's last second-factor authentication


def create_app() -> FastAPI:
    if os.environ.get("MMI_ENV") != "dev":
        raise RuntimeError("dev issuer requires MMI_ENV=dev")
    issuer = DevIssuer(os.environ.get("MMI_ISSUER", "http://dev-issuer.local"))
    app = FastAPI(title="dev issuer (local only)")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/public-key", response_class=PlainTextResponse)
    def public_key() -> str:
        return issuer.public_pem

    @app.post("/token")
    def token(req: TokenRequest) -> dict[str, str]:
        if req.user:
            if not USER_SUBJECT.fullmatch(req.subject) or req.subject.startswith(("svc-", "dev-")):
                raise HTTPException(422, "user subjects are plain ids and never look like service identities")
        elif not req.subject.startswith(("dev-", "svc-")):
            raise HTTPException(422, "dev subjects must start with dev- or svc-")
        auth_time = datetime.fromtimestamp(req.auth_time, UTC) if req.auth_time else None
        return {"access_token": issuer.issue(req.subject, req.audience, req.roles, auth_time=auth_time)}

    return app
