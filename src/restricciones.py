"""
Motor de detección de restricciones duras (RD-01 a RD-10).
Ver Informe de Ingeniería Parte I, Sección 3.2 (Tabla 2).

Cada función recibe la propuesta de horario completa y los catálogos
de docentes/aulas, y retorna una lista de objetos Conflicto.
La complejidad de cada verificación es polinomial (O(n^2) en el peor
caso, comparando pares de sesiones) tal como se sustenta en la
Sección 1.3 del informe: este motor NO genera el horario, solo lo
valida.
"""

from dataclasses import dataclass, field
from itertools import combinations

from .models import PropuestaHorario, Docente, Aula, Sesion, HORAS_MAXIMAS_POR_DEDICACION

FRANJA_INICIO = 7
FRANJA_FIN = 22
FRANJA_FIN_SABADO = 13
RECESO_INICIO = 12
RECESO_FIN = 13


@dataclass
class Conflicto:
    tipo: str            # "RD-01", "RD-02", ...
    descripcion: str
    sesiones: list = field(default_factory=list)  # list[Sesion]

    def __str__(self):
        ids = ", ".join(s.id for s in self.sesiones)
        return f"[{self.tipo}] {self.descripcion} (sesiones: {ids})"


def _docentes_por_id(docentes):
    return {d.id: d for d in docentes}


def _aulas_por_id(aulas):
    return {a.id: a for a in aulas}


def rd01_cruce_docente(propuesta: PropuestaHorario) -> list:
    """RD-01: un docente no puede tener dos sesiones simultáneas."""
    conflictos = []
    for s1, s2 in combinations(propuesta.sesiones, 2):
        if s1.docente_id == s2.docente_id and s1.se_traslapa_con(s2):
            conflictos.append(Conflicto(
                "RD-01",
                f"El docente {s1.docente_id} tiene dos sesiones cruzadas",
                [s1, s2],
            ))
    return conflictos


def rd02_cruce_aula(propuesta: PropuestaHorario) -> list:
    """RD-02: un aula no puede tener dos sesiones simultáneas."""
    conflictos = []
    for s1, s2 in combinations(propuesta.sesiones, 2):
        if s1.aula_id == s2.aula_id and s1.se_traslapa_con(s2):
            conflictos.append(Conflicto(
                "RD-02",
                f"El aula {s1.aula_id} tiene dos sesiones cruzadas",
                [s1, s2],
            ))
    return conflictos


def rd03_cruce_grupo(propuesta: PropuestaHorario) -> list:
    """RD-03: dos asignaturas del mismo grupo (cohorte) no pueden
    programarse en el mismo bloque horario."""
    conflictos = []
    for s1, s2 in combinations(propuesta.sesiones, 2):
        if s1.grupo == s2.grupo and s1.curso != s2.curso and s1.se_traslapa_con(s2):
            conflictos.append(Conflicto(
                "RD-03",
                f"El grupo {s1.grupo} tiene cruce entre {s1.curso} y {s2.curso}",
                [s1, s2],
            ))
    return conflictos


def rd04_franja_institucional(propuesta: PropuestaHorario) -> list:
    """RD-04: franja institucional y receso obligatorio."""
    conflictos = []
    for s in propuesta.sesiones:
        fin_dia = FRANJA_FIN_SABADO if s.dia == "Sábado" else FRANJA_FIN
        fuera_de_franja = s.hora_inicio < FRANJA_INICIO or s.hora_fin > fin_dia
        en_receso = s.hora_inicio < RECESO_FIN and RECESO_INICIO < s.hora_fin
        if fuera_de_franja:
            conflictos.append(Conflicto(
                "RD-04", f"Sesión {s.id} fuera de la franja institucional", [s]))
        if en_receso:
            conflictos.append(Conflicto(
                "RD-04", f"Sesión {s.id} cae en el receso 12m-1pm", [s]))
    return conflictos


def rd05_disponibilidad_docente(propuesta: PropuestaHorario, docentes: list) -> list:
    """RD-05: la sesión debe respetar las franjas declaradas por el docente."""
    conflictos = []
    docs = _docentes_por_id(docentes)
    for s in propuesta.sesiones:
        docente = docs.get(s.docente_id)
        if not docente or not docente.franjas_disponibles:
            continue  # sin restricción declarada
        compatible = any(
            dia == s.dia and hi <= s.hora_inicio and s.hora_fin <= hf
            for dia, hi, hf in docente.franjas_disponibles
        )
        if not compatible:
            conflictos.append(Conflicto(
                "RD-05",
                f"Sesión {s.id} fuera de la disponibilidad declarada por {docente.nombre}",
                [s],
            ))
    return conflictos


def rd06_capacidad_aula(propuesta: PropuestaHorario, aulas: list) -> list:
    """RD-06: el aula debe tener capacidad suficiente para el grupo."""
    conflictos = []
    aulas_dict = _aulas_por_id(aulas)
    for s in propuesta.sesiones:
        aula = aulas_dict.get(s.aula_id)
        if aula and s.cupo_esperado > aula.capacidad:
            conflictos.append(Conflicto(
                "RD-06",
                f"Sesión {s.id} espera {s.cupo_esperado} estudiantes "
                f"pero el aula {aula.nombre} tiene capacidad {aula.capacidad}",
                [s],
            ))
    return conflictos


def rd07_duracion_sesion(propuesta: PropuestaHorario, duracion_esperada: int = 2) -> list:
    """RD-07: cada sesión debe durar exactamente lo parametrizado
    (por defecto 2 horas, ver RF-13)."""
    conflictos = []
    for s in propuesta.sesiones:
        if s.duracion() != duracion_esperada:
            conflictos.append(Conflicto(
                "RD-07",
                f"Sesión {s.id} dura {s.duracion()}h, se esperaban {duracion_esperada}h",
                [s],
            ))
    return conflictos


def rd08_tope_estudiantes(propuesta: PropuestaHorario, tope: int = 40, tolerancia: float = 0.10) -> list:
    """RD-08: cupo máximo por sección (parametrizable)."""
    limite = int(tope * (1 + tolerancia))
    conflictos = []
    for s in propuesta.sesiones:
        if s.cupo_esperado > limite:
            conflictos.append(Conflicto(
                "RD-08",
                f"Sesión {s.id} espera {s.cupo_esperado} estudiantes, supera el tope de {limite}",
                [s],
            ))
    return conflictos


def rd09_dedicacion_docente(propuesta: PropuestaHorario, docentes: list) -> list:
    """RD-09: la carga total del docente no debe exceder su dedicación."""
    conflictos = []
    docs = _docentes_por_id(docentes)
    for docente in docentes:
        sesiones = propuesta.sesiones_de_docente(docente.id)
        horas_totales = sum(s.duracion() for s in sesiones)
        maximo = HORAS_MAXIMAS_POR_DEDICACION[docente.dedicacion]
        if horas_totales > maximo:
            conflictos.append(Conflicto(
                "RD-09",
                f"{docente.nombre} tiene {horas_totales}h asignadas, "
                f"excede su dedicación ({maximo}h/semana)",
                sesiones,
            ))
    return conflictos


def rd10_tecnologia_aula(propuesta: PropuestaHorario, aulas: list) -> list:
    """RD-10: el aula debe tener la tecnología/accesibilidad requerida."""
    conflictos = []
    aulas_dict = _aulas_por_id(aulas)
    for s in propuesta.sesiones:
        if not s.tecnologia_requerida:
            continue
        aula = aulas_dict.get(s.aula_id)
        if aula and not s.tecnologia_requerida.issubset(aula.tecnologia):
            faltante = s.tecnologia_requerida - aula.tecnologia
            nombres = ", ".join(t.value for t in faltante)
            conflictos.append(Conflicto(
                "RD-10",
                f"Aula {aula.nombre} no tiene la tecnología requerida por {s.id}: {nombres}",
                [s],
            ))
    return conflictos


# Lista de todas las verificaciones que requieren solo la propuesta.
_VERIFICACIONES_SOLO_PROPUESTA = [
    rd01_cruce_docente,
    rd02_cruce_aula,
    rd03_cruce_grupo,
    rd04_franja_institucional,
]


def detectar_todos(propuesta: PropuestaHorario, docentes: list, aulas: list) -> list:
    """Ejecuta las diez verificaciones de restricciones duras y agrega
    todos los conflictos encontrados. Ver RF-04 a RF-09 del Informe M1."""
    conflictos = []
    for verificacion in _VERIFICACIONES_SOLO_PROPUESTA:
        conflictos.extend(verificacion(propuesta))
    conflictos.extend(rd05_disponibilidad_docente(propuesta, docentes))
    conflictos.extend(rd06_capacidad_aula(propuesta, aulas))
    conflictos.extend(rd07_duracion_sesion(propuesta))
    conflictos.extend(rd08_tope_estudiantes(propuesta))
    conflictos.extend(rd09_dedicacion_docente(propuesta, docentes))
    conflictos.extend(rd10_tecnologia_aula(propuesta, aulas))
    return conflictos
