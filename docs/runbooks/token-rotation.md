# Guía de rotación de tokens Siweb (Token Rotation Runbook)

## Contexto

El token de API de Siweb360 es un token compartido con la aplicación existente de farmacia. No debe ser revocado sin previa coordinación con el equipo de la otra aplicación.

## Frecuencia y desencadenantes

- Expiración periódica planificada (semestral/anual).
- Sospecha de compromiso o exposición accidental.
- Notificación de renovación por parte de Siweb360.

## Procedimiento de rotación coordinada

1. **Coordinación previa**: Acordar la ventana de rotación con los administradores de la aplicación de farmacia hermana.
2. **Generación del nuevo token**: Obtener el nuevo token Bearer desde el panel administrativo de Siweb360 o vía el proveedor.
3. **Actualización en Azure Key Vault**:
   - Acceder al Key Vault de producción mediante Managed Identity o rol de Key Vault Secrets Officer.
   - Crear una nueva versión del secreto `siweb-reader-token` (y `siweb-writer-token` si corresponde):

     ```bash
     az keyvault secret set --vault-name mmi-prod-kv --name siweb-reader-token --value "<NUEVO_TOKEN>"
     az keyvault secret set --vault-name mmi-prod-kv --name siweb-cost-writer-token --value "<NUEVO_TOKEN_WRITER>"
     ```

4. **Verificación**:
   - Disparar una ejecución de prueba del job `siweb-connector` en preproducción o una comprobación `GET /inventory/warehouses` con límite 1.
   - Confirmar en los logs que no se produce error 401:
     `SYNC_OK kind=warehouses`
5. **Notificación**: Confirmar a la aplicación hermana que la rotación se ha completado satisfactoriamente.
