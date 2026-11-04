"""Run the mock: ``python -m siweb_mock`` (port 8089)."""

import os

import uvicorn

from . import create_app

if __name__ == "__main__":
    uvicorn.run(create_app(), host=os.environ.get("MOCK_HOST", "0.0.0.0"), port=int(os.environ.get("MOCK_PORT", "8089")))  # noqa: S104
