# Procedimiento de simulacro de alertas (Alert Drill Runbook)

## Objetivo

Verificar en el entorno de preproducción/pruebas que las alertas se disparan ante fallos inducidos dentro del límite objetivo de 1 hora (SC-013).

## Frecuencia

- Antes del paso a producción (Gate 0 release checklist).
- Trimestralmente durante la fase de operación.

## Requisitos previos

- Despliegue de infraestructura con `infra/bicep/modules/alerts.bicep`.
- Action Group configurado con dirección de correo o canal del equipo.
- Acceso a Azure Monitor / Log Analytics del entorno de pruebas.

## Pasos del simulacro

### 1. Inyección de fallo de sincronización (`SYNC_FAILED`)

1. En el Container App Job de sincronización (`siweb-connector`), configurar temporalmente una credencial inválida en `MMI_SIWEB_TOKEN`:

   ```bash
   az containerapp job execution start --name mmi-connector-job --resource-group mmi-stage-rg
   ```

2. Observar la salida en Log Analytics:

   ```kusto
   ContainerAppConsoleLogs_CL
   | where ContainerJobName_s has "connector"
   | where Log_s has "SYNC_FAILED"
   ```

3. Registrar la hora de inicio y la hora de recepción del correo de alerta.
   - **Objetivo**: Tiempo hasta la alerta <= 15 minutos (ventana de evaluación: `PT15M`).

### 2. Inyección de mensaje envenenado (`POISON_MESSAGE`)

1. Insertar un mensaje malformado en la cola `procurement-events`:

   ```bash
   az storage message put --queue-name procurement-events --content "{invalid-json"
   ```

2. El worker consumidor detectará el fallo y moverá el mensaje a `procurement-events-poison`.
3. Verificar en Log Analytics:

   ```kusto
   ContainerAppConsoleLogs_CL
   | where Log_s has "POISON_MESSAGE"
   ```

4. Registrar el tiempo hasta recibir la alerta.
   - **Objetivo**: Tiempo hasta la alerta <= 15 minutos (`PT15M`).

### 3. Registro de resultados

| Fecha | Tipo de fallo inyectado | Hora inyección | Hora alerta recibida | Tiempo total | ¿Cumple <= 1h? | Responsable |
|---|---|---|---|---|---|---|
| YYYY-MM-DD | SYNC_FAILED | HH:MM | HH:MM | MM min | Sí | Comprador / Admin |
| YYYY-MM-DD | POISON_MESSAGE | HH:MM | HH:MM | MM min | Sí | Comprador / Admin |

## Alertas de la consola (feature 010)

1. Colocar una cifra sintética de copia antigua en `ops-inputs/` y ejecutar `python -m worker` una vez.
2. Comprobar en Administración → «Alertas» que existe **una** alerta abierta, aunque se repita el paso 1 varias veces.
3. Comprobar que el registro contiene una sola línea `ADMIN_ALERT_OPENED` y que llega el correo (regla `admin-alert-opened`, hasta 15 minutos). Sin canal de correo, la consola lo indica.
4. Reconocer la alerta (segundo factor reciente) y corregir la cifra: la alerta se cierra sola en la siguiente evaluación.
