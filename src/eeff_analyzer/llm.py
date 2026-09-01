"""Punto de extensión para IA; la versión inicial no invoca proveedores externos."""

from typing import Protocol


class InterpretationProvider(Protocol):
    def interpret(self, payload: dict) -> dict:
        """Recibirá datos ya calculados y devolverá una respuesta estructurada."""


def provider_not_configured(_: dict) -> dict:
    return {"status": "not_configured", "message": "La interpretación por IA se habilitará mediante una API configurable."}

