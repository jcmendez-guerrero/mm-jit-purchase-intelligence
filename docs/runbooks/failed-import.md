# Guía de resolución: importación de datos predictivos fallida

## Síntomas y alertas

- Alerta `mmi-import-failed` (marcador `IMPORT_FAILED` en los registros) o varias alertas `mmi-upload-rejected` seguidas.
- En Administración, la sección «Importaciones en segundo plano» muestra una tarea en estado «Fallida» con un código de error.

## Qué ha pasado en realidad

- Una importación fallida **no cambia nada**: el conjunto activo sigue siendo el anterior y los movimientos del ERP no se tocan.
- Los registros solo guardan códigos estables (por ejemplo `import_failed`), nunca el contenido ni el nombre del archivo.

## Diagnóstico

1. Abrir Administración y anotar el código de error de la tarea y el conjunto (nombre y versión).
2. Consultar el registro de la tarea:

   ```kusto
   ContainerAppConsoleLogs_CL
   | where Log_s has "IMPORT_FAILED" or Log_s has "UPLOAD_REJECTED"
   | order by TimeGenerated desc
   | take 50
   ```

3. Interpretar el código:
   - `import_failed`: error inesperado al validar. Reintentar una vez; si se repite, revisar el archivo con la plantilla.
   - `import_missing_column`, `import_ambiguous_time`: el archivo no sigue la plantilla. Pedir a quien lo subió que corrija el archivo y lo suba de nuevo.
   - `import_too_many_rows`, `import_decompression_limit`, `import_file_too_large`: el archivo supera los límites. Dividirlo.
   - Muchos `UPLOAD_REJECTED` en poco tiempo: posible uso indebido. Comprobar quién subió los archivos en el registro de auditoría antes de seguir.

## Procedimiento

1. Si el motivo es transitorio, en Administración pulsar «Repetir» en la tarea fallida. La repetición es idempotente: si ya hay una en cola o en curso, se reutiliza y no se duplica nada.
2. Si el archivo es incorrecto, no repetir: subir una versión corregida desde «Datos predictivos».
3. Si el problema persiste, descartar el conjunto («Rechazar») para que no quede pendiente.

## Verificación

- La tarea pasa a «Terminada» o se descarta el conjunto.
- El conjunto activo en «Datos predictivos» es el esperado y la última previsión referencia esa versión.
