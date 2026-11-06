// Entry point. Skeleton: wires naming + storage; compute, alerts, budget and the writer identity are
// added by tasks T045, T046, T102, T122-T124. Existing shared resources are referenced, not created.

targetScope = 'resourceGroup'

@description('Workload prefix (from the git-ignored parameter file).')
param workload string
@allowed(['dev', 'test', 'prod'])
param environment string = 'dev'
param location string = resourceGroup().location

module names 'modules/naming.bicep' = {
  name: 'naming'
  params: { workload: workload, environment: environment }
}

// One queue per consumer; each gets a "<name>-poison" queue as well.
var queueNames = [
  'inventory-in'
  'forecast-in'
  'procurement-in'
  'costwriter-in'
  'bff-notifications'
]

@description('Managed identity that may write raw payloads (the connector).')
param connectorPrincipalIds array = []
@description('Managed identities that may only read raw payloads (inventory-service, procurement-service).')
param payloadReaderPrincipalIds array = []
@description('Managed identity of forecast-service, the only reader and writer of uploaded seed files.')
param seedFilePrincipalIds array = []

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    name: names.outputs.storageAccount
    location: location
    queueNames: queueNames
    rawWriterPrincipalIds: connectorPrincipalIds
    rawReaderPrincipalIds: payloadReaderPrincipalIds
    seedPrincipalIds: seedFilePrincipalIds
  }
}

@description('Existing shared Log Analytics workspace (referenced, not created).')
param logAnalyticsId string = ''
@description('Alert e-mail address (git-ignored parameter file).')
param alertEmail string = ''

// Alerts are deployed only when the shared workspace and a recipient are configured.
module alerts 'modules/alerts.bicep' = if (!empty(logAnalyticsId) && !empty(alertEmail)) {
  name: 'alerts'
  params: {
    namePrefix: 'alert-${workload}-${environment}'
    location: location
    logAnalyticsId: logAnalyticsId
    connectorJobName: names.outputs.containerAppJob
    alertEmail: alertEmail
  }
}

@description('Container Apps environment id (existing shared environment).')
param environmentId string = ''
@description('Forecast image, pinned by digest.')
param forecastImage string = ''
@description('User-assigned identity id for the forecast job.')
param forecastIdentityId string = ''
@description('Cron schedule (UTC) for the forecast job, after the night sync window.')
param forecastCron string = '30 5 * * *'

// Forecast job (T069): scale-to-zero, one replica, runs after the Siweb sync window.
module forecastJob 'modules/containerAppJob.bicep' = if (!empty(environmentId) && !empty(forecastImage) && !empty(forecastIdentityId)) {
  name: 'forecast-job'
  params: {
    name: '${names.outputs.containerAppJob}-forecast'
    location: location
    environmentId: environmentId
    image: forecastImage
    identityId: forecastIdentityId
    cronExpression: forecastCron
    command: ['python', '-m', 'job']
    replicaTimeoutSeconds: 1800
  }
}

output storageAccountId string = storage.outputs.accountId
