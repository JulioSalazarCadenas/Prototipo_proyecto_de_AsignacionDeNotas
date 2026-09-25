# Sistema de Planeación de Horarios (SPH) — Prototipo

**Proyecto Núcleo 2 · Grupo 8 · Programa de Ingeniería de Sistemas · Universidad El Bosque · 2026-2**

Integrantes: David Esteban Caicedo Saldaña, Santiago Granados Pascagaza, Johan Santiago
Yepes Casallas, Julio César Salazar Cárdenas, Jhonatan Camilo Lozano Buitrago.
Docente: Ing. Samuel Galindo Pinzón.

## Propósito

Este repositorio contiene el primer prototipo del componente de software descrito en el
**Informe de Ingeniería Parte I** del proyecto: un sistema que, dada una propuesta de
horario del Programa de Ingeniería de Sistemas, **detecta conflictos** de restricciones
duras y **recomienda alternativas** para resolverlos, siguiendo el ciclo

```
detectar → recomendar → (el Coordinador Académico elige) → revalidar
```

hasta llegar a un horario sin conflictos para las condiciones vigentes del semestre. El
porqué de este enfoque (en vez de un optimizador global desde cero) está justificado en la
Sección 1.3 del Informe M1: acotar el problema a las ~80 aulas propias del programa y a una
estrategia de detección + recomendación por vecindario acotado lo hace viable en las doce
semanas del curso.

> **Estado: primer prototipo.** No pretende estar completo ni pulido — el objetivo de esta
> entrega es tener código funcionando en el repositorio desde el Módulo 1, como exigen los
> lineamientos del curso. Varias piezas (interfaz web, persistencia, selección interactiva)
> quedan para las siguientes iteraciones.

## Qué hace hoy

- Modela docentes, aulas, sesiones y la propuesta de horario del semestre (`src/models.py`).
- Detecta las diez restricciones duras identificadas en el Informe M1 —RD-01 a RD-10—
  (`src/restricciones.py`), con complejidad polinomial (no es un buscador combinatorio).
- Para cada conflicto, sugiere alternativas explorando un vecindario acotado (otra aula
  compatible, otra franja del mismo docente) en vez de recalcular todo el horario
  (`src/motor_recomendacion.py`).
- Corre sobre un conjunto de datos de prueba con 10 docentes, 8 aulas y 20 asignaturas,
  con conflictos insertados a propósito para poder verificar que el motor los detecta todos
  (`src/datos_prueba.py`), tal como exige el criterio de prueba de la Sección 3.3 del informe.

## Qué NO hace todavía

- No tiene interfaz web (RNF-04) — por ahora es un script de línea de comandos.
- No persiste datos en una base de datos (aún no hay Módulo 2 / decisión de stack).
- No permite seleccionar interactivamente una alternativa (RF-11): solo las lista.
- Dos preguntas del juicio de expertos (P5: ¿validar todo el semestre o por sección?, P9:
  ¿historial?) siguen abiertas y no están implementadas — ver Sección 6.4 del Informe M1.

## Cómo ejecutarlo

Requiere Python 3.9 o superior. No tiene dependencias externas.

```bash
python main.py
```

Esto imprime el estado de cada sesión (`[OK]` / `[CONFLICTO]`), el detalle de cada conflicto
encontrado y las alternativas sugeridas para resolverlo.

## Cómo correr las pruebas

```bash
python tests/test_motor_deteccion.py
```

Verifica que los diez tipos de restricción (RD-01 a RD-10) se detecten correctamente sobre
los datos de prueba, y que las sesiones sin conflicto no generen falsos positivos (RNF-02).

## Estructura del repositorio

```
pn2-prototype/
├── main.py                      # script de demostración (CLI)
├── src/
│   ├── models.py                # Docente, Aula, Sesión, PropuestaHorario
│   ├── restricciones.py         # motor de detección (RD-01 a RD-10)
│   ├── motor_recomendacion.py   # motor de recomendación de alternativas (RF-10)
│   └── datos_prueba.py          # conjunto de datos de prueba
└── tests/
    └── test_motor_deteccion.py  # pruebas de humo
```

## Trazabilidad con el Informe M1

Este prototipo cubre, de forma inicial, los requisitos RF-04 a RF-10 (detección y
recomendación) sobre las restricciones RD-01 a RD-10 (Tabla 2 del informe). El detalle
completo de requisitos, restricciones y la matriz de trazabilidad está en el Informe de
Ingeniería Parte I (Overleaf del equipo), no en este repositorio.
