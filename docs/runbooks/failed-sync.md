# Guía de resolución: Fallo de sincronización Siweb (Failed Sync Runbook)

## Síntomas y alertas
- Alerta `mmi-sync-failed` o `mmi-sync-stale` recibida por correo/Teams.
- Registros en Log Analytics contienen `SYNC_FAILED` o no contienen `SYNC_OK` en las últimas 36 horas.

## Diagnóstico
1. Consultar el log del último job de sincronización:
   ```kusto
   ContainerAppConsoleLogs_CL
   | where ContainerJobName_s has "connector"
   | order by TimeGenerated desc
   | take 100
   ```
2. Identificar el motivo del fallo:
   - `reason=token_rejected` (HTTP 401): El token de Siweb ha caducado o ha sido revocado. Seguir la guía de rotación de tokens (`token-rotation.md`).
   - `reason=quota_denied`: Se superó el presupuesto por hora (500 peticiones/hora). El conector se detiene de forma segura y reanudará la siguiente noche.
   - `reason=allowlist_refused`: Se intentó acceder a una URL o método no incluido en la lista cerrada. Revisar posibles cambios de endpoint en el ERP.
   - `HTTP 500 / Timeout`: Indisponibilidad temporal del ERP Siweb360.

## Procedimiento de mitigación
1. Si el token expiró: Actualizar el secreto en Azure Key Vault y reiniciar el job.
2. Si el fallo fue por caída del ERP: Esperar al restablecimiento y disparar una ejecución manual del job fuera de horario de pico:
   ```bash
   az containerapp job execution start --name mmi-connector-job --resource-group mmi-prod-rg
   ```
3. Verificar en la base de datos que no se promovieron datos parciales:
   ```sql
   SELECT * FROM integration.sync_runs ORDER BY started_at DESC LIMIT 5;
   ```
4. Confirmar que el job finaliza con código 0 y emite `SYNC_OK`.
