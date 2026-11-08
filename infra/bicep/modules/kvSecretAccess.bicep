// Key Vault Secrets User, scoped to individual secrets (least privilege). Deployed at the vault's resource group scope.
// The secrets themselves are created out of band (runbook); only the grants are managed here.

param vaultName string
@description('[{ principalId, secret }]')
param grants array

// Built-in role definition id (public Azure constant, not a credential): Key Vault Secrets User.
var roleKvReader = '4633458b-17de-408a-b874-0445c86b69e6'

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' existing = { name: vaultName }
resource secrets 'Microsoft.KeyVault/vaults/secrets@2023-07-01' existing = [for g in grants: { parent: vault, name: g.secret }]

resource read 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (g, i) in grants: {
  scope: secrets[i]
  name: guid(vault.id, g.secret, g.principalId, roleKvReader)
  properties: { principalId: g.principalId, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleKvReader) }
}]
