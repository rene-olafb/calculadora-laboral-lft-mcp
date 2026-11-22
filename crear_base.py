import sqlite3
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).parent / "lft_local.db"


def inicializar_base_datos():
    with closing(sqlite3.connect(DB_PATH)) as conexion:
        with conexion:
            cursor = conexion.cursor()

            # 1. Tabla de Salarios Mínimos con restricciones de integridad y gobernanza
            cursor.execute("DROP TABLE IF EXISTS salarios_minimos")
            cursor.execute("""
                CREATE TABLE salarios_minimos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    anio INTEGER NOT NULL,
                    zona TEXT NOT NULL CHECK (zona IN ('general', 'zlfn')),
                    monto_diario TEXT NOT NULL,
                    vigencia_inicio TEXT NOT NULL,
                    vigencia_fin TEXT NOT NULL,
                    fuente_dof TEXT NOT NULL,
                    verificado_dof INTEGER NOT NULL CHECK (verificado_dof IN (0, 1)),
                    CHECK (CAST(monto_diario AS REAL) > 0),
                    CHECK (vigencia_inicio <= vigencia_fin)
                )
            """)

            # 2. Tabla maestra de artículos relevantes de la LFT
            cursor.execute("DROP TABLE IF EXISTS articulos_lft")
            cursor.execute("""
                CREATE TABLE articulos_lft (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    articulo TEXT NOT NULL,
                    titulo_tema TEXT NOT NULL,
                    regla_normativa TEXT NOT NULL,
                    url_oficial TEXT NOT NULL
                )
            """)

            # 3. Tabla virtual FTS5 con url_oficial como columna no indexada
            cursor.execute("DROP TABLE IF EXISTS articulos_lft_fts")
            cursor.execute("""
                CREATE VIRTUAL TABLE articulos_lft_fts USING fts5(
                    articulo,
                    titulo_tema,
                    regla_normativa,
                    url_oficial UNINDEXED
                )
            """)

            # Salarios mínimos almacenados como texto decimal exacto (1 = cotejado en DOF; 0 = pendiente)
            salarios = [
                (2024, "general", "248.93", "2024-01-01", "2024-12-31", "DOF 12-12-2023 (Resolución CONASAMI)", 1),
                (2024, "zlfn", "374.89", "2024-01-01", "2024-12-31", "DOF 12-12-2023 (Resolución CONASAMI)", 1),
                (2025, "general", "278.80", "2025-01-01", "2025-12-31", "DOF 19-12-2024 (Resolución CONASAMI)", 1),
                (2025, "zlfn", "419.88", "2025-01-01", "2025-12-31", "DOF 19-12-2024 (Resolución CONASAMI)", 1),
                (2026, "general", "315.04", "2026-01-01", "2026-12-31", "Resolución CONASAMI dic-2025 (Pendiente cotejo directo DOF)", 0),
                (2026, "zlfn", "440.87", "2026-01-01", "2026-12-31", "Resolución CONASAMI dic-2025 (Pendiente cotejo directo DOF)", 0),
            ]

            cursor.executemany("""
                INSERT INTO salarios_minimos (
                    anio, zona, monto_diario, vigencia_inicio, vigencia_fin, fuente_dof, verificado_dof
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, salarios)

            url_lft = "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFT.pdf"
            articulos = [
                (
                    "Art. 47, fraccs. I-XV y párrs. 2 a último",
                    "Rescisión justificada y aviso de despido",
                    "Enumera las causas de rescisión sin responsabilidad para el patrón. El aviso escrito con conductas y fechas debe entregarse personalmente al trabajador al momento del despido, o bien comunicarse al Tribunal competente dentro de los 5 días hábiles siguientes señalando el último domicilio registrado, sin requerir negativa previa. La prescripción no corre hasta la recepción personal del aviso; su falta presume separación injustificada salvo prueba en contrario.",
                    url_lft,
                ),
                (
                    "Art. 48, párrs. 1, 2, 3 y 4",
                    "Indemnización constitucional y salarios vencidos",
                    "En despido injustificado el trabajador puede solicitar reinstalación o indemnización de 3 meses de salario (90 días bajo base mensual de 30 días, art. 89 párr. 3). Si el patrón no comprueba la causa, proceden salarios vencidos hasta por 12 meses; si el juicio no concluye o no se cumple la sentencia, se generan intereses del 2% mensual sobre 15 meses de salario, capitalizables al pago.",
                    url_lft,
                ),
                (
                    "Arts. 49, 50 (fraccs. I-III), 51 y 52",
                    "Indemnización de 20 días por año de servicio",
                    "La indemnización de 20 días de salario por año de servicios (art. 50, fracc. II, para tiempo indeterminado) no opera automáticamente en todo despido injustificado. Procede en supuestos específicos como exención patronal de reinstalar (art. 49) o rescisión imputable al patrón (art. 51), donde el art. 52 otorga 30 días al trabajador para separarse y reclamar el art. 50.",
                    url_lft,
                ),
                (
                    "Art. 76, párrs. 1 y 2",
                    "Días mínimos de vacaciones por antigüedad",
                    "Personas trabajadoras con más de un año de servicios disfrutan de un periodo anual de vacaciones pagadas mínimo de 12 días laborables, aumentando 2 días por cada año subsecuente hasta llegar a 20 días en el quinto año. A partir del sexto año aumenta 2 días por cada 5 de servicios (22 días en años 6 a 10; 24 en años 11 a 15).",
                    url_lft,
                ),
                (
                    "Arts. 80 y 87",
                    "Prima vacacional y aguinaldo mínimo legal",
                    "El art. 80 fija una prima vacacional mínima del 25% sobre los salarios del periodo vacacional. El art. 87 establece un aguinaldo anual mínimo de 15 días de salario pagadero antes del 20 de diciembre, y su pago proporcional a quienes no hayan cumplido el año de servicios.",
                    url_lft,
                ),
                (
                    "Arts. 84 y 89, párrs. 1, 2 y 3",
                    "Salario Diario Integrado (SDI) para indemnizaciones",
                    "El art. 84 integra el salario con cuota diaria, gratificaciones, percepciones, habitación, primas, comisiones, prestaciones en especie y cualquier otra cantidad entregada por el trabajo. El art. 89 ordena usar este salario integrado para indemnizaciones; en salario variable (párr. 2) se promedian los últimos 30 días efectivamente trabajados.",
                    url_lft,
                ),
                (
                    "Art. 162, fraccs. I, II y III; Arts. 485 y 486",
                    "Prima de antigüedad y tope de 2 salarios mínimos",
                    "Para trabajadores de planta consiste en 12 días de salario por cada año de servicios (art. 162, fracc. I). En separación por despido justificado o injustificado se paga sin exigir 15 años de antigüedad (fracc. III). Por remisión de la fracc. II a los arts. 485 y 486, tiene piso de 1 SMG y tope de 2 salarios mínimos del área geográfica.",
                    url_lft,
                ),
                (
                    "Art. 516 y Art. 518, párrs. 1 a 4",
                    "Prescripción de 2 meses por despido y regla general de 1 año",
                    "El art. 516 fija la prescripción general de 1 año desde el día siguiente a que cada obligación sea exigible. El art. 518, párr. 1, establece el plazo especial de 2 meses para acciones de trabajadores separados del trabajo; el párr. 2 señala que corre desde el día siguiente a la separación, y los párrs. 3 y 4 regulan su suspensión por conciliación prejudicial.",
                    url_lft,
                ),
                (
                    "Art. 517, fraccs. I y II",
                    "Prescripción especial de 1 mes (patrón y separación del trabajador)",
                    "Prescriben en 1 mes: (fracc. I) las acciones de los patrones para despedir, disciplinar o efectuar descuentos a los trabajadores, desde que se conozca la causa; y (fracc. II) las acciones de los trabajadores para separarse del trabajo, desde que se conozca la causa de separación.",
                    url_lft,
                ),
                (
                    "Arts. 521 (fraccs. I-III) y 684-B, párr. 1",
                    "Interrupción y suspensión de la prescripción por conciliación",
                    "El art. 521 establece las causas de interrupción de la prescripción, incluyendo la presentación de la demanda (fracc. I) y la presentación de la solicitud de conciliación prejudicial ante el Centro de Conciliación competente (fracc. III, en relación con el art. 684-B), reanudándose el término al día siguiente en que concluya el procedimiento sin convenio.",
                    url_lft,
                ),
            ]

            cursor.executemany("""
                INSERT INTO articulos_lft (articulo, titulo_tema, regla_normativa, url_oficial)
                VALUES (?, ?, ?, ?)
            """, articulos)

            cursor.execute("""
                INSERT INTO articulos_lft_fts (articulo, titulo_tema, regla_normativa, url_oficial)
                SELECT articulo, titulo_tema, regla_normativa, url_oficial FROM articulos_lft
            """)

    print(f"Base de datos v0.3 '{DB_PATH.name}' creada y poblada correctamente.")


if __name__ == "__main__":
    inicializar_base_datos()