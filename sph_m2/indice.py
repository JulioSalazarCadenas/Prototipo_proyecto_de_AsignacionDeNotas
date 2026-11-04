"""Contexto de validación con índice de ocupación por (eje, clave, día).
Permite comprobar una sesión contra solo las sesiones que comparten docente, aula
o grupo ese día, en lugar de comparar todos los pares (O(n^2))."""
from __future__ import annotations
from dataclasses import replace
from collections import defaultdict
from src.models import Sesion, PropuestaHorario
from .parametros import Parametros


class ContextoValidacion:
    EJES = ("docente", "aula", "grupo")

    def __init__(self, propuesta: PropuestaHorario, docentes: list, aulas: list, parametros: Parametros):
        self.parametros = parametros
        self.docentes = {d.id: d for d in docentes}
        self.aulas = {a.id: a for a in aulas}
        self.orden = {s.id: i for i, s in enumerate(propuesta.sesiones)}
        self.por_id = {s.id: s for s in propuesta.sesiones}
        self._idx = defaultdict(set)
        self._horas_docente = defaultdict(int)
        for s in propuesta.sesiones:
            self._indexar(s)

    # -- mantenimiento del índice -------------------------------------------------
    def _claves(self, s: Sesion):
        return (("docente", s.docente_id, s.dia), ("aula", s.aula_id, s.dia), ("grupo", s.grupo, s.dia))

    def _indexar(self, s: Sesion):
        for k in self._claves(s):
            self._idx[k].add(s.id)
        self._horas_docente[s.docente_id] += s.duracion()

    def _desindexar(self, s: Sesion):
        for k in self._claves(s):
            self._idx[k].discard(s.id)
        self._horas_docente[s.docente_id] -= s.duracion()

    def mover(self, sesion_id: str, **cambios) -> Sesion:
        """Aplica cambios (dia, hora_inicio, hora_fin, aula_id, docente_id) y devuelve la sesión anterior."""
        vieja = self.por_id[sesion_id]
        nueva = replace(vieja, **cambios)
        self._desindexar(vieja)
        self.por_id[sesion_id] = nueva
        self._indexar(nueva)
        return vieja

    # -- consultas ------------------------------------------------------------------
    def mismos(self, eje: str, s: Sesion):
        """Sesiones (distintas de s) que comparten el eje y el día con s."""
        clave = {"docente": s.docente_id, "aula": s.aula_id, "grupo": s.grupo}[eje]
        for otro_id in self._idx.get((eje, clave, s.dia), ()):
            if otro_id != s.id:
                yield self.por_id[otro_id]

    def sesiones_de_docente(self, docente_id: str):
        ids = set()
        for dia in self.parametros.dias:
            ids |= self._idx.get(("docente", docente_id, dia), set())
        return [self.por_id[i] for i in sorted(ids, key=self.orden.get)]

    def horas_de_docente(self, docente_id: str) -> int:
        return self._horas_docente.get(docente_id, 0)

    def sesiones(self):
        return list(self.por_id.values())

    def a_propuesta(self, semestre: str = "") -> PropuestaHorario:
        return PropuestaHorario(semestre, sorted(self.por_id.values(), key=lambda s: self.orden[s.id]))
