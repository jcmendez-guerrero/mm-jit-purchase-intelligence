"""T143: Test that every failure class has an alert rule and evaluation windows total <= 1 hour (SC-013)."""

import re
from pathlib import Path

ALERTS_BICEP = Path(__file__).resolve().parents[1] / "bicep" / "modules" / "alerts.bicep"


def test_alerts_bicep_exists_and_contains_action_group():
    assert ALERTS_BICEP.exists()
    content = ALERTS_BICEP.read_text()
    assert "Microsoft.Insights/actionGroups" in content
    assert "Microsoft.Insights/scheduledQueryRules" in content


def test_every_failure_class_has_alert_rule():
    content = ALERTS_BICEP.read_text()

    required_classes = [
        "sync-failed",
        "quota-denied",
        "allowlist-refused",
        "queue-poison",
        "cost-write-failed",
        "auth-denials",
        "unmatched-writes",
        "suspicious-approvals",
        "import-failed",
        "upload-rejected",
        "role-mirror-lag",
        "admin-alert-opened",
    ]

    for failure_class in required_classes:
        assert f"key: '{failure_class}'" in content, f"Missing alert rule for failure class: {failure_class}"


def test_rule_evaluation_frequency_and_window_size_bounded():
    content = ALERTS_BICEP.read_text()

    # Find all evaluationFrequency and windowSize entries inside the rules array
    rule_blocks = re.findall(r"\{\s*key:\s*'([^']+)'(?:.|\n)+?evaluationFrequency:\s*'([^']+)'\s*windowSize:\s*'([^']+)'", content)
    assert len(rule_blocks) >= 11

    # All failure alert rules must evaluate within <= 1 hour (PT5M, PT15M, PT30M, PT1H)
    valid_durations = {"PT5M", "PT10M", "PT15M", "PT30M", "PT1H"}
    for key, eval_freq, win_size in rule_blocks:
        assert eval_freq in valid_durations, f"Rule {key} evaluationFrequency {eval_freq} exceeds 1 hour"
        assert win_size in valid_durations, f"Rule {key} windowSize {win_size} exceeds 1 hour"


def test_new_rules_watch_the_markers_the_services_log():
    """T153: the markers are emitted by forecast-service (IMPORT_FAILED, UPLOAD_REJECTED) and api-bff (ROLE_MIRROR_LAG)."""
    content = ALERTS_BICEP.read_text()
    root = ALERTS_BICEP.parents[3]
    emitters = {"IMPORT_FAILED": "services/forecast-service/src/seeds/jobs.py", "UPLOAD_REJECTED": "services/forecast-service/src/imports_api.py",
                "ROLE_MIRROR_LAG": "services/api-bff/src/worker.py"}
    for marker, source in emitters.items():
        assert marker in content, marker
        assert marker in (root / source).read_text(), f"{source} does not log {marker}"
