# Sistema de Planeación de Horarios (SPH) — Prototipo

**Proyecto Núcleo 2 · Grupo 8 · Programa de Ingeniería de Sistemas · Universidad El Bosque · 2026-2**

Integrantes: David Esteban Caicedo Saldaña, Santiago Granados Pascagaza, Johan Santiago
Yepes Casallas, Julio César Salazar Cárdenas, Jhonatan Camilo Lozano Buitrago.
Docente: Ing. Samuel Galindo Pinzón.

## Propósito

Este repositorio contiene el prototipo del componente de software descrito en el
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

> **Estado: prototipo en evolución.** El repositorio tiene dos capas: el primer prototipo
> del Módulo 1 (`src/`) y la extensión del Módulo 2 (`sph_m2/`, `db/`, `bench/`), que
> reutiliza el primero sin modificarlo. Varias piezas (interfaz web, persistencia real,
> selección interactiva) quedan para las siguientes iteraciones.

## Qué hace hoy

**Prototipo base (Módulo 1) — `src/`**

- Modela docentes, aulas, sesiones y la propuesta de horario del semestre (`src/models.py`).
- Detecta las diez restricciones duras identificadas en el Informe M1 —RD-01 a RD-10—
  (`src/restricciones.py`), con complejidad polinomial (no es un buscador combinatorio).
- Para cada conflicto, sugiere alternativas explorando un vecindario acotado (otra aula
  compatible, otra franja del mismo docente) en vez de recalcular todo el horario
  (`src/motor_recomendacion.py`).
- Corre sobre un conjunto de datos de prueba con 10 docentes, 8 aulas y 20 asignaturas,
  con conflictos insertados a propósito para poder verificar que el motor los detecta todos
  (`src/datos_prueba.py`), tal como exige el criterio de prueba de la Sección 3.3 del informe.

**Extensión (Módulo 2) — `sph_m2/`, `db/`, `bench/`, `ejemplos_cambio/`**

- **Validador incremental** (`sph_m2/validador.py`, `sph_m2/reglas.py`, `sph_m2/indice.py`):
  las reglas RD-01 a RD-10 se reimplementan como estrategias intercambiables (patrón
  Strategy) registradas en un catálogo. Un índice de ocupación por docente, aula y grupo
  evita comparar todos los pares de sesiones (O(n²)). Agregar una regla nueva es crear un
  archivo `sph_m2/reglas_*.py`; el validador lo descubre solo, sin modificar código existente.
- **Parámetros externalizados** (`sph_m2/parametros.py`): los valores de negocio (por ejemplo,
  el tope de estudiantes) se leen de un JSON por semestre en lugar de estar fijos en el código
  (RF-13, RNF-06).
- **Resolutor iterativo** (`sph_m2/resolutor.py`): de descenso estricto con evaluación
  incremental. En cada iteración genera candidatos para un conflicto, conserva solo los que
  reducen el total de conflictos y elige uno según un criterio. Como el número de conflictos
  baja en cada paso, termina en a lo sumo C0 iteraciones (C0 = conflictos iniciales) y
  devuelve `SIN_CONFLICTOS` o `SIN_SOLUCION`.
- **Criterios de recomendación intercambiables** (`sph_m2/criterios.py`): menor movimiento,
  mantener aula, mantener docente y las reglas blandas RB-01 a RB-03 (evitar días
  consecutivos, distribuir horas, minimizar huecos), combinables por prioridad.
- **Esquema de base de datos** (`db/schema.sql`, `db/cargador.py`): modelo relacional del
  sistema y un cargador que vuelca los datos de prueba en SQLite en memoria y los reconstruye
  como `PropuestaHorario`, para verificar que el esquema es consistente con el modelo.
- **Benchmark de escalabilidad** (`bench/`): generador de horarios sintéticos con conflictos
  inyectados, una línea base ingenua (revalida copiando la propuesta completa con
  `src/restricciones.py`) y las mediciones que la comparan con el enfoque incremental.
- **Prueba de modificabilidad** (`ejemplos_cambio/`): una regla nueva (RD-11: un docente no
  puede dictar más de N sesiones el mismo día) y un cambio de parámetros para 2027-1
  (tope de estudiantes en 35), que se incorporan sin editar ningún archivo existente.

## Qué NO hace todavía

- No tiene interfaz web (RNF-04) — por ahora es un script de línea de comandos.
- `main.py` sigue usando solo el prototipo base (`src/`); el validador y el resolutor de
  `sph_m2/` se ejecutan desde las pruebas y el benchmark, no desde la CLI.
- No hay base de datos persistente: el esquema SQL solo se valida sobre SQLite en memoria
  y todavía no está conectado a la aplicación.
- No permite seleccionar interactivamente una alternativa (RF-11): el prototipo base solo las
  lista y el resolutor elige automáticamente según el criterio configurado.
- Dos preguntas del juicio de expertos (P5: ¿validar todo el semestre o por sección?, P9:
  ¿historial?) siguen abiertas y no están implementadas — ver Sección 6.4 del Informe M1.

## Cómo ejecutarlo

