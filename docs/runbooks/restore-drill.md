# Procedimiento de simulacro de copia de seguridad y restauración (Restore Drill Runbook)

## Objetivo

Verificar la capacidad de recuperación ante desastres (DR) y el cumplimiento de los objetivos de recuperación:

- **RPO (Recovery Point Objective)**: <= 24 horas (pérdida máxima admisible de datos).
- **RTO (Recovery Time Objective)**: <= 4 horas (tiempo máximo para restablecer el servicio).

## Alcance

1. Base de datos PostgreSQL (schemas: `integration`, `inventory`, `forecasting`, `procurement`, `costwrite`).
2. Almacenamiento Blob de datos brutos (cuentas de blob de sincronización y auditoría).

## Frecuencia

- Semestral en el entorno de preproducción / staging.
- Tras cambios mayores de versión o arquitectura.

## Procedimiento paso a paso

### 1. Verificación de copias de seguridad existentes

1. Verificar que los backups automáticos de Azure Database for PostgreSQL están activos:

   ```bash
   az postgres flexible-server backup list --resource-group mmi-stage-rg --server-name mmi-stage-postgres
   ```

2. Verificar el snapshot más reciente y el punto de restauración disponible.

### 2. Ejecución de la restauración en base de datos de prueba

1. Restaurar en un nuevo servidor temporal `mmi-restore-test`:

   ```bash
   az postgres flexible-server restore \
     --resource-group mmi-stage-rg \
     --name mmi-restore-test \
     --source-server mmi-stage-postgres \
     --restore-point-in-time "2026-11-04T02:00:00Z"
   ```

2. Validar integridad de esquemas y tablas:
   - Conectar con `psql` al servidor restaurado.
   - Ejecutar conteo de registros y validar hash de checkpoints:

     ```sql
     SELECT count(*) FROM integration.sync_runs;
     SELECT count(*) FROM inventory.stock_snapshots;
     SELECT count(*) FROM procurement.proposals;
     SELECT count(*) FROM costwrite.audit_log;
     ```

   - Comprobar que no hay corrupción de datos y que las restricciones de clave foránea y roles se mantienen íntegras.

### 3. Validación de consistencia con Blob Storage

1. Verificar que los URIs de payload en `integration.sync_runs` y `costwrite.audit_log` existen en el contenedor Blob de almacenamiento:

   ```bash
   az storage blob exists --account-name mmistageblobs --container-name raw --name "<run_id>.json"
   ```

### 4. Limpieza y registro de métricas

1. Eliminar el servidor temporal de prueba:

   ```bash
   az postgres flexible-server delete --resource-group mmi-stage-rg --name mmi-restore-test --yes
   ```

2. Registrar los resultados en el registro del simulacro:

| Fecha | Hora inicio | Hora fin | Tiempo total (RTO) | Punto restaurado (RPO) | ¿Éxito? | Observaciones |
|---|---|---|---|---|---|---|
| YYYY-MM-DD | HH:MM | HH:MM | X min | YYYY-MM-DD HH:MM | Sí | Restauración verificada OK |
