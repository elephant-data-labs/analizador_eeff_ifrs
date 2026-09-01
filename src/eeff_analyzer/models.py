from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class Context:
    identifier: str
    entity_identifier: Optional[str]
    period_type: str
    start_date: Optional[str]
    end_date: Optional[str]
    dimensions: tuple[str, ...]


@dataclass(frozen=True)
class Fact:
    concept: str
    namespace: str
    context_ref: str
    value: Decimal
    unit: Optional[str]
    decimals: Optional[str]
    label: Optional[str]
    context: Context
