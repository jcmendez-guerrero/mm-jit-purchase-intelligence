// T102: the Siweb cost writer runs under its own identity, separate from the read-only connector (constitution Principle I).
// The identity can read only its own Key Vault secret and the one queue it consumes; the connector identity has no access to
// either. Egress to the ERP is limited in the application (closed allowlist: one host, one PUT, one read). A network-level
// FQDN egress rule would need Azure Firewall, which does not fit the shared EUR 120/month budget: recorded as open in ADR-006.

param name string
param location string = resourceGroup().location
param environmentId string
@description('Image pinned by digest.')
param image string
@description('Existing Key Vault holding the writer secret (referenced, not created).')
param keyVaultName string
@description('Name of the secret only the writer may read.')
param writerSecretName string
@description('Existing storage account that hosts the queues.')
param storageAccountName string
@description('Approved Siweb base URL, from the git-ignored parameter file.')
param siwebBaseUrl string
param procurementUrl string
param databaseUrlSecretName string
@description('Poll interval; the job exits when the queue is empty, so it scales to zero.')
param cronExpression string = '*/5 * * * *'

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${name}-id'
  location: location
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' existing = { name: keyVaultName }
resource secret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = { parent: vault, name: writerSecretName }
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = { name: storageAccountName }
resource queueSvc 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' existing = { parent: storage, name: 'default' }
resource queue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' existing = { parent: queueSvc, name: 'costwriter-in' }

var kvSecretsUser = '4633458b-17de-408a-b874-0151c9ac4a8d'          // Key Vault Secrets User
var queueProcessor = '8a0f0c08-91a1-4084-bc3d-661d67233fed'         // Storage Queue Data Message Processor
var queueSender = 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80c'            // Storage Queue Data Message Sender (outcome events go to another queue)

resource readSecret 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: secret
  name: guid(secret.id, identity.id, kvSecretsUser)
  properties: { principalId: identity.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUser) }
}

resource consumeQueue 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: queue
  name: guid(queue.id, identity.id, queueProcessor)
  properties: { principalId: identity.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', queueProcessor) }
}

resource sendOutcomes 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, identity.id, queueSender)
  properties: { principalId: identity.properties.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', queueSender) }
}

module job 'containerAppJob.bicep' = {
  name: '${name}-job'
  params: {
    name: name
    location: location
    environmentId: environmentId
    image: image
    identityId: identity.id
    cronExpression: cronExpression
    command: ['python', '-m', 'job']
    replicaTimeoutSeconds: 900
    env: [
      { name: 'MMI_SIWEB_BASE_URL', value: siwebBaseUrl }
      { name: 'MMI_PROCUREMENT_URL', value: procurementUrl }
      { name: 'MMI_KEYVAULT_URL', value: vault.properties.vaultUri }
      { name: 'MMI_SIWEB_WRITER_SECRET', value: writerSecretName }
      { name: 'MMI_QUEUE_URL', value: storage.properties.primaryEndpoints.queue }
      { name: 'MMI_DATABASE_URL_SECRET', value: databaseUrlSecretName }
    ]
  }
}

output identityPrincipalId string = identity.properties.principalId
