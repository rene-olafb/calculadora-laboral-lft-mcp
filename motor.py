import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

# Ruta absoluta para que Claude Desktop siempre encuentre la base de datos
DB_PATH = Path(__file__).parent / "lft_local.db"


def _dias_vacaciones_ley(dias_trabajados: int) -> int:
    """Calcula los días mínimos de vacaciones conforme al art. 76 LFT vigente."""
    anio_servicio = (dias_trabajados // 365) + 1
    if anio_servicio == 1:
        return 12
    elif anio_servicio == 2:
        return 14
    elif anio_servicio == 3:
        return 16
    elif anio_servicio == 4:
        return 18
    elif anio_servicio == 5:
        return 20
    else:
        return 20 + ((anio_servicio - 1) // 5) * 2


def calcular_despido_injustificado(
    fecha_ingreso: Optional[str] = None,
    fecha_despido: Optional[str] = None,
    salario_diario_cuota: Optional[float] = None,
    salario_diario_integrado: Optional[float] = None,
    zona_salarial: str = "general",
) -> dict:
    """
    Calcula de forma determinista la indemnización constitucional (90 días)
    y la prima de antigüedad (12 días/año con tope de 2 SMG) leyendo el
    salario mínimo oficial directamente desde lft_local.db.
    """
    # 1. Validación estricta de datos faltantes
    faltantes = []
    if not fecha_ingreso:
        faltantes.append("fecha_ingreso (formato YYYY-MM-DD)")
    if not fecha_despido:
        faltantes.append("fecha_despido (formato YYYY-MM-DD)")
    if salario_diario_cuota is None:
        faltantes.append("salario_diario_cuota (cuota diaria base)")
    if salario_diario_integrado is None:
        faltantes.append("salario_diario_integrado (SDI para indemnización)")

    if faltantes:
        return {
            "estado": "FALTAN_DATOS",
            "mensaje": "Cálculo detenido. Faltan datos obligatorios para emitir un resultado auditable.",
            "datos_faltantes": faltantes,
        }

    # 2. Validación de fechas
    try:
        f_ingreso = date.fromisoformat(fecha_ingreso)
        f_despido = date.fromisoformat(fecha_despido)
    except ValueError:
        return {
            "estado": "ERROR_VALIDACION",
            "mensaje": "Las fechas deben tener formato ISO estricto: YYYY-MM-DD.",
        }

    if f_despido < f_ingreso:
        return {
            "estado": "ERROR_VALIDACION",
            "mensaje": "Contradicción fáctica: la fecha de despido es anterior a la fecha de ingreso.",
        }

    # 3. Validación de montos salariales
    if salario_diario_cuota <= 0 or salario_diario_integrado <= 0:
        return {
            "estado": "ERROR_VALIDACION",
            "mensaje": "Los salarios deben ser mayores a cero.",
        }

    if salario_diario_integrado < salario_diario_cuota:
        return {
            "estado": "ERROR_VALIDACION",
            "mensaje": "Contradicción técnica: el SDI no puede ser menor a la cuota diaria (art. 84 LFT).",
        }

    # 4. Consulta determinista del Salario Mínimo en SQLite
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute(
        """
        SELECT monto_diario, fuente_dof, verificado_dof
        FROM salarios_minimos
        WHERE zona = ? AND ? BETWEEN vigencia_inicio AND vigencia_fin
        """,
        (zona_salarial.lower(), fecha_despido),
    )
    fila_smg = cursor.fetchone()
    conexion.close()

    if not fila_smg:
        return {
            "estado": "ERROR_DATO_NORMATIVO",
            "mensaje": f"No existe un salario mínimo registrado en lft_local.db para la fecha {fecha_despido} y zona '{zona_salarial}'.",
        }

    salario_minimo_vigente, fuente_dof, verificado_dof = fila_smg

    # 5. Cálculo de antigüedad y auditoría del factor mínimo de SDI (art. 76 LFT)
    dias_trabajados = (f_despido - f_ingreso).days + 1
    anios_antiguedad = dias_trabajados / 365.0
    dias_vacaciones = _dias_vacaciones_ley(dias_trabajados)
    factor_minimo = 1 + (15 + (dias_vacaciones * 0.25)) / 365.0
    sdi_minimo_legal = round(salario_diario_cuota * factor_minimo, 2)

    alertas_auditoria = []
    if verificado_dof == 0:
        alertas_auditoria.append(
            f"Gobernanza de datos: El SMG de ${salario_minimo_vigente} ({fuente_dof}) tiene bandera verificado_dof=0; cotejar publicación primaria antes de presentar demanda."
        )
    if salario_diario_integrado < (sdi_minimo_legal - 0.05):
        alertas_auditoria.append(
            f"Posible subestimación de SDI: Para {dias_trabajados} días trabajados corresponden {dias_vacaciones} días de vacaciones (art. 76 LFT), lo que arroja un SDI mínimo legal de ${sdi_minimo_legal} MXN (superior a los ${salario_diario_integrado} MXN ingresados)."
        )

    # 6. Cálculos económicos
    indemnizacion_constitucional = round(salario_diario_integrado * 90, 2)

    tope_prima = salario_minimo_vigente * 2
    if salario_diario_cuota > tope_prima:
        salario_base_prima = tope_prima
        aplico_tope = True
    elif salario_diario_cuota < salario_minimo_vigente:
        salario_base_prima = salario_minimo_vigente
        aplico_tope = False
    else:
        salario_base_prima = salario_diario_cuota
        aplico_tope = False

    prima_antiguedad = round((anios_antiguedad * 12) * salario_base_prima, 2)
    total = round(indemnizacion_constitucional + prima_antiguedad, 2)

    return {
        "estado": "OK",
        "parametros_verificados": {
            "dias_trabajados": dias_trabajados,
            "anios_antiguedad": round(anios_antiguedad, 4),
            "salario_minimo_aplicado_mxn": salario_minimo_vigente,
            "fuente_salario_minimo": fuente_dof,
            "verificado_en_dof": bool(verificado_dof),
            "salario_base_prima_mxn": round(salario_base_prima, 2),
            "aplico_tope_2_smg": aplico_tope,
        },
        "desglose": {
            "indemnizacion_constitucional_90_dias": {
                "monto_mxn": indemnizacion_constitucional,
                "fundamento": "Arts. 48, párr. 1, y 89, párr. 1, LFT; Art. 123, Apartado A, fracc. XXII, CPEUM (sin tope de 2 SMG).",
            },
            "prima_de_antiguedad": {
                "monto_mxn": prima_antiguedad,
                "fundamento": "Art. 162, fraccs. I, II y III, en relación con arts. 485 y 486, LFT.",
            },
        },
        "total_parcial_mxn": total,
        "alertas_auditoria": alertas_auditoria,
    }


STOPWORDS_ES = {
    "de", "la", "el", "los", "las", "un", "una", "unos", "unas",
    "por", "para", "en", "y", "o", "a", "que", "es", "sobre",
    "con", "del", "al", "se", "su", "sus", "como", "mas", "art",
    "articulo", "articulos", "lft", "ley", "ano", "anos", "dia", "dias",
}


def buscar_normativa_lft(consulta: str) -> dict:
    """Busca reglas y fundamentos exactos en el índice FTS5 de lft_local.db ordenados por BM25."""
    tokens_crudos = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9]+", consulta.lower())
    tokens_filtrados = [t for t in tokens_crudos if t not in STOPWORDS_ES and len(t) > 1]

    if not tokens_filtrados:
        return {
            "estado": "ERROR",
            "mensaje": "La consulta debe incluir términos jurídicos específicos (ej. 'prescripcion', 'tope', 'aviso').",
        }

    # Usamos comodín de prefijo (*) para capturar singular/plural (ej. plazo -> plazos)
    query_fts = " OR ".join(f"{token}*" for token in tokens_filtrados)

    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    cursor.execute(
        """
        SELECT articulo, titulo_tema, regla_normativa
        FROM articulos_lft_fts
        WHERE articulos_lft_fts MATCH ?
        ORDER BY rank
        LIMIT 5
        """,
        (query_fts,),
    )
    resultados = cursor.fetchall()
    conexion.close()

    if not resultados:
        return {
            "estado": "SIN_RESULTADOS",
            "mensaje": f"No se encontraron artículos indexados para: {consulta}",
        }

    return {
        "estado": "OK",
        "resultados": [
            {
                "articulo": fila[0],
                "tema": fila[1],
                "regla_normativa": fila[2],
                "fuente_oficial": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFT.pdf",
            }
            for fila in resultados
        ],
    }