"""Cálculos financieros reproducibles basados en conceptos XBRL."""

from __future__ import annotations

from decimal import Decimal, DivisionByZero, InvalidOperation

import pandas as pd

from .xbrl import XbrlInstance


RATIO_DEFINITIONS = [
    ("Liquidez corriente", "Veces", "CurrentAssets", "CurrentLiabilities", "Activo corriente / Pasivo corriente"),
    ("Prueba ácida", "Veces", "CurrentAssetsLessInventories", "CurrentLiabilities", "(Activo corriente - Inventarios) / Pasivo corriente"),
    ("Liquidez de caja", "Veces", "CashAndCashEquivalents", "CurrentLiabilities", "Efectivo y equivalentes / Pasivo corriente"),
    ("Endeudamiento sobre activos", "%", "Liabilities", "Assets", "Pasivos totales / Activos totales"),
    ("Deuda sobre patrimonio", "Veces", "Liabilities", "Equity", "Pasivos totales / Patrimonio"),
    ("Multiplicador patrimonial", "Veces", "Assets", "Equity", "Activos totales / Patrimonio"),
    ("Rotación de activos al cierre", "Veces", "Revenue", "Assets", "Ingresos / Activos totales al cierre"),
    ("Rotación de cuentas por cobrar", "Veces", "Revenue", "TradeAndOtherCurrentReceivables", "Ingresos / Deudores comerciales y otras cuentas por cobrar"),
    ("Rotación de inventarios", "Veces", "Revenue", "Inventories", "Ingresos / Inventarios"),
    ("Margen operacional", "%", "ProfitLossFromOperatingActivities", "Revenue", "Resultado operacional / Ingresos"),
    ("Margen neto", "%", "ProfitLoss", "Revenue", "Ganancia (pérdida) / Ingresos"),
    ("Cobertura de gastos financieros", "Veces", "ProfitLossFromOperatingActivities", "FinanceCosts", "Resultado operacional / Gastos financieros"),
    ("ROA al cierre", "%", "ProfitLoss", "Assets", "Ganancia (pérdida) / Activos totales al cierre"),
    ("ROE al cierre", "%", "ProfitLoss", "Equity", "Ganancia (pérdida) / Patrimonio al cierre"),
    ("Flujo operacional / ingresos", "%", "CashFlowsFromUsedInOperatingActivities", "Revenue", "Flujo operacional / Ingresos"),
]

# Razones expresadas en días, derivadas de una rotación ya calculada (365 / rotación).
DAYS_DEFINITIONS = [
    ("Días de cobro", "Rotación de cuentas por cobrar", "365 / Rotación de cuentas por cobrar"),
    ("Días de inventario", "Rotación de inventarios", "365 / Rotación de inventarios"),
]

# Indicadores por acción. El número de acciones se lee del XBRL (unidad xbrli:shares,
# no es un monto en pesos), por lo que estos valores quedan en pesos por acción.
PER_SHARE_DEFINITIONS = [
    ("Utilidad por acción", "ProfitLoss", "Ganancia (pérdida) / Número de acciones suscritas y pagadas"),
    ("Valor libro por acción", "Equity", "Patrimonio / Número de acciones suscritas y pagadas"),
]

