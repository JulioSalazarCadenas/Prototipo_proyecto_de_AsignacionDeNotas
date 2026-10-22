"""Reglas duras RD-01..RD-10 como objetos Strategy + registro de reglas.

Patrón: Strategy (GoF). Cada regla es una estrategia intercambiable con la misma interfaz
(`ReglaRestriccion`). El `ValidadorRestricciones` no conoce ninguna regla concreta: itera sobre
las reglas registradas (principio abierto/cerrado, OCP). Agregar RD-11 = crear una clase nueva
decorada con @regla("RD-11"); ningún archivo existente se modifica.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from src.restricciones import Conflicto
from src.models import Sesion

SESION = "sesion"    # la regla se evalúa por sesión (unaria o de pares)
DOCENTE = "docente"  # la regla agrega por docente (p. ej. carga semanal)

REGISTRO: dict = {}


def regla(identificador: str):
    """Decorador de registro: añade la clase al catálogo de reglas disponibles."""
    def decorar(clase):
        clase.id = identificador
        REGISTRO[identificador] = clase
        return clase
    return decorar


class ReglaRestriccion(ABC):
    id: str = "RD-??"
    ambito: str = SESION

    def __init__(self, parametros):
        self.p = parametros

    def evaluar_sesion(self, ctx, s: Sesion) -> list:
        """Conflictos de esta regla en los que participa la sesión s (cada par se reporta una vez por s)."""
        return []

    def evaluar_docente(self, ctx, docente_id: str) -> list:
        """Solo para reglas con ámbito DOCENTE."""
        return []


def _par(tipo, desc, ctx, a: Sesion, b: Sesion) -> Conflicto:
    a, b = sorted((a, b), key=lambda x: ctx.orden[x.id])
    return Conflicto(tipo, desc, [a, b])


@regla("RD-01")
class CruceDocente(ReglaRestriccion):
    def evaluar_sesion(self, ctx, s):
        return [_par(self.id, f"El docente {s.docente_id} tiene dos sesiones cruzadas", ctx, s, o)
                for o in ctx.mismos("docente", s) if s.se_traslapa_con(o)]


@regla("RD-02")
class CruceAula(ReglaRestriccion):
    def evaluar_sesion(self, ctx, s):
        return [_par(self.id, f"El aula {s.aula_id} tiene dos sesiones cruzadas", ctx, s, o)
                for o in ctx.mismos("aula", s) if s.se_traslapa_con(o)]


@regla("RD-03")
class CruceGrupo(ReglaRestriccion):
    def evaluar_sesion(self, ctx, s):
        out = []
        for o in ctx.mismos("grupo", s):
            if o.curso != s.curso and s.se_traslapa_con(o):
                a, b = sorted((s, o), key=lambda x: ctx.orden[x.id])
                out.append(Conflicto(self.id, f"El grupo {s.grupo} tiene cruce entre {a.curso} y {b.curso}", [a, b]))
        return out


@regla("RD-04")
class FranjaInstitucional(ReglaRestriccion):
    def evaluar_sesion(self, ctx, s):
        p, out = self.p, []
        if s.hora_inicio < p.franja_inicio or s.hora_fin > p.fin_de_dia(s.dia):
            out.append(Conflicto(self.id, f"Sesión {s.id} fuera de la franja institucional", [s]))
        if s.hora_inicio < p.receso_fin and p.receso_inicio < s.hora_fin:
            out.append(Conflicto(self.id, f"Sesión {s.id} cae en el receso 12m-1pm", [s]))
        return out


@regla("RD-05")
class DisponibilidadDocente(ReglaRestriccion):
    def evaluar_sesion(self, ctx, s):
        d = ctx.docentes.get(s.docente_id)
        if not d or not d.franjas_disponibles:
            return []
        if any(dia == s.dia and hi <= s.hora_inicio and s.hora_fin <= hf for dia, hi, hf in d.franjas_disponibles):
            return []
        return [Conflicto(self.id, f"Sesión {s.id} fuera de la disponibilidad declarada por {d.nombre}", [s])]


@regla("RD-06")
class CapacidadAula(ReglaRestriccion):
    def evaluar_sesion(self, ctx, s):
        a = ctx.aulas.get(s.aula_id)
        if a and s.cupo_esperado > a.capacidad:
            return [Conflicto(self.id, f"Sesión {s.id} espera {s.cupo_esperado} estudiantes "
                              f"pero el aula {a.nombre} tiene capacidad {a.capacidad}", [s])]
        return []


@regla("RD-07")
class DuracionSesion(ReglaRestriccion):
    def evaluar_sesion(self, ctx, s):
        if s.duracion() != self.p.duracion_sesion:
            return [Conflicto(self.id, f"Sesión {s.id} dura {s.duracion()}h, se esperaban {self.p.duracion_sesion}h", [s])]
        return []


@regla("RD-08")
class TopeEstudiantes(ReglaRestriccion):
    def evaluar_sesion(self, ctx, s):
        lim = self.p.limite_cupo()
        if s.cupo_esperado > lim:
            return [Conflicto(self.id, f"Sesión {s.id} espera {s.cupo_esperado} estudiantes, supera el tope de {lim}", [s])]
        return []


@regla("RD-09")
class DedicacionDocente(ReglaRestriccion):
    ambito = DOCENTE

    def evaluar_docente(self, ctx, docente_id):
        d = ctx.docentes.get(docente_id)
        if d is None:
            return []
        horas, maximo = ctx.horas_de_docente(docente_id), self.p.horas_de(d.dedicacion)
        if horas > maximo:
            return [Conflicto(self.id, f"{d.nombre} tiene {horas}h asignadas, excede su dedicación ({maximo}h/semana)",
                              ctx.sesiones_de_docente(docente_id))]
        return []


@regla("RD-10")
class TecnologiaAula(ReglaRestriccion):
    def evaluar_sesion(self, ctx, s):
        if not s.tecnologia_requerida:
            return []
        a = ctx.aulas.get(s.aula_id)
        if a and not s.tecnologia_requerida.issubset(a.tecnologia):
            falt = ", ".join(t.value for t in s.tecnologia_requerida - a.tecnologia)
            return [Conflicto(self.id, f"Aula {a.nombre} no tiene la tecnología requerida por {s.id}: {falt}", [s])]
        return []
