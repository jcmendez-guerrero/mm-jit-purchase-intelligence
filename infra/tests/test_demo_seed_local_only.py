"""The synthetic demo seed (MMI-5, T035/T048) exists only in the local compose stack, never in cloud configuration (rule 7a)."""

from pathlib import Path

INFRA = Path(__file__).resolve().parents[1]


def test_the_flag_is_set_in_local_compose_only():
    assert 'MMI_DEMO_SEED: "1"' in (INFRA / "compose.yaml").read_text()
    offenders = [str(p.relative_to(INFRA)) for p in INFRA.rglob("*") if p.is_file() and p.suffix in {".bicep", ".bicepparam", ".json", ".tf", ".tfvars"}
                 and "MMI_DEMO_SEED" in p.read_text(errors="ignore")]
    assert offenders == []
