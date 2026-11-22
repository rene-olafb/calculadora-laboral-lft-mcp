# CalculadorLaboralLFT — Servidor MCP Determinista y Auditoría Jurídica (México)

Servidor local del **Model Context Protocol (MCP)** construido en Python y SQLite (FTS5) para eliminar alucinaciones aritméticas, errores de cita normativa y evasión de candados (*guardrail bypass*) en el cálculo de indemnizaciones por despido injustificado conforme a la **Ley Federal del Trabajo (LFT)** de México.

---

## 1. Problema de Ingeniería Jurídica

Los Modelos de Lenguaje (LLMs) sin herramientas deterministas cometen fallos sistemáticos en derecho laboral mexicano:
1. **Confusión de plazos de prescripción:** Aplican el plazo general de 1 año (art. 516 LFT) en lugar del plazo especial de **2 meses** para acciones derivadas de separación laboral (art. 518, párr. 1, LFT).
2. **Aplicación errónea de topes salariales:** Confunden el ámbito del tope de 2 salarios mínimos (art. 162, fracc. II, y art. 486 LFT, aplicable a la prima de antigüedad) con la base sin tope de la indemnización constitucional de 90 días (arts. 48 y 89 LFT).
3. **Inclusión automática de los 20 días por año:** Suman la indemnización del art. 50, fracc. II, LFT de manera automática sin verificar los supuestos de excepción de los arts. 49 y 51 LFT.
4. **Evasión de candados (*Guardrail Bypass*):** Ante expedientes incompletos, los agentes tienden a asumir salarios o fechas por su cuenta para forzar un resultado numérico.

---

## 2. Arquitectura del Sistema

```text
+-------------------+       stdio (JSON-RPC)       +--------------------+
|  Claude Desktop   | <--------------------------> |  servidor_mcp.py   |
|   (Cliente MCP)   |                              |   (MCP SDK 2.x)    |
+-------------------+                              +---------+----------+
                                                             |
                                                             v
+-------------------+       SQL / BM25 (FTS5)      +--------------------+
|   lft_local.db    | <--------------------------> |      motor.py      |
| (SQLite + FTS5)   |                              | (Lógica Determin.) |
+-------------------+                              +--------------------+