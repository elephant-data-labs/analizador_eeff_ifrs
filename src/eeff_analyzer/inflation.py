"""Corrección monetaria para comparar montos en pesos de distintos períodos.

Los factores de reajuste anual corresponden a la corrección monetaria del
capital propio tributario que publica cada enero el Servicio de Impuestos
Internos (SII) de Chile, mediante circular, para el año comercial recién
terminado (variación del IPC de noviembre a noviembre). No es el IPC de
prensa (diciembre a diciembre): es el valor oficial que se usa para restatar
cifras contables de un año a pesos de otro.

Esta tabla es de mantención manual: cuando el SII publique la circular de un
nuevo año comercial, agregar la entrada correspondiente más abajo. No se
descarga ni se calcula automáticamente; no hay inferencia ni IA involucrada.

Fuente: circulares del SII (https://www.sii.cl/normativa_legislacion/circulares).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

# Año comercial -> factor de reajuste anual (1 + porcentaje de corrección monetaria).
# Cada factor lleva pesos de fines del año anterior a pesos de fines de este año.
ANNUAL_ADJUSTMENT_FACTORS: dict[int, Decimal] = {
    2020: Decimal("1.027"),  # 2,7% - Circular N° 4 de 2021
    2021: Decimal("1.065"),  # 6,5% - Circular N° 6 de 2022
    2022: Decimal("1.133"),  # 13,3% - Circular N° 4 de 2023
    2023: Decimal("1.048"),  # 4,8% - Circular N° 5 de 2024
    2024: Decimal("1.042"),  # 4,2% - Circular N° 6 de 2025
    2025: Decimal("1.034"),  # 3,4% - Circular N° 5 de 2026
}


def adjustment_factor(from_year: int, to_year: int) -> Optional[Decimal]:
    """Factor acumulado para llevar pesos de cierre `from_year` a pesos de cierre `to_year`.

    Ambos años son "año comercial" (el año del cierre, ej. 2020 para 31-12-2020).
    Devuelve None si falta algún factor anual de la tabla dentro del rango, o si
    `to_year` es anterior a `from_year` (esta tabla solo proyecta hacia adelante).
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
