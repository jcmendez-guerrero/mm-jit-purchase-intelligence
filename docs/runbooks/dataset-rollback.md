# Guía de resolución: deshacer la activación de un conjunto predictivo

## Cuándo usarla

- Tras activar un conjunto, las previsiones o las cantidades propuestas no tienen sentido (por ejemplo, un archivo con unidades equivocadas que pasó la validación).

## Qué hace y qué no hace

- **Hace:** reactiva la versión anterior del conjunto, deja el conjunto retirado como «sustituido» (no se borra) y encola una nueva previsión que registra la versión usada.
- **No hace:** no modifica los movimientos ni las ventas del ERP; los datos reales siempre prevalecen sobre los predictivos.
- Requiere rol de comprador o administrador y queda registrado en la auditoría (quién, cuándo, versiones).

## Procedimiento

1. En «Datos predictivos», comprobar cuál es el conjunto activo y su versión.
2. Pulsar «Volver a la versión anterior» y confirmar. Si no hay versión anterior, el sistema lo indica y vuelve a usar solo el historial del ERP.
3. En Administración, comprobar en «Ejecuciones del modelo» que aparece una ejecución nueva con la versión restaurada. Si no aparece en unos minutos, pulsar «Repetir previsión» (es idempotente).
4. Las propuestas en borrador se recalculan al abrirlas; las ya enviadas o aprobadas no cambian: revisarlas con la persona que aprueba.

## Verificación

- La versión activa es la esperada y la ejecución más reciente la referencia.
- Los registros de auditoría muestran la activación y el deshacer, con la cadena de hashes íntegra.