Requiere Python 3.9 o superior. El código no tiene dependencias externas (solo biblioteca
estándar); `pytest` es necesario únicamente para correr la suite de pruebas.

```bash
python main.py
```

Esto imprime el estado de cada sesión (`[OK]` / `[CONFLICTO]`), el detalle de cada conflicto
encontrado y las alternativas sugeridas para resolverlo.

## Cómo correr las pruebas

```bash
pip install pytest
python -m pytest tests/
```

La suite completa tiene 11 pruebas y tarda pocos segundos. La prueba original también se
puede ejecutar sola, sin pytest:

```bash
python tests/test_motor_deteccion.py
```

| Archivo | Qué verifica |
|---|---|
| `test_motor_deteccion.py` | Los diez tipos de restricción (RD-01 a RD-10) se detectan sobre los datos de prueba y las sesiones sin conflicto no generan falsos positivos (RNF-02). |
| `test_equivalencia.py` | El validador incremental de `sph_m2/` produce exactamente los mismos conflictos que el motor original de `src/`, tanto con los datos de prueba como con horarios aleatorios que ejercitan todas las reglas. |
| `test_resolutor.py` | El cambio en el número de conflictos calculado de forma incremental coincide con el recálculo completo; el resolutor termina sin empeorar nunca el horario; y los criterios se intercambian sin tocar el resolutor. |
| `test_esquema_sql.py` | Cargar los datos en el esquema SQL y leerlos de vuelta conserva los conflictos (salvo las diferencias esperadas por la normalización del esquema), y el esquema hace cumplir la integridad referencial y sus restricciones CHECK. |
| `test_ingenuo_vs_incremental.py` | La optimización no cambia las decisiones: el resolutor incremental sigue la misma trayectoria (estado, iteraciones y candidatos evaluados) que la línea base ingenua. |
| `test_prueba_de_cambio.py` | Agregar RD-11 y cambiar los parámetros a 2027-1 solo añade archivos nuevos (no modifica ninguno existente), y el sistema detecta con la regla y los parámetros nuevos manteniendo la evaluación incremental consistente. |

## Cómo correr el benchmark

Desde la raíz del repositorio (tarda cerca de un minuto):

```bash
python -m bench.run_bench resultados.json
```

Imprime las mediciones en consola y guarda los resultados en `resultados.json`
(entorno, detección, evaluación por candidato, resolución y variación del número de aulas).
Si no se indica archivo de salida, usa `resultados.json` en el directorio actual.

## Estructura del repositorio

```
pn2-prototype/
├── main.py                       # script de demostración (CLI, usa src/)
├── requirements.txt
├── src/                          # prototipo base (Módulo 1)
│   ├── models.py                 # Docente, Aula, Sesión, PropuestaHorario
│   ├── restricciones.py          # motor de detección (RD-01 a RD-10)
│   ├── motor_recomendacion.py    # motor de recomendación de alternativas (RF-10)
│   └── datos_prueba.py           # conjunto de datos de prueba
├── sph_m2/                       # extensión (Módulo 2)
│   ├── parametros.py             # parámetros de negocio por semestre
│   ├── reglas.py                 # RD-01 a RD-10 como estrategias + registro
│   ├── indice.py                 # índice de ocupación (contexto de validación)
│   ├── validador.py              # validador incremental
│   ├── criterios.py              # criterios de recomendación intercambiables
│   └── resolutor.py              # resolutor de descenso estricto
├── db/
│   ├── schema.sql                # esquema relacional
│   └── cargador.py               # carga/lectura sobre SQLite
├── bench/
│   ├── sintetico.py              # generador de horarios sintéticos
│   ├── ingenuo.py                # línea base ingenua
│   └── run_bench.py              # mediciones de escalabilidad
├── ejemplos_cambio/
│   ├── reglas_rd11.py            # regla RD-11 (ejemplo de extensión)
│   └── parametros_2027-1.json    # parámetros de ejemplo para 2027-1
└── tests/
    ├── test_motor_deteccion.py
    ├── test_equivalencia.py
    ├── test_resolutor.py
    ├── test_esquema_sql.py
    ├── test_ingenuo_vs_incremental.py
    └── test_prueba_de_cambio.py
```

> `ejemplos_cambio/reglas_rd11.py` está fuera de `sph_m2/` a propósito: el validador carga
> automáticamente todo archivo `sph_m2/reglas_*.py`, y esta regla es un ejemplo que solo se
> activa copiándola ahí (así lo hace `test_prueba_de_cambio.py`).

## Trazabilidad con el Informe M1

El prototipo base cubre los requisitos RF-04 a RF-10 (detección y recomendación) sobre las
restricciones RD-01 a RD-10 (Tabla 2 del informe). La extensión del Módulo 2 mantiene esas
mismas restricciones, agrega los criterios de recomendación RB-01 a RB-03 y externaliza los
parámetros de negocio (RF-13, RNF-06). El detalle completo de requisitos, restricciones y la
matriz de trazabilidad está en el Informe de Ingeniería Parte I (Overleaf del equipo), no en
este repositorio.
