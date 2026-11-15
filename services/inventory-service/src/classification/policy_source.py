"""T010a: where the classification thresholds come from, and the version id recorded with every result (feature 012, FR-007).

T010 found that the business policy console on main stores none of these thresholds, so the source today is the
``ClassificationConfig`` defaults. The version id is a hash of the values, so any change to a threshold gives a new id and
older results stay explainable under the configuration that produced them. When the policy console later holds these
fields, only ``current_config`` changes; callers keep receiving ``(config, version_id)``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from classification.segments import ClassificationConfig

PREFIX = "defaults-"


def version_id(cfg: ClassificationConfig) -> str:
    body = json.dumps(asdict(cfg), sort_keys=True, separators=(",", ":"))
    return PREFIX + hashlib.sha256(body.encode()).hexdigest()[:16]


def current_config() -> tuple[ClassificationConfig, str]:
    cfg = ClassificationConfig()
    return cfg, version_id(cfg)
