"""Consolidación temporal de instancias XBRL locales, sin descargas ni IA."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd

from .analysis import RATIO_EXPLANATIONS, calculate_ratios
from .inflation import adjustment_factor
from .xbrl import XbrlInstance


@dataclass(frozen=True)
class HistoricalCase:
    path: Path
    closing_date: str
    entity_identifier: str | None
    instance: XbrlInstance
    entity_name: str | None = None


def company_folders(directory: str | Path) -> list[dict]:
    """Lista las carpetas de empresa dentro de data/raw, sin abrir ningún ZIP.

    Cada subcarpeta que contenga al menos un ZIP se ofrece como una empresa. Los
    ZIP sueltos en la raíz también se ofrecen, para no romper repositorios que
    todavía no están organizados por carpetas.

    Esta función es deliberadamente barata: solo mira nombres de archivo. Así,
    abrir la aplicación no obliga a parsear el repositorio completo; se lee solo
    la carpeta que el usuario elija.
    """
    root = Path(directory)
    if not root.is_dir():
        return []
    options = [
        {"label": path.name, "path": path}
        for path in sorted(root.iterdir())
        if path.is_dir() and any(path.glob("*.zip"))
    ]
    if any(root.glob("*.zip")):
        options.append({"label": "ZIP sueltos en data/raw", "path": root})
    return options


def load_local_cases(directory: str | Path) -> list[HistoricalCase]:
    """Lee cada ZIP XBRL de una carpeta y usa su último cierre informado."""
    cases = []
    for path in sorted(Path(directory).glob("*.zip")):
        instance = XbrlInstance.from_file(path)
        periods = instance.periods()
        if not periods:
            continue
        entities = instance.entity_identifiers()
        entity_identifier = next(iter(entities)) if len(entities) == 1 else None
        cases.append(HistoricalCase(
            path=path,
            closing_date=max(periods),
            entity_identifier=entity_identifier,
            instance=instance,
            entity_name=instance.entity_name(entity_identifier) if entity_identifier else None,
        ))
    cases.sort(key=lambda case: case.closing_date)
    _validate_periods(cases)
    return cases


def _validate_periods(cases: list[HistoricalCase]) -> None:
    """Evita mezclar dos ZIP de la MISMA entidad con el mismo cierre.

    Distintas entidades sí pueden compartir fecha de cierre (por ejemplo, todas
    con cierre 31-12): eso es normal y no es un error. Lo que sí es un error es
    tener dos archivos que digan ser la misma entidad con el mismo cierre.
    """
    seen: dict[tuple[str | None, str], Path] = {}
    for case in cases:
        key = (case.entity_identifier, case.closing_date)
        if key in seen:
            raise ValueError(
                "Hay más de un ZIP con el mismo período de cierre para la misma entidad: "
                f"{seen[key].name} y {case.path.name} (RUT {case.entity_identifier or 'sin RUT'}, "
                f"cierre {case.closing_date})."
            )
        seen[key] = case.path


def filter_by_entity(cases: Iterable[HistoricalCase], entity_identifier: str | None) -> tuple[list[HistoricalCase], list[HistoricalCase]]:
    """Separa casos de la entidad seleccionada de los ZIP inconsistentes."""
    cases = list(cases)
    if not entity_identifier:
        return cases, []
    included = [case for case in cases if case.entity_identifier == entity_identifier]
    excluded = [case for case in cases if case.entity_identifier != entity_identifier]
    return included, excluded


def entity_options(cases: Iterable[HistoricalCase]) -> list[dict]:
    """Agrupa los ZIP locales por entidad (RUT) para elegir con cuál empresa trabajar.

    Un ZIP sin RUT identificable (entity_identifier ausente o ambiguo) no se
    ofrece como opción: por seguridad, no se puede elegir ni mezclar con nada.
    """
    groups: dict[str, list[HistoricalCase]] = {}
    for case in cases:
        if not case.entity_identifier:
            continue
        groups.setdefault(case.entity_identifier, []).append(case)

    options = []
    for entity_identifier, group in groups.items():
        group = sorted(group, key=lambda case: case.closing_date)
        # El nombre declarado puede variar levemente entre años (p. ej. "Y FILIALES"
        # aparece o desaparece); se usa el del cierre más reciente como el vigente.
        display_name = next((case.entity_name for case in reversed(group) if case.entity_name), None)
        options.append({
            "entity_identifier": entity_identifier,
            "display_name": display_name,
            "cases": group,
            "latest_case": group[-1],
        })
    options.sort(key=lambda option: option["display_name"] or option["entity_identifier"])
    return options


def statement_history(cases: Iterable[HistoricalCase], catalog: Iterable[tuple[str, str, str]]) -> pd.DataFrame:
    cases = list(cases)
    rows = []
    for statement, concept, fallback_label in catalog:
        row = {"Estado": statement, "Concepto XBRL": concept, "Cuenta": fallback_label}
        for case in cases:
            fact = case.instance.find_fact(concept, case.closing_date)
            row[case.closing_date] = fact.value if fact else None
        rows.append(row)
    return pd.DataFrame(rows)


def ratio_history(cases: Iterable[HistoricalCase]) -> pd.DataFrame:
    cases = list(cases)
    rows: dict[str, dict] = {}
    for case in cases:
        ratios = calculate_ratios(case.instance, case.closing_date)
        for _, ratio in ratios.iterrows():
            name = ratio["Indicador"]
            rows.setdefault(name, {
                "Indicador": name,
                "Unidad": ratio["Unidad"],
                "Fórmula": ratio["Fórmula"],
                "Interpretación": ratio.get("Interpretación", ""),
            })[case.closing_date] = ratio["Valor"] if ratio["Estado"] == "Calculado" else None
    _append_average_balance_ratios(rows, cases)
    _append_leverage_degrees(rows, cases)
    return pd.DataFrame(rows.values())


def _append_leverage_degrees(rows: dict[str, dict], cases: list[HistoricalCase]) -> None:
    """Agrega los grados de apalancamiento operativo, financiero y combinado.

    Se calculan sobre variaciones porcentuales entre cierres consecutivos, por lo
    que el primer período queda vacío por construcción. Si la variación del
    denominador es cero el cociente no tiene sentido económico, así que en ese
    caso se deja vacío en vez de informar un número engañoso.
    """
    definitions = [
        ("Grado de apalancamiento operativo (GAO)", "ProfitLossFromOperatingActivities", "Revenue",
         "Variación % del resultado operacional / Variación % de los ingresos"),
        ("Grado de apalancamiento financiero (GAF)", "ProfitLoss", "ProfitLossFromOperatingActivities",
         "Variación % de la utilidad neta / Variación % del resultado operacional"),
    ]
    for name, _, _, formula in definitions:
        rows[name] = {"Indicador": name, "Unidad": "Veces", "Fórmula": formula, "Interpretación": RATIO_EXPLANATIONS.get(name, "")}
    combined = "Grado de apalancamiento combinado (GAC)"
    rows[combined] = {
        "Indicador": combined,
        "Unidad": "Veces",
        "Fórmula": "GAO x GAF",
        "Interpretación": RATIO_EXPLANATIONS.get(combined, ""),
    }

    for previous, current in zip(cases, cases[1:]):
        consecutive_periods = date.fromisoformat(current.closing_date).year - date.fromisoformat(previous.closing_date).year == 1
        for name, numerator, denominator, _ in definitions:
            value = None
            if consecutive_periods:
                numerator_change = _percentage_variation(previous, current, numerator)
                denominator_change = _percentage_variation(previous, current, denominator)
                if numerator_change is not None and denominator_change is not None and denominator_change != 0:
                    value = numerator_change / denominator_change
            rows[name][current.closing_date] = value
        operating = rows[definitions[0][0]][current.closing_date]
        financial = rows[definitions[1][0]][current.closing_date]
        rows[combined][current.closing_date] = None if operating is None or financial is None else operating * financial


def _percentage_variation(previous: HistoricalCase, current: HistoricalCase, concept: str):
    """Variación porcentual de una cuenta entre dos cierres. None si falta un dato.

    Se divide por el valor absoluto del saldo anterior para que el signo del
    resultado refleje la dirección real del cambio incluso si la base es negativa.
    """
    previous_fact = previous.instance.find_fact(concept, previous.closing_date)
    current_fact = current.instance.find_fact(concept, current.closing_date)
    if not previous_fact or not current_fact or previous_fact.value == 0:
        return None
    return (current_fact.value - previous_fact.value) / abs(previous_fact.value) * 100


def _append_average_balance_ratios(rows: dict[str, dict], cases: list[HistoricalCase]) -> None:
    """Agrega razones que usan el saldo medio entre el cierre actual y previo.

    El primer período queda vacío de forma deliberada: no existe un saldo inicial
    en la serie local con el cual formar el promedio.
    """
    definitions = [
        ("Rotación de activos promedio", "Veces", "Revenue", "Assets", "Ingresos / Activos promedio"),
        ("ROA con activos promedio", "%", "ProfitLoss", "Assets", "Ganancia (pérdida) / Activos promedio"),
        ("ROE con patrimonio promedio", "%", "ProfitLoss", "Equity", "Ganancia (pérdida) / Patrimonio promedio"),
    ]
    for name, unit, numerator, balance, formula in definitions:
        rows[name] = {"Indicador": name, "Unidad": unit, "Fórmula": formula, "Interpretación": RATIO_EXPLANATIONS.get(name, "")}

    for previous, current in zip(cases, cases[1:]):
        consecutive_periods = date.fromisoformat(current.closing_date).year - date.fromisoformat(previous.closing_date).year == 1
        for name, unit, numerator, balance, _ in definitions:
            numerator_fact = current.instance.find_fact(numerator, current.closing_date)
            opening_fact = previous.instance.find_fact(balance, previous.closing_date)
            closing_fact = current.instance.find_fact(balance, current.closing_date)
            if not consecutive_periods or not numerator_fact or not opening_fact or not closing_fact:
                rows[name][current.closing_date] = None
                continue
            average_balance = (opening_fact.value + closing_fact.value) / 2
            value = None if average_balance == 0 else numerator_fact.value / average_balance
            rows[name][current.closing_date] = value * 100 if value is not None and unit == "%" else value


def real_statement_history(amounts: pd.DataFrame, cases: Iterable[HistoricalCase], base_year: int) -> pd.DataFrame:
    """Convierte cada columna de período de `amounts` a pesos de `base_year`.

    Usa el IPC del INE medido diciembre a diciembre (ver `inflation.py`), que es
    la ventana correcta para comparar cierres de balance del 31 de diciembre —
    no la corrección monetaria tributaria del SII, que mide noviembre a
    noviembre para otro propósito. Si falta el factor de algún año (por
    ejemplo, un año fuera de la tabla mantenida a mano), esa columna queda en
    None en vez de mostrar una cifra incorrecta.
    """
    cases = list(cases)
    result = amounts[["Estado", "Concepto XBRL", "Cuenta"]].copy()
    for case in cases:
        year = int(case.closing_date[:4])
        factor = adjustment_factor(year, base_year)
        if factor is None:
            result[case.closing_date] = None
        else:
            result[case.closing_date] = amounts[case.closing_date].map(
                lambda value: None if pd.isna(value) else value * factor
            )
    return result


def percentage_change(frame: pd.DataFrame, period_columns: list[str]) -> pd.DataFrame:
    """Calcula variación porcentual interanual para una tabla con columnas de períodos."""
    result = frame[["Estado", "Concepto XBRL", "Cuenta"]].copy()
    for previous, current in zip(period_columns, period_columns[1:]):
        base = pd.to_numeric(frame[previous], errors="coerce")
        value = pd.to_numeric(frame[current], errors="coerce")
        result[f"{current} vs {previous}"] = (value / base - 1) * 100
    return result


def vertical_analysis(frame: pd.DataFrame, period_columns: list[str]) -> pd.DataFrame:
    """Análisis vertical: cada partida como porcentaje de una base del mismo período.

    La base depende del estado al que pertenece la cuenta: las partidas de balance
    se expresan sobre activos totales y las de resultados sobre ingresos, que es la
    convención del análisis vertical. Las cuentas de flujo de efectivo se dejan
    fuera porque no tienen una base natural dentro de esta misma tabla.
    """
    bases = {
        "Estado de situación financiera": "Assets",
        "Estado de resultados": "Revenue",
    }
    rows = frame[frame["Estado"].isin(bases)].copy()
    result = rows[["Estado", "Concepto XBRL", "Cuenta"]].copy()
    for period in period_columns:
        values = pd.to_numeric(rows[period], errors="coerce")
        base_values = []
        for statement in rows["Estado"]:
            base_concept = bases[statement]
            match = frame.loc[frame["Concepto XBRL"] == base_concept, period]
            base = pd.to_numeric(match, errors="coerce").iloc[0] if not match.empty else None
            base_values.append(None if base in (None, 0) or pd.isna(base) else base)
        result[period] = [
            None if pd.isna(value) or base is None else value / base * 100
            for value, base in zip(values, base_values)
        ]
    return result


def horizontal_analysis(frame: pd.DataFrame, period_columns: list[str]) -> pd.DataFrame:
    """Análisis horizontal en números índice, con base 100 en el primer período.

    Un índice de 130 significa que la cuenta está 30% por encima de su nivel del
    año base. Si la cuenta no tiene dato en el año base no se puede indexar y la
    fila queda vacía, en vez de mostrar una serie sin punto de comparación.
    """
    result = frame[["Estado", "Concepto XBRL", "Cuenta"]].copy()
    if not period_columns:
        return result
    base_period = period_columns[0]
    base_values = pd.to_numeric(frame[base_period], errors="coerce")
    for period in period_columns:
        values = pd.to_numeric(frame[period], errors="coerce")
        result[period] = [
            None if pd.isna(value) or pd.isna(base) or base == 0 else value / base * 100
            for value, base in zip(values, base_values)
        ]
    return result
