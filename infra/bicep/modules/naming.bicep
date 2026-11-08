// The single place where resource names are produced (ADR-002: Terraform-ready).
// Pattern: <abbreviation>-<workload>-<env>[-<name>]. Real prefixes come from parameters, never from source.
// Plain functions (not a module) so names can be used where Bicep needs a value known at the start of the deployment.

@export()
func containerApp(workload string, env string) string => 'ca-${workload}-${env}'
@export()
func containerAppJob(workload string, env string) string => 'caj-${workload}-${env}'
@export()
func containerAppsEnvironment(workload string, env string) string => 'cae-${workload}-${env}'
@export()
@description('Storage names are 3-24 lowercase letters and digits. A non-empty override wins (an existing naming convention).')
func storageAccount(workload string, env string, override string) string => !empty(override) ? override : toLower('st${replace(workload, '-', '')}${env}')
@export()
func identityPrefix(workload string, env string) string => 'id-${workload}-${env}'
@export()
func budget(workload string, env string) string => 'budget-${workload}-${env}'
