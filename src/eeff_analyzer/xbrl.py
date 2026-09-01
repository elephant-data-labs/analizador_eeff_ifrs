from __future__ import annotations

import re
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import BinaryIO, Iterable, Optional

import pandas as pd
from lxml import etree

from .models import Context, Fact

XBRLI = "http://www.xbrl.org/2003/instance"
XLINK = "http://www.w3.org/1999/xlink"


def _local_name(tag: str) -> str:
    return etree.QName(tag).localname


def _namespace(tag: str) -> str:
    return etree.QName(tag).namespace or ""


def _clean_text(value: Optional[str]) -> str:
    return " ".join((value or "").split())


def _describe_context(context: Context) -> str:
    """Descripción legible de un contexto XBRL: tipo de período, fechas y dimensión."""
    if context.period_type == "instant":
        description = f"Instante {context.end_date}"
    else:
        description = f"Período {context.start_date} a {context.end_date}"
    if context.dimensions:
        description += " · " + "; ".join(context.dimensions)
    return description


class XbrlInstance:
    """Representación consultable de una instancia XBRL, sin inferencia externa."""

    def __init__(
        self,
        contexts: dict[str, Context],
        units: dict[str, str],
        labels: dict[str, str],
        facts: list[Fact],
        entity_names: Optional[dict[str, str]] = None,
    ):
        self.contexts = contexts
        self.units = units
        self.labels = labels
        self.facts = facts
        self.entity_names = entity_names or {}

    @classmethod
    def from_zip(cls, source: str | Path | BinaryIO) -> "XbrlInstance":
        """Carga la única instancia `.xbrl` del ZIP y sus archivos de etiquetas."""
        with zipfile.ZipFile(source) as archive:
            xbrl_names = [name for name in archive.namelist() if name.lower().endswith(".xbrl")]
            if len(xbrl_names) != 1:
                raise ValueError(f"Se esperaba una sola instancia .xbrl; se encontraron {len(xbrl_names)}.")
            labels = {}
            for name in archive.namelist():
                if "label" in name.lower() and name.lower().endswith(".xml"):
                    labels.update(_read_labels(archive.read(name)))
            return cls._from_xml(archive.read(xbrl_names[0]), labels)

    @classmethod
    def from_file(cls, source: str | Path) -> "XbrlInstance":
        path = Path(source)
        if path.suffix.lower() == ".zip":
            return cls.from_zip(path)
        return cls._from_xml(path.read_bytes(), {})

    @classmethod
    def _from_xml(cls, xml: bytes, labels: dict[str, str]) -> "XbrlInstance":
        root = etree.fromstring(xml)
        contexts = _read_contexts(root)
        units = _read_units(root)
        facts = _read_facts(root, contexts, units, labels)
        entity_names = _read_entity_names(root, contexts)
        return cls(contexts, units, labels, facts, entity_names)

    def periods(self) -> list[str]:
        return sorted({context.end_date for context in self.contexts.values() if context.end_date})

    def entity_identifiers(self) -> set[str]:
        return {context.entity_identifier for context in self.contexts.values() if context.entity_identifier}

    def entity_name(self, entity_identifier: Optional[str] = None) -> Optional[str]:
        """Nombre de la entidad declarante, leído del XBRL (no inferido del nombre del archivo)."""
        if entity_identifier is None:
            identifiers = self.entity_identifiers()
            entity_identifier = next(iter(identifiers)) if len(identifiers) == 1 else None
        if entity_identifier is None:
            return None
        return self.entity_names.get(entity_identifier)

    def find_fact(self, concept: str, period_end: str) -> Optional[Fact]:
        """Busca una cuenta por concepto, favoreciendo hechos sin dimensiones."""
        candidates = [
            fact for fact in self.facts
            if fact.concept == concept and fact.context.end_date == period_end
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda fact: (bool(fact.context.dimensions), fact.context.period_type != "instant"))
        return candidates[0]

    def statement_rows(self, catalog: Iterable[tuple[str, str, str]], period_end: str) -> pd.DataFrame:
        rows = []
        for statement, concept, fallback_label in catalog:
            fact = self.find_fact(concept, period_end)
            rows.append({
                "Estado": statement,
                "Concepto XBRL": concept,
                "Cuenta": (fact.label if fact and fact.label else fallback_label),
                "Valor": fact.value if fact else None,
                "Unidad": fact.unit if fact else None,
                "Contexto": _describe_context(fact.context) if fact else None,
            })
        return pd.DataFrame(rows)

    def facts_frame(self, period_end: Optional[str] = None) -> pd.DataFrame:
        selected = [fact for fact in self.facts if not period_end or fact.context.end_date == period_end]
        return pd.DataFrame([
            {
                "Concepto XBRL": fact.concept,
                "Etiqueta": fact.label or fact.concept,
                "Valor": fact.value,
                "Unidad": fact.unit,
                "Período": fact.context.end_date,
                "Tipo período": fact.context.period_type,
                "Dimensiones": "; ".join(fact.context.dimensions),
                "Contexto": fact.context_ref,
            }
            for fact in selected
        ])


def _read_contexts(root: etree._Element) -> dict[str, Context]:
    result = {}
    for node in root.findall(f"{{{XBRLI}}}context"):
        entity_identifier = node.findtext(f"{{{XBRLI}}}entity/{{{XBRLI}}}identifier")
        period = node.find(f"{{{XBRLI}}}period")
        instant = period.findtext(f"{{{XBRLI}}}instant") if period is not None else None
        start = period.findtext(f"{{{XBRLI}}}startDate") if period is not None else None
        end = period.findtext(f"{{{XBRLI}}}endDate") if period is not None else None
        dimensions = tuple(sorted(_clean_text(member.text) for member in node.xpath('.//*[local-name()="explicitMember" or local-name()="typedMember"]')))
        result[node.get("id")] = Context(
            identifier=node.get("id"),
            entity_identifier=_clean_text(entity_identifier) or None,
            period_type="instant" if instant else "duration",
            start_date=start,
            end_date=instant or end,
            dimensions=dimensions,
        )
    return result


def _read_entity_names(root: etree._Element, contexts: dict[str, Context]) -> dict[str, str]:
    """Nombre de la entidad declarante por RUT, leído del concepto IFRS estándar
    `NameOfReportingEntityOrOtherMeansOfIdentification` (es texto, no un hecho numérico,
    por lo que `_read_facts` no lo captura)."""
    names: dict[str, str] = {}
    for node in root:
        if _local_name(node.tag) != "NameOfReportingEntityOrOtherMeansOfIdentification":
            continue
        context = contexts.get(node.get("contextRef"))
        if context is None or not context.entity_identifier:
            continue
        text = _clean_text(node.text)
        if text:
            names.setdefault(context.entity_identifier, text)
    return names


def _read_units(root: etree._Element) -> dict[str, str]:
    result = {}
    for node in root.findall(f"{{{XBRLI}}}unit"):
        measures = [_clean_text(measure.text) for measure in node.findall(f".//{{{XBRLI}}}measure")]
        result[node.get("id")] = " / ".join(measures)
    return result


def _read_facts(root: etree._Element, contexts: dict[str, Context], units: dict[str, str], labels: dict[str, str]) -> list[Fact]:
    ignored = {"context", "unit", "schemaRef", "linkbaseRef"}
    facts = []
    for node in root:
        if _local_name(node.tag) in ignored or not node.get("contextRef"):
            continue
        raw_value = _clean_text(node.text).replace(" ", "")
        try:
            value = Decimal(raw_value)
        except (InvalidOperation, ValueError):
            continue
        context_ref = node.get("contextRef")
        context = contexts.get(context_ref)
        if context is None:
            continue
        concept = _local_name(node.tag)
        facts.append(Fact(
            concept=concept,
            namespace=_namespace(node.tag),
            context_ref=context_ref,
            value=value,
            unit=units.get(node.get("unitRef")),
            decimals=node.get("decimals"),
            label=labels.get(concept),
            context=context,
        ))
    return facts


def _read_labels(xml: bytes) -> dict[str, str]:
    root = etree.fromstring(xml)
    resources = {node.get(f"{{{XLINK}}}label"): _clean_text(node.text) for node in root.xpath('.//*[local-name()="label"]')}
    locations = {}
    for node in root.xpath('.//*[local-name()="loc"]'):
        href = node.get(f"{{{XLINK}}}href", "")
        fragment = href.split("#")[-1]
        locations[node.get(f"{{{XLINK}}}label")] = re.split(r"[_:]", fragment)[-1]
    result = {}
    for arc in root.xpath('.//*[local-name()="labelArc"]'):
        source = arc.get(f"{{{XLINK}}}from")
        target = arc.get(f"{{{XLINK}}}to")
        concept = locations.get(source)
        label = resources.get(target)
        if concept and label and concept not in result:
            result[concept] = label
    return result
