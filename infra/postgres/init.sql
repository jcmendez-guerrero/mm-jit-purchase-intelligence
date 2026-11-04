-- Local development only. One schema and one role per service; no cross-schema access.
-- Passwords are throwaway local values (the compose stack is never exposed).
\set ON_ERROR_STOP on

DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT * FROM (VALUES
    ('integration','integration_svc'), ('inventory','inventory_svc'), ('forecasting','forecasting_svc'),
    ('procurement','procurement_svc'), ('costwrite','costwrite_svc')) AS t(schema_name, role_name)
  LOOP
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', r.role_name, 'dev-only-local');
    EXECUTE format('CREATE SCHEMA %I AUTHORIZATION %I', r.schema_name, r.role_name);
    EXECUTE format('ALTER ROLE %I SET search_path = %I', r.role_name, r.schema_name);
  END LOOP;
END $$;

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE mmi FROM PUBLIC;
GRANT CONNECT ON DATABASE mmi TO integration_svc, inventory_svc, forecasting_svc, procurement_svc, costwrite_svc;
