from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from generator import Dataset

TOKEN = "synthetic-test-token"  # noqa: S105 - mock only; never a real token


@dataclass
class MockConfig:
    token: str = TOKEN
    rate_limit_per_hour: int | None = None       # None = unlimited; otherwise 429 once exceeded
    send_retry_after: bool = False               # real API documents no Retry-After (open item V3)
    max_page_size: int = 200
    insert_after_movement_requests: int | None = None  # newest-first paging shifts mid-run
    insert_count: int = 5
    missing_pages: set[int] = field(default_factory=set)   # movements pages answering 500 once
    unauthorized_after: int | None = None        # token "expires" after N requests (401)
    # supplier-cost PUT behaviour (suppliers.py)
    put_semantics: str = "merge"                 # "merge" keeps omitted fields; "replace" resets them
    allow_create: bool = False                   # PUT for a missing product-supplier link
    fail_next_puts: int = 0
    fail_status: int = 503


@dataclass
class MockState:
    data: Dataset
    config: MockConfig = field(default_factory=MockConfig)
    request_log: list[dict[str, Any]] = field(default_factory=list)
    movements_requests: int = 0
    total_requests: int = 0
    window_started: float = field(default_factory=time.time)
    failed_pages_served: set[int] = field(default_factory=set)
    next_movement_id: int = 0
    movements: list[dict[str, Any]] = field(default_factory=list)  # oldest first
    suppliers: dict[int, list[dict[str, Any]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.request_log.clear()
        self.movements_requests = self.total_requests = 0
        self.failed_pages_served.clear()
        self.movements = copy.deepcopy(self.data.movements)
        self.suppliers = copy.deepcopy(self.data.suppliers)
        self.next_movement_id = (self.movements[-1]["id"] if self.movements else 0) + 1
        self.window_started = time.time()

    def insert_new_movements(self) -> None:
        template = next((m for m in reversed(self.movements) if m["reason"] == "sale_shipment"), None)
        for _ in range(self.config.insert_count):
            if template is None:
                return
            m = copy.deepcopy(template)
            m.update(id=self.next_movement_id, created_at=datetime.now().replace(microsecond=0).isoformat())  # noqa: DTZ005 - offset-less like the real API
            self.next_movement_id += 1
            self.movements.append(m)

    def writes(self) -> list[dict[str, Any]]:
        return [r for r in self.request_log if r["method"] not in ("GET", "HEAD")]
