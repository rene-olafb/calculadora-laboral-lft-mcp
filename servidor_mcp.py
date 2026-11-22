from mcp.server.mcpserver import MCPServer
from typing import Optional
from motor import calcular_despido_injustificado, buscar_normativa_lft

mcp = MCPServer("CalculadorLaboralLFT")


@mcp.tool()
def calcular_indemnizacion_lft(
    fecha_ingreso: Optional[str] = None,
    fecha_despido: Optional[str] = None,
    salario_diario_cuota: Optional[float] = None,
    salario_diario_integrado: Optional[float] = None,
    zona_salarial: str = "general",
) -> dict:
    """
    Calcula de forma determinista la indemnización constitucional (90 días)
    y la prima de antigüedad (12 días/año con tope de 2 SMG) leyendo el
    salario mínimo desde lft_local.db.
    REGLA CRÍTICA: Si el usuario omite algún dato, pásalo como None.
    Si esta herramienta devuelve estado 'FALTAN_DATOS', DETENTE inmediatamente
    y solicita al usuario los datos faltantes. PROHIBIDO asumir valores estimados,
    pisos salariales o reintentar la llamada inventando parámetros.
    """
    return calcular_despido_injustificado(
        fecha_ingreso=fecha_ingreso,
        fecha_despido=fecha_despido,
        salario_diario_cuota=salario_diario_cuota,
        salario_diario_integrado=salario_diario_integrado,
        zona_salarial=zona_salarial,
    )


@mcp.tool()
def consultar_normativa_lft(consulta: str) -> dict:
    """
    Busca reglas jurídicas verificadas de la Ley Federal del Trabajo en la base
    de datos SQLite local (FTS5) sobre prescripción, aviso de rescisión,
    indemnización de 20 días por año, vacaciones y prima de antigüedad.
    Úsala antes de afirmar plazos legales o fracciones de artículos.
    """
    return buscar_normativa_lft(consulta=consulta)


if __name__ == "__main__":
    mcp.run()