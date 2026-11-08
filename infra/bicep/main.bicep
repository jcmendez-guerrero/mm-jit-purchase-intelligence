// Entry point. Deploys into an existing resource group and reuses the shared platform: container registry, Key Vault,
// PostgreSQL flexible server and Log Analytics workspace are referenced by id, never created (constitution Principle V).
// Created here: the consumption-only Container Apps environment, storage + queues, one managed identity per workload,
// the apps and jobs, alerts and the budget. Images are pinned by digest. Real values live in the git-ignored parameter file.

targetScope = 'resourceGroup'

@description('Workload prefix (from the git-ignored parameter file).')
param workload string
@allowed(['dev', 'test', 'prod'])
param environment string = 'dev'
param location string = resourceGroup().location

@description('Existing storage account name to use instead of the generated one (3-24 lowercase letters and digits).')
param storageAccountName string = ''

// --- Shared platform (existing) -------------------------------------------------------------------------------------
@description('Resource id of the shared Log Analytics workspace that receives the environment logs and alerts.')
param logAnalyticsId string
@description('Alert e-mail address (git-ignored parameter file).')
param alertEmail string
@description('Resource id of the shared container registry. Workload identities get AcrPull on it.')
param registryId string
@description('Resource id of the shared Key Vault. Workload identities get Secrets User on individual secrets.')
param keyVaultId string
@description('Fully qualified host name of the shared PostgreSQL flexible server (informational; connection strings live in Key Vault).')
param postgresHost string = ''
@description('Directory (tenant) id; builds the issuer and JWKS URL used to validate service tokens.')
param entraTenantId string

// --- Siweb ----------------------------------------------------------------------------------------------------------
@description('Approved Siweb base URL.')
param siwebBaseUrl string
@description('Key Vault secret holding the read-only Siweb token (connector only).')
param siwebReaderSecretName string
@description('Key Vault secret holding the supplier-cost writer token (cost writer only).')
param siwebWriterSecretName string = ''
@description('Deploy the supplier-cost writer. Keep false until T135 has verified the PUT on a non-production record.')
param deployCostWriter bool = false

// --- Key Vault secret names (values are created out of band, see docs/runbooks/azure-bootstrap.md) -----------------------
@description('Per-service connection secrets are named "<prefix>-<service>": connector, inventory, forecast, procurement, bff, costwrite.')
param dbUrlPrefix string = 'mmi-db-url'
@description('Key Vault secret holding the BFF session signing key (32+ characters).')
param sessionSecretName string = 'mmi-bff-session-secret'

// --- Images, pinned by digest (resolved by the deploy workflow) --------------------------------------------------------
@description('Image references per workload: connector, costWriter, inventory, forecast, procurement, bff, web.')
param images object

// --- Schedules (UTC) ------------------------------------------------------------------------------------------------
@description('Siweb sync, inside the 01:00-06:00 Europe/Madrid window.')
param connectorCron string = '0 1 * * *'
@description('Queue workers run one short pass and exit, so they scale to zero between runs.')
param workerCron string = '*/10 * * * *'
param forecastCron string = '30 5 * * *'
@description('Daily forecast job. Off until job.py can call inventory-service with its managed identity.')
param deployForecastJob bool = false

@description('Alert rules query ContainerAppConsoleLogs_CL columns that only exist once the environment has written logs. Deploy the first time without alerts, then enable.')
param deployAlerts bool = true
param deployBudget bool = true
@description('First day of the budget period (the first of the current month by default).')
param budgetStartDate string = utcNow('yyyy-MM-01T00:00:00Z')

import * as naming from 'modules/naming.bicep'

var identityPrefix = naming.identityPrefix(workload, environment)
var storageName = naming.storageAccount(workload, environment, storageAccountName)
var appPrefix = naming.containerApp(workload, environment)
var jobPrefix = naming.containerAppJob(workload, environment)

var acrParts = split(registryId, '/')
var acrName = last(acrParts)
var acrScope = resourceGroup(acrParts[2], acrParts[4])
// The login server can carry a generated suffix (domain name label scope), so read it from the registry.
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = { name: acrName, scope: acrScope }
var registryServer = registry.properties.loginServer
var kvParts = split(keyVaultId, '/')
var kvName = last(kvParts)
var kvScope = resourceGroup(kvParts[2], kvParts[4])
var vaultUri = 'https://${kvName}${az.environment().suffixes.keyvaultDns}/'
var issuer = '${az.environment().authentication.loginEndpoint}${entraTenantId}/v2.0'
var jwksUrl = '${az.environment().authentication.loginEndpoint}${entraTenantId}/discovery/v2.0/keys'

// --- Identities: one per workload, so access is granted per workload ----------------------------------------------------
resource idConnector 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = { name: '${identityPrefix}-connector', location: location }
resource idInventory 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = { name: '${identityPrefix}-inventory', location: location }
resource idForecast 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = { name: '${identityPrefix}-forecast', location: location }
resource idProcurement 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = { name: '${identityPrefix}-procurement', location: location }
resource idBff 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = { name: '${identityPrefix}-bff', location: location }
resource idWeb 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = { name: '${identityPrefix}-web', location: location }
resource idCostWriter 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = { name: '${identityPrefix}-costwriter', location: location }

module registryAccess 'modules/acrPull.bicep' = {
  name: 'acr-pull'
  scope: acrScope
  params: {
    registryName: acrName
    principalIds: [
      idConnector.properties.principalId
      idInventory.properties.principalId
      idForecast.properties.principalId
      idProcurement.properties.principalId
      idBff.properties.principalId
      idWeb.properties.principalId
      idCostWriter.properties.principalId
    ]
  }
}

var secretGrants = concat(
  [
    { principalId: idConnector.properties.principalId, secret: siwebReaderSecretName }
    { principalId: idConnector.properties.principalId, secret: '${dbUrlPrefix}-connector' }
    { principalId: idInventory.properties.principalId, secret: '${dbUrlPrefix}-inventory' }
    { principalId: idForecast.properties.principalId, secret: '${dbUrlPrefix}-forecast' }
    { principalId: idProcurement.properties.principalId, secret: '${dbUrlPrefix}-procurement' }
    { principalId: idBff.properties.principalId, secret: '${dbUrlPrefix}-bff' }
    { principalId: idBff.properties.principalId, secret: sessionSecretName }
  ],
  deployCostWriter ? [
    { principalId: idCostWriter.properties.principalId, secret: siwebWriterSecretName }
    { principalId: idCostWriter.properties.principalId, secret: '${dbUrlPrefix}-costwrite' }
  ] : []
)

module secretAccess 'modules/kvSecretAccess.bicep' = {
  name: 'kv-access'
  scope: kvScope
  params: { vaultName: kvName, grants: secretGrants }
}

// --- Storage and queues ---------------------------------------------------------------------------------------------
// One queue per consumer; each gets a "<name>-poison" queue as well.
var queueNames = [
  'inventory-in'
  'forecast-in'
  'procurement-in'
  'costwriter-in'
  'bff-notifications'
]

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    name: storageName
    location: location
    queueNames: queueNames
    rawWriterPrincipalIds: [idConnector.properties.principalId]
    rawReaderPrincipalIds: [idInventory.properties.principalId, idProcurement.properties.principalId]
    seedPrincipalIds: [idForecast.properties.principalId]
  }
}

// Queue roles are granted on the account: each service consumes its own queue and sends events to the others, and the
// poison queues are written by the consumer. Per-queue scoping would need one assignment per queue and identity.
module queueRoles 'modules/queueAccess.bicep' = {
  name: 'queue-roles'
  dependsOn: [storage]
  params: {
    storageAccountName: storageName
    grants: [
      { principalId: idConnector.properties.principalId, role: 'sender' }
      { principalId: idInventory.properties.principalId, role: 'processor' }
      { principalId: idInventory.properties.principalId, role: 'sender' }
      { principalId: idForecast.properties.principalId, role: 'processor' }
      { principalId: idForecast.properties.principalId, role: 'sender' }
      { principalId: idProcurement.properties.principalId, role: 'processor' }
      { principalId: idProcurement.properties.principalId, role: 'sender' }
      { principalId: idBff.properties.principalId, role: 'processor' }
      { principalId: idBff.properties.principalId, role: 'sender' }
    ]
  }
}

