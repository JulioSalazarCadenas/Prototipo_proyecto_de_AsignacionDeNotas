"""
Modelos de dominio del Sistema de Planeación de Horarios (SPH).
Proyecto Núcleo 2 - Grupo 8 - Universidad El Bosque.

Estos modelos representan las entidades descritas en el Informe de
Ingeniería Parte I (Sección 5, RF-01 a RF-03).
"""

from dataclasses import dataclass, field
from enum import Enum


class Dedicacion(Enum):
    """Dedicaciones docentes según el Estatuto Docente (RD-09)."""
    TIEMPO_COMPLETO = "tiempo_completo"
    TRES_CUARTOS = "tres_cuartos"
    MEDIO_TIEMPO = "medio_tiempo"
    UN_CUARTO = "un_cuarto"


# Horas semanales máximas asociadas a cada dedicación.
# NOTA: son valores de prototipo, pendientes de confirmar con Talento
# Humano (ver pregunta P3 del juicio de expertos, Informe M1).
HORAS_MAXIMAS_POR_DEDICACION = {
    Dedicacion.TIEMPO_COMPLETO: 20,
    Dedicacion.TRES_CUARTOS: 15,
    Dedicacion.MEDIO_TIEMPO: 10,
    Dedicacion.UN_CUARTO: 5,
}


class Tecnologia(Enum):
    """Características tecnológicas de un aula (RD-10)."""
    COMPUTADORES = "computadores"
    VIDEO_BEAM = "video_beam"
    TELEPRESENCIA = "telepresencia"
    SILLAS_MOVILES = "sillas_moviles"


DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]


@dataclass
class Docente:
    id: str
    nombre: str
    dedicacion: Dedicacion
    especialidad: str = ""
    # Franjas en las que el docente SÍ puede dictar clase.
    # Lista de tuplas (dia, hora_inicio, hora_fin). Si está vacía,
    # se asume disponibilidad total dentro de la franja institucional.
    franjas_disponibles: list = field(default_factory=list)

    def horas_maximas(self) -> int:
        return HORAS_MAXIMAS_POR_DEDICACION[self.dedicacion]


@dataclass
class Aula:
    id: str
    nombre: str
    capacidad: int
    tecnologia: set = field(default_factory=set)   # set[Tecnologia]
    accesibilidad: bool = False


@dataclass
class Sesion:
    """Una sesión de dos horas de una sección, ya ubicada en un
    día/franja/aula/docente (o pendiente de asignar aula/docente)."""
    id: str
    curso: str
    grupo: str          # cohorte de estudiantes, p.ej. "SIS-3A"
    dia: str
    hora_inicio: int     # hora en formato 24h, ej. 7, 14, 19
    hora_fin: int
    docente_id: str
    aula_id: str
    cupo_esperado: int = 30
    tecnologia_requerida: set = field(default_factory=set)  # set[Tecnologia]

    def se_traslapa_con(self, otra: "Sesion") -> bool:
        """True si esta sesión comparte día y se cruza en horario con otra."""
        if self.dia != otra.dia:
            return False
        return self.hora_inicio < otra.hora_fin and otra.hora_inicio < self.hora_fin

    def duracion(self) -> int:
        return self.hora_fin - self.hora_inicio


@dataclass
class PropuestaHorario:
    """La propuesta de horario del semestre que el SPH valida (RF-03).
    Puede haberse creado copiando la plantilla del semestre anterior."""
    semestre: str
    sesiones: list  # list[Sesion]

    def sesiones_de_docente(self, docente_id: str):
        return [s for s in self.sesiones if s.docente_id == docente_id]

    def sesiones_de_grupo(self, grupo: str):
        return [s for s in self.sesiones if s.grupo == grupo]
