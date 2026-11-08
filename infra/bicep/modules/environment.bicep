// Consumption-only Container Apps environment (no workload profiles, no dedicated plan: scales to zero).
// Logs go to the existing shared Log Analytics workspace. The shared key is read at deployment time
// and never emitted as an output or stored in source.

param name string
param location string = resourceGroup().location
@description('Resource id of the existing shared Log Analytics workspace.')
param logAnalyticsId string

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: name
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: reference(logAnalyticsId, '2022-10-01').customerId
        sharedKey: listKeys(logAnalyticsId, '2022-10-01').primarySharedKey
      }
    }
    zoneRedundant: false
  }
}

output id string = env.id
output defaultDomain string = env.properties.defaultDomain
