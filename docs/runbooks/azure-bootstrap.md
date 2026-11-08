# Azure bootstrap and first deployment

One-time setup that sits outside the pipeline, then the pipeline does every later deployment. All names, ids and
secrets are placeholders here: the real values stay in the git-ignored parameter file, GitHub secrets/variables and
Key Vault (repository is public).

## 1. What is shared and what is created

Shared and **referenced, not created**: container registry, Key Vault, PostgreSQL flexible server, Log Analytics workspace.
Created by `infra/bicep/main.bicep` in the MMI resource group: Container Apps environment (consumption only), storage
account + queues, one user-assigned identity per workload, apps, jobs, alerts, budget.

## 2. Secrets to create in Key Vault (values never leave Azure)

| Secret | Created by | Read by |
|---|---|---|
| Siweb read-only token (name = `siwebReaderSecretName`) | you, once (token-rotation runbook) | connector only |
| Siweb writer token (name = `siwebWriterSecretName`) | you, only when the cost writer is enabled | cost writer only |
| `mmi-db-url-<service>` (connector, inventory, forecast, procurement, bff, costwrite) | `infra/postgres/bootstrap.sh` | that service only |
| `mmi-bff-session-secret` | `openssl rand -base64 48 \| az keyvault secret set --vault-name <kv> --name mmi-bff-session-secret --file /dev/stdin` | api-bff only |

The Key Vault must use Azure RBAC authorization (the pipeline grants Secrets User per secret). Secrets referenced in
`main.bicep` must exist before the first deployment, otherwise the role assignment step fails.

## 3. Database

Run `infra/postgres/bootstrap.sh` once from a machine that can reach the server (set the inputs described in the script).
It creates database `mmi`, one schema and role per service, and stores each connection string in Key Vault.
Schema changes afterwards are applied by the migration jobs (`<job-prefix>-mig-<service>`), which the deploy workflow starts.

## 4. GitHub (repository settings, not committed)

- Environment `production` with required reviewers.
- Secrets: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
- Variables: `AZURE_RESOURCE_GROUP`, `ACR_NAME`, `MMI_WORKLOAD`, `MMI_ENVIRONMENT`, `STORAGE_ACCOUNT_NAME`,
  `LOG_ANALYTICS_ID`, `REGISTRY_ID`, `KEY_VAULT_ID`, `POSTGRES_HOST`, `ALERT_EMAIL`, `SIWEB_BASE_URL`,
  `SIWEB_READER_SECRET_NAME`, `SIWEB_WRITER_SECRET_NAME`, optional `DEPLOY_COST_WRITER` (default `false`).
- The deploy identity needs a federated credential for `repo:<owner>/<repo>:environment:production`.

## 5. Azure permissions of the deploy identity

Contributor and a role-assignment role (for example Role Based Access Control Administrator, ideally constrained to the
Azure built-in roles used here: AcrPull, Key Vault Secrets User, Storage Blob/Queue Data roles) on the MMI resource group;
AcrPush and the role-assignment role on the registry; the role-assignment role on the Key Vault; read and list keys on the
Log Analytics workspace (the environment reads its shared key at deployment time, it is never output).

## 6. Entra ID (service-to-service tokens)

Services validate tokens with `MMI_ISSUER` / `MMI_JWKS_URL` (tenant-based, v2.0) and audience `api://mmi-<service>`.
For managed-identity calls to work, the application registration must expose those identifier URIs and app roles, assign
them to the workload identities, and issue v2 tokens (`accessTokenAcceptedVersion = 2`). Interactive sign-in through the
BFF is not implemented yet (only dev login, which production refuses), so the web UI cannot be used by people until
that feature exists.

## 7. Known limits of this deployment

- Cost writer is off by default (`deployCostWriter = false`) until T135 is verified on a non-production record.
- The daily forecast job is off (`deployForecastJob = false`): `job.py` needs a static inventory token today.
- Derived artifacts (demand, forecast, proposals) use local-file writers only; they do not survive a container restart.
- The queue roles are granted at storage-account scope.
- First deployment may need one re-run if role assignments have not propagated when the apps read their Key Vault secrets.
