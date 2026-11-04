"""Pruebas de restricciones: intentos de crear choques sobre un horario limpio. Cada caso debe ser BLOQUEADO
por la regla esperada y dejar intactas la memoria, la tabla sesion y la bitácora. Genera qa/logs/bloqueo.log."""
import csv, os, shutil, sys, tempfile
from sph import almacen
from sph.servicio import ServicioHorarios, MovimientoBloqueado

EJEMPLO = os.path.join(os.path.dirname(__file__), "..", "datos", "ejemplo")
CONFLICTIVAS = {"S09", "S14", "S16", "S17", "S18", "S19", "S20"}   # se excluyen para obtener un horario limpio


def servicio_limpio(carpeta=None, con=None):
    """Horario del ejemplo SIN las 7 sesiones con conflicto insertado: 13 sesiones, 0 conflictos."""
    carpeta = carpeta or tempfile.mkdtemp(prefix="sph_limpio_")
    for nombre in ("docentes.csv", "aulas.csv"):
        shutil.copy(os.path.join(EJEMPLO, nombre), carpeta)
    with open(os.path.join(EJEMPLO, "sesiones.csv"), newline="", encoding="utf-8") as f, \
            open(os.path.join(carpeta, "sesiones.csv"), "w", newline="", encoding="utf-8") as g:
        filas = list(csv.reader(f))
        w = csv.writer(g)
        w.writerow(filas[0])
        w.writerows(r for r in filas[1:] if r[0] not in CONFLICTIVAS)
    con = con or almacen.crear_bd()
    idp = almacen.importar_csv(con, carpeta)
    return ServicioHorarios(con, idp)


# (regla, descripción del intento, sesión, argumentos de mover)
CASOS = [
    ("RD-01", "Mover S01 al miércoles 7h, cuando su docente D01 ya dicta S11", "S01", dict(dia="Miércoles", hora_inicio=7)),
    ("RD-02", "Mover S01 al aula A02, ocupada el lunes 7-9 por S03", "S01", dict(aula="A02")),
    ("RD-03", "Mover S02 al lunes 7h: el grupo SIS-3A ya tiene S01 en ese bloque", "S02", dict(dia="Lunes", hora_inicio=7)),
    ("RD-04", "Mover S01 a las 11h (11-13 cruza el receso 12-13)", "S01", dict(hora_inicio=11)),
    ("RD-04", "Mover S01 a las 21h (21-23 sale de la franja 7-22)", "S01", dict(hora_inicio=21)),
    ("RD-05", "Mover S03 al jueves: la docente D03 solo declaró lunes, miércoles y viernes", "S03", dict(dia="Jueves")),
    ("RD-06", "Mover S01 (40 estudiantes) al aula A05 de capacidad 20", "S01", dict(aula="A05")),
    ("RD-07", "Alargar S01 a 3 horas (7-10)", "S01", dict(hora_fin=10)),
    ("RD-10", "Mover S02 (requiere computadores) al aula A01, que no los tiene", "S02", dict(aula="A01")),
]


def caso_rd09(sv):
    """RD-09: dos movimientos válidos hacia D06 (1/4 de tiempo, 5 h) y un tercero que lo lleva a 6 h."""
    sv.mover("S01", docente="D06")                       # D06: 2 + 2 = 4 h  (permitido)
    return "S11", dict(docente="D06")                    # 6 h > 5 h: debe bloquearse


def _estado(sv):
    filas = sv.con.execute("SELECT codigo,id_docente,id_aula,dia,hora_inicio,hora_fin FROM sesion ORDER BY id_sesion").fetchall()
    return filas, len(sv.bitacora()), {k: (v.dia, v.hora_inicio, v.hora_fin, v.aula_id, v.docente_id) for k, v in sv.ctx.por_id.items()}


def ejecutar(out=sys.stdout):
    resultados = []
    def intento(regla, desc, sv, sid, kw):
        antes = _estado(sv)
        try:
            sv.mover(sid, **kw)
            bloqueado, reglas, detalle = False, set(), []
        except MovimientoBloqueado as e:
            bloqueado, reglas, detalle = True, set(e.empeoran), e.conflictos
        intacto = _estado(sv) == antes
        ok = bloqueado and regla in reglas and intacto
        print(f"[{'OK' if ok else 'FALLA'}] {regla} · {desc}", file=out)
        print(f"       bloqueado={bloqueado} reglas={sorted(reglas)} BD/memoria/bitácora intactas={intacto}", file=out)
        for d in detalle:
            print(f"       {d}", file=out)
        resultados.append(ok)
    for regla, desc, sid, kw in CASOS:
        sv = servicio_limpio()
        assert not sv.conflictos(), "el horario base debe estar limpio"
        intento(regla, desc, sv, sid, kw)
    sv = servicio_limpio()
    sid, kw = caso_rd09(sv)
    intento("RD-09", "Con D06 ya en 4 h, asignarle S11 (2 h más = 6 h > 5 h de 1/4 de tiempo)", sv, sid, kw)
    # control positivo: un movimiento sin choques SÍ se aplica y queda en la bitácora
    sv = servicio_limpio()
    r = sv.mover("S01", dia="Martes", hora_inicio=14)
    ok = r.delta == 0 and len(sv.bitacora()) == 1 and not sv.conflictos()
    print(f"[{'OK' if ok else 'FALLA'}] CONTROL · Mover S01 al martes 14h (libre) se aplica y queda en bitácora (cambio #{r.id_cambio})", file=out)
    resultados.append(ok)
    # RD-08 no depende de la posición: el cupo es atributo de la sección
    print("[NOTA] RD-08 (tope de estudiantes) depende del cupo de la sección, que ningún movimiento modifica; "
          "se verifica en la detección (tests/test_servicio.py::test_rd08_se_detecta_en_datos_importados).", file=out)
    print(f"\nResumen: {sum(resultados)}/{len(resultados)} casos OK", file=out)
    return resultados


if __name__ == "__main__":
    sys.exit(0 if all(ejecutar()) else 1)
