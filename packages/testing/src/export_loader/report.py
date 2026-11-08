"""T017: counts and review items for one load, shaped like the ``load_result`` contract.

Invariant (SC-002): loaded + updated + unchanged + quarantined + excluded + services == rows. Review details are built from
fixed templates, are capped, and have anything that looks like an e-mail address or a long number (tax id, IBAN, phone)
removed before they are kept.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

CODE = re.compile(r"^[a-z0-9_]+$")
LONG_NUMBER = re.compile(r"[A-Za-z]{0,2}\d[\dA-Za-z ]{7,}\d")
EMAIL = re.compile(r"\S+@\S+")
MAX_DETAIL = 200


class UnbalancedReport(Exception):
    pass


def clean_detail(detail: str) -> str:
    out = EMAIL.sub("[oculto]", detail)
    out = LONG_NUMBER.sub("[oculto]", out)
    return out[:MAX_DETAIL]


@dataclass
class LoadReport:
    kind: str
    file_sha256: str
    rows: int
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    loaded: int = 0
    updated: int = 0
    unchanged: int = 0
    quarantined: int = 0
    excluded: int = 0
    services: int = 0
    differences: int = 0
    reviews: list[dict[str, Any]] = field(default_factory=list)
    interpretations: dict[str, Any] = field(default_factory=dict)

    def review(self, row: int, code: str, detail: str = "", source: str = "loader") -> None:
        if not CODE.match(code):
            raise ValueError(f"review code must be snake_case: {code!r}")
        self.reviews.append({"row": row, "code": code, "detail": clean_detail(detail), "source": source})

    def exclude(self, n: int = 1) -> None:
        self.excluded += n

    def balanced(self) -> bool:
        return self.loaded + self.updated + self.unchanged + self.quarantined + self.excluded + self.services == self.rows

    def result(self) -> dict[str, Any]:
        if not self.balanced():
            raise UnbalancedReport(
                f"{self.kind}: {self.loaded}+{self.updated}+{self.unchanged}+{self.quarantined}+{self.excluded}+{self.services} != {self.rows}"
            )
        out: dict[str, Any] = {
            "run_id": self.run_id, "kind": self.kind, "file_sha256": self.file_sha256, "rows": self.rows,
            "loaded": self.loaded, "updated": self.updated, "unchanged": self.unchanged, "quarantined": self.quarantined,
            "excluded": self.excluded, "services": self.services, "differences": self.differences, "review": list(self.reviews),
        }
        if self.interpretations:
            out["interpretations"] = dict(self.interpretations)
        return out