# Interpretación en lenguaje simple de cada indicador. Es texto de apoyo para
# lectura humana: no participa en ningún cálculo ni valida cifras.
RATIO_EXPLANATIONS = {
    "Capital de trabajo": "Recursos disponibles después de cubrir las obligaciones de corto plazo. Un valor positivo indica holgura operativa; uno negativo sugiere presión de liquidez.",
    "Liquidez corriente": "Cuántas veces el activo corriente cubre el pasivo corriente. Como referencia general, valores cercanos o superiores a 1,0x se asocian a una posición de corto plazo más cómoda.",
    "Prueba ácida": "Igual que la liquidez corriente, pero excluye inventarios por ser el activo corriente menos líquido. Mide la capacidad de pago inmediata sin depender de vender existencias.",
    "Liquidez de caja": "Cobertura de las obligaciones de corto plazo usando solo efectivo y equivalentes, sin considerar cuentas por cobrar ni inventarios.",
    "Endeudamiento sobre activos": "Porcentaje del activo total financiado con deuda. A mayor valor, mayor dependencia de financiamiento de terceros frente al patrimonio.",
    "Deuda sobre patrimonio": "Compara la deuda total con el patrimonio de los accionistas. Valores más altos indican mayor apalancamiento financiero.",
    "Multiplicador patrimonial": "Veces que el activo total supera al patrimonio; refleja cuánto del activo está financiado con deuda además de capital propio.",
    "Rotación de activos al cierre": "Veces que los ingresos del período 'giran' sobre el activo total al cierre. Un valor mayor sugiere un uso más eficiente de los activos para generar ventas.",
    "Rotación de cuentas por cobrar": "Veces que los ingresos del período cubren el saldo de deudores comerciales. A mayor rotación, más rápido cobra la empresa lo que factura.",
    "Rotación de inventarios": "Veces que los ingresos cubren el saldo de inventarios. Atención: la versión de texto de estudio usa costo de ventas en el numerador, pero este emisor no informa esa partida como concepto XBRL separado, por lo que aquí se usa ingresos; el nivel no es comparable con el de una fórmula con costo de ventas, aunque su evolución en el tiempo sí es informativa.",
    "Margen operacional": "Porcentaje de los ingresos que queda como resultado operacional, es decir, antes de resultados financieros e impuestos. Aísla el desempeño del negocio de su estructura de financiamiento.",
    "Margen neto": "Porcentaje de los ingresos que se convierte en ganancia final, después de todos los costos, gastos e impuestos.",
    "Cobertura de gastos financieros": "Veces que el resultado operacional alcanza a cubrir los gastos financieros del período. Es el indicador clásico de holgura frente al servicio de la deuda y suele aparecer en los covenants.",
    "Días de cobro": "Días promedio que tarda la empresa en transformar sus ventas en caja, obtenidos como 365 dividido por la rotación de cuentas por cobrar.",
    "Días de inventario": "Días promedio que las existencias permanecen en inventario, obtenidos como 365 dividido por la rotación de inventarios. Hereda la salvedad de esa rotación respecto del costo de ventas.",
    "Utilidad por acción": "Ganancia del período que corresponde a cada acción suscrita y pagada. Se calcula con el total de acciones informado en el XBRL, sin distinguir entre series accionarias.",
    "Valor libro por acción": "Patrimonio contable que respalda cada acción. Comparado con el precio de mercado da la razón bolsa/libro, que requiere un dato de precio externo al XBRL.",
    "Grado de apalancamiento operativo (GAO)": "Cuánto amplifica el resultado operacional una variación de 1% en las ventas. A mayor peso de los costos fijos, mayor GAO y mayor riesgo operacional.",
    "Grado de apalancamiento financiero (GAF)": "Cuánto amplifica la utilidad neta una variación de 1% en el resultado operacional. Refleja el efecto de los gastos financieros fijos de la deuda.",
    "Grado de apalancamiento combinado (GAC)": "Producto del GAO y el GAF: cuánto amplifica la utilidad neta una variación de 1% en las ventas, considerando a la vez la estructura de costos y la de financiamiento.",
    "ROA al cierre": "Ganancia generada por cada peso de activos, medida con el saldo de activos al cierre del período.",
    "ROE al cierre": "Ganancia generada por cada peso aportado por los accionistas, medida con el saldo de patrimonio al cierre del período.",
    "Flujo operacional / ingresos": "Proporción de los ingresos que se traduce en caja generada por la operación del negocio, antes de actividades de inversión y financiamiento.",
    "ROE Du Pont al cierre": "Descompone el ROE en tres factores: margen neto (rentabilidad sobre ventas), rotación de activos (eficiencia de uso de activos) y multiplicador patrimonial (apalancamiento).",
    "Rotación de activos promedio": "Misma lógica que la rotación al cierre, pero usa el promedio entre el activo del período anterior y el actual, suavizando variaciones puntuales de balance.",
    "ROA con activos promedio": "ROA calculado sobre el activo promedio entre dos cierres consecutivos, en vez del activo puntual de cierre.",
    "ROE con patrimonio promedio": "ROE calculado sobre el patrimonio promedio entre dos cierres consecutivos, en vez del patrimonio puntual de cierre.",
}


