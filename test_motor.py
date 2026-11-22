import unittest
from motor import calcular_despido_injustificado, buscar_normativa_lft


class TestMotorLaboralLFT(unittest.TestCase):
    """Batería de pruebas deterministas para validación aritmética, jurídica y de recuperación."""

    def test_01_calculo_valido_con_tope_y_sdi_correcto(self):
        """Caso 5.º año de servicio con SDI ajustado a 20 días de vacaciones (art. 76 LFT)."""
        res = calcular_despido_injustificado(
            fecha_ingreso="2022-03-01",
            fecha_despido="2026-11-19",
            salario_diario_cuota=800.00,
            salario_diario_integrado=843.84,
            zona_salarial="general",
        )
        self.assertEqual(res["estado"], "OK")
        self.assertEqual(res["parametros_verificados"]["dias_trabajados"], 1725)
        self.assertTrue(res["parametros_verificados"]["aplico_tope_2_smg"])
        self.assertEqual(res["parametros_verificados"]["salario_base_prima_mxn"], 630.08)
        self.assertEqual(
            res["desglose"]["indemnizacion_constitucional_90_dias"]["monto_mxn"], 75945.60
        )
        self.assertEqual(res["desglose"]["prima_de_antiguedad"]["monto_mxn"], 35733.30)
        self.assertEqual(res["total_parcial_mxn"], 111678.90)
        # Solo debe existir la alerta de gobernanza DOF=0, no de subestimación de SDI
        self.assertEqual(len(res["alertas_auditoria"]), 1)

    def test_02_bloqueo_datos_faltantes(self):
        """El motor debe detenerse si falta el SDI o fechas."""
        res = calcular_despido_injustificado(
            fecha_ingreso="2022-03-01",
            salario_diario_cuota=800.00,
        )
        self.assertEqual(res["estado"], "FALTAN_DATOS")
        self.assertIn("fecha_despido (formato YYYY-MM-DD)", res["datos_faltantes"])
        self.assertIn(
            "salario_diario_integrado (SDI para indemnización)", res["datos_faltantes"]
        )

    def test_03_contradiccion_fechas(self):
        """Rechazo cuando la fecha de despido es anterior al ingreso."""
        res = calcular_despido_injustificado(
            fecha_ingreso="2026-11-19",
            fecha_despido="2022-03-01",
            salario_diario_cuota=800.00,
            salario_diario_integrado=843.84,
        )
        self.assertEqual(res["estado"], "ERROR_VALIDACION")

    def test_04_contradiccion_sdi_menor_a_cuota(self):
        """Rechazo cuando el SDI es inferior a la cuota diaria (art. 84 LFT)."""
        res = calcular_despido_injustificado(
            fecha_ingreso="2025-01-01",
            fecha_despido="2025-12-31",
            salario_diario_cuota=500.00,
            salario_diario_integrado=480.00,
        )
        self.assertEqual(res["estado"], "ERROR_VALIDACION")

    def test_05_alerta_subestimacion_sdi_quinto_anio(self):
        """Detecta cuando el SDI corresponde a 12 días de vacaciones en lugar de 20 (art. 76 LFT)."""
        res = calcular_despido_injustificado(
            fecha_ingreso="2022-03-01",
            fecha_despido="2026-11-19",
            salario_diario_cuota=800.00,
            salario_diario_integrado=839.45,
        )
        self.assertEqual(res["estado"], "OK")
        alertas_texto = " ".join(res["alertas_auditoria"])
        self.assertIn("Posible subestimación de SDI", alertas_texto)
        self.assertIn("20 días de vacaciones", alertas_texto)

    def test_06_gobernanza_dato_no_verificado_dof(self):
        """Emite advertencia explícita cuando verificado_dof == 0 en SQLite."""
        res = calcular_despido_injustificado(
            fecha_ingreso="2026-01-01",
            fecha_despido="2026-06-01",
            salario_diario_cuota=400.00,
            salario_diario_integrado=420.00,
        )
        self.assertFalse(res["parametros_verificados"]["verificado_en_dof"])
        alertas_texto = " ".join(res["alertas_auditoria"])
        self.assertIn("verificado_dof=0", alertas_texto)

    def test_07_busqueda_fts5_ranking_bm25(self):
        """Verifica que BM25 posicione prescripción (art. 518) y 20 días (art. 50) en el top 2."""
        res = buscar_normativa_lft("prescripcion y 20 dias por ano")
        self.assertEqual(res["estado"], "OK")
        articulos = [r["articulo"] for r in res["resultados"]]
        self.assertEqual(articulos[0], "Arts. 516 y 518, párr. 1")
        self.assertEqual(articulos[1], "Arts. 49 y 50, fraccs. I, II y III")

    def test_08_fecha_sin_salario_minimo_registrado(self):
        """Rechazo controlado si se consulta un año fuera de la base de datos."""
        res = calcular_despido_injustificado(
            fecha_ingreso="2020-01-01",
            fecha_despido="2020-06-01",
            salario_diario_cuota=300.00,
            salario_diario_integrado=320.00,
        )
        self.assertEqual(res["estado"], "ERROR_DATO_NORMATIVO")


if __name__ == "__main__":
    unittest.main(verbosity=2)