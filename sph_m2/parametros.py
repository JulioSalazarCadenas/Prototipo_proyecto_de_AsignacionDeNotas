"""Parámetros de negocio externalizados (RF-13, RNF-06)."""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from src.models import Dedicacion, HORAS_MAXIMAS_POR_DEDICACION


@dataclass(frozen=True)
class Parametros:
    duracion_sesion: int = 2
    tope_estudiantes: int = 40
    tolerancia_tope: float = 0.10
    franja_inicio: int = 7
    franja_fin: int = 22
    franja_fin_sabado: int = 13
    receso_inicio: int = 12
    receso_fin: int = 13
    horas_maximas: dict = field(default_factory=lambda: {d.value: h for d, h in HORAS_MAXIMAS_POR_DEDICACION.items()})
    dias: tuple = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado")
    # Parámetros de reglas añadidas después (p. ej. RD-11) viven aquí sin tocar esta clase:
    extra: dict = field(default_factory=dict)

    def limite_cupo(self) -> int:
        return int(self.tope_estudiantes * (1 + self.tolerancia_tope))

    def horas_de(self, dedicacion: Dedicacion) -> int:
        return self.horas_maximas[dedicacion.value]

    def fin_de_dia(self, dia: str) -> int:
        return self.franja_fin_sabado if dia == "Sábado" else self.franja_fin

    @classmethod
    def desde_json(cls, ruta: str) -> "Parametros":
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        if "dias" in datos:
            datos["dias"] = tuple(datos["dias"])
        return cls(**datos)

    def a_dict(self) -> dict:
        return asdict(self)
