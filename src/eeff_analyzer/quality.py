"""Controles de consistencia contable para datos XBRL ya extraídos."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from .historical import HistoricalCase
from .xbrl import XbrlInstance


def balance_check(instance: XbrlInstance, period_end: str) -> dict:
    """Verifica Activos = Pasivos + Patrimonio para un período de cierre."""
    concepts = {concept: instance.find_fact(concept, period_end) for concept in ("Assets", "Liabilities", "Equity")}
    assets = concepts["Assets"].value if concepts["Assets"] else None
    liabilities = concepts["Liabilities"].value if concepts["Liabilities"] else None
    equity = concepts["Equity"].value if concepts["Equity"] else None
    difference = None if None in (assets, liabilities, equity) else assets - liabilities - equity
    return {
        "Activos": assets,
        "Pasivos + patrimonio": None if liabilities is None or equity is None else liabilities + equity,
        "Diferencia": difference,
        "Estado": "Validado" if difference == Decimal(0) else "Pendiente: falta una cuenta" if difference is None else "Diferencia detectada",
    }


def historical_quality(cases: list[HistoricalCase], selected_entity: str | None) -> pd.DataFrame:
    """Resumen de archivo, período, entidad y ecuación contable para cada ZIP local."""
    rows = []
    for case in cases:
        check = balance_check(case.instance, case.closing_date)
        included = case.entity_identifier == selected_entity if selected_entity else True
        rows.append({
            "Archivo": case.path.name,
            "Cierre": case.closing_date,
            "Entidad XBRL": case.entity_identifier or "No identificada",
            "Uso en la serie": "Incluido" if included else "Excluido: entidad distinta",
            "Ecuación contable": check["Estado"],
            "Diferencia": check["Diferencia"],
        })
    return pd.DataFrame(rows)
