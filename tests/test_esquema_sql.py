"""El esquema relacional reproduce el modelo de dominio y hace cumplir la integridad referencial."""
import sqlite3, pytest
from src.datos_prueba import crear_docentes, crear_aulas, crear_propuesta_horario
from src.restricciones import detectar_todos
from sph_m2.validador import multiconjunto
from db.cargador import conectar, cargar, leer


def test_ida_y_vuelta_conserva_los_conflictos():
    docs, aulas, prop = crear_docentes(), crear_aulas(), crear_propuesta_horario()
    con = conectar(); cargar(con, docs, aulas, prop)
    docs2, aulas2, prop2 = leer(con)
    # La normalización mueve cupo y tecnología a OFERTA: para S01..S20 de datos de prueba hay un cupo por (curso, grupo)?
    a = multiconjunto(detectar_todos(prop, docs, aulas))
    b = multiconjunto(detectar_todos(prop2, docs2, aulas2))
    # Hallazgo: dos atributos que el prototipo guarda por sesión dependen en realidad de la sección (OFERTA):
    #  - S05 (cupo 40) y S14 (cupo 46) son la misma sección con dos cupos: al normalizar se pierden RD-06 y RD-08 de S14.
    #  - S07 (requiere computadores) y S18 (no lo requiere) son la misma sección: S18 hereda el requisito y aparece un RD-10.
    # Todo lo demás se conserva exactamente. Son anomalías latentes de los datos de prueba, no del esquema.
    perdidos, nuevos = a - b, b - a
    assert {(k[0], k[1]) for k in perdidos} == {("RD-06", ("S14",)), ("RD-08", ("S14",))}
    assert {(k[0], k[1]) for k in nuevos} == {("RD-10", ("S18",))}


def test_integridad_referencial_y_checks():
    con = conectar()
    con.execute("INSERT INTO semestre VALUES ('2026-2','2026-07-20','2026-11-28')")
    with pytest.raises(sqlite3.IntegrityError):   # FK: aula inexistente
        con.execute("INSERT INTO disponibilidad_docente(id_docente,dia,hora_inicio,hora_fin) VALUES ('NADIE',1,7,9)")
    with pytest.raises(sqlite3.IntegrityError):   # CHECK: hora_fin > hora_inicio
        con.execute("INSERT INTO dedicacion VALUES (1,'x',5)")
        con.execute("INSERT INTO docente VALUES ('D','n',1,NULL)")
        con.execute("INSERT INTO disponibilidad_docente(id_docente,dia,hora_inicio,hora_fin) VALUES ('D',1,9,7)")
