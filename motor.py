import re
import sqlite3
import unicodedata
from contextlib import closing
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Optional, Union

DB_PATH = Path(__file__).parent / "lft_local.db"
CENTAVO = Decimal("0.01")
NumeroEntrada = Union[str, int, float, Decimal]


def _redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _parsear_decimal(valor: NumeroEntrada) -> Optional[Decimal]:
    """Convierte de forma segura a Decimal rechazando booleanos, NaN e infinitos."""
    if isinstance(valor, bool):
        return None
    try:
        d = valor if isinstance(valor, Decimal) else Decimal(str(valor).strip())
    except (InvalidOperation, AttributeError, ValueError):
        return None
    if not d.is_finite():
        return None
    return d


def _fecha_aniversario(f_ingreso: date, anio: int) -> date:
    """Devuelve la fecha de aniversario laboral; si ingresó el 29-feb, en año no bisiesto pasa al 1-mar."""
    try:
        return date(anio, f_ingreso.month, f_ingreso.day)
    except ValueError:
        return date(anio, 3, 1)


def _calcular_antiguedad_calendario(f_ingreso: date, f_despido: date) -> dict:
    """
    Calcula aniversarios completos y fracción residual por calendario real,
    evitando la acumulación de días bisiestos de la división simple entre 365.
    """
    aniv_anio_despido = _fecha_aniversario(f_ingreso, f_despido.year)
    if f_despido >= aniv_anio_despido:
        anios_completos = f_despido.year - f_ingreso.year
        ultimo_aniversario = aniv_anio_despido
    else:
        anios_completos = f_despido.year - f_ingreso.year - 1
        ultimo_aniversario = _fecha_aniversario(f_ingreso, f_despido.year - 1)

    siguiente_aniversario = _fecha_aniversario(f_ingreso, ultimo_aniversario.year + 1)
    dias_anio_en_curso = (siguiente_aniversario - ultimo_aniversario).days
    dias_residuales = (f_despido - ultimo_aniversario).days + 1
    dias_calendario_intervalo = (f_despido - f_ingreso).days + 1

    antiguedad_anios = Decimal(anios_completos) + (
        Decimal(dias_residuales) / Decimal(dias_anio_en_curso)
    )
    anio_servicio_en_curso = anios_completos + 1

    return {
        "dias_calendario_intervalo": dias_calendario_intervalo,
        "anios_completos": anios_completos,
        "dias_residuales": dias_residuales,
        "dias_anio_en_curso": dias_anio_en_curso,
        "anio_servicio_en_curso": anio_servicio_en_curso,
        "antiguedad_anios": antiguedad_anios,
    }


def _dias_vacaciones_ley(anio_servicio: int) -> int:
    """Calcula los días mínimos de vacaciones conforme al art. 76 LFT vigente."""
    if anio_servicio <= 1:
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


def _abrir_conexion_lectura() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"No se encontró la base de datos normativa en {DB_PATH}")
    uri = f"{DB_PATH.resolve().as_uri()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def calcular_despido_injustificado(
    fecha_ingreso: Optional[str] = None,
    fecha_despido: Optional[str] = None,
    salario_diario_cuota: Optional[NumeroEntrada] = None,
    salario_diario_integrado: Optional[NumeroEntrada] = None,
    zona_salarial: Optional[str] = None,
    tipo_separacion: Optional[str] = None,
    tipo_salario: Optional[str] = None,
) -> dict:
    """
    Calcula de forma determinista con aritmética Decimal y calendario real
    la indemnización constitucional (90 días) y la prima de antigüedad (12 días/año
    con piso de 1 SMG y tope de 2 SMG) bajo una política estricta Fail-Closed.
    """
    # 1. Validación estricta de datos obligatorios (sin defaults silenciosos)
    faltantes = []
    if not fecha_ingreso:
        faltantes.append("fecha_ingreso (YYYY-MM-DD)")
    if not fecha_despido:
        faltantes.append("fecha_despido (YYYY-MM-DD)")
    if salario_diario_cuota is None:
        faltantes.append("salario_diario_cuota (cuota diaria base)")
    if salario_diario_integrado is None:
        faltantes.append("salario_diario_integrado (SDI para indemnización)")
    if not zona_salarial:
        faltantes.append("zona_salarial ('general' o 'zlfn')")
    if not tipo_separacion:
        faltantes.append("tipo_separacion (ej. 'despido_injustificado')")
    if not tipo_salario:
        faltantes.append("tipo_salario ('fijo' o 'variable')")

    if faltantes:
        return {
            "estado": "FALTAN_DATOS",
            "mensaje": "Cálculo detenido. Faltan datos obligatorios para emitir un resultado auditable.",
            "datos_faltantes": faltantes,
        }

    # 2. Control de alcance jurídico (Fail-Closed)
    zona_norm = str(zona_salarial).strip().lower()
    separacion_norm = str(tipo_separacion).strip().lower()
    salario_norm = str(tipo_salario).strip().lower()

    if separacion_norm != "despido_injustificado":
        return {
            "estado": "FUERA_DE_ALCANCE",
            "mensaje": f"El motor solo calcula 'despido_injustificado'. El supuesto '{tipo_separacion}' requiere reglas de procedencia distintas (arts. 47, 51, 52 y 162 LFT).",
        }

    if salario_norm != "fijo":
        return {
            "estado": "FUERA_DE_ALCANCE",
            "mensaje": f"El motor solo soporta salario 'fijo'. Para salario '{tipo_salario}' debe promediarse el ingreso de los últimos 30 días efectivamente trabajados (art. 89, párr. 2, LFT).",
        }

    if zona_norm not in {"general", "zlfn"}:
        return {
            "estado": "FUERA_DE_ALCANCE",
            "mensaje": f"Zona salarial '{zona_salarial}' no soportada. Valores permitidos: 'general' o 'zlfn'. Si laboró en varias áreas aplica el promedio de sus salarios mínimos (art. 486 LFT).",
        }

    # 3. Validación estricta de fechas ISO
    try:
        f_ingreso = date.fromisoformat(str(fecha_ingreso).strip())
        f_despido = date.fromisoformat(str(fecha_despido).strip())
    except ValueError:
        return {
            "estado": "ERROR_VALIDACION",
            "mensaje": "Las fechas deben tener formato ISO válido: YYYY-MM-DD.",
        }

    if f_despido < f_ingreso:
        return {
            "estado": "ERROR_VALIDACION",
            "mensaje": "Contradicción fáctica: la fecha de despido es anterior a la fecha de ingreso.",
        }

    # 4. Validación estricta de montos con Decimal
    cuota_dec = _parsear_decimal(salario_diario_cuota)
    sdi_dec = _parsear_decimal(salario_diario_integrado)

    if cuota_dec is None or sdi_dec is None:
        return {
            "estado": "ERROR_VALIDACION",
            "mensaje": "Los salarios deben ser valores numéricos decimales finitos válidos.",
        }

    if cuota_dec <= 0 or sdi_dec <= 0:
        return {
            "estado": "ERROR_VALIDACION",
            "mensaje": "Los salarios deben ser mayores a cero.",
        }

    if sdi_dec < cuota_dec:
        return {
            "estado": "ERROR_VALIDACION",
            "mensaje": "Contradicción técnica: el SDI no puede ser menor a la cuota diaria (art. 84 LFT).",
        }

    # 5. Consulta determinista del Salario Mínimo en SQLite (solo lectura, fecha ISO normalizada)
    fecha_despido_iso = f_despido.isoformat()
    try:
        with closing(_abrir_conexion_lectura()) as conexion:
            cursor = conexion.cursor()
            cursor.execute(
                """
                SELECT monto_diario, fuente_dof, verificado_dof
                FROM salarios_minimos
                WHERE zona = ? AND ? BETWEEN vigencia_inicio AND vigencia_fin
                """,
                (zona_norm, fecha_despido_iso),
            )
            filas_smg = cursor.fetchall()
    except (FileNotFoundError, sqlite3.Error) as exc:
        return {
            "estado": "ERROR_DATO_NORMATIVO",
            "mensaje": f"Error al consultar lft_local.db: {exc}",
        }

    if len(filas_smg) == 0:
        return {
            "estado": "ERROR_DATO_NORMATIVO",
            "mensaje": f"No existe un salario mínimo registrado en lft_local.db para la fecha {fecha_despido_iso} y zona '{zona_norm}'.",
        }

    if len(filas_smg) > 1:
        return {
            "estado": "ERROR_DATO_NORMATIVO",
            "mensaje": f"Error de integridad en lft_local.db: existen vigencias solapadas para {fecha_despido_iso} en zona '{zona_norm}'.",
        }

    smg_str, fuente_dof, verificado_dof = filas_smg[0]
    smg_dec = Decimal(smg_str)

    # 6. Antigüedad por aniversarios reales y auditoría de factor mínimo de SDI
    ant = _calcular_antiguedad_calendario(f_ingreso, f_despido)
    dias_vacaciones = _dias_vacaciones_ley(ant["anio_servicio_en_curso"])
    factor_minimo = Decimal("1") + (
        Decimal("15") + (Decimal(dias_vacaciones) * Decimal("0.25"))
    ) / Decimal("365")
    sdi_minimo_legal = _redondear(cuota_dec * factor_minimo)

    alertas_auditoria = []
    if verificado_dof == 0:
        alertas_auditoria.append(
            f"Gobernanza de datos: El SMG de ${smg_dec} ({fuente_dof}) tiene bandera verificado_dof=0; cotejar publicación primaria en el DOF."
        )

    tolerancia = Decimal("0.05")
    if sdi_dec < (sdi_minimo_legal - tolerancia):
        alertas_auditoria.append(
            f"Posible subestimación de SDI (escenario de prestaciones mínimas): En el año de servicio #{ant['anio_servicio_en_curso']} corresponden {dias_vacaciones} días de vacaciones (art. 76 LFT), lo que da un SDI mínimo de referencia de ${sdi_minimo_legal} MXN (superior a ${sdi_dec} MXN)."
        )

    # 7. Cálculos económicos en Decimal con ROUND_HALF_UP
    indemnizacion_constitucional = _redondear(sdi_dec * Decimal("90"))

    tope_prima = smg_dec * Decimal("2")
    if cuota_dec > tope_prima:
        salario_base_prima = tope_prima
        aplico_tope = True
    elif cuota_dec < smg_dec:
        salario_base_prima = smg_dec
        aplico_tope = False
    else:
        salario_base_prima = cuota_dec
        aplico_tope = False

    prima_antiguedad = _redondear(
        ant["antiguedad_anios"] * Decimal("12") * salario_base_prima
    )
    total = _redondear(indemnizacion_constitucional + prima_antiguedad)

    estado_final = (
        "ESTIMACION_CON_SUPUESTOS" if alertas_auditoria else "CALCULO_VERIFICADO"
    )

    return {
        "estado": estado_final,
        "parametros_verificados": {
            "zona_salarial": zona_norm,
            "dias_calendario_intervalo": ant["dias_calendario_intervalo"],
            "anios_completos": ant["anios_completos"],
            "dias_residuales": ant["dias_residuales"],
            "anio_servicio_en_curso": ant["anio_servicio_en_curso"],
            "antiguedad_anios": float(ant["antiguedad_anios"].quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "convencion_antiguedad": "Aniversarios reales de calendario + fracción residual inclusiva sobre días del año laboral en curso; redondeo ROUND_HALF_UP.",
            "salario_minimo_aplicado_mxn": float(smg_dec),
            "fuente_salario_minimo": fuente_dof,
            "verificado_en_dof": bool(verificado_dof),
            "salario_base_prima_mxn": float(_redondear(salario_base_prima)),
            "aplico_tope_2_smg": aplico_tope,
        },
        "desglose": {
            "indemnizacion_constitucional_90_dias": {
                "monto_mxn": float(indemnizacion_constitucional),
                "fundamento": "Arts. 48, párr. 1, y 89, párrs. 1 y 3, LFT; Art. 123, Apartado A, fracc. XXII, CPEUM (sin tope de 2 SMG).",
            },
            "prima_de_antiguedad": {
                "monto_mxn": float(prima_antiguedad),
                "fundamento": "Art. 162, fraccs. I, II y III, en relación con arts. 485 y 486, LFT (piso 1 SMG, tope 2 SMG).",
            },
        },
        "total_parcial_mxn": float(total),
        "conceptos_no_incluidos": [
            "Finiquito: salarios devengados no pagados, aguinaldo proporcional (art. 87), vacaciones y prima vacacional proporcionales (arts. 79 y 80).",
            "Salarios vencidos e intereses en juicio (art. 48, párrs. 2 y 3, LFT).",
            "Indemnización de 20 días por año (solo en supuestos de arts. 49, 50, 51 y 52 LFT).",
        ],
        "alertas_auditoria": alertas_auditoria,
    }


STOPWORDS_ES = {
    "de", "la", "el", "los", "las", "un", "una", "unos", "unas",
    "por", "para", "en", "y", "o", "a", "que", "es", "sobre",
    "con", "del", "al", "se", "su", "sus", "como", "mas", "art",
    "articulo", "articulos", "lft", "ley", "ano", "anos", "dia", "dias",
}


def _normalizar_sin_diacriticos(texto: str) -> str:
    """Elimina tildes y diéresis (ej. 'antigüedad' -> 'antiguedad', 'días' -> 'dias')."""
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def buscar_normativa_lft(consulta: str) -> dict:
    """
    Busca reglas jurídicas en lft_local.db usando FTS5/BM25 con normalización
    de acentos/diéresis y estrategia escalonada (frase exacta -> AND -> OR).
    """
    if not consulta or len(consulta) > 300:
        return {
            "estado": "ERROR",
            "mensaje": "La consulta está vacía o excede el límite permitido de 300 caracteres.",
        }

    texto_limpio = _normalizar_sin_diacriticos(consulta)
    tokens_crudos = re.findall(r"[a-z0-9]+", texto_limpio)
    tokens_filtrados = [
        t for t in tokens_crudos
        if t not in STOPWORDS_ES and (len(t) > 1 or t.isdigit())
    ][:12]

    if not tokens_filtrados:
        return {
            "estado": "ERROR",
            "mensaje": "La consulta debe incluir términos jurídicos específicos (ej. 'prescripcion', '2 meses', '517', 'antiguedad').",
        }

    def _formato_token(tok: str) -> str:
        # Los números se buscan exactos (evita que '2' coincida con '20' o '25')
        return tok if tok.isdigit() else f"{tok}*"

    consultas_escalonadas = []
    if len(tokens_filtrados) > 1:
        frase = " ".join(tokens_filtrados)
        consultas_escalonadas.append(("FRASE_EXACTA", f'"{frase}"'))
        consultas_escalonadas.append(("AND", " AND ".join(_formato_token(t) for t in tokens_filtrados)))
    consultas_escalonadas.append(("OR", " OR ".join(_formato_token(t) for t in tokens_filtrados)))

    try:
        with closing(_abrir_conexion_lectura()) as conexion:
            cursor = conexion.cursor()
            resultados = []
            estrategia_usada = None
            for nombre_estrategia, query_fts in consultas_escalonadas:
                cursor.execute(
                    """
                    SELECT articulo, titulo_tema, regla_normativa, url_oficial
                    FROM articulos_lft_fts
                    WHERE articulos_lft_fts MATCH ?
                    ORDER BY rank
                    LIMIT 5
                    """,
                    (query_fts,),
                )
                resultados = cursor.fetchall()
                if resultados:
                    estrategia_usada = nombre_estrategia
                    break
    except (FileNotFoundError, sqlite3.Error) as exc:
        return {
            "estado": "ERROR_DATO_NORMATIVO",
            "mensaje": f"Error al consultar el índice FTS5 en lft_local.db: {exc}",
        }

    if not resultados:
        return {
            "estado": "SIN_RESULTADOS",
            "mensaje": f"No se encontraron artículos indexados para: {consulta}",
        }

    return {
        "estado": "OK",
        "estrategia_busqueda": estrategia_usada,
        "resultados": [
            {
                "articulo": fila[0],
                "tema": fila[1],
                "regla_normativa": fila[2],
                "fuente_oficial": fila[3],
            }
            for fila in resultados
        ],
    }