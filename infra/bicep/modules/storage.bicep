// Blob (raw payloads) and Storage Queues (messaging). Public access off, TLS 1.2, retention lifecycle.
// Raw payloads are immutable (time-based retention, WORM) until their retention ends, then deleted (FR-008). Only the
// connector can write them; inventory-service and procurement-service can only read them.

param name string
param location string = resourceGroup().location
param queueNames array
param rawContainerName string = 'raw-payloads'
@description('Raw payloads are deleted after this many days (spec assumption: 90).')
param rawRetentionDays int = 90
@description('Blobs cannot be modified or deleted for this many days after creation. One day below the retention so the purge job and the lifecycle rule can delete a payload the moment it expires.')
param rawImmutableDays int = 89
@description('Principal ids (managed identities) that may write raw payloads: the connector only.')
param rawWriterPrincipalIds array = []
@description('Principal ids that may read raw payloads: inventory-service and procurement-service.')
param rawReaderPrincipalIds array = []
@description('Private container for uploaded predictive seed files (MMI 002, FR-020). Encrypted at rest by the storage service; never public.')
param seedContainerName string = 'seed-quarantine'
@description('Seed files are deleted after this many days (retention policy, ADR-020).')
param seedRetentionDays int = 30
@description('Principal ids that may read and write seed files: forecast-service only.')
param seedPrincipalIds array = []

var blobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'   // Storage Blob Data Contributor
var blobDataReader = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'        // Storage Blob Data Reader

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

resource rawImmutability 'Microsoft.Storage/storageAccounts/blobServices/containers/immutabilityPolicies@2023-05-01' = {
  parent: raw
  name: 'default'
  properties: {
    immutabilityPeriodSinceCreationInDays: rawImmutableDays
    allowProtectedAppendWrites: false
  }
}

resource seed 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blob
  name: seedContainerName
  properties: { publicAccess: 'None' }
}

resource seedAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for id in seedPrincipalIds: {
  scope: seed
  name: guid(seed.id, id, blobDataContributor)
  properties: { principalId: id, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributor) }
}]

resource rawWriters 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for id in rawWriterPrincipalIds: {
  scope: raw
  name: guid(raw.id, id, blobDataContributor)
  properties: { principalId: id, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributor) }
}]

resource rawReaders 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for id in rawReaderPrincipalIds: {
  scope: raw
  name: guid(raw.id, id, blobDataReader)
  properties: { principalId: id, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataReader) }
}]

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
        {
          name: 'expire-seed-files'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: { blobTypes: ['blockBlob'], prefixMatch: ['${seedContainerName}/'] }
            actions: { baseBlob: { delete: { daysAfterModificationGreaterThan: seedRetentionDays } } }
          }
        }
      ]
    }
  }
}

output accountId string = account.id
@description('Blob endpoint to give forecast-service as MMI_SEED_ACCOUNT_URL (container seed-quarantine, access by managed identity only).')
output blobEndpoint string = account.properties.primaryEndpoints.blob
