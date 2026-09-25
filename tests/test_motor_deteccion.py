"""
Pruebas de humo (sanity checks) del motor de detección.
Ejecutar con: python -m pytest tests/  (o simplemente python tests/test_motor_deteccion.py)

Estas pruebas son mínimas -es un primer prototipo-, pero verifican que
cada restricción dura (RD-01 a RD-10) se dispare al menos una vez sobre
los datos de prueba, tal como exige el criterio de prueba del Informe M1
(Sección 3.3): "el sistema detecte el 100% de los conflictos duros
insertados deliberadamente".
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.datos_prueba import crear_docentes, crear_aulas, crear_propuesta_horario
from src.restricciones import detectar_todos


def test_detecta_todos_los_tipos_de_conflicto_insertados():
    docentes = crear_docentes()
    aulas = crear_aulas()
    propuesta = crear_propuesta_horario()

    conflictos = detectar_todos(propuesta, docentes, aulas)
    tipos_encontrados = {c.tipo for c in conflictos}

    tipos_esperados = {
        "RD-01", "RD-02", "RD-03", "RD-04", "RD-05",
        "RD-06", "RD-07", "RD-08", "RD-09", "RD-10",
    }
    faltantes = tipos_esperados - tipos_encontrados
    assert not faltantes, f"No se detectaron los tipos de conflicto: {faltantes}"


def test_no_hay_falsos_positivos_en_sesiones_limpias():
    """RNF-02: las sesiones que no se diseñaron con conflicto no
    deberían aparecer en ningún reporte (ver S01..S15 sin marcar)."""
    docentes = crear_docentes()
    aulas = crear_aulas()
    propuesta = crear_propuesta_horario()

    conflictos = detectar_todos(propuesta, docentes, aulas)
    sesiones_en_conflicto = {s.id for c in conflictos for s in c.sesiones}

    # S05 y S08 están diseñadas explícitamente sin conflicto.
    assert "S05" not in sesiones_en_conflicto
    assert "S08" not in sesiones_en_conflicto


if __name__ == "__main__":
    test_detecta_todos_los_tipos_de_conflicto_insertados()
    test_no_hay_falsos_positivos_en_sesiones_limpias()
    print("OK: todas las pruebas de humo pasaron.")
