"""Línea base RECONSTRUIDA según lo descrito en el dossier (Fase 2, sec. G): cada candidato se evalúa
copiando la propuesta y revalidando con src.restricciones.detectar_todos. No es el código del equipo."""
import copy, time
from dataclasses import replace
from src.models import PropuestaHorario
from src.restricciones import detectar_todos
from sph_m2.criterios import Movimiento, MenorMovimiento
from sph_m2.parametros import Parametros
from sph_m2.resolutor import Resolutor, horas_de_inicio


def evaluar_candidato(prop, docentes, aulas, mov):
    copia = PropuestaHorario(prop.semestre, [replace(s) if s.id != mov.sesion_id else
                                              replace(s, dia=mov.dia, hora_inicio=mov.hora_inicio,
                                                      hora_fin=mov.hora_fin, aula_id=mov.aula_id) for s in prop.sesiones])
    return len(detectar_todos(copia, docentes, aulas))


def resolver_ingenuo(prop, docentes, aulas, tiempo_max=600):
    p = Parametros()
    t0 = time.perf_counter()
    actual = PropuestaHorario(prop.semestre, [replace(s) for s in prop.sesiones])
    n = len(detectar_todos(actual, docentes, aulas)); c0 = n
    it = cand = 0
    crit = MenorMovimiento()
    aux = Resolutor(actual, docentes, aulas, p)  # solo para reutilizar el generador de candidatos
    while n > 0:
        if time.perf_counter() - t0 > tiempo_max:
            return dict(estado="TIEMPO_AGOTADO", it=it, cand=cand, c0=c0, cf=n, seg=time.perf_counter() - t0)
        confl = detectar_todos(actual, docentes, aulas)
        mejor = None
        for c in confl:
            for s in c.sesiones:
                for mov in aux.candidatos(s):
                    cand += 1
                    m = evaluar_candidato(actual, docentes, aulas, mov)
                    if m < n:
                        k = (crit.costo(s, mov, aux.ctx), m - n, mov.dia, mov.hora_inicio, mov.aula_id, mov.docente_id)
                        if mejor is None or k < mejor[0]:
                            mejor = (k, mov)
            if mejor:
                break
        if not mejor:
            return dict(estado="SIN_SOLUCION", it=it, cand=cand, c0=c0, cf=n, seg=time.perf_counter() - t0)
        mov = mejor[1]
        actual.sesiones = [replace(s, dia=mov.dia, hora_inicio=mov.hora_inicio, hora_fin=mov.hora_fin, aula_id=mov.aula_id)
                           if s.id == mov.sesion_id else s for s in actual.sesiones]
        aux = Resolutor(actual, docentes, aulas, p)
        n = len(detectar_todos(actual, docentes, aulas)); it += 1
    return dict(estado="SIN_CONFLICTOS", it=it, cand=cand, c0=c0, cf=0, seg=time.perf_counter() - t0)
