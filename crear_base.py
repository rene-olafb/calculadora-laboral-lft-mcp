import sqlite3

DB_NAME = "lft_local.db"


def inicializar_base_datos():
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()

    # 1. Tabla de Salarios Mínimos con control de gobernanza y trazabilidad
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS salarios_minimos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anio INTEGER NOT NULL,
            zona TEXT NOT NULL,
            monto_diario REAL NOT NULL,
            vigencia_inicio TEXT NOT NULL,
            vigencia_fin TEXT NOT NULL,
            fuente_dof TEXT NOT NULL,
            verificado_dof INTEGER NOT NULL CHECK (verificado_dof IN (0, 1))
        )
    """)

    # 2. Tabla maestra de artículos relevantes de la LFT
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articulos_lft (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            articulo TEXT NOT NULL,
            titulo_tema TEXT NOT NULL,
            regla_normativa TEXT NOT NULL,
            url_oficial TEXT NOT NULL
        )
    """)

    # 3. Tabla virtual FTS5 para búsqueda léxica rápida (motor de búsqueda)
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS articulos_lft_fts USING fts5(
            articulo,
            titulo_tema,
            regla_normativa
        )
    """)

    # Limpiamos registros previos para evitar duplicados si ejecutas el script varias veces
    cursor.execute("DELETE FROM salarios_minimos")
    cursor.execute("DELETE FROM articulos_lft")
    cursor.execute("DELETE FROM articulos_lft_fts")

    # Datos de salarios mínimos (1 = verificado en DOF; 0 = pendiente de cotejo primario)
    salarios = [
        (2024, "general", 248.93, "2024-01-01", "2024-12-31", "DOF 12-12-2023 (Resolución CONASAMI)", 1),
        (2025, "general", 278.80, "2025-01-01", "2025-12-31", "DOF 19-12-2024 (Resolución CONASAMI)", 1),
        (2026, "general", 315.04, "2026-01-01", "2026-12-31", "Resolución CONASAMI dic-2025 (Pendiente cotejo directo DOF)", 0),
    ]

    cursor.executemany("""
        INSERT INTO salarios_minimos (
            anio, zona, monto_diario, vigencia_inicio, vigencia_fin, fuente_dof, verificado_dof
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, salarios)

    # Síntesis normativa estructurada con fundamento exacto
    url_lft = "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFT.pdf"
    articulos = [
        (
            "Art. 47, fraccs. I-XV y párrs. penúltimo y antepenúltimo",
            "Rescisión justificada y aviso de despido",
            "Enumera las causas de rescisión sin responsabilidad para el patrón. Exige entregar aviso escrito al trabajador en el momento del despido o comunicarlo al Tribunal dentro de los 5 días hábiles siguientes si el trabajador se niega a recibirlo. La falta de aviso presume la separación injustificada.",
            url_lft,
        ),
        (
            "Art. 48, párrs. 1, 2 y 3",
            "Indemnización constitucional y salarios vencidos",
            "En despido injustificado el trabajador puede pedir reinstalación o indemnización de 3 meses de salario (90 días). Incluye salarios vencidos desde el despido hasta por 12 meses; si el juicio excede ese plazo, se pagan intereses del 2% mensual sobre el importe de 15 meses de salario.",
            url_lft,
        ),
        (
            "Arts. 49 y 50, fraccs. I, II y III",
            "Indemnización de 20 días por año de servicio",
            "La indemnización de 20 días de salario por cada año de servicios prestados (art. 50, fracc. II, para tiempo indeterminado) no aplica automáticamente a todo despido, sino cuando el patrón queda eximido de reinstalar (art. 49) o en rescisión imputable al patrón (art. 51).",
            url_lft,
        ),
        (
            "Art. 76, párrs. 1 y 2",
            "Días mínimos de vacaciones por antigüedad",
            "Personas trabajadoras con más de un año de servicios disfrutan de un periodo anual de vacaciones pagadas de al menos 12 días laborables, aumentando en 2 días por cada año subsecuente hasta llegar a 20 días (en el quinto año). A partir del sexto año aumenta 2 días por cada 5 de servicios.",
            url_lft,
        ),
        (
            "Arts. 80 y 87",
            "Prima vacacional y aguinaldo mínimo legal",
            "El art. 80 fija una prima vacacional mínima del 25% sobre los salarios correspondientes al periodo de vacaciones. El art. 87 establece un aguinaldo anual mínimo equivalente a 15 días de salario, pagadero antes del 20 de diciembre, o su parte proporcional.",
            url_lft,
        ),
        (
            "Arts. 84 y 89, párr. 1",
            "Salario Diario Integrado (SDI) para indemnizaciones",
            "El art. 84 dispone que el salario se integra con los pagos en efectivo por cuota diaria, gratificaciones, percepciones, habitación, primas, comisiones y prestaciones en especie. El art. 89 ordena usar este salario integrado como base para determinar indemnizaciones.",
            url_lft,
        ),
        (
            "Art. 162, fraccs. I, II y III; Arts. 485 y 486",
            "Prima de antigüedad y tope de 2 salarios mínimos",
            "Consiste en el importe de 12 días de salario por cada año de servicios (art. 162, fracc. I). En despido injustificado se paga sin importar la antigüedad (fracc. III). Conforme a la fracc. II y los arts. 485 y 486, la base salarial tiene piso de 1 SMG y tope máximo de 2 salarios mínimos.",
            url_lft,
        ),
        (
            "Arts. 516 y 518, párr. 1",
            "Plazos de prescripción en materia laboral",
            "El art. 516 fija la regla general de prescripción de 1 año para acciones de trabajo. Sin embargo, el art. 518, párr. 1, establece la regla especial de 2 meses para las acciones de los trabajadores que sean separados del trabajo, contados a partir del día siguiente a la separación.",
            url_lft,
        ),
    ]

    cursor.executemany("""
        INSERT INTO articulos_lft (articulo, titulo_tema, regla_normativa, url_oficial)
        VALUES (?, ?, ?, ?)
    """, articulos)

    # Sincronizamos el índice de búsqueda FTS5
    cursor.execute("""
        INSERT INTO articulos_lft_fts (articulo, titulo_tema, regla_normativa)
        SELECT articulo, titulo_tema, regla_normativa FROM articulos_lft
    """)

    conexion.commit()
    conexion.close()
    print(f"Base de datos '{DB_NAME}' creada y poblada correctamente.")


if __name__ == "__main__":
    inicializar_base_datos()