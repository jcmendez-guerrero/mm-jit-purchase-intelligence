// Alerts for the Siweb connector and platform services (T046, T122).
// Rules read console logs for stable markers so queries do not depend on free-text wording.
// Evaluation windows are <= 1 hour (SC-013).

param location string = resourceGroup().location
param namePrefix string
@description('Existing Log Analytics workspace that receives the Container Apps environment logs.')
param logAnalyticsId string
@description('Name of the connector job as it appears in the logs.')
param connectorJobName string
@description('Alert e-mail address, supplied by the git-ignored parameter file.')
param alertEmail string
@description('A scheduled night job that has not completed for this long is stale.')
param staleAfterHours int = 36

var logTable = 'ContainerAppConsoleLogs_CL'
var scope = [logAnalyticsId]

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${namePrefix}-ag'
  location: 'global'
  properties: {
    groupShortName: 'mmi-alerts'
    enabled: true
    emailReceivers: [{ name: 'buyer-admin', emailAddress: alertEmail, useCommonAlertSchema: true }]
  }
}

var rules = [
  {
    key: 'sync-failed'
    description: 'A Siweb sync run failed (rejected token or aborted run). Data is stale until fixed.'
    severity: 1
    query: '${logTable} | where ContainerJobName_s == "${connectorJobName}" | where Log_s has "SYNC_FAILED"'
    evaluationFrequency: 'PT15M'
    windowSize: 'PT15M'
  }
  {
    key: 'quota-denied'
    description: 'The connector hit its hourly request budget (shared Siweb limit). Expected during backfill, not in steady state.'
    severity: 3
    query: '${logTable} | where ContainerJobName_s == "${connectorJobName}" | where Log_s has "QUOTA_DENIED"'
    evaluationFrequency: 'PT1H'
    windowSize: 'PT1H'
  }
  {
    key: 'allowlist-refused'
    description: 'The connector refused an outbound request outside its allowlist (possible misconfiguration or compromise).'
    severity: 0
    query: '${logTable} | where ContainerJobName_s == "${connectorJobName}" | where Log_s has "ALLOWLIST_REFUSED"'
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
  }
  {
    key: 'queue-poison'
    description: 'A message was rejected and sent to a poison queue (deserialization, checksum, or freshness failure).'
    severity: 1
    query: '${logTable} | where Log_s has "POISON_MESSAGE" or Log_s has "poison_queue"'
    evaluationFrequency: 'PT15M'
    windowSize: 'PT15M'
  }
  {
    key: 'cost-write-failed'
    description: 'A supplier cost write-back to Siweb failed or was rejected by ERP allowlist/validation.'
    severity: 1
    query: '${logTable} | where Log_s has "COST_WRITE_FAILED"'
    evaluationFrequency: 'PT15M'
    windowSize: 'PT15M'
  }
  {
    key: 'auth-denials'
    description: 'Repeated unauthorized access attempts, missing permissions, or invalid tokens detected at BFF/services.'
    severity: 2
    query: '${logTable} | where Log_s has "Access refused" or Log_s has "AUTH_DENIED"'
    evaluationFrequency: 'PT15M'
    windowSize: 'PT15M'
  }
  {
    key: 'unmatched-writes'
    description: 'An ERP supplier-cost write completed but read-after-write verification did not match the expected cost.'
    severity: 0
    query: '${logTable} | where Log_s has "UNMATCHED_WRITE" or Log_s has "write_mismatch"'
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
  }
  {
    key: 'suspicious-approvals'
    description: 'An approval anomaly was attempted (e.g. self-approval attempt or approval with stale MFA).'
    severity: 1
    query: '${logTable} | where Log_s has "forbidden_mfa_stale" or Log_s has "self_approval_refused" or Log_s has "SUSPICIOUS_APPROVAL"'
    evaluationFrequency: 'PT15M'
    windowSize: 'PT15M'
  }
  {
    key: 'import-failed'
    description: 'A background predictive-data import failed. The dataset stays unchanged; an admin can re-run it from the status page.'
    severity: 2
    query: '${logTable} | where Log_s has "IMPORT_FAILED"'
    evaluationFrequency: 'PT15M'
    windowSize: 'PT15M'
  }
  {
    key: 'upload-rejected'
    description: 'Several uploads were refused in a short time (size, type, decompression or row limits): possible misuse or a broken template.'
    severity: 3
    query: '${logTable} | where Log_s has "UPLOAD_REJECTED" | summarize n = count() | where n >= 5'
    evaluationFrequency: 'PT15M'
    windowSize: 'PT15M'
  }
  {
    key: 'admin-alert-opened'
    description: 'The administration console opened an alert (stale source, failed job, old backup, budget, role-mirror lag). The marker carries codes only; details are in the console.'
    severity: 2
    query: '${logTable} | where Log_s has "ADMIN_ALERT_OPENED"'
    evaluationFrequency: 'PT15M'
    windowSize: 'PT15M'
  }
  {
    key: 'role-mirror-lag'
    description: 'A role change has not reached procurement for 15 minutes or failed; permissions may differ between the console and the service.'
    severity: 1
    query: '${logTable} | where Log_s has "ROLE_MIRROR_LAG"'
    evaluationFrequency: 'PT15M'
    windowSize: 'PT15M'
  }
]

resource logRules 'Microsoft.Insights/scheduledQueryRules@2022-06-15' = [for r in rules: {
  name: '${namePrefix}-${r.key}'
  location: location
  properties: {
    displayName: '${namePrefix}-${r.key}'
    description: r.description
    severity: r.severity
    enabled: true
    scopes: scope
    evaluationFrequency: r.evaluationFrequency
    windowSize: r.windowSize
    criteria: {
      allOf: [
        { query: r.query, timeAggregation: 'Count', operator: 'GreaterThan', threshold: 0, failingPeriods: { numberOfEvaluationPeriods: 1, minFailingPeriodsToAlert: 1 } }
      ]
    }
    actions: { actionGroups: [actionGroup.id] }
  }
}]

// Freshness: alert when no successful sync was logged recently. Missing logs also fire, because the
// condition is "fewer than one SYNC_OK in the window".
resource staleRule 'Microsoft.Insights/scheduledQueryRules@2022-06-15' = {
  name: '${namePrefix}-sync-stale'
  location: location
  properties: {
    displayName: '${namePrefix}-sync-stale'
    description: 'No successful Siweb sync in the last ${staleAfterHours} hours.'
    severity: 2
    enabled: true
    scopes: scope
    evaluationFrequency: 'PT1H'
    windowSize: 'PT${staleAfterHours}H'
    criteria: {
      allOf: [
        {
          query: '${logTable} | where ContainerJobName_s == "${connectorJobName}" | where Log_s has "SYNC_OK"'
          timeAggregation: 'Count'
          operator: 'LessThan'
          threshold: 1
          failingPeriods: { numberOfEvaluationPeriods: 1, minFailingPeriodsToAlert: 1 }
        }
      ]
    }
    actions: { actionGroups: [actionGroup.id] }
  }
}

output actionGroupId string = actionGroup.id
