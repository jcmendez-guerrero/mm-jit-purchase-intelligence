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

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: { name: names.outputs.storageAccount, location: location, queueNames: queueNames }
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

output storageAccountId string = storage.outputs.accountId
