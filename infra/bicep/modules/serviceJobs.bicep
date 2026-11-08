// Per-service jobs: a manual migration job and, where the service has a queue worker, a short cron job.
// Each runs the service image under that service's own identity and database role.

param location string = resourceGroup().location
param environmentId string
param jobPrefix string
param registryServer string
param workerCron string
@description('[{ key, dir, image, identityId, env, secrets, migrate, work }]')
param services array

module migrations 'containerAppJob.bicep' = [for s in services: if (s.migrate) {
  name: 'job-migrate-${s.key}'
  params: {
    name: '${jobPrefix}-mig-${s.key}'
    location: location
    environmentId: environmentId
    image: s.image
    identityId: s.identityId
    registryServer: registryServer
    command: ['sh', '-c', 'cd /app/services/${s.dir} && exec alembic upgrade head']
    replicaTimeoutSeconds: 900
    secrets: s.secrets
    env: s.env
  }
}]

module workers 'containerAppJob.bicep' = [for s in services: if (s.work) {
  name: 'job-worker-${s.key}'
  params: {
    name: '${jobPrefix}-wrk-${s.key}'
    location: location
    environmentId: environmentId
    image: s.image
    identityId: s.identityId
    registryServer: registryServer
    cronExpression: workerCron
    command: ['sh', '-c', 'cd /app/services/${s.dir} && exec python -m worker']
    replicaTimeoutSeconds: 600
    secrets: s.secrets
    env: s.env
  }
}]
