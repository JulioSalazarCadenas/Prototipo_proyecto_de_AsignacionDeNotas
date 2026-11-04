"""Criterios de recomendación intercambiables (Strategy #2; RB-01..RB-03 del M1).
Contrato: costo(original, movimiento, ctx) -> tupla comparable; menor es mejor.
Se evalúa SOLO entre candidatos que ya reducen conflictos, por lo que no puede degradar la validez."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Movimiento:
    sesion_id: str
    dia: str
    hora_inicio: int
    hora_fin: int
    aula_id: str
    docente_id: str

    def como_cambios(self) -> dict:
        return dict(dia=self.dia, hora_inicio=self.hora_inicio, hora_fin=self.hora_fin,
                    aula_id=self.aula_id, docente_id=self.docente_id)


class CriterioRecomendacion(ABC):
    nombre = "criterio"

    @abstractmethod
    def costo(self, original, mov: Movimiento, ctx) -> tuple: ...


class MenorMovimiento(CriterioRecomendacion):
    nombre = "Menor movimiento"

    def costo(self, o, m, ctx):
        cambios = (o.dia != m.dia) + (o.hora_inicio != m.hora_inicio) + (o.aula_id != m.aula_id) + (o.docente_id != m.docente_id)
        dist = abs(ctx.parametros.dias.index(m.dia) - ctx.parametros.dias.index(o.dia)) * 24 + abs(m.hora_inicio - o.hora_inicio)
        return (cambios, dist)


class MantenerAula(CriterioRecomendacion):
    nombre = "Mantener aula"

    def costo(self, o, m, ctx):
        return (o.aula_id != m.aula_id, o.docente_id != m.docente_id, abs(m.hora_inicio - o.hora_inicio))


class MantenerDocente(CriterioRecomendacion):
    nombre = "Mantener docente"

    def costo(self, o, m, ctx):
        return (o.docente_id != m.docente_id, o.dia != m.dia, abs(m.hora_inicio - o.hora_inicio))


class EvitarDiasConsecutivos(CriterioRecomendacion):
    """RB-01: evitar sesiones del mismo curso en días consecutivos."""
    nombre = "Evitar días consecutivos (RB-01)"

    def costo(self, o, m, ctx):
        dias = ctx.parametros.dias
        i = dias.index(m.dia)
        hermanas = [s for s in ctx.sesiones() if s.curso == o.curso and s.grupo == o.grupo and s.id != o.id]
        consecutivas = sum(1 for s in hermanas if abs(dias.index(s.dia) - i) == 1)
        return (consecutivas,)


class DistribuirHoras(CriterioRecomendacion):
    """RB-02: distribuir las sesiones del mismo curso en horas distintas."""
    nombre = "Distribuir horas (RB-02)"

    def costo(self, o, m, ctx):
        hermanas = [s for s in ctx.sesiones() if s.curso == o.curso and s.grupo == o.grupo and s.id != o.id]
        return (sum(1 for s in hermanas if s.hora_inicio == m.hora_inicio),)


class MinimizarHuecos(CriterioRecomendacion):
    """RB-03: minimizar los huecos del docente en el día de destino."""
    nombre = "Minimizar huecos (RB-03)"

    def costo(self, o, m, ctx):
        otras = [s for s in ctx.sesiones() if s.docente_id == m.docente_id and s.dia == m.dia and s.id != o.id]
        if not otras:
            return (0,)
        horas = sorted([(s.hora_inicio, s.hora_fin) for s in otras] + [(m.hora_inicio, m.hora_fin)])
        return (sum(max(0, b[0] - a[1]) for a, b in zip(horas, horas[1:])),)


class Compuesto(CriterioRecomendacion):
    """Composición lexicográfica de criterios (prioridad en el orden dado)."""

    def __init__(self, *criterios):
        self.criterios = criterios
        self.nombre = " > ".join(c.nombre for c in criterios)

    def costo(self, o, m, ctx):
        out = ()
        for c in self.criterios:
            out += c.costo(o, m, ctx)
        return out
