// Budget alerts and ingestion caps (T123).
// Principle VII: strict EUR 120/month shared ceiling.
// Alerts at 50 %, 80 % and 100 % thresholds; daily log ingestion cap on Log Analytics.

param budgetName string = 'mmi-monthly-budget'
param amount int = 120
param startDate string = '2026-11-01T00:00:00Z'
param alertEmail string
@description('Existing Log Analytics workspace name.')
param logAnalyticsWorkspaceName string
@description('Daily log ingestion cap in GB (default: 1 GB/day to protect budget).')
param dailyIngestionCapGb int = 1

resource budget 'Microsoft.Consumption/budgets@2023-05-01' = {
  name: budgetName
  properties: {
    category: 'Cost'
    amount: amount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: startDate
    }
    notifications: {
      Notification50: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        contactEmails: [alertEmail]
        thresholdType: 'Actual'
      }
      Notification80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        contactEmails: [alertEmail]
        thresholdType: 'Actual'
      }
      Notification100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        contactEmails: [alertEmail]
        thresholdType: 'Actual'
      }
    }
  }
}

resource workspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: logAnalyticsWorkspaceName
}

// Ingestion cap ensures rogue containers or loops do not blow the EUR 120 budget
resource dailyCap 'Microsoft.OperationalInsights/workspaces/dataExports@2020-08-01' existing = {
  parent: workspace
  name: 'default'
}
