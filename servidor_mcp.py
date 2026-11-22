from mcp.server.mcpserver import MCPServer
from typing import Optional, Union
from motor import calcular_despido_injustificado, buscar_normativa_lft

mcp = MCPServer("CalculadorLaboralLFT")


@mcp.tool()
def calcular_indemnizacion_lft(
    fecha_ingreso: Optional[str] = None,
    fecha_despido: Optional[str] = None,
    salario_diario_cuota: Optional[Union[str, float]] = None,
    salario_diario_integrado: Optional[Union[str, float]] = None,
    zona_salarial: Optional[str] = None,
    tipo_separacion: Optional[str] = None,
    tipo_salario: Optional[str] = None,
) -> dict:
    """
    Calcula de forma determinista (Decimal + calendario real) la indemnización
    constitucional (90 días) y la prima de antigüedad (12 días/año con tope de 2 SMG).
    REGLAS CRÍTICAS:
    1. Si el usuario omite cualquier dato (incluida zona_salarial, tipo_separacion o
       tipo_salario), pásalo como None. PROHIBIDO asumir valores por defecto.
    2. Si devuelve 'FALTAN_DATOS' o 'FUERA_DE_ALCANCE', DETENTE e informa al usuario;
       PROHIBIDO reintentar inventando parámetros.
    3. Si devuelve 'ESTIMACION_CON_SUPUESTOS', DEBES reportar todas las alertas de
       auditoría y nunca presentar la cifra como cálculo definitivo verificado.
    """
    return calcular_despido_injustificado(
        fecha_ingreso=fecha_ingreso,
        fecha_despido=fecha_despido,
        salario_diario_cuota=salario_diario_cuota,
        salario_diario_integrado=salario_diario_integrado,
        zona_salarial=zona_salarial,
        tipo_separacion=tipo_separacion,
        tipo_salario=tipo_salario,
    )


@mcp.tool()
def consultar_normativa_lft(consulta: str) -> dict:
    """
    Busca reglas jurídicas verificadas de la Ley Federal del Trabajo en la base
    SQLite local (FTS5/BM25) sobre despido, aviso (art. 47), 20 días por año
    (arts. 49-52), vacaciones (art. 76), SDI (arts. 84/89), prima de antigüedad
    (arts. 162/485/486) y prescripción/conciliación (arts. 516, 517, 518, 521, 684-B).
    Úsala siempre antes de afirmar plazos legales o fracciones de artículos.
    """
    return buscar_normativa_lft(consulta=consulta)


if __name__ == "__main__":
    mcp.run()