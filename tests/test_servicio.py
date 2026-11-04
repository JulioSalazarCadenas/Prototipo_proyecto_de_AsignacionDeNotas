import pytest
from qa.bloqueo import CASOS, servicio_limpio, caso_rd09, _estado
from sph import almacen
from sph.servicio import ServicioHorarios, MovimientoBloqueado, SinCambiosParaDeshacer, Sugerencia
from sph.validador import por_tipo
import os

EJEMPLO = os.path.join(os.path.dirname(__file__), "..", "datos", "ejemplo")


def sv_ejemplo():
    con = almacen.crear_bd()
    return ServicioHorarios(con, almacen.importar_csv(con, EJEMPLO))


def test_horario_base_limpio():
    assert servicio_limpio().resumen()["total"] == 0


@pytest.mark.parametrize("regla,desc,sid,kw", CASOS, ids=[f"{c[0]}-{i}" for i, c in enumerate(CASOS)])
def test_bloquea_y_no_modifica_nada(regla, desc, sid, kw):
    sv = servicio_limpio()
    antes = _estado(sv)
    with pytest.raises(MovimientoBloqueado) as e:
        sv.mover(sid, **kw)
    assert regla in e.value.empeoran
    assert _estado(sv) == antes
    sv.recargar()                                    # lo que hay en la BD coincide con la memoria
    assert sv.resumen()["total"] == 0


def test_bloquea_rd09():
    sv = servicio_limpio()
    sid, kw = caso_rd09(sv)
    antes = _estado(sv)
    with pytest.raises(MovimientoBloqueado) as e:
        sv.mover(sid, **kw)
    assert "RD-09" in e.value.empeoran and _estado(sv) == antes


def test_rd08_se_detecta_en_datos_importados():
    assert sv_ejemplo().resumen()["por_regla"]["RD-08"] == 1


def test_movimiento_valido_se_persiste_y_queda_en_bitacora():
    sv = servicio_limpio()
    sv.mover("S01", dia="Martes", hora_inicio=14)
    sv.recargar()
    s = sv.sesion("S01")
    assert (s.dia, s.hora_inicio, s.hora_fin) == ("Martes", 14, 16)
    b = sv.bitacora()
    assert len(b) == 1 and b[0][1] == "S01" and b[0][2] == "MANUAL"


def test_movimiento_que_mejora_una_sesion_en_conflicto_es_permitido():
    sv = sv_ejemplo()
    antes = sv.resumen()["total"]
    r = sv.mover("S16", dia="Martes", hora_inicio=14)       # S16 choca con S02 (D02); se resuelve
    assert r.delta == -1 and sv.resumen()["total"] == antes - 1


def test_parametros_invalidos_no_alteran_nada():
    sv = servicio_limpio()
    for kw in (dict(dia="Domingo"), dict(aula="A99"), dict(docente="D99")):
        with pytest.raises(ValueError):
            sv.mover("S01", **kw)
    with pytest.raises(KeyError):
        sv.mover("S99", dia="Lunes")
    assert sv.bitacora() == []


def test_recomendar_devuelve_solo_alternativas_validas():
    sv = sv_ejemplo()
    base = por_tipo(sv.conflictos())
    for sid in ("S16", "S02", "S18", "S19", "S09", "S20", "S17", "S14"):
        for sug in sv.recomendar(sid, n=5):
            copia = sv.ctx.a_propuesta()
            sv2 = sv_ejemplo()
            sv2.mover(sid, sug.movimiento.dia, sug.movimiento.hora_inicio, sug.movimiento.aula_id, sug.movimiento.docente_id)
            nuevo = por_tipo(sv2.conflictos())
            assert all(nuevo[t] <= base[t] for t in nuevo), (sid, sug)
            assert sum(nuevo.values()) < sum(base.values())


def test_recomendar_en_sesion_sin_conflicto_no_propone():
    assert sv_ejemplo().recomendar("S04") == []


def test_aplicar_sugerencia_deja_trazabilidad():
    sv = sv_ejemplo()
    sug = sv.recomendar("S16", n=1)[0]
    sv.aplicar("S16", sug)
    f = sv.bitacora()[-1]
    assert f[2] == "SUGERENCIA" and f[3] == "Menor movimiento"


def test_resolver_auto_aplicar_equivale_a_simulacion():
    a, b = sv_ejemplo(), sv_ejemplo()
    sim = a.resolver_auto()
    assert a.resumen()["total"] == 11 and a.bitacora() == []        # simulación: no persiste
    real = b.resolver_auto(aplicar=True)
    assert (sim.iteraciones, sim.conflictos_finales) == (real.iteraciones, real.conflictos_finales) == (6, 4)
    b.recargar()
    assert b.resumen()["total"] == 4 and len(b.bitacora()) == 6


def test_dataset_de_ejemplo_pendientes_esperados():
    sv = sv_ejemplo()
    res = sv.resolver_auto(aplicar=True)
    assert sorted((c.tipo, tuple(s.id for s in c.sesiones)) for c in res.pendientes) == [
        ("RD-06", ("S14",)), ("RD-07", ("S17",)), ("RD-08", ("S14",)), ("RD-09", ("S06", "S17"))]


def test_deshacer_restaura_y_se_registra():
    sv = sv_ejemplo()
    antes = _estado(sv)[0]
    sv.mover("S16", dia="Martes", hora_inicio=14)
    sv.deshacer()
    assert _estado(sv)[0] == antes
    b = sv.bitacora()
    assert [x[2] for x in b] == ["MANUAL", "DESHACER"] and b[1][13] == b[0][0]
    with pytest.raises(SinCambiosParaDeshacer):
        sv.deshacer()


def test_deshacer_en_orden_inverso():
    sv = sv_ejemplo()
    antes = _estado(sv)[0]
    sv.mover("S16", dia="Martes", hora_inicio=14)
    sv.mover("S19", dia="Miércoles", hora_inicio=10)
    sv.deshacer(); sv.deshacer()
    assert _estado(sv)[0] == antes


def test_validar_marca_estado_de_la_propuesta():
    sv = servicio_limpio()
    assert sv.validar() is True
    assert sv.con.execute("SELECT estado FROM propuesta").fetchone()[0] == "VALIDADA"
    assert sv_ejemplo().validar() is False


def test_desactivar_regla_persiste_y_cambia_la_deteccion():
    sv = sv_ejemplo()
    assert "RD-05" in sv.resumen()["por_regla"]
    sv.activar_regla("RD-05", False)
    assert "RD-05" not in sv.resumen()["por_regla"] and sv.resumen()["total"] == 10
    sv2 = ServicioHorarios(sv.con, sv.id_propuesta)              # nueva instancia: la preferencia vive en la BD
    assert "RD-05" not in sv2.resumen()["por_regla"]
    sv2.activar_regla("RD-05", True)
    assert sv2.resumen()["total"] == 11
    with pytest.raises(KeyError):
        sv2.activar_regla("RD-99", False)


def test_el_resolutor_respeta_las_reglas_inactivas():
    sv = sv_ejemplo()
    sv.activar_regla("RD-05", False)
    res = sv.resolver_auto()
    assert all(c.tipo != "RD-05" for c in res.pendientes) and res.conflictos_iniciales == 10


def test_cli_parametros_cambian_la_deteccion(tmp_path, capsys):
    from sph import cli
    bd = str(tmp_path / "t.db")
    assert cli.main(["importar", "--bd", bd, "--carpeta", EJEMPLO]) == 0
    assert cli.main(["parametros", "--bd", bd, "--fijar", "tope_estudiantes=35"]) == 0
    salida = capsys.readouterr().out
    assert "tope_estudiantes     35" in salida and "Conflictos: 15" in salida
    assert cli.main(["parametros", "--bd", bd, "--fijar", "tope_estudiantes=35", "--desde", "2028-1"]) == 1   # semestre inexistente
    assert cli.main(["parametros", "--bd", bd, "--fijar", "tope_estudiantes=40"]) == 0
    assert "Conflictos: 11" in capsys.readouterr().out


def test_cli_prueba_de_ruptura_devuelve_codigo_2(tmp_path, capsys):
    from sph import cli
    bd = str(tmp_path / "t.db")
    cli.main(["importar", "--bd", bd, "--carpeta", EJEMPLO])
    cli.main(["mover", "S16", "--bd", bd, "--dia", "Martes", "--hora", "14"])     # resuelve un conflicto (permitido)
    assert cli.main(["mover", "S01", "--bd", bd, "--dia", "Miércoles", "--hora", "7"]) == 2
    assert "BLOQUEADO" in capsys.readouterr().out


def test_exportar_csv_marca_las_sesiones_en_conflicto(tmp_path):
    import csv as _csv
    from sph import exportar
    sv = sv_ejemplo()
    ruta = exportar.exportar_csv(sv, str(tmp_path / "h.csv"))
    filas = list(_csv.DictReader(open(ruta, encoding="utf-8")))
    assert len(filas) == 20
    por = {f["codigo"]: f for f in filas}
    assert "RD-01" in por["S16"]["conflictos"] and por["S04"]["conflictos"] == ""
    assert por["S02"]["docente"] == "Carlos Peña"


def test_exportar_html_tiene_las_tres_vistas_y_resalta_conflictos(tmp_path):
    from sph import exportar
    sv = sv_ejemplo()
    html = open(exportar.exportar_html(sv, str(tmp_path / "h.html")), encoding="utf-8").read()
    for titulo in ("Por grupo", "Por docente", "Por aula"):
        assert titulo in html
    assert "Conflictos abiertos: 11" in html and 'class="ses mal"' in html
    sv.resolver_auto(aplicar=True)
    html2 = open(exportar.exportar_html(sv, str(tmp_path / "h2.html")), encoding="utf-8").read()
    assert "Conflictos abiertos: 4" in html2


def test_cli_parametro_invalido_se_rechaza_sin_escribir(tmp_path, capsys):
    from sph import cli
    bd = str(tmp_path / "t.db")
    cli.main(["importar", "--bd", bd, "--carpeta", EJEMPLO])
    capsys.readouterr()
    for malo in ("tope_estudiantes=abc", "tope_estudiantes=40.5", "tope_estudiantes=-3", "tolerancia_tope=2",
                 "franja_inicio=23", "receso_inicio=14", "inventado=hola"):
        assert cli.main(["parametros", "--bd", bd, "--fijar", malo]) == 1, malo
    assert cli.main(["parametros", "--bd", bd, "--fijar", "tope_estudiantes=35", "tope_estudiantes=xyz"]) == 1   # todo o nada
    capsys.readouterr()
    assert cli.main(["validar", "--bd", bd]) == 3                      # la base sigue operando
    assert "Conflictos: 11" in capsys.readouterr().out


def test_cli_importar_carpeta_inexistente_no_crea_ni_borra(tmp_path, capsys):
    from sph import cli
    bd = str(tmp_path / "t.db")
    assert cli.main(["importar", "--bd", bd, "--carpeta", str(tmp_path / "nohay")]) == 1
    assert not os.path.exists(bd) and not os.path.exists(bd + ".tmp")
    assert "no existe" in capsys.readouterr().out
    assert cli.main(["importar", "--bd", bd, "--carpeta", EJEMPLO]) == 0
    # una importación rechazada con --reemplazar conserva la base anterior
    vacia = tmp_path / "vacia"; vacia.mkdir()
    assert cli.main(["importar", "--bd", bd, "--carpeta", str(vacia), "--reemplazar"]) == 1
    assert "Falta docentes.csv" in capsys.readouterr().out
    assert cli.main(["validar", "--bd", bd]) == 3 and not os.path.exists(bd + ".tmp")


def test_importar_rechaza_encabezados_incompletos(tmp_path):
    import shutil
    carpeta = tmp_path / "c"; shutil.copytree(EJEMPLO, carpeta)
    (carpeta / "aulas.csv").write_text("id,nombre\nA01,Salón\n", encoding="utf-8")
    with pytest.raises(almacen.ErrorImportacion) as e:
        almacen.importar_csv(almacen.crear_bd(), str(carpeta))
    assert "faltan las columnas capacidad, tecnologias, accesible" in e.value.errores[0]


def test_cli_importar_sobre_base_existente_exige_reemplazar(tmp_path, capsys):
    from sph import cli
    bd = str(tmp_path / "t.db")
    assert cli.main(["importar", "--bd", bd, "--carpeta", EJEMPLO]) == 0
    capsys.readouterr()
    assert cli.main(["importar", "--bd", bd, "--carpeta", EJEMPLO]) == 1
    assert "Use --reemplazar" in capsys.readouterr().out
    assert cli.main(["importar", "--bd", bd, "--carpeta", EJEMPLO, "--reemplazar"]) == 0
    assert not os.path.exists(bd + ".tmp")


def _copia_ejemplo(tmp_path, archivo, reemplazos):
    """Copia el conjunto de ejemplo y reemplaza texto en un CSV (conserva los saltos de línea)."""
    import shutil
    carpeta = tmp_path / "c"; shutil.copytree(EJEMPLO, carpeta)
    ruta = carpeta / archivo
    texto = ruta.read_bytes().decode("utf-8")
    for viejo, nuevo in reemplazos:
        assert viejo in texto, viejo
        texto = texto.replace(viejo, nuevo, 1)
    ruta.write_bytes(texto.encode("utf-8"))
    return carpeta


def test_importar_rechaza_disponibilidad_con_horas_invertidas(tmp_path, capsys):
    from sph import cli
    carpeta = _copia_ejemplo(tmp_path, "docentes.csv", [("D01,Ana Torres,tiempo_completo,Algoritmos,", "D01,Ana Torres,tiempo_completo,Algoritmos,Lunes 13-7")])
    bd = str(tmp_path / "t.db")
    assert cli.main(["importar", "--bd", bd, "--carpeta", str(carpeta)]) == 1
    out = capsys.readouterr().out
    assert "disponibilidad inválida «Lunes 13-7»" in out and "Traceback" not in out
    assert not os.path.exists(bd) and not os.path.exists(bd + ".tmp")


def test_importar_rechaza_campos_obligatorios_vacios(tmp_path):
    carpeta = _copia_ejemplo(tmp_path, "aulas.csv", [("A01,", ",")])
    with pytest.raises(almacen.ErrorImportacion) as e:
        almacen.importar_csv(almacen.crear_bd(), str(carpeta))
    assert any("obligatorio" in m and "id" in m for m in e.value.errores)


def test_cli_importar_otro_semestre_exige_fechas_validas(tmp_path, capsys):
    from sph import cli
    bd = str(tmp_path / "t.db")
    base = ["importar", "--bd", bd, "--carpeta", EJEMPLO, "--semestre", "2027-1"]
    assert cli.main(base) == 1 and "indique las fechas" in capsys.readouterr().out
    assert cli.main(base + ["--inicio", "2027-13-45", "--fin", "2027-05-29"]) == 1 and "AAAA-MM-DD" in capsys.readouterr().out
    assert cli.main(base + ["--inicio", "2027-05-29", "--fin", "2027-01-25"]) == 1 and "posterior" in capsys.readouterr().out
    assert not os.path.exists(bd)
    assert cli.main(base + ["--inicio", "2027-01-25", "--fin", "2027-05-29"]) == 0
    con = almacen.conectar(bd)
    assert con.execute("SELECT fecha_inicio, fecha_fin FROM semestre WHERE id_semestre='2027-1'").fetchone() == ("2027-01-25", "2027-05-29")
