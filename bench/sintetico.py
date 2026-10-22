"""Generador sintético reproducible: horario inicial limpio + k conflictos inyectados."""
import random
from src.models import Docente, Aula, Sesion, PropuestaHorario, Dedicacion, Tecnologia

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
HORAS = [7, 9, 14, 16, 18, 20]          # bloques de 2 h dentro de la franja y fuera del receso


def generar(n_sesiones, n_aulas=None, n_docentes=None, k_conflictos=3, semilla=1):
    rnd = random.Random(semilla)
    n_aulas = n_aulas or max(8, n_sesiones // 8)
    n_docentes = n_docentes or max(4, n_sesiones // 4)
    n_grupos = max(2, n_sesiones // 6)
    docentes = [Docente(f"D{i:04d}", f"Docente {i}", Dedicacion.TIEMPO_COMPLETO, f"E{i % 5}") for i in range(n_docentes)]
    aulas = [Aula(f"A{i:04d}", f"Aula {i}", 45, {Tecnologia.VIDEO_BEAM}) for i in range(n_aulas)]
    ocupado = set()
    horas = {d.id: 0 for d in docentes}
    sesiones = []
    for i in range(n_sesiones):
        grupo = f"G{rnd.randrange(n_grupos):04d}"
        doc = docentes[rnd.randrange(n_docentes)]
        while horas[doc.id] + 2 > 20:
            doc = docentes[rnd.randrange(n_docentes)]
        horas[doc.id] += 2
        for _ in range(2000):
            dia, hi, aula = rnd.choice(DIAS), rnd.choice(HORAS), aulas[rnd.randrange(n_aulas)]
            if dia == "Sábado" and hi + 2 > 13:
                continue
            if all((eje, k, dia, hi) not in ocupado for eje, k in (("d", doc.id), ("a", aula.id), ("g", grupo))):
                break
        else:
            raise RuntimeError("no hay espacio: aumente aulas/docentes")
        for eje, k in (("d", doc.id), ("a", aula.id), ("g", grupo)):
            ocupado.add((eje, k, dia, hi))
        sesiones.append(Sesion(f"S{i:05d}", f"Curso{i % max(1, n_sesiones // 3)}", grupo, dia, hi, hi + 2,
                               doc.id, aula.id, 30))
    # inyección: la mitad cruces de aula, la mitad de docente
    victimas = rnd.sample(range(n_sesiones), min(k_conflictos, n_sesiones))
    for j, vi in enumerate(victimas):
        v = sesiones[vi]
        o = sesiones[(vi + 1 + rnd.randrange(n_sesiones - 1)) % n_sesiones]
        if j % 2 == 0:
            v.dia, v.hora_inicio, v.hora_fin, v.aula_id = o.dia, o.hora_inicio, o.hora_fin, o.aula_id
        elif horas[o.docente_id] + 2 <= 20:
            horas[v.docente_id] -= 2; horas[o.docente_id] += 2
            v.dia, v.hora_inicio, v.hora_fin, v.docente_id = o.dia, o.hora_inicio, o.hora_fin, o.docente_id
        else:
            v.dia, v.hora_inicio, v.hora_fin, v.aula_id = o.dia, o.hora_inicio, o.hora_fin, o.aula_id
    return PropuestaHorario("sintetico", sesiones), docentes, aulas
