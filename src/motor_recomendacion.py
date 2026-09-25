"""
Motor de recomendación de alternativas (RF-10).

Para cada conflicto detectado, explora un VECINDARIO ACOTADO de
alternativas -no el espacio completo de combinaciones-, tal como se
sustenta en la Sección 1.3 del Informe M1: esto es lo que mantiene el
prototipo en complejidad polinomial en vez de una búsqueda combinatoria
completa (CSP/backtracking).

Este motor solo SUGIERE. La decisión final es del Coordinador Académico
(RF-11) - el prototipo no aplica ningún cambio automáticamente.
"""

from .models import DIAS_SEMANA, Sesion
from .restricciones import (
    Conflicto, FRANJA_INICIO, FRANJA_FIN, FRANJA_FIN_SABADO,
    RECESO_INICIO, RECESO_FIN,
)

DURACION_SESION = 2  # horas, ver RD-07


def _aula_libre_en(aula_id: str, dia: str, hora_inicio: int, hora_fin: int, propuesta, ignorar_sesion_id: str) -> bool:
    for s in propuesta.sesiones:
        if s.id == ignorar_sesion_id or s.aula_id != aula_id:
            continue
        if s.dia == dia and s.hora_inicio < hora_fin and hora_inicio < s.hora_fin:
            return False
    return True


def _docente_libre_en(docente_id: str, dia: str, hora_inicio: int, hora_fin: int, propuesta, ignorar_sesion_id: str) -> bool:
    for s in propuesta.sesiones:
        if s.id == ignorar_sesion_id or s.docente_id != docente_id:
            continue
        if s.dia == dia and s.hora_inicio < hora_fin and hora_inicio < s.hora_fin:
            return False
    return True


def sugerir_aulas_alternativas(sesion: Sesion, propuesta, aulas, max_alternativas: int = 3) -> list:
    """Vecindario: aulas con capacidad y tecnología compatibles, libres
    en el mismo día/hora de la sesión en conflicto (RF-07, RF-10)."""
    alternativas = []
    for aula in aulas:
        if aula.id == sesion.aula_id:
            continue
        if aula.capacidad < sesion.cupo_esperado:
            continue
        if not sesion.tecnologia_requerida.issubset(aula.tecnologia):
            continue
        if not _aula_libre_en(aula.id, sesion.dia, sesion.hora_inicio, sesion.hora_fin, propuesta, sesion.id):
            continue
        alternativas.append(
            f"Reasignar {sesion.id} al aula {aula.nombre} "
            f"(capacidad {aula.capacidad}, mismo día y hora)"
        )
        if len(alternativas) >= max_alternativas:
            break
    return alternativas


def sugerir_franjas_alternativas(sesion: Sesion, propuesta, max_alternativas: int = 3) -> list:
    """Vecindario: mismo día en otras horas, y mismo bloque horario en
    otros días de la semana, para el mismo docente y aula (RF-10)."""
    alternativas = []
    candidatos = []
    # Mismo día, otras horas posibles (cada 1h dentro de la franja institucional)
    for hi in range(FRANJA_INICIO, FRANJA_FIN - DURACION_SESION + 1):
        hf = hi + DURACION_SESION
        if hi < RECESO_FIN and RECESO_INICIO < hf:
            continue  # cae en el receso
        candidatos.append((sesion.dia, hi, hf))
    # Mismo bloque horario, otros días
    for dia in DIAS_SEMANA:
        if dia == sesion.dia:
            continue
        fin_dia = FRANJA_FIN_SABADO if dia == "Sábado" else FRANJA_FIN
        if sesion.hora_fin > fin_dia:
            continue
        candidatos.append((dia, sesion.hora_inicio, sesion.hora_fin))

    for dia, hi, hf in candidatos:
        if (dia, hi, hf) == (sesion.dia, sesion.hora_inicio, sesion.hora_fin):
            continue
        docente_ok = _docente_libre_en(sesion.docente_id, dia, hi, hf, propuesta, sesion.id)
        aula_ok = _aula_libre_en(sesion.aula_id, dia, hi, hf, propuesta, sesion.id)
        if docente_ok and aula_ok:
            alternativas.append(
                f"Mover {sesion.id} a {dia} de {hi}:00 a {hf}:00 "
                f"(mismo docente y aula, sin nuevos cruces)"
            )
        if len(alternativas) >= max_alternativas:
            break
    return alternativas


def generar_alternativas(conflicto: Conflicto, propuesta, docentes, aulas) -> list:
    """Punto de entrada del motor de recomendación (RF-10). Despacha
    según el tipo de conflicto a la búsqueda de vecindario adecuada."""
    sesion = conflicto.sesiones[0]

    if conflicto.tipo in ("RD-02", "RD-06", "RD-10"):
        alternativas = sugerir_aulas_alternativas(sesion, propuesta, aulas)
        alternativas += sugerir_franjas_alternativas(sesion, propuesta)
        return alternativas or ["No se encontró un aula ni una franja alternativa en los datos de prueba; requiere ajuste manual."]

    if conflicto.tipo in ("RD-01", "RD-05"):
        alternativas = sugerir_franjas_alternativas(sesion, propuesta)
        return alternativas or ["No se encontró una franja alternativa sin cruce; requiere ajuste manual."]

    if conflicto.tipo == "RD-09":
        docente = next((d for d in docentes if d.id == sesion.docente_id), None)
        nombre = docente.nombre if docente else sesion.docente_id
        return [
            f"Redistribuir alguna sesión de {nombre} a otro docente con la misma "
            f"especialidad y margen disponible, o reducir su carga asignada."
        ]

    # RD-03, RD-04, RD-08 y demás: sugerencia genérica de vecindario horario
    alternativas = sugerir_franjas_alternativas(sesion, propuesta)
    return alternativas or ["Requiere ajuste manual del coordinador (sin alternativa automática en este prototipo)."]
