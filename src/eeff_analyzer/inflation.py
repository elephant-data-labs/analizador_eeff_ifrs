"""IPC para reexpresar cifras de EEFF de distintos cierres a un mismo período.

Los estados financieros que analiza esta app cierran al 31 de diciembre, así
que para llevar, por ejemplo, un monto de diciembre de 2024 a pesos de
diciembre de 2025, corresponde usar la variación del IPC medida exactamente
entre esos dos cierres — es decir, el IPC del INE, diciembre a diciembre (no
la corrección monetaria tributaria del SII, que mide noviembre a noviembre
para otro propósito: el reajuste del capital propio tributario y la renta
líquida imponible, un cálculo que este analizador no hace).

Fuente: boletines mensuales del INE
(https://www.ine.gob.cl/estadisticas/economia/precios-y-costos/ipc).

La tabla cubre siempre los últimos 5 años completos: al agregar la fila del
año nuevo (enero, cuando se publica el dato de diciembre), se elimina la fila
más antigua. Es de mantención manual: no se descarga ni se calcula
automáticamente; no hay inferencia ni IA involucrada.

Precisión importante: esto es una reexpresión ANALÍTICA para hacer las
cifras comparables entre años, con fines académicos/de análisis. No es una
reexpresión de estados financieros bajo IAS 29 (economías hiperinflacionarias),
que exige otra metodología (partidas monetarias vs. no monetarias, un índice
general de precios definido por la norma, tratamiento distinto del
patrimonio, etc.). Si en algún momento se necesita una reexpresión IAS 29
formal, debe implementarse aparte.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

# Año -> variación de diciembre a diciembre (1 + porcentaje). Cada factor lleva
# pesos de diciembre del año anterior a pesos de diciembre de este año.
# Mantener siempre los últimos 5 años: al sumar el año nuevo, quitar el más antiguo.
ANNUAL_VARIATION_INE_DIC_DIC: dict[int, Decimal] = {
    2021: Decimal("1.072"),  # 7,2% - IPC dic-2021, INE
    2022: Decimal("1.128"),  # 12,8% - IPC dic-2022, INE
    2023: Decimal("1.039"),  # 3,9% - IPC dic-2023, INE
    2024: Decimal("1.045"),  # 4,5% - IPC dic-2024, INE
    2025: Decimal("1.035"),  # 3,5% - IPC dic-2025, INE
}

ANNUAL_ADJUSTMENT_FACTORS: dict[int, Decimal] = ANNUAL_VARIATION_INE_DIC_DIC


def adjustment_factor(from_year: int, to_year: int) -> Optional[Decimal]:
    """Factor acumulado para llevar pesos de cierre `from_year` a pesos de cierre `to_year`.

    Ambos años son el año del cierre (ej. 2024 para 31-12-2024). Encadena la
    variación anual del IPC (INE, dic-dic) de cada año entre `from_year` y
    `to_year`: por ejemplo, de 2022 a 2025 se multiplica el factor de 2023,
    2024 y 2025. Devuelve None si falta algún factor anual dentro del rango,
    o si `to_year` es anterior a `from_year` (esta tabla solo proyecta hacia
    adelante).
    """
    if from_year == to_year:
        return Decimal("1")
    if from_year > to_year:
        return None
    factor = Decimal("1")
    for year in range(from_year + 1, to_year + 1):
        annual = ANNUAL_ADJUSTMENT_FACTORS.get(year)
        if annual is None:
            return None
        factor *= annual
    return factor


def adjust_to_period(value, from_year: int, to_year: int):
    """Ajusta un monto nominal de `from_year` a pesos de `to_year`. None si falta un factor."""
    if value is None:
        return None
    factor = adjustment_factor(from_year, to_year)
    if factor is None:
        return None
    return value * factor
    
