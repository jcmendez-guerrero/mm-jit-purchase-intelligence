"""Local-only token issuer for Compose. Refuses to start unless MMI_ENV=dev. Never deployed."""

import os

from fastapi import FastAPI, HTTPException
from mmi_common.auth import DevIssuer
from pydantic import BaseModel


class TokenRequest(BaseModel):
    subject: str
    audience: str
    roles: list[str] = []


def create_app() -> FastAPI:
    if os.environ.get("MMI_ENV") != "dev":
        raise RuntimeError("dev issuer requires MMI_ENV=dev")
    issuer = DevIssuer(os.environ.get("MMI_ISSUER", "http://dev-issuer.local"))
    app = FastAPI(title="dev issuer (local only)")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/public-key")
    def public_key() -> str:
        return issuer.public_pem

    @app.post("/token")
    def token(req: TokenRequest) -> dict[str, str]:
        if not req.subject.startswith(("dev-", "svc-")):
            raise HTTPException(422, "dev subjects must start with dev- or svc-")
        return {"access_token": issuer.issue(req.subject, req.audience, req.roles)}

    return app
