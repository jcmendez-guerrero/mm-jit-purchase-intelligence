"""Database-level guards: audit events are append-only; cost versions are immutable except attestations.

Triggers fire for every role, including the owner, so a bug or a stolen service credential cannot rewrite history
through ordinary SQL (dropping a trigger needs DDL rights the runtime does not use). Only PostgreSQL has them; the unit
tests on SQLite rely on the application code and on the hash chain.

Revision ID: 0004
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

ATTESTATION = "'verified_at','verified_by','superseded_by','jump_confirmed_by','jump_confirmed_at'"


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
        CREATE FUNCTION forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = 'integrity_constraint_violation';
        END $$""")
    op.execute("CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION forbid_change()")
    op.execute("CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON audit_events FOR EACH STATEMENT EXECUTE FUNCTION forbid_change()")
    op.execute(f"""
        CREATE FUNCTION guard_supplier_costs() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'supplier_costs rows are never deleted' USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            IF (to_jsonb(NEW) - ARRAY[{ATTESTATION}]) IS DISTINCT FROM (to_jsonb(OLD) - ARRAY[{ATTESTATION}]) THEN
                RAISE EXCEPTION 'supplier_costs values are immutable; add a new version' USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            IF OLD.superseded_by IS NOT NULL AND NEW.superseded_by IS DISTINCT FROM OLD.superseded_by THEN
                RAISE EXCEPTION 'a superseded cost cannot be re-pointed' USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END $$""")
    op.execute("CREATE TRIGGER supplier_costs_immutable BEFORE UPDATE OR DELETE ON supplier_costs FOR EACH ROW EXECUTE FUNCTION guard_supplier_costs()")
    op.execute("CREATE TRIGGER supplier_costs_no_truncate BEFORE TRUNCATE ON supplier_costs FOR EACH STATEMENT EXECUTE FUNCTION forbid_change()")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP TRIGGER IF EXISTS supplier_costs_no_truncate ON supplier_costs")
    op.execute("DROP TRIGGER IF EXISTS audit_events_no_truncate ON audit_events")
    op.execute("DROP TRIGGER IF EXISTS supplier_costs_immutable ON supplier_costs")
    op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS guard_supplier_costs()")
    op.execute("DROP FUNCTION IF EXISTS forbid_change()")
