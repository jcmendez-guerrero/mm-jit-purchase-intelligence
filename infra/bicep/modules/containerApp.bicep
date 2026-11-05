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
            { type: 'Readiness', httpGet: { path: '/readyz', port: targetPort } }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: maxReplicas }
    }
  }
}

output id string = app.id
