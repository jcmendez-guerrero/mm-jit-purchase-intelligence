# Guía de resolución: los roles no llegan al servicio de compras

## Síntomas y alertas

- Alerta `mmi-role-mirror-lag` (marcador `ROLE_MIRROR_LAG`).
- En Administración, las secciones «Sincronización de roles con compras» y «Comunicación con compras» muestra pendientes o fallidos, o una antigüedad de más de 15 minutos.
- Una persona con un rol recién concedido puede usar la consola pero compras rechaza la acción (o al revés tras retirar un rol).

## Por qué importa

El servicio de compras mantiene su propia copia de los roles para decidir quién puede aprobar. Mientras la copia no se actualiza, una **retirada** de rol puede tardar en aplicarse allí. La consola aplica la retirada al instante, y compras solo acepta cambios con una revisión más reciente, así que los reintentos nunca restauran un rol retirado.

## Diagnóstico

1. En Administración, anotar cuántos cambios están pendientes o fallidos y el más antiguo.
2. Consultar los registros:

   ```kusto
   ContainerAppConsoleLogs_CL
   | where Log_s has "ROLE_MIRROR_FAILED" or Log_s has "ROLE_MIRROR_LAG"
   | order by TimeGenerated desc
   | take 50
   ```

3. Causas habituales: servicio de compras detenido o reiniciándose (se escala a cero y tarda en arrancar), identidad de servicio sin permiso, error de red.

## Procedimiento

1. Si compras estaba arrancando, esperar un par de minutos: la tarea periódica reintenta sola (hasta 8 intentos con espera creciente).
2. Si hay cambios fallidos, pulsar «Reintentar envío» en «Comunicación con compras» (Administración). Es idempotente.
3. Si una **retirada** de rol urgente no ha llegado, desactivar temporalmente al usuario en la consola (efecto inmediato) y repetir la sincronización.
4. Si el fallo persiste más de una hora, revisar la identidad de servicio y los permisos del servicio de compras (sin pegar secretos en tickets ni en el repositorio).

## Verificación

- Pendientes y fallidos a 0 y antigüedad 0 min.
- El registro de auditoría de roles conserva la cadena íntegra.

## Alertas y consola (feature 010)

- Un retraso superior al umbral («Retraso de roles (minutos)», 15 por defecto) abre la alerta «Cambios de rol sin comunicar a compras»; un envío agotado (8 intentos) aparece en «Trabajos y colas» como «En cola de errores» y se reintenta desde el mismo botón.
- Reintentar, cambiar roles y reconocer alertas exigen un segundo factor de menos de 5 minutos; cada intento, permitido o rechazado, queda en el registro de auditoría (Administración → «Registro de auditoría»).