// --- Container Apps environment (consumption only) -----------------------------------------------------------------------
module caEnvironment 'modules/environment.bicep' = {
  name: 'ca-environment'
  params: { name: naming.containerAppsEnvironment(workload, environment), location: location, logAnalyticsId: logAnalyticsId }
}

var internalDomain = 'internal.${caEnvironment.outputs.defaultDomain}'
var inventoryUrl = 'https://${appPrefix}-inventory.${internalDomain}'
var forecastUrl = 'https://${appPrefix}-forecast.${internalDomain}'
var procurementUrl = 'https://${appPrefix}-procurement.${internalDomain}'
var bffHost = '${appPrefix}-bff.${internalDomain}'

func dbSecret(vaultUri string, prefix string, key string, identityId string) array => [
  { name: 'db-url', keyVaultUrl: '${vaultUri}secrets/${prefix}-${key}', identity: identityId }
]

var dbEnv = [{ name: 'MMI_DATABASE_URL', secretRef: 'db-url' }]
var commonEnv = [
  { name: 'MMI_ENV', value: 'prod' }
  { name: 'MMI_QUEUE_URL', value: storage.outputs.queueEndpoint }
  { name: 'MMI_ISSUER', value: issuer }
  { name: 'MMI_JWKS_URL', value: jwksUrl }
]

var inventoryEnv = concat(commonEnv, dbEnv, [
  { name: 'MMI_BLOB_ACCOUNT_URL', value: storage.outputs.blobEndpoint }
  { name: 'MMI_BLOB_CONTAINER', value: 'raw-payloads' }
  { name: 'MMI_FORECAST_URL', value: forecastUrl }
])
var forecastEnv = concat(commonEnv, dbEnv, [
  { name: 'MMI_INVENTORY_URL', value: inventoryUrl }
  { name: 'MMI_SEED_ACCOUNT_URL', value: storage.outputs.blobEndpoint }
  { name: 'MMI_SEED_CONTAINER', value: 'seed-quarantine' }
])
var procurementEnv = concat(commonEnv, dbEnv, [
  { name: 'MMI_BLOB_ACCOUNT_URL', value: storage.outputs.blobEndpoint }
  { name: 'MMI_BLOB_CONTAINER', value: 'raw-payloads' }
  { name: 'MMI_INVENTORY_URL', value: inventoryUrl }
  { name: 'MMI_FORECAST_URL', value: forecastUrl }
])
var bffEnv = concat(commonEnv, dbEnv, [
  { name: 'MMI_SESSION_SECRET', secretRef: 'session-secret' }
  { name: 'MMI_COOKIE_SECURE', value: '1' }
  { name: 'MMI_INVENTORY_URL', value: inventoryUrl }
  { name: 'MMI_FORECAST_URL', value: forecastUrl }
  { name: 'MMI_PROCUREMENT_URL', value: procurementUrl }
])
var connectorEnv = concat(commonEnv, dbEnv, [
  { name: 'MMI_SIWEB_BASE_URL', value: siwebBaseUrl }
  { name: 'MMI_KEYVAULT_URL', value: vaultUri }
  { name: 'MMI_SIWEB_SECRET_NAME', value: siwebReaderSecretName }
  { name: 'MMI_BLOB_ACCOUNT_URL', value: storage.outputs.blobEndpoint }
  { name: 'MMI_BLOB_CONTAINER', value: 'raw-payloads' }
])

var bffSecrets = concat(
  dbSecret(vaultUri, dbUrlPrefix, 'bff', idBff.id),
  [{ name: 'session-secret', keyVaultUrl: '${vaultUri}secrets/${sessionSecretName}', identity: idBff.id }]
)

