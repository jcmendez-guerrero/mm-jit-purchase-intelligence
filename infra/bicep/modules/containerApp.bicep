// One Container App, scale-to-zero with a replica cap (constitution Principle V).
// Reuses the existing Container Apps environment and registry (passed in by id); creates neither.

param name string
param location string = resourceGroup().location
param environmentId string
param image string // pinned by digest: registry/repo@sha256:...
param identityId string // user-assigned managed identity for this workload only
param targetPort int = 8000
param maxReplicas int = 1
param cpu string = '0.25'
param memory string = '0.5Gi'
param env array = [] // [{name, value}] or [{name, secretRef}]; Key Vault references only for secrets
param ingressExternal bool = false
param readinessPath string = '/readyz' // the SPA container only serves /healthz
@description('Registry login server (shared ACR). Pulled with the workload identity (AcrPull), never with a password.')
param registryServer string = ''
@description('Container App secrets: [{ name, keyVaultUrl, identity }]. Values stay in Key Vault.')
param secrets array = []

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      registries: empty(registryServer) ? [] : [{ server: registryServer, identity: identityId }]
      secrets: secrets
      ingress: {
        external: ingressExternal
        targetPort: targetPort
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: name
          image: image
          env: env
          resources: { cpu: json(cpu), memory: memory }
          probes: [
            { type: 'Liveness', httpGet: { path: '/healthz', port: targetPort } }
            { type: 'Readiness', httpGet: { path: readinessPath, port: targetPort } }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: maxReplicas }
    }
  }
}

output id string = app.id
output fqdn string = app.properties.configuration.ingress.fqdn
