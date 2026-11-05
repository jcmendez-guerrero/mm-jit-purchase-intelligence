# Guía de resolución: Mensajes en cola de veneno (Poison Queue Runbook)

## Síntomas y alertas

- Alerta `mmi-queue-poison` recibida.
- La cola `<nombre-cola>-poison` contiene uno o más mensajes.
- Marcador `POISON_MESSAGE` en los logs de consola.

## Diagnóstico

1. Inspeccionar los mensajes en la cola de veneno sin eliminarlos:

   ```bash
   az storage message peek --queue-name <queue>-poison --num-messages 5
   ```

2. Analizar la causa raíz:
   - **Checksum inválido**: El payload en Blob Storage no coincide con el sha256 del sobre del evento (posible corrupción o escritura concurrente).
   - **Esquema inválido**: El mensaje no cumple el esquema JSON de la versión del evento.
   - **Mensaje caducado**: La marca temporal `occurred_at` excede la ventana de frescura máxima (24 horas, o 1 hora en escrituras de coste).
   - **Exceso de reintentos**: El worker falló repetidamente al procesar el mensaje debido a un error transitorio o bug de código.

## Procedimiento de mitigación

1. Si se trata de un bug en el servicio consumidor: Desplegar el parche correspondiente.
2. Una vez corregido el problema, mover el mensaje de vuelta a la cola principal:
   - Extraer el contenido del mensaje de la cola de veneno.
   - Reinsertarlo en la cola principal mediante `az storage message put`.
   - Eliminar el mensaje de la cola de veneno.
3. Si el mensaje es corrupto o no recuperable: Documentar el incidente en el registro de incidencias y eliminar el mensaje tras guardar una copia para análisis forense.
