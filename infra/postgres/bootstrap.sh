#!/usr/bin/env bash
# One-time bootstrap of the MMI database on the SHARED PostgreSQL flexible server.
# Creates database `mmi`, one schema and one login role per service (no cross-schema access), generates a random password
# per role and stores the full connection string in Key Vault as "<prefix>-<service>". Passwords are never printed or logged.
#
# Inputs (environment variables; real values stay on your machine, never in the repository):
#   PGHOST          server FQDN                       PGADMIN   administrator login
#   PGADMIN_TOKEN   password or `az account get-access-token --resource-type oss-rdbms` token for PGADMIN
#   KEY_VAULT_NAME  shared Key Vault                  DB_URL_PREFIX  secret prefix (default: mmi-db-url)
# Requires: psql, openssl, az (logged in, Key Vault Secrets Officer on the vault), network access to the server.
set -euo pipefail

: "${PGHOST:?}" "${PGADMIN:?}" "${PGADMIN_TOKEN:?}" "${KEY_VAULT_NAME:?}"
prefix="${DB_URL_PREFIX:-mmi-db-url}"
export PGSSLMODE=require

admin() { PGPASSWORD="$PGADMIN_TOKEN" psql -v ON_ERROR_STOP=1 -h "$PGHOST" -U "$PGADMIN" "$@"; }

if ! admin -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='mmi'" | grep -q 1; then
	admin -d postgres -c 'CREATE DATABASE mmi'
fi

# key | schema | role
services=("connector integration integration_svc" "inventory inventory inventory_svc" "forecast forecasting forecasting_svc"
	"procurement procurement procurement_svc" "bff bff bff_svc" "costwrite costwrite costwrite_svc")

for entry in "${services[@]}"; do
	read -r key schema role <<<"$entry"
	secret_name="$prefix-$key"
	if az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name "$secret_name" >/dev/null 2>&1; then
		echo "skip $key: secret already exists (rotate with the token-rotation runbook)"
		continue
	fi
	pw="$(openssl rand -base64 36 | tr -d '/+=\n' | cut -c1-40)"
	admin -d mmi -v pw="$pw" -v role="$role" -v schema="$schema" <<'SQL' >/dev/null
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'role', :'pw') \gexec
SELECT format('CREATE SCHEMA %I AUTHORIZATION %I', :'schema', :'role') \gexec
SELECT format('ALTER ROLE %I SET search_path = %I', :'role', :'schema') \gexec
SELECT format('GRANT CONNECT ON DATABASE mmi TO %I', :'role') \gexec
SQL
	url="postgresql+psycopg://$role:$pw@$PGHOST:5432/mmi?sslmode=require"
	az keyvault secret set --vault-name "$KEY_VAULT_NAME" --name "$secret_name" --value "$url" >/dev/null
	echo "created $role and secret $secret_name"
done

admin -d mmi -c 'REVOKE ALL ON SCHEMA public FROM PUBLIC' -c 'REVOKE ALL ON DATABASE mmi FROM PUBLIC' >/dev/null
echo "done"
