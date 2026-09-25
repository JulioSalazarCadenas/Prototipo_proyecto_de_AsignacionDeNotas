#!/usr/bin/env python3
"""
Prototipo del Sistema de Planeación de Horarios (SPH) - Proyecto Núcleo 2.
Grupo 8 - Universidad El Bosque.

Este script demuestra, sobre el conjunto de datos de prueba definido en
src/datos_prueba.py, el ciclo descrito en el Informe M1 (Sección 3.3):

    detectar -> recomendar -> (el coordinador elige) -> revalidar

ADVERTENCIA: este es un PRIMER PROTOTIPO. Cubre el motor de detección
(RD-01 a RD-10) y una primera versión del motor de recomendación
(RF-10), pero todavía no tiene interfaz web (RNF-04), ni persistencia
en base de datos, ni la selección interactiva de alternativas (RF-11).
Esas piezas quedan para las siguientes iteraciones del Módulo 2/3.

Uso:
    python main.py
"""

from src.datos_prueba import crear_docentes, crear_aulas, crear_propuesta_horario
from src.restricciones import detectar_todos
from src.motor_recomendacion import generar_alternativas

VERDE = "\033[92m"
NARANJA = "\033[93m"
NEGRITA = "\033[1m"
RESET = "\033[0m"


def imprimir_encabezado(texto):
    print(f"\n{NEGRITA}{texto}{RESET}")
    print("-" * len(texto))


def main():
    docentes = crear_docentes()
    aulas = crear_aulas()
    propuesta = crear_propuesta_horario()

    imprimir_encabezado(
        f"Validando propuesta de horario {propuesta.semestre} "
        f"({len(propuesta.sesiones)} sesiones, {len(docentes)} docentes, {len(aulas)} aulas)"
    )

    conflictos = detectar_todos(propuesta, docentes, aulas)

    sesiones_en_conflicto = {s.id for c in conflictos for s in c.sesiones}
    for sesion in propuesta.sesiones:
        estado = f"{NARANJA}[CONFLICTO]{RESET}" if sesion.id in sesiones_en_conflicto else f"{VERDE}[OK]{RESET}"
        print(f"  {estado} {sesion.id} - {sesion.curso} ({sesion.grupo}) "
              f"{sesion.dia} {sesion.hora_inicio}:00-{sesion.hora_fin}:00 "
              f"- {sesion.docente_id} - {sesion.aula_id}")

    imprimir_encabezado(f"Conflictos detectados: {len(conflictos)}")
    if not conflictos:
        print(f"  {VERDE}Sin conflictos duros. El horario cumple las restricciones (Tabla 2).{RESET}")
        return

    for i, conflicto in enumerate(conflictos, start=1):
        print(f"\n  {NARANJA}{i}. {conflicto}{RESET}")
        alternativas = generar_alternativas(conflicto, propuesta, docentes, aulas)
        print("     Alternativas sugeridas:")
        for alt in alternativas:
            print(f"       - {alt}")

    imprimir_encabezado("Resumen por tipo de restricción")
    conteo = {}
    for c in conflictos:
        conteo[c.tipo] = conteo.get(c.tipo, 0) + 1
    for tipo in sorted(conteo):
        print(f"  {tipo}: {conteo[tipo]} conflicto(s)")


if __name__ == "__main__":
    main()
