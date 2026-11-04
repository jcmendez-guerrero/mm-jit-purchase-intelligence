// Blob (raw payloads) and Storage Queues (messaging). Public access off, TLS 1.2, retention lifecycle.

param name string
param location string = resourceGroup().location
param queueNames array
param rawContainerName string = 'raw-payloads'
@description('Raw payloads are deleted after this many days (spec assumption: 90).')
param rawRetentionDays int = 90

resource account 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false // managed identities only
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blob 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: account
  name: 'default'
}

resource raw 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blob
  name: rawContainerName
  properties: { publicAccess: 'None' }
}

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = {
  parent: account
  name: 'default'
}

resource queues 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = [for q in queueNames: {
  parent: queueService
  name: q
}]

resource poison 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = [for q in queueNames: {
  parent: queueService
  name: '${q}-poison'
}]

resource lifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2023-05-01' = {
  parent: account
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          name: 'expire-raw-payloads'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: { blobTypes: ['blockBlob'], prefixMatch: ['${rawContainerName}/'] }
            actions: { baseBlob: { delete: { daysAfterModificationGreaterThan: rawRetentionDays } } }
          }
        }
      ]
    }
  }
}

output accountId string = account.id
