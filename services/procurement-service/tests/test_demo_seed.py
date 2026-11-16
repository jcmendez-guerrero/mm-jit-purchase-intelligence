"""T035/T048 option A: the local-only synthetic seed (Agent 00 conditions: own schema, synthetic, never in the cloud)."""

from decimal import Decimal

from db.tables import proposal_lines, proposals
from local_demo import seed as demo
from sqlalchemy import select


def test_it_is_off_unless_asked_and_never_in_prod_or_staging():
    assert not demo.enabled({})
    assert not demo.enabled({"MMI_DEMO_SEED": "0"})
    assert demo.enabled({"MMI_DEMO_SEED": "1", "MMI_ENV": "dev"})
    assert not demo.enabled({"MMI_DEMO_SEED": "1", "MMI_ENV": "prod"})
    assert not demo.enabled({"MMI_DEMO_SEED": "1", "MMI_ENV": "staging"})


def test_it_seeds_one_synthetic_draft_through_the_real_inputs_provider_and_only_once(engine):
    pid = demo.seed(engine)
    assert pid is not None
    assert demo.seed(engine) is None
    with engine.connect() as c:
        rows = c.execute(select(proposals)).all()
        lines = c.execute(select(proposal_lines).where(proposal_lines.c.proposal_id == pid)).all()
    assert len(rows) == 1 and rows[0].status == "draft" and rows[0].created_by == "demo-seed"
    assert lines and all(Decimal(str(r.line_total)) > 0 for r in lines)
    assert {r.variant_id for r in lines} <= {9101, 9102, 9103, 9104}


def test_it_registers_the_dev_approvers_so_a_draft_can_be_sent_for_approval(engine):
    from users.directory import DbUserDirectory

    demo.seed(engine)
    assert DbUserDirectory(engine).active_approvers() == {"approver-1", "approver-2"}
