# Guía de resolución: Fallo en escritura de coste a Siweb (Failed Cost Write Runbook)

## Síntomas y alertas
- Alerta `mmi-cost-write-failed` o `mmi-unmatched-writes` recibida.
- Marcador `COST_WRITE_FAILED` o `UNMATCHED_WRITE` en logs de consola de `siweb-cost-writer`.
- En el panel de control de compras, la solicitud de escritura aparece con estado `failed`.

## Diagnóstico
1. Consultar el registro de auditoría encadenado (hash chain) en `costwrite.audit_log`:
   ```sql
   SELECT * FROM costwrite.audit_log WHERE status = 'failed' ORDER BY timestamp DESC LIMIT 5;
   ```
2. Verificar el motivo del fallo:
   - **`pending_link`**: No existe asociación previa entre el producto y el proveedor en el ERP. El ERP rechaza la creación autónoma de nuevos enlaces proveedor-producto; el coste debe mantenerse local o el enlace debe crearse manualmente en el ERP.
   - **`mismatch`**: Tras la escritura `PUT`, la lectura de comprobación posterior (`GET`) arrojó un valor distinto al escrito. Posible conflicto de concurrencia o modificación externa en Siweb.
   - **`auth_expired`**: El token del escritor ha expirado o no tiene permisos sobre la ruta `PUT /inventory/products/{id}/suppliers/{contact_id}`.
   - **`allowlist_refused`**: Se intentó escribir en una ruta o método no autorizado (bloqueo por diseño).

## Procedimiento de mitigación
1. Si el motivo fue `pending_link`:
   - Informar al comprador para que cree la relación producto-proveedor en la interfaz de Siweb360 si es pertinente.
2. Si el motivo fue `mismatch`:
   - El escritor reintentará de forma acotada. Si persiste, el cambio queda bloqueado para evitar sobreescritura destructiva.
   - El comprador debe revisar el coste en la pantalla de Siweb360 y reconfirmar manualmente el valor deseado.
3. Si el motivo fue un error de red o timeout transitorio:
   - El worker reintentará automáticamente hasta el límite configurado (3 reintentos).
   - Verificar la cadena de hash con `verify_chain()` para asegurar la integridad de la auditoría.
