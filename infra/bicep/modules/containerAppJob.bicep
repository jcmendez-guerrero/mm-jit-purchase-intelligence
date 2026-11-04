// One scheduled/manual Container Apps Job. Parallelism 1 and a replica timeout keep cost bounded.

param name string
param location string = resourceGroup().location
param environmentId string
param image string // pinned by digest
param identityId string
param cronExpression string = '' // empty => manual trigger only
param replicaTimeoutSeconds int = 3600
param env array = []
param command array = [] // overrides the image CMD, e.g. ['python', '-m', 'job', 'all']

resource job 'Microsoft.App/jobs@2024-03-01' = {
  name: name
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: empty(cronExpression) ? 'Manual' : 'Schedule'
      replicaTimeout: replicaTimeoutSeconds
      replicaRetryLimit: 1
      manualTriggerConfig: empty(cronExpression) ? { parallelism: 1, replicaCompletionCount: 1 } : null
      scheduleTriggerConfig: empty(cronExpression) ? null : { cronExpression: cronExpression, parallelism: 1, replicaCompletionCount: 1 }
    }
    template: {
      containers: [
        { name: name, image: image, command: empty(command) ? null : command, env: env, resources: { cpu: json('0.5'), memory: '1Gi' } }
      ]
    }
  }
}

output id string = job.id
