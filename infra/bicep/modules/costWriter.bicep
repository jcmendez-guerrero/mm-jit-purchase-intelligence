// T102: the Siweb cost writer runs under its own identity, separate from the read-only connector (constitution Principle I).
// The identity (created in main.bicep) can read only its own Key Vault secrets and the queue it consumes; the connector identity
// has no access to either. Egress to the ERP is limited in the application (closed allowlist: one host, one PUT, one read). A
// network-level FQDN egress rule would need Azure Firewall, which does not fit the shared EUR 120/month budget (ADR-006).
// Deployed only when deployCostWriter is true, i.e. after T135 verified the supplier-cost PUT on a non-production record.

param name string
param location string = resourceGroup().location
param environmentId string
@description('Image pinned by digest.')
param image string
param identityId string
param identityPrincipalId string
param registryServer string
@description('Vault URI of the existing Key Vault (referenced, not created).')
param vaultUri string
@description('Name of the secret only the writer may read.')
param writerSecretName string
@description('Name of the Key Vault secret holding the writer role connection string.')
param databaseUrlSecretName string
@description('Existing storage account that hosts the queues.')
param storageAccountName string
@description('Approved Siweb base URL, from the git-ignored parameter file.')
param siwebBaseUrl string
param procurementUrl string
@description('Poll interval; the job exits when the queue is empty, so it scales to zero.')
param cronExpression string = '*/5 * * * *'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = { name: storageAccountName }
resource queueSvc 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' existing = { parent: storage, name: 'default' }
resource queue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' existing = { parent: queueSvc, name: 'costwriter-in' }

var queueProcessor = '8a0f0c08-91a1-4084-bc3d-661d67233fed'         // Storage Queue Data Message Processor
var queueSender = 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a'            // Storage Queue Data Message Sender (outcome events go to another queue)

resource consumeQueue 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: queue
  name: guid(queue.id, identityPrincipalId, queueProcessor)
  properties: { principalId: identityPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', queueProcessor) }
}

resource sendOutcomes 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, identityPrincipalId, queueSender)
  properties: { principalId: identityPrincipalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', queueSender) }
}

module job 'containerAppJob.bicep' = {
  name: '${name}-job'
  dependsOn: [consumeQueue, sendOutcomes]
  params: {
    name: name
    location: location
    environmentId: environmentId
    image: image
    identityId: identityId
    registryServer: registryServer
    cronExpression: cronExpression
    command: ['python', '-m', 'job']
    replicaTimeoutSeconds: 900
    secrets: [{ name: 'db-url', keyVaultUrl: '${vaultUri}secrets/${databaseUrlSecretName}', identity: identityId }]
    env: [
      { name: 'MMI_ENV', value: 'prod' }
      { name: 'MMI_SIWEB_BASE_URL', value: siwebBaseUrl }
      { name: 'MMI_PROCUREMENT_URL', value: procurementUrl }
      { name: 'MMI_KEYVAULT_URL', value: vaultUri }
      { name: 'MMI_SIWEB_WRITER_SECRET', value: writerSecretName }
      { name: 'MMI_QUEUE_URL', value: storage.properties.primaryEndpoints.queue }
      { name: 'MMI_DATABASE_URL', secretRef: 'db-url' }
    ]
  }
}