// Roll-out order: access first, so the first revision can read its secrets and pull its image.
module inventoryApp 'modules/containerApp.bicep' = {
  name: 'app-inventory'
  dependsOn: [registryAccess, secretAccess]
  params: {
    name: '${appPrefix}-inventory'
    location: location
    environmentId: caEnvironment.outputs.id
    image: images.inventory
    identityId: idInventory.id
    registryServer: registryServer
    secrets: dbSecret(vaultUri, dbUrlPrefix, 'inventory', idInventory.id)
    env: inventoryEnv
  }
}

module forecastApp 'modules/containerApp.bicep' = {
  name: 'app-forecast'
  dependsOn: [registryAccess, secretAccess]
  params: {
    name: '${appPrefix}-forecast'
    location: location
    environmentId: caEnvironment.outputs.id
    image: images.forecast
    identityId: idForecast.id
    registryServer: registryServer
    secrets: dbSecret(vaultUri, dbUrlPrefix, 'forecast', idForecast.id)
    env: forecastEnv
  }
}

module procurementApp 'modules/containerApp.bicep' = {
  name: 'app-procurement'
  dependsOn: [registryAccess, secretAccess]
  params: {
    name: '${appPrefix}-procurement'
    location: location
    environmentId: caEnvironment.outputs.id
    image: images.procurement
    identityId: idProcurement.id
    registryServer: registryServer
    secrets: dbSecret(vaultUri, dbUrlPrefix, 'procurement', idProcurement.id)
    env: procurementEnv
  }
}

module bffApp 'modules/containerApp.bicep' = {
  name: 'app-bff'
  dependsOn: [registryAccess, secretAccess]
  params: {
    name: '${appPrefix}-bff'
    location: location
    environmentId: caEnvironment.outputs.id
    image: images.bff
    identityId: idBff.id
    registryServer: registryServer
    secrets: bffSecrets
    env: bffEnv
  }
}

// The only public endpoint. nginx serves the SPA and proxies /api to the BFF over the internal https name.
module webApp 'modules/containerApp.bicep' = {
  name: 'app-web'
  dependsOn: [registryAccess]
  params: {
    name: '${appPrefix}-web'
    location: location
    environmentId: caEnvironment.outputs.id
    image: images.web
    identityId: idWeb.id
    registryServer: registryServer
    targetPort: 8080
    readinessPath: '/healthz'
    ingressExternal: true
    env: [
      { name: 'API_BFF_URL', value: 'https://${bffHost}' }
      { name: 'API_BFF_HOST', value: bffHost }
    ]
  }
}

// --- Jobs -----------------------------------------------------------------------------------------------------------------

// Siweb connector: read-only, GET allowlist, runs in the night window. The job name is what the alerts watch.
module connectorJob 'modules/containerAppJob.bicep' = {
  name: 'job-connector'
  dependsOn: [registryAccess, secretAccess]
  params: {
    name: jobPrefix
    location: location
    environmentId: caEnvironment.outputs.id
    image: images.connector
    identityId: idConnector.id
    registryServer: registryServer
    cronExpression: connectorCron
    command: ['python', '-m', 'job', 'all']
    replicaTimeoutSeconds: 3600
    secrets: dbSecret(vaultUri, dbUrlPrefix, 'connector', idConnector.id)
    env: connectorEnv
  }
}

