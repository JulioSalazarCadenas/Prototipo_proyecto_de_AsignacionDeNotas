"""Resolutor iterativo de descenso estricto con evaluación incremental.

Ciclo: detectar -> (para un conflicto) generar candidatos -> filtrar los que reducen el número total
de conflictos -> elegir con el criterio -> aplicar -> actualizar conflictos afectados.

Alternativa válida (decisión de M3, Ajuste 1 del autodiagnóstico): un candidato se acepta solo si
(a) reduce el número total de conflictos (delta < 0) y (b) no aumenta el número de conflictos de
ninguna regla (sin regresión por regla). Con permitir_regresion=True se recupera el comportamiento
de M2 (solo delta < 0).

Los conflictos 'atascados' se reintentan después de cada movimiento aplicado (atascados.clear()):
un movimiento posterior puede liberar un aula u horario y desatascar otro conflicto.

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
    desatascados: int = 0   # conflictos que se resolvieron gracias al reintento tras otro movimiento


def horas_de_inicio(p, dia, dur):
    for hi in range(p.franja_inicio, p.fin_de_dia(dia) - dur + 1):
        if hi < p.receso_fin and p.receso_inicio < hi + dur:
            continue  # prefiltro barato: receso (RD-04)
        yield hi


class Resolutor:
    def __init__(self, propuesta, docentes, aulas, parametros, criterio=None, validador=None,
                 cambiar_docente=False, max_iteraciones=None, permitir_regresion=False, prefiltro=True,
                 reintentar_atascados=True):
        self.p = parametros
        self.permitir_regresion = permitir_regresion
        self.prefiltro = prefiltro
        self.reintentar_atascados = reintentar_atascados   # False solo para el experimento de ablación
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
        aulas = self._aulas_para(s)
        for dia in p.dias:
            for hi in horas_de_inicio(p, dia, dur):
                for aula in aulas:
                    for doc in docs:
                        if (dia, hi, aula, doc) == (s.dia, s.hora_inicio, s.aula_id, s.docente_id):
                            continue
                        yield Movimiento(s.id, dia, hi, hi + dur, aula, doc)

    def _aulas_para(self, s):
        """Prefiltro unario (4.1.4 de M2): si el aula actual cumple capacidad y tecnología, las aulas que
        no las cumplen solo podrían añadir RD-06/RD-10 (regresión) y se omiten sin cambiar el resultado."""
        if not self.prefiltro or self.permitir_regresion:
            return self.aula_ids
        a0 = self.ctx.aulas.get(s.aula_id)
        if a0 is None or not self._apta(s, a0):
            return self.aula_ids
        return [a for a in self.aula_ids if self._apta(s, self.ctx.aulas[a])]

    @staticmethod
    def _apta(s, aula) -> bool:
        return s.cupo_esperado <= aula.capacidad and s.tecnologia_requerida.issubset(aula.tecnologia)

    def evaluar(self, mov: Movimiento):
        """(delta, regresion): delta total exacto y si alguna regla aumenta su número de conflictos."""
        ctx, val = self.ctx, self.val
        s = ctx.por_id[mov.sesion_id]
        docs = {s.docente_id, mov.docente_id}
        antes = val.contar_por_tipo(ctx, s.id, docs)
        vieja = ctx.mover(s.id, **mov.como_cambios())
        despues = val.contar_por_tipo(ctx, s.id, docs)
        ctx.mover(s.id, **{k: getattr(vieja, k) for k in ("dia", "hora_inicio", "hora_fin", "aula_id", "docente_id")})
        delta = sum(despues.values()) - sum(antes.values())
        regresion = any(despues[t] > antes[t] for t in despues)
        return delta, regresion

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
        atascados, alguna_vez = set(), set()
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
                        d, regresion = self.evaluar(mov)
                        if d < 0 and (self.permitir_regresion or not regresion):
                            mejores.append((self.criterio.costo(s, mov, ctx), d, mov))
                if mejores:
                    mejores.sort(key=lambda t: (t[0], t[1], t[2].dia, t[2].hora_inicio, t[2].aula_id, t[2].docente_id))
                    elegido = (k, mejores[0])
                    break
                atascados.add(k)
                alguna_vez.add(k)
            if elegido is None:
                res.estado = SIN_SOLUCION
                break
            k, (costo, d, mov) = elegido
            if k in alguna_vez:
                res.desatascados += 1
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
            if self.reintentar_atascados:
                atascados.clear()
        res.conflictos_finales = len(activos)
        res.pendientes = [activos[k] for k in sorted(activos)]
        res.segundos = time.perf_counter() - t0
        return res
