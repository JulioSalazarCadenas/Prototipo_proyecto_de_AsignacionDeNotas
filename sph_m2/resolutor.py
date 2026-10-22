"""Resolutor iterativo de descenso estricto con evaluación incremental.

Ciclo: detectar -> (para un conflicto) generar candidatos -> filtrar los que reducen el número total
de conflictos -> elegir con el criterio -> aplicar -> actualizar conflictos afectados.

Terminación: el número de conflictos es un entero no negativo que decrece estrictamente en cada
iteración aplicada, luego hay a lo sumo C0 iteraciones (C0 = conflictos iniciales). La salida
SIN_SOLUCION significa 'ningún movimiento local mejora', NO 'el problema es infactible'.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from .indice import ContextoValidacion
from .validador import ValidadorRestricciones, clave
from .criterios import Movimiento, MenorMovimiento

SIN_CONFLICTOS = "SIN_CONFLICTOS"
SIN_SOLUCION = "SIN_SOLUCION"
LIMITE = "LIMITE_ITERACIONES"


@dataclass
class Resultado:
    estado: str
    iteraciones: int
    conflictos_iniciales: int
    conflictos_finales: int
    candidatos_evaluados: int
    historial: list = field(default_factory=list)
    segundos: float = 0.0
    pendientes: list = field(default_factory=list)


def horas_de_inicio(p, dia, dur):
    for hi in range(p.franja_inicio, p.fin_de_dia(dia) - dur + 1):
        if hi < p.receso_fin and p.receso_inicio < hi + dur:
            continue  # prefiltro barato: receso (RD-04)
        yield hi


class Resolutor:
    def __init__(self, propuesta, docentes, aulas, parametros, criterio=None, validador=None,
                 cambiar_docente=False, max_iteraciones=None):
        self.p = parametros
        self.ctx = ContextoValidacion(propuesta, docentes, aulas, parametros)
        self.val = validador or ValidadorRestricciones(parametros)
        self.criterio = criterio or MenorMovimiento()
        self.cambiar_docente = cambiar_docente
        self.max_iteraciones = max_iteraciones
        self.aula_ids = [a.id for a in aulas]
        self._docentes_por_esp = {}
        for d in docentes:
            self._docentes_por_esp.setdefault(d.especialidad, []).append(d.id)

    # -- generación de candidatos (vecindario acotado) -------------------------------
    def candidatos(self, s):
        p = self.p
        dur = s.duracion()
        docs = [s.docente_id]
        if self.cambiar_docente:
            esp = self.ctx.docentes[s.docente_id].especialidad if s.docente_id in self.ctx.docentes else None
            docs += [d for d in self._docentes_por_esp.get(esp, []) if d != s.docente_id]
        for dia in p.dias:
            for hi in horas_de_inicio(p, dia, dur):
                for aula in self.aula_ids:
                    for doc in docs:
                        if (dia, hi, aula, doc) == (s.dia, s.hora_inicio, s.aula_id, s.docente_id):
                            continue
                        yield Movimiento(s.id, dia, hi, hi + dur, aula, doc)

    def delta(self, mov: Movimiento) -> int:
        """Variación exacta del número total de conflictos si se aplicara mov (sin copiar la propuesta)."""
        ctx, val = self.ctx, self.val
        s = ctx.por_id[mov.sesion_id]
        docs = {s.docente_id, mov.docente_id}
        antes = val.contar_afectados(ctx, s.id, docs)
        vieja = ctx.mover(s.id, **mov.como_cambios())
        despues = val.contar_afectados(ctx, s.id, docs)
        ctx.mover(s.id, **{k: getattr(vieja, k) for k in ("dia", "hora_inicio", "hora_fin", "aula_id", "docente_id")})
        return despues - antes

    # -- ciclo principal ----------------------------------------------------------------
    def resolver(self) -> Resultado:
        t0 = time.perf_counter()
        ctx, val = self.ctx, self.val
        activos = {clave(c): c for c in val.detectar_todos(ctx)}
        c0 = len(activos)
        tope = self.max_iteraciones if self.max_iteraciones is not None else c0
        res = Resultado(SIN_CONFLICTOS, 0, c0, c0, 0)
        atascados = set()
        while activos:
            if res.iteraciones >= tope:
                res.estado = LIMITE
                break
            elegido = None
            for k in sorted(activos):
                if k in atascados:
                    continue
                c = activos[k]
                mejores = []
                for sid in sorted({s.id for s in c.sesiones}):
                    s = ctx.por_id[sid]
                    for mov in self.candidatos(s):
                        res.candidatos_evaluados += 1
                        d = self.delta(mov)
                        if d < 0:
                            mejores.append((self.criterio.costo(s, mov, ctx), d, mov))
                if mejores:
                    mejores.sort(key=lambda t: (t[0], t[1], t[2].dia, t[2].hora_inicio, t[2].aula_id, t[2].docente_id))
                    elegido = (k, mejores[0])
                    break
                atascados.add(k)
            if elegido is None:
                res.estado = SIN_SOLUCION
                break
            k, (costo, d, mov) = elegido
            s = ctx.por_id[mov.sesion_id]
            docs = {s.docente_id, mov.docente_id}
            # quitar conflictos afectados, aplicar, añadir los nuevos
            for c in val.conflictos_de_sesion(ctx, s):
                activos.pop(clave(c), None)
            for dd in docs:
                for c in val.conflictos_de_docente(ctx, dd):
                    activos.pop(clave(c), None)
            ctx.mover(s.id, **mov.como_cambios())
            for c in val.conflictos_de_sesion(ctx, ctx.por_id[s.id]):
                activos[clave(c)] = c
            for dd in docs:
                for c in val.conflictos_de_docente(ctx, dd):
                    activos[clave(c)] = c
            res.iteraciones += 1
            res.historial.append((s.id, mov.dia, mov.hora_inicio, mov.aula_id, mov.docente_id, d))
            atascados.clear()
        res.conflictos_finales = len(activos)
        res.pendientes = [activos[k] for k in sorted(activos)]
        res.segundos = time.perf_counter() - t0
        return res
