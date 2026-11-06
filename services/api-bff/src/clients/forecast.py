"""Client for forecast-service."""

from __future__ import annotations

import os

from .base import DownstreamClient


class ForecastClient(DownstreamClient):
    def __init__(self, base_url: str | None = None):
        super().__init__(base_url or os.environ.get("MMI_FORECAST_URL", "http://forecast-service:8000"), "api://mmi-forecast-service")
