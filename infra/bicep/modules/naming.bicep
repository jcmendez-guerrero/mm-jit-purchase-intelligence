// The single place where resource names are produced (ADR-002: Terraform-ready).
// Pattern: <abbreviation>-<workload>-<env>[-<name>]. Real prefixes come from parameters, never from source.

@description('Short workload prefix, supplied by the (git-ignored) parameter file.')
param workload string

@allowed(['dev', 'test', 'prod'])
param environment string

output containerApp string = 'ca-${workload}-${environment}'
output containerAppJob string = 'caj-${workload}-${environment}'
output storageAccount string = toLower('st${replace(workload, '-', '')}${environment}')
output logAnalytics string = 'log-${workload}-${environment}'
output identityPrefix string = 'id-${workload}-${environment}'
output budget string = 'budget-${workload}-${environment}'
