// AcrPull on the shared registry for workload identities. Deployed at the registry's resource group scope.

param registryName string
param principalIds array

var acrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d' // AcrPull

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = { name: registryName }

resource pull 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for id in principalIds: {
  scope: registry
  name: guid(registry.id, id, acrPull)
  properties: { principalId: id, principalType: 'ServicePrincipal', roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPull) }
}]
