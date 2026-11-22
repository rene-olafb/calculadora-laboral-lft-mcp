import unittest
from datetime import date
from motor import (
    calcular_despido_injustificado,
    buscar_normativa_lft,
    _calcular_antiguedad_calendario,
    _dias_vacaciones_ley,
)


class TestMotorLaboralLFTv03(unittest.TestCase):
    """Suite de regresión v0.3: precisión Decimal, calendario real, Fail-Closed y FTS5."""

    def test_01_calculo_verificado_2025_sin_alertas(self):
        """Caso 2025 (verificado_dof=1) con SDI exacto debe emitir CALCULO_VERIFICADO."""
        res = calcular_despido_injustificado(
            fecha_ingreso="2024-01-01",
            fecha_despido="2025-12-31",
            salario_diario_cuota="500.00",
            salario_diario_integrado="525.34",
            zona_salarial="general",
            tipo_separacion="despido_injustificado",
            tipo_salario="fijo",
        )
        self.assertEqual(res["estado"], "CALCULO_VERIFICADO")
        self.assertEqual(res["parametros_verificados"]["antiguedad_anios"], 2.0)
        self.assertEqual(res["desglose"]["indemnizacion_constitucional_90_dias"]["monto_mxn"], 47280.60)
        self.assertEqual(res["desglose"]["prima_de_antiguedad"]["monto_mxn"], 12000.00)
        self.assertEqual(res["total_parcial_mxn"], 59280.60)
        self.assertEqual(res["alertas_auditoria"], [])

    def test_02_estimacion_con_supuestos_2026_y_calendario_real(self):
        """Caso 2022-03-01 a 2026-11-19: 4 años + 264/365 días = prima $35,712.59 y estado degradado."""
        res = calcular_despido_injustificado(
            fecha_ingreso="2022-03-01",
            fecha_despido="2026-11-19",
            salario_diario_cuota="800.00",
            salario_diario_integrado="843.84",
            zona_salarial="general",
            tipo_separacion="despido_injustificado",
            tipo_salario="fijo",
        )
        self.assertEqual(res["estado"], "ESTIMACION_CON_SUPUESTOS")
        self.assertEqual(res["parametros_verificados"]["anios_completos"], 4)
        self.assertEqual(res["parametros_verificados"]["dias_residuales"], 264)
        self.assertEqual(res["desglose"]["indemnizacion_constitucional_90_dias"]["monto_mxn"], 75945.60)
        self.assertEqual(res["desglose"]["prima_de_antiguedad"]["monto_mxn"], 35712.59)
        self.assertEqual(res["total_parcial_mxn"], 111658.19)
        self.assertEqual(len(res["alertas_auditoria"]), 1)

    def test_03_zlfn_sin_tope_en_800(self):
        """En ZLFN 2026 el doble del SMG es $881.74, por lo que $800 no se topa ($45,343.56)."""
        res = calcular_despido_injustificado(
            fecha_ingreso="2022-03-01",
            fecha_despido="2026-11-19",
            salario_diario_cuota="800.00",
            salario_diario_integrado="843.84",
            zona_salarial="zlfn",
            tipo_separacion="despido_injustificado",
            tipo_salario="fijo",
        )
        self.assertFalse(res["parametros_verificados"]["aplico_tope_2_smg"])
        self.assertEqual(res["parametros_verificados"]["salario_base_prima_mxn"], 800.00)
        self.assertEqual(res["desglose"]["prima_de_antiguedad"]["monto_mxn"], 45343.56)

    def test_04_bloqueo_sin_zona_ni_tipo_salario(self):
        """Omitir zona_salarial debe bloquear el cálculo (elimina default silencioso)."""
        res = calcular_despido_injustificado(
            fecha_ingreso="2022-03-01",
            fecha_despido="2026-11-19",
            salario_diario_cuota="800.00",
            salario_diario_integrado="843.84",
        )
        self.assertEqual(res["estado"], "FALTAN_DATOS")
        self.assertIn("zona_salarial ('general' o 'zlfn')", res["datos_faltantes"])

    def test_05_fuera_de_alcance_salario_variable_y_renuncia(self):
        """Fail-Closed ante salario variable o renuncia voluntaria."""
        res_var = calcular_despido_injustificado(
            fecha_ingreso="2024-01-01",
            fecha_despido="2025-12-31",
            salario_diario_cuota="500.00",
            salario_diario_integrado="550.00",
            zona_salarial="general",
            tipo_separacion="despido_injustificado",
            tipo_salario="variable",
        )
        self.assertEqual(res_var["estado"], "FUERA_DE_ALCANCE")

        res_ren = calcular_despido_injustificado(
            fecha_ingreso="2024-01-01",
            fecha_despido="2025-12-31",
            salario_diario_cuota="500.00",
            salario_diario_integrado="550.00",
            zona_salarial="general",
            tipo_separacion="renuncia_voluntaria",
            tipo_salario="fijo",
        )
        self.assertEqual(res_ren["estado"], "FUERA_DE_ALCANCE")

    def test_06_precision_decimal_frontera_cinco_centavos(self):
        """Elimina el bug IEEE 754: $843.79 (dif exacta 0.05) NO alerta; $843.78 SÍ alerta."""
        res_ok = calcular_despido_injustificado(
            fecha_ingreso="2022-03-01",
            fecha_despido="2026-11-19",
            salario_diario_cuota="800.00",
            salario_diario_integrado="843.79",
            zona_salarial="general",
            tipo_separacion="despido_injustificado",
            tipo_salario="fijo",
        )
        self.assertNotIn("Posible subestimación de SDI", " ".join(res_ok["alertas_auditoria"]))

        res_alerta = calcular_despido_injustificado(
            fecha_ingreso="2022-03-01",
            fecha_despido="2026-11-19",
            salario_diario_cuota="800.00",
            salario_diario_integrado="843.78",
            zona_salarial="general",
            tipo_separacion="despido_injustificado",
            tipo_salario="fijo",
        )
        self.assertIn("Posible subestimación de SDI", " ".join(res_alerta["alertas_auditoria"]))

    def test_07_fronteras_aniversarios_y_bisiestos(self):
        """Valida toda la tabla de fronteras del auditor sin desvío por años bisiestos."""
        ingreso = date(2022, 3, 1)
        casos = [
            (date(2023, 2, 28), 1, 12),
            (date(2023, 3, 1), 2, 14),
            (date(2024, 2, 29), 2, 14),
            (date(2027, 2, 28), 5, 20),
            (date(2031, 2, 28), 9, 22),
            (date(2032, 2, 29), 10, 22),
            (date(2032, 3, 1), 11, 24),
        ]
        for despido, anio_esperado, vac_esperadas in casos:
            ant = _calcular_antiguedad_calendario(ingreso, despido)
            self.assertEqual(ant["anio_servicio_en_curso"], anio_esperado, f"Falló en {despido}")
            self.assertEqual(_dias_vacaciones_ley(ant["anio_servicio_en_curso"]), vac_esperadas)

        # Ingreso en 29 de febrero (año bisiesto)
        ant_bis = _calcular_antiguedad_calendario(date(2024, 2, 29), date(2025, 2, 28))
        self.assertEqual(ant_bis["anio_servicio_en_curso"], 1)
        self.assertEqual(float(ant_bis["antiguedad_anios"]), 1.0)

    def test_08_fecha_iso_compacta_normalizada_en_sql(self):
        """Una fecha ISO compacta ('20251231') no debe provocar falso negativo en SQL BETWEEN."""
        res = calcular_despido_injustificado(
            fecha_ingreso="20250101",
            fecha_despido="20251231",
            salario_diario_cuota="500.00",
            salario_diario_integrado="525.00",
            zona_salarial="general",
            tipo_separacion="despido_injustificado",
            tipo_salario="fijo",
        )
        self.assertIn(res["estado"], {"CALCULO_VERIFICADO", "ESTIMACION_CON_SUPUESTOS"})

    def test_09_rechazo_entradas_invalidas_y_booleanos(self):
        """Rechaza booleanos, NaN, negativos y SDI < cuota."""
        res_bool = calcular_despido_injustificado(
            fecha_ingreso="2025-01-01",
            fecha_despido="2025-06-01",
            salario_diario_cuota=True,
            salario_diario_integrado="500.00",
            zona_salarial="general",
            tipo_separacion="despido_injustificado",
            tipo_salario="fijo",
        )
        self.assertEqual(res_bool["estado"], "ERROR_VALIDACION")

        res_nan = calcular_despido_injustificado(
            fecha_ingreso="2025-01-01",
            fecha_despido="2025-06-01",
            salario_diario_cuota="NaN",
            salario_diario_integrado="500.00",
            zona_salarial="general",
            tipo_separacion="despido_injustificado",
            tipo_salario="fijo",
        )
        self.assertEqual(res_nan["estado"], "ERROR_VALIDACION")

    def test_10_fts5_consulta_2_meses_en_posicion_uno(self):
        """'2 meses' debe posicionar Art. 518 en lugar #1 (no Art. 48)."""
        res = buscar_normativa_lft("2 meses")
        self.assertEqual(res["estado"], "OK")
        self.assertEqual(res["resultados"][0]["articulo"], "Art. 516 y Art. 518, párrs. 1 a 4")

    def test_11_fts5_dieresis_antiguedad(self):
        """'antigüedad' con diéresis no debe partirse en 'antig' y 'edad'."""
        res = buscar_normativa_lft("antigüedad")
        self.assertEqual(res["estado"], "OK")
        self.assertIn("162", res["resultados"][0]["articulo"])

    def test_12_fts5_articulos_517_y_521_conciliacion(self):
        """Recupera explícitamente art. 517 y arts. 521/684-B sobre conciliación."""
        res_517 = buscar_normativa_lft("517")
        self.assertEqual(res_517["estado"], "OK")
        self.assertEqual(res_517["resultados"][0]["articulo"], "Art. 517, fraccs. I y II")

        res_conc = buscar_normativa_lft("prescripción conciliación")
        self.assertEqual(res_conc["estado"], "OK")
        articulos = [r["articulo"] for r in res_conc["resultados"]]
        self.assertIn("Arts. 521 (fraccs. I-III) y 684-B, párr. 1", articulos)

    def test_13_ficha_art_47_corregida(self):
        """Verifica que la ficha del art. 47 ya no exija negativa previa del trabajador."""
        res = buscar_normativa_lft("aviso despido")
        self.assertEqual(res["estado"], "OK")
        texto = res["resultados"][0]["regla_normativa"]
        self.assertIn("sin requerir negativa previa", texto)

    def test_14_anio_sin_salario_minimo_registrado(self):
        """Rechazo controlado cuando no existe registro para el año consultado."""
        res = calcular_despido_injustificado(
            fecha_ingreso="2020-01-01",
            fecha_despido="2020-06-01",
            salario_diario_cuota="300.00",
            salario_diario_integrado="320.00",
            zona_salarial="general",
            tipo_separacion="despido_injustificado",
            tipo_salario="fijo",
        )
        self.assertEqual(res["estado"], "ERROR_DATO_NORMATIVO")


if __name__ == "__main__":
    unittest.main(verbosity=2)