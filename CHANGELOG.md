# Changelog

## v0.3

Cambios verificables en el código y el historial inspeccionado:

- Se declara la dependencia `mcp>=2.0.0,<3.0.0`, y el servidor usa `MCPServer`.
- El motor sustituye cálculos monetarios con `float` por `Decimal`, valida números finitos y redondea a centavos con `ROUND_HALF_UP`.
- La antigüedad se calcula con aniversarios reales y una fracción residual sobre los días del año laboral en curso, incluidos los casos de ingreso el 29 de febrero.
- Se aplica una política *Fail-Closed*: exige siete datos del motor y delimita el cálculo a despido injustificado, salario fijo y zonas `general` o `zlfn`. Los resultados de decisión incluyen `FALTAN_DATOS`, `FUERA_DE_ALCANCE`, `ESTIMACION_CON_SUPUESTOS` y `CALCULO_VERIFICADO`; las validaciones y consultas normativas también tienen estados de error explícitos.
- La base guarda montos salariales como texto decimal y añade registros por zona para `general` y `zlfn`. Los registros 2026 están marcados como pendientes de cotejo directo en DOF.
- Se fortalece la búsqueda FTS5/BM25 con normalización de diacríticos y estrategia escalonada (frase exacta, AND y OR).
- Se actualizan las fichas normativas: el art. 47 ya no condiciona la comunicación al Tribunal a una negativa previa del trabajador; se incluye el art. 52 junto con los supuestos de los arts. 49–51; los arts. 517 y 518 distinguen la prescripción especial de un mes y la acción por separación de dos meses; y el art. 521 recoge la interrupción vinculada a la solicitud de conciliación prejudicial.
- La suite de regresión pasa a 14 pruebas e incluye precisión decimal, aniversarios, zonas salariales, estados de alcance y búsquedas normativas.

## v0.2

Es la primera versión presente en el historial de código inspeccionado:

- Añade un servidor MCP en Python, un motor determinista para indemnización por despido injustificado y una base SQLite con datos salariales y fichas de la LFT.
- Añade búsqueda normativa mediante SQLite FTS5 ordenada por `rank`/BM25.
- El cálculo inicial usaba aritmética de punto flotante y antigüedad calculada como días divididos entre 365; la base de salarios inicial solo incluía la zona `general`.
- La base normativa inicial contenía, entre otras, fichas de los arts. 47, 48, 49–50, 76, 80, 84 y 89, 162, 516 y 518. La revisión de v0.3 modifica el tratamiento de los artículos señalados arriba.

## v0.1

No hay código ni cambios de v0.1 en los dos commits disponibles en el historial inspeccionado (`v0.2` es el primer commit que incorpora los archivos del proyecto). Por tanto, no es posible atribuirle características técnicas sin evidencia.
