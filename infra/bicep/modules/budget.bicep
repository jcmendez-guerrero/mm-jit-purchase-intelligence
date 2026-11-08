// Budget alerts (T123). Principle VII: strict EUR 120/month shared ceiling, alerts at 50 %, 80 % and 100 %.
// Deployed at resource-group scope, so it tracks this resource group only. The log ingestion cap is set on the shared
// workspace by its owner (daily quota), not here: this module no longer pretends to enforce it.

param budgetName string = 'mmi-monthly-budget'
param amount int = 120
param startDate string = '2026-11-01T00:00:00Z'
param alertEmail string

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
