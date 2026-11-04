// Alerts for the Siweb connector (T046). T122 extends this file with freshness-by-metric, queue age,
// cost-write outcomes, auth denials and approval anomalies.
// Rules read the job's console logs. The job writes stable markers (SYNC_FAILED, QUOTA_DENIED,
// ALLOWLIST_REFUSED, SYNC_OK) so alert queries do not depend on free-text wording.

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
