# SPH – Sistema de Planeación de Horarios de Clases

Proyecto Núcleo 2 (2026-2) · Universidad El Bosque · Programa de Ingeniería de Sistemas · Grupo 8
Docente: Ing. Samuel Galindo Pinzón

El SPH **detecta** los conflictos de una propuesta de horario (restricciones duras RD-01 a RD-10), **recomienda**
alternativas válidas, deja la **decisión al Coordinador** y **revalida**. Ningún movimiento puede crear un choque de
docente, aula o grupo: el servicio lo bloquea antes de escribir en la base de datos.

Alcance real de esta entrega (M3): aplicación con **frontend** (interfaz web local de una pantalla: rejilla semanal,
arrastrar y soltar, alternativas, resolución automática, parámetros y reglas), **backend** (servidor HTTP local con API
JSON, `sph/web.py`) y **base de datos** SQLite. Debajo, motor de restricciones (patrón Strategy), resolutor de descenso
estricto, servicio con bloqueo de choques, bitácora inmutable, importador CSV, exportación CSV/HTML y línea de comandos.
**No** incluye autenticación ni perfiles, ni la API REST completa ni PostgreSQL de M2 (ver Documento 1, Acta de Cierre).

## Documentación de la entrega

| Documento | Archivo |
|---|---|
| 1. Informe de Ingeniería | `PN2_Grupo8_Doc1_Informe.pdf` |
| 2. Anexos Técnicos (UML y DER) | `PN2_Grupo8_Doc2_Anexos.pdf` |
| 3. Manual Técnico (arquitectura, diccionario de datos, despliegue) | `PN2_Grupo8_Doc3_ManualTecnico.pdf` |
| 4. Manual de Usuario | `PN2_Grupo8_Doc4_ManualUsuario.pdf` |

## Requisitos

- Python 3.11 o superior (probado con 3.11, 3.12 y 3.13; el código no usa paquetes externos).
- SQLite incluido en la biblioteca estándar de Python (probado con SQLite 3.45.1).
- Solo para las pruebas: `pytest` (`requirements.txt`).

## Instalación desde cero

```bash
git clone <URL-del-repositorio> sph && cd sph
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt      # solo instala pytest
python -m pytest -q                  # debe terminar en «65 passed» (o más)
```

## Ejecutar la aplicación (interfaz web)

```bash
python main.py web --bd sph.db        # abre http://127.0.0.1:8000/ ; con --puerto 8001 cambia el puerto; --no-abrir no abre el navegador
```

Si la base no existe, la pantalla ofrece la demostración ampliada (30 docentes, 20 aulas, 73 sesiones, 14 conflictos), la pequeña (10 / 8 / 20, 11 conflictos) o subir sus tres CSV. El botón «Cargar datos» de la barra vuelve a abrir esas opciones (reemplaza los datos actuales). Solo escucha en
`127.0.0.1` (sin autenticación): no la exponga a una red. Ctrl+C detiene el servidor.

## Uso rápido por línea de comandos (demostración con 10 docentes, 8 aulas y 20 sesiones)

```bash
python main.py importar --bd sph.db --carpeta datos/ejemplo --reemplazar   # crea la BD y carga los CSV
python main.py validar  --bd sph.db                                        # 11 conflictos (RD-01 a RD-10)
python main.py recomendar S16 --bd sph.db                                  # tres alternativas válidas
python main.py recomendar S16 --aplicar 1 --bd sph.db                      # aplica la primera (queda en bitácora)
python main.py mover S01 --dia Miércoles --hora 7 --bd sph.db              # «prueba de ruptura»: BLOQUEADO
python main.py resolver --bd sph.db                                        # simulación (no guarda)
python main.py resolver --aplicar --bd sph.db                              # resuelve y guarda
python main.py deshacer --bd sph.db                                        # revierte el último cambio
python main.py bitacora --bd sph.db                                        # historial de cambios
python main.py exportar --formato html --salida horario.html --bd sph.db   # horario por grupo, docente y aula
python main.py exportar --formato csv  --salida horario.csv  --bd sph.db
python main.py reglas --desactivar RD-05 --bd sph.db                       # activar/desactivar reglas
```

Códigos de salida: `0` correcto · `1` error de uso o de datos · `2` movimiento bloqueado · `3` la propuesta tiene conflictos.

## Formato de los CSV de entrada (carpeta `datos/ejemplo/`)

- `docentes.csv`: `id, nombre, dedicacion, especialidad, disponibilidad` (`Lunes 7-13;Miércoles 7-13`; vacío = sin restricción).
  Dedicaciones: `tiempo_completo`, `tres_cuartos`, `medio_tiempo`, `un_cuarto`.
- `aulas.csv`: `id, nombre, capacidad, tecnologias, accesible` (tecnologías separadas por `;`: `computadores`, `video_beam`, `telepresencia`, `sillas_moviles`).
- `sesiones.csv`: `codigo, curso, grupo, dia, hora_inicio, hora_fin, docente_id, aula_id, cupo, tecnologias`.

La importación es **todo o nada**: si hay errores, se listan todos y no se escribe nada (ni se crea ni se borra ninguna base de datos). Si el archivo `--bd` ya existe, hay que usar `--reemplazar`; la base anterior solo se reemplaza cuando la importación es válida.

## Estructura del repositorio

```
main.py            punto de entrada (CLI y servidor web)
sph/               paquete del sistema (reglas, validador, resolutor, servicio, almacén, exportación, CLI, web.py, schema.sql)
sph/static/        frontend de la interfaz web (index.html, app.js, estilos.css)
src/               modelos del prototipo de M1 (Sesion, Docente, Aula…), sin modificar su semántica
datos/ejemplo/     conjunto de demostración pequeño (CSV: 10 docentes, 8 aulas, 20 sesiones)
datos/ampliado/    conjunto ampliado (30 docentes, 20 aulas, 73 sesiones); lo genera datos/generar_ampliado.py
tests/             65 pruebas automatizadas (pytest)
qa/                scripts de calidad: bloqueo de choques, estrés, ablación, modificabilidad; logs en qa/logs/
bench/             generador sintético y mediciones de escalabilidad
ejemplos_cambio/   RD-11 y parámetros 2027-1 para la prueba de modificabilidad
```

## Reproducir la evidencia de calidad

```bash
python -m qa.bloqueo           # intentos de crear choques sobre un horario limpio (11 casos)
python -m qa.modificabilidad   # escenarios de modificabilidad (4)
python -m qa.ablacion 3000     # efecto del reintento de conflictos atascados
python -m qa.estres qa/logs/estres.json   # 100 a 10 000 sesiones, extremo a extremo (tarda varios minutos)
python -m qa.bench_final qa/logs/bench_final.json
```

## Mantenimiento

Agregar una regla = crear `sph/reglas_rdNN.py` con una clase decorada `@regla("RD-NN")` (ver
`ejemplos_cambio/reglas_rd11.py`); no se modifica ningún archivo existente. Los valores de negocio (tope de estudiantes,
franja, receso, horas por dedicación) son datos de la base (tablas `parametro` y `dedicacion`). Detalle en el Documento 3.

## Autoría

Integrantes: David Esteban Caicedo Saldaña, Santiago Granados Pascagaza, Johan Santiago Yepes Casallas y
Jhonatan Camilo Lozano Buitrago. Para el uso de herramientas de IA, ver el anexo del Documento 1.
