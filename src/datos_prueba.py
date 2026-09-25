"""
Conjunto de datos de prueba del prototipo, conforme al criterio de
prueba definido en el Informe M1 (Sección 3.3, Paso 3): al menos 10
docentes, un subconjunto representativo de las aulas propias del
programa, y 20 asignaturas -incluyendo horarios sin conflictos y
conflictos insertados deliberadamente para validar el motor de
detección.

Los nombres de docentes y aulas son ficticios, creados solo para
efectos de este prototipo.
"""

from .models import Docente, Aula, Sesion, PropuestaHorario, Dedicacion, Tecnologia


def crear_docentes():
    return [
        Docente("D01", "Ana Torres", Dedicacion.TIEMPO_COMPLETO, "Algoritmos"),
        Docente("D02", "Carlos Peña", Dedicacion.TIEMPO_COMPLETO, "Bases de Datos"),
        Docente("D03", "Diana Ruiz", Dedicacion.TRES_CUARTOS, "Redes",
                franjas_disponibles=[("Lunes", 7, 13), ("Miércoles", 7, 13), ("Viernes", 7, 13)]),
        Docente("D04", "Esteban Gómez", Dedicacion.MEDIO_TIEMPO, "Matemáticas",
                franjas_disponibles=[("Martes", 16, 22), ("Jueves", 16, 22)]),
        Docente("D05", "Fabiola Nieto", Dedicacion.TIEMPO_COMPLETO, "Ingeniería de Software"),
        Docente("D06", "Germán Salas", Dedicacion.UN_CUARTO, "Electiva"),
        Docente("D07", "Helena Prieto", Dedicacion.TRES_CUARTOS, "Sistemas Operativos"),
        Docente("D08", "Iván Cortés", Dedicacion.TIEMPO_COMPLETO, "Arquitectura de Software"),
        Docente("D09", "Julia Méndez", Dedicacion.MEDIO_TIEMPO, "Física"),
        Docente("D10", "Kevin Rojas", Dedicacion.TIEMPO_COMPLETO, "Inteligencia Artificial"),
    ]


def crear_aulas():
    return [
        Aula("A01", "Salón 301", capacidad=45, tecnologia={Tecnologia.VIDEO_BEAM}),
        Aula("A02", "Salón 302", capacidad=45, tecnologia={Tecnologia.VIDEO_BEAM}),
        Aula("A03", "Lab. Cómputo 1", capacidad=30,
             tecnologia={Tecnologia.COMPUTADORES, Tecnologia.VIDEO_BEAM}),
        Aula("A04", "Lab. Cómputo 2", capacidad=30,
             tecnologia={Tecnologia.COMPUTADORES, Tecnologia.VIDEO_BEAM}),
        Aula("A05", "Salón 205", capacidad=20, tecnologia=set()),
        Aula("A06", "Sala Telepresencia", capacidad=25,
             tecnologia={Tecnologia.TELEPRESENCIA, Tecnologia.VIDEO_BEAM}, accesibilidad=True),
        Aula("A07", "Salón 210 (accesible)", capacidad=35,
             tecnologia={Tecnologia.VIDEO_BEAM}, accesibilidad=True),
        Aula("A08", "Salón 110", capacidad=40, tecnologia={Tecnologia.VIDEO_BEAM}),
    ]


def crear_propuesta_horario() -> PropuestaHorario:
    """20 sesiones. La mayoría sin conflicto; unas pocas con un
    conflicto insertado a propósito, identificado en el comentario."""
    sesiones = [
        # --- Sesiones sin conflicto ---
        Sesion("S01", "Estructuras de Datos", "SIS-3A", "Lunes", 7, 9, "D01", "A01", 40),
        Sesion("S02", "Bases de Datos I", "SIS-3A", "Martes", 9, 11, "D02", "A03", 30,
               tecnologia_requerida={Tecnologia.COMPUTADORES}),
        Sesion("S03", "Redes de Computadores", "SIS-4A", "Lunes", 7, 9, "D03", "A02", 35),
        Sesion("S04", "Cálculo Diferencial", "SIS-1A", "Martes", 16, 18, "D04", "A05", 20),
        Sesion("S05", "Ingeniería de Software I", "SIS-5A", "Miércoles", 9, 11, "D05", "A01", 40),
        Sesion("S06", "Electiva de Profundización", "SIS-6A", "Jueves", 14, 16, "D06", "A05", 18),
        Sesion("S07", "Sistemas Operativos", "SIS-4A", "Viernes", 9, 11, "D07", "A03", 30,
               tecnologia_requerida={Tecnologia.COMPUTADORES}),
        Sesion("S08", "Arquitectura de Software", "SIS-6A", "Martes", 7, 9, "D08", "A02", 35),
        # RD-04: esta sesión cae parcialmente en el receso institucional (12m-1pm)
        Sesion("S09", "Física Mecánica", "SIS-1A", "Jueves", 11, 13, "D09", "A05", 20),
        Sesion("S10", "Inteligencia Artificial", "SIS-7A", "Miércoles", 14, 16, "D10", "A06", 25,
               tecnologia_requerida={Tecnologia.VIDEO_BEAM}),
        Sesion("S11", "Estructuras de Datos", "SIS-3A", "Miércoles", 7, 9, "D01", "A01", 40),
        Sesion("S12", "Bases de Datos I", "SIS-3A", "Jueves", 9, 11, "D02", "A04", 30,
               tecnologia_requerida={Tecnologia.COMPUTADORES}),
        Sesion("S13", "Redes de Computadores", "SIS-4A", "Miércoles", 7, 9, "D03", "A02", 35),
        # RD-08: 46 estudiantes supera el tope de 40 (+10% = 44)
        Sesion("S14", "Ingeniería de Software I", "SIS-5A", "Viernes", 9, 11, "D05", "A01", 46),
        Sesion("S15", "Proyecto de Telepresencia", "SIS-7A", "Viernes", 14, 16, "D10", "A06", 22,
               tecnologia_requerida={Tecnologia.TELEPRESENCIA}),

        # --- Conflictos insertados a propósito (para probar el motor) ---

        # RD-01: D02 queda con dos sesiones cruzadas el martes 9-11
        Sesion("S16", "Electiva de Bases de Datos", "SIS-6A", "Martes", 10, 12, "D02", "A08", 30),

        # RD-02: A01 queda con dos sesiones cruzadas el lunes 7-9 (choca con S01).
        # También, sumada a S06, deja a D06 (1/4 de tiempo, máx. 5h) en 6h: RD-09.
        Sesion("S17", "Cátedra Institucional", "SIS-1B", "Lunes", 8, 12, "D06", "A01", 40),

        # RD-03: mismo grupo SIS-4A con dos asignaturas cruzadas el lunes 7-9 (choca con S03)
        Sesion("S18", "Sistemas Operativos", "SIS-4A", "Lunes", 8, 10, "D07", "A08", 30),

        # RD-05: D03 solo declaró disponibilidad L/Mi/V en la mañana; esta sesión es jueves en la tarde
        Sesion("S19", "Redes Avanzadas", "SIS-4A", "Jueves", 16, 18, "D03", "A08", 30),

        # RD-06 + RD-10: aula A05 (cap. 20, sin cómputo) asignada a un curso de 30 que requiere cómputo
        Sesion("S20", "Minería de Datos", "SIS-7A", "Viernes", 16, 18, "D10", "A05", 30,
               tecnologia_requerida={Tecnologia.COMPUTADORES}),
    ]
    return PropuestaHorario(semestre="2026-2", sesiones=sesiones)
