# CalculadorLaboralLFT — servidor MCP y motor determinista (v0.3)

Servidor local en Python para consultar una base normativa SQLite y calcular, dentro de un alcance limitado, la indemnización constitucional y la prima de antigüedad por despido injustificado en México. El motor calcula con `Decimal`, consulta salarios mínimos vigentes y conserva alertas de auditoría; no sustituye asesoría jurídica.

## Arquitectura

- `crear_base.py` crea y puebla `lft_local.db` con registros de salario mínimo, fuentes y artículos de la LFT. Incluye una tabla virtual FTS5 para búsqueda normativa.
- `motor.py` contiene el cálculo y la búsqueda. Lee SQLite en modo solo lectura; usa FTS5, ordenamiento BM25 (`rank`) y consultas escalonadas de frase exacta, AND y OR. Normaliza acentos y limita los resultados a cinco.
- `servidor_mcp.py` registra las herramientas MCP `calcular_indemnizacion_lft` y `consultar_normativa_lft`.
- `requirements.txt` limita la dependencia `mcp` a la versión mayor 2 (`mcp>=2.0.0,<3.0.0`).

El cálculo es únicamente para `despido_injustificado` y salario `fijo`. La prima de antigüedad se calcula con 12 días por año, con piso de un salario mínimo y tope de dos; la indemnización constitucional de 90 días se calcula sobre el SDI sin ese tope. No incluye finiquito, salarios vencidos e intereses ni indemnización de 20 días por año.

## Datos obligatorios del motor

Para emitir un cálculo, `calcular_despido_injustificado` requiere los siete datos siguientes; si falta uno devuelve `FALTAN_DATOS`:

1. `fecha_ingreso` — fecha ISO.
2. `fecha_despido` — fecha ISO.
3. `salario_diario_cuota` — cuota diaria positiva.
4. `salario_diario_integrado` — SDI positivo y no menor que la cuota.
5. `zona_salarial` — `general` o `zlfn`.
6. `tipo_separacion` — `despido_injustificado`.
7. `tipo_salario` — `fijo`.

**Límite actual del adaptador MCP:** `calcular_indemnizacion_lft` expone solo los primeros cinco campos (con `zona_salarial` predeterminada a `general`) y no reenvía `tipo_separacion` ni `tipo_salario`. Por ello, tal como está implementado, una llamada a esa herramienta no puede satisfacer los siete datos del motor y este responderá `FALTAN_DATOS`. La lista anterior describe los requisitos del motor, no los campos actualmente disponibles en la herramienta MCP.

## Estados de salida del cálculo

Los cuatro estados de decisión del cálculo son:

- `FALTAN_DATOS`: falta uno o más de los siete datos requeridos.
- `FUERA_DE_ALCANCE`: separación distinta de despido injustificado, salario distinto de fijo o zona no soportada.
- `ESTIMACION_CON_SUPUESTOS`: hay alertas de auditoría, por ejemplo, un salario mínimo marcado sin cotejo directo en DOF.
- `CALCULO_VERIFICADO`: cálculo sin alertas de auditoría.

También se devuelven estados de error cuando no es posible validar entradas o consultar datos normativos, incluidos `ERROR_VALIDACION` y `ERROR_DATO_NORMATIVO`. La búsqueda normativa tiene sus propios estados (`OK`, `ERROR`, `SIN_RESULTADOS` y `ERROR_DATO_NORMATIVO`).

## Caso de prueba v0.3

La prueba `test_02_estimacion_con_supuestos_2026_y_calendario_real` usa ingreso `2022-03-01`, despido `2026-11-19`, cuota diaria `$800.00`, SDI `$843.84` y zona `general`. El resultado es `ESTIMACION_CON_SUPUESTOS`:

**Indemnización constitucional: $75,945.60 + prima de antigüedad: $35,712.59 = total parcial: $111,658.19.**

La estimación se marca con alerta porque el registro salarial de 2026 tiene `verificado_dof=0`. La antigüedad se calcula por aniversarios reales y fracción residual del año laboral en curso, no mediante una división fija entre 365.

## Pruebas y ejecución local

La suite de `test_motor.py` contiene **14 pruebas unitarias**. Para regenerar la base y ejecutar la suite:

```bash
python -m pip install -r requirements.txt
python crear_base.py
python test_motor.py
```

GitHub Actions ejecuta ambos scripts en Python 3.12 en cada `push` o `pull_request` dirigido a `main`.