// Database migrations (manual jobs, started by the deploy workflow before the apps roll out) and queue workers
// (one short pass per run, scale to zero in between). Defined in one module so the per-service lists can carry
// values that are only known during the deployment.
var serviceJobs = [
  { key: 'connector', dir: 'siweb-connector', image: images.connector, identityId: idConnector.id, env: connectorEnv, secrets: dbSecret(vaultUri, dbUrlPrefix, 'connector', idConnector.id), migrate: true, work: false }
  { key: 'inventory', dir: 'inventory-service', image: images.inventory, identityId: idInventory.id, env: inventoryEnv, secrets: dbSecret(vaultUri, dbUrlPrefix, 'inventory', idInventory.id), migrate: true, work: true }
  { key: 'forecast', dir: 'forecast-service', image: images.forecast, identityId: idForecast.id, env: forecastEnv, secrets: dbSecret(vaultUri, dbUrlPrefix, 'forecast', idForecast.id), migrate: true, work: true }
  { key: 'procurement', dir: 'procurement-service', image: images.procurement, identityId: idProcurement.id, env: procurementEnv, secrets: dbSecret(vaultUri, dbUrlPrefix, 'procurement', idProcurement.id), migrate: true, work: true }
  { key: 'bff', dir: 'api-bff', image: images.bff, identityId: idBff.id, env: bffEnv, secrets: bffSecrets, migrate: true, work: true }
  { key: 'costwrite', dir: 'siweb-cost-writer', image: deployCostWriter ? images.costWriter : images.connector, identityId: idCostWriter.id, env: concat(commonEnv, dbEnv), secrets: dbSecret(vaultUri, dbUrlPrefix, 'costwrite', idCostWriter.id), migrate: deployCostWriter, work: false }
]

module serviceJobModule 'modules/serviceJobs.bicep' = {
  name: 'service-jobs'
  dependsOn: [registryAccess, secretAccess]
  params: {
    location: location
    environmentId: caEnvironment.outputs.id
    jobPrefix: jobPrefix
    registryServer: registryServer
    workerCron: workerCron
    services: serviceJobs
  }
}

module forecastJob 'modules/containerAppJob.bicep' = if (deployForecastJob) {
  name: 'forecast-job'
  dependsOn: [registryAccess, secretAccess]
  params: {
    name: '${jobPrefix}-forecast'
    location: location
    environmentId: caEnvironment.outputs.id
    image: images.forecast
    identityId: idForecast.id
    registryServer: registryServer
    cronExpression: forecastCron
    command: ['sh', '-c', 'cd /app/services/forecast-service && exec python -m job']
    replicaTimeoutSeconds: 1800
    secrets: dbSecret(vaultUri, dbUrlPrefix, 'forecast', idForecast.id)
    env: forecastEnv
  }
}

// Supplier-cost writer (the single permitted ERP write). Off until T135 is verified on a non-production record.
module costWriter 'modules/costWriter.bicep' = if (deployCostWriter) {
  name: 'cost-writer'
  dependsOn: [registryAccess, secretAccess, queueRoles]
  params: {
    name: '${jobPrefix}-costwriter'
    location: location
    environmentId: caEnvironment.outputs.id
    image: images.costWriter
    identityId: idCostWriter.id
    identityPrincipalId: idCostWriter.properties.principalId
    registryServer: registryServer
    vaultUri: vaultUri
    writerSecretName: siwebWriterSecretName
    databaseUrlSecretName: '${dbUrlPrefix}-costwrite'
    storageAccountName: storageName
    siwebBaseUrl: siwebBaseUrl
    procurementUrl: procurementUrl
  }
}

// --- Alerts and budget ----------------------------------------------------------------------------------------------------
module alerts 'modules/alerts.bicep' = if (deployAlerts) {
  name: 'alerts'
  params: {
    namePrefix: 'alert-${workload}-${environment}'
    location: location
    logAnalyticsId: logAnalyticsId
    connectorJobName: jobPrefix
    alertEmail: alertEmail
  }
}

module budget 'modules/budget.bicep' = if (deployBudget) {
  name: 'budget'
  params: { budgetName: naming.budget(workload, environment), alertEmail: alertEmail, startDate: budgetStartDate }
}

output storageAccountId string = storage.outputs.accountId
@description('Set as MMI_SEED_ACCOUNT_URL on forecast-service and its worker; without it production refuses to start the import API.')
output seedAccountUrl string = storage.outputs.blobEndpoint
output webUrl string = 'https://${webApp.outputs.fqdn}'
@description('Resource names the deploy workflow uses to run migrations and roll out new digests.')
output names object = {
  apps: { inventory: '${appPrefix}-inventory', forecast: '${appPrefix}-forecast', procurement: '${appPrefix}-procurement', bff: '${appPrefix}-bff', web: '${appPrefix}-web' }
  jobPrefix: jobPrefix
  postgresHost: postgresHost
}
