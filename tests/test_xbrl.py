import unittest
from pathlib import Path

from eeff_analyzer.xbrl import XbrlInstance
from eeff_analyzer.analysis import calculate_ratios
from eeff_analyzer.historical import filter_by_entity, load_local_cases, ratio_history, statement_history
from eeff_analyzer.quality import balance_check


ROOT = Path(__file__).parents[1]


def case_directory() -> Path:
    """Carpeta con los ZIP de Aguas Andinas.

    Los tests no dependen de cómo esté organizado data/raw: sirven tanto si los
    ZIP están sueltos en la raíz como si están dentro de una carpeta por
    empresa (data/raw/aguas_andinas), que es la organización recomendada.
    """
    raw = ROOT / "data" / "raw"
    if raw.is_dir():
        for candidate in sorted(raw.iterdir()):
            if candidate.is_dir() and any(candidate.glob("aguas_andinas_*.zip")):
                return candidate
    return raw


CASE_DIRECTORY = case_directory()
CASE = CASE_DIRECTORY / "aguas_andinas_2025_12_xbrl.zip"


class TestAguasAndinasXbrl(unittest.TestCase):
    def test_reads_aguas_andinas_instance(self):
        instance = XbrlInstance.from_file(CASE)
        self.assertGreater(len(instance.facts), 100)
        self.assertIn("2025-12-31", instance.periods())

    def test_finds_total_assets_for_closing_date(self):
        instance = XbrlInstance.from_file(CASE)
        fact = instance.find_fact("Assets", "2025-12-31")
        self.assertIsNotNone(fact)
        self.assertEqual(fact.value, 3160940487000)

    def test_validates_balance_equation(self):
        instance = XbrlInstance.from_file(CASE)
        check = balance_check(instance, "2025-12-31")
        self.assertEqual(check["Estado"], "Validado")
        self.assertEqual(check["Diferencia"], 0)

    def test_calculates_liquidity_ratio(self):
        instance = XbrlInstance.from_file(CASE)
        ratios = calculate_ratios(instance, "2025-12-31")
        liquidity = ratios.loc[ratios["Indicador"] == "Liquidez corriente"].iloc[0]
        self.assertEqual(liquidity["Estado"], "Calculado")
        self.assertAlmostEqual(float(liquidity["Valor"]), 1.2474, places=4)

    def test_calculates_working_capital_and_dupont(self):
        instance = XbrlInstance.from_file(CASE)
        ratios = calculate_ratios(instance, "2025-12-31").set_index("Indicador")
        self.assertEqual(ratios.loc["Capital de trabajo", "Valor"], 69244374000)
        self.assertAlmostEqual(float(ratios.loc["ROE Du Pont al cierre", "Valor"]), 10.5679, places=4)

    def test_loads_local_history(self):
        # El ZIP de 2022 traía un error de tageo en el XBRL fuente: sus 824 contextos
        # usaban el RUT de otra entidad (90413000-1) en vez del de Aguas Andinas
        # (61808000-5), aunque los montos coinciden exactamente con los estados
        # financieros oficiales de Aguas Andinas a esa fecha. Se corrigió el RUT
        # dentro del propio archivo (ver data/raw_originales_sin_corregir/ para el
        # original), por lo que ya no hay ningún cierre excluido en esta carpeta.
        all_cases = load_local_cases(CASE_DIRECTORY)
        cases, excluded = filter_by_entity(all_cases, "61808000-5")
        self.assertGreaterEqual(len(cases), 2)
        self.assertEqual(excluded, [])
        periods = [case.closing_date for case in cases]
        self.assertEqual(periods, sorted(periods))
        self.assertIn("2025-12-31", periods)
        self.assertFalse(statement_history(cases, [("", "Assets", "Activos")]).empty)
        ratios = ratio_history(cases)
        self.assertIn("Liquidez corriente", ratios["Indicador"].tolist())
        roa_average = ratios.loc[ratios["Indicador"] == "ROA con activos promedio", "2025-12-31"].iloc[0]
        self.assertGreater(float(roa_average), 0)


if __name__ == "__main__":
    unittest.main()