def _divide(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    try:
        return numerator / denominator
    except (DivisionByZero, InvalidOperation):
        return None


def calculate_ratios(instance: XbrlInstance, period_end: str) -> pd.DataFrame:
    """Devuelve ratios y trazabilidad de las cuentas exactas usadas en cada uno."""
    rows = []
    facts = {concept: instance.find_fact(concept, period_end) for concept in {
        "Assets", "CurrentAssets", "CurrentLiabilities", "CashAndCashEquivalents",
        "Inventories", "Liabilities", "Equity", "Revenue", "ProfitLoss",
        "CashFlowsFromUsedInOperatingActivities",
    }}
    current_assets = facts["CurrentAssets"].value if facts["CurrentAssets"] else None
    current_liabilities = facts["CurrentLiabilities"].value if facts["CurrentLiabilities"] else None
    inventories = facts["Inventories"].value if facts["Inventories"] else None
    working_capital = None if current_assets is None or current_liabilities is None else current_assets - current_liabilities
    rows.append({
        "Indicador": "Capital de trabajo",
        "Valor": working_capital,
        "Unidad": facts["CurrentAssets"].unit if facts["CurrentAssets"] else "Moneda",
        "Fórmula": "Activo corriente - Pasivo corriente",
        "Numerador XBRL": "CurrentAssets",
        "Denominador XBRL": "CurrentLiabilities",
        "Estado": "Calculado" if working_capital is not None else "No calculable: falta una cuenta",
        "Interpretación": RATIO_EXPLANATIONS.get("Capital de trabajo", ""),
    })
    for name, unit, numerator_concept, denominator_concept, formula in RATIO_DEFINITIONS:
        if numerator_concept == "CurrentAssetsLessInventories":
            numerator_value = None if current_assets is None or inventories is None else current_assets - inventories
            numerator_available = numerator_value is not None
        else:
            numerator_fact = facts.get(numerator_concept) or instance.find_fact(numerator_concept, period_end)
            numerator_value = numerator_fact.value if numerator_fact else None
            numerator_available = numerator_value is not None
        denominator_fact = facts.get(denominator_concept) or instance.find_fact(denominator_concept, period_end)
        ratio = _divide(
            numerator_value,
            denominator_fact.value if denominator_fact else None,
        )
        rows.append({
            "Indicador": name,
            "Valor": ratio * 100 if ratio is not None and unit == "%" else ratio,
            "Unidad": unit,
            "Fórmula": formula,
            "Numerador XBRL": numerator_concept,
            "Denominador XBRL": denominator_concept,
            "Estado": "Calculado" if ratio is not None else "No calculable: falta una cuenta o el denominador es cero",
            "Interpretación": RATIO_EXPLANATIONS.get(name, ""),
        })
    calculated = {row["Indicador"]: row["Valor"] for row in rows if row["Estado"] == "Calculado"}

    for name, source_ratio, formula in DAYS_DEFINITIONS:
        rotation = calculated.get(source_ratio)
        days = None if rotation is None or rotation == 0 else Decimal(365) / rotation
        rows.append({
            "Indicador": name,
            "Valor": days,
            "Unidad": "Días",
            "Fórmula": formula,
            "Numerador XBRL": "365 (constante)",
            "Denominador XBRL": source_ratio,
            "Estado": "Calculado" if days is not None else f"No calculable: falta {source_ratio}",
            "Interpretación": RATIO_EXPLANATIONS.get(name, ""),
        })

    shares_fact = instance.find_fact("NumberOfSharesOutstanding", period_end)
    shares = shares_fact.value if shares_fact else None
    for name, concept, formula in PER_SHARE_DEFINITIONS:
        amount_fact = facts.get(concept) or instance.find_fact(concept, period_end)
        amount = amount_fact.value if amount_fact else None
        per_share = None if amount is None or not shares else amount / shares
        rows.append({
            "Indicador": name,
            "Valor": per_share,
            "Unidad": "$/acción",
            "Fórmula": formula,
            "Numerador XBRL": concept,
            "Denominador XBRL": "NumberOfSharesOutstanding",
            "Estado": "Calculado" if per_share is not None else "No calculable: falta una cuenta o el número de acciones",
            "Interpretación": RATIO_EXPLANATIONS.get(name, ""),
        })

    dupont_components = [
        calculated.get("Margen neto"),
        calculated.get("Rotación de activos al cierre"),
        calculated.get("Multiplicador patrimonial"),
    ]
    dupont_value = None if any(value is None for value in dupont_components) else dupont_components[0] / 100 * dupont_components[1] * dupont_components[2] * 100
    rows.append({
        "Indicador": "ROE Du Pont al cierre",
        "Valor": dupont_value,
        "Unidad": "%",
        "Fórmula": "Margen neto x Rotación de activos al cierre x Multiplicador patrimonial",
        "Numerador XBRL": "ProfitLoss; Revenue; Assets",
        "Denominador XBRL": "Revenue; Assets; Equity",
        "Estado": "Calculado" if dupont_value is not None else "No calculable: faltan componentes Du Pont",
        "Interpretación": RATIO_EXPLANATIONS.get("ROE Du Pont al cierre", ""),
    })
    return pd.DataFrame(rows)
