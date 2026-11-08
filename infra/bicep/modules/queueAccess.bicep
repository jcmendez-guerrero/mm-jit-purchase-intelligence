// Queue data-plane roles for workload identities on the MMI storage account.

param storageAccountName string
@description('[{ principalId, role }] where role is "processor" or "sender".')
param grants array

var roles = {
  processor: '8a0f0c08-91a1-4084-bc3d-661d67233fed' // Storage Queue Data Message Processor
  sender: 'c6a89b2d-59bc-44d0-9896-0f6e12d7b80a'    // Storage Queue Data Message Sender
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = { name: storageAccountName }

resource assign 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for g in grants: {
  scope: storage
  name: guid(storage.id, g.principalId, roles[g.role])
  properties: { principalId: g.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles[g.role]) }
}]
