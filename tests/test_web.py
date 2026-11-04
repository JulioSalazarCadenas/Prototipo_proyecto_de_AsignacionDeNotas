"""Interfaz web: API JSON sobre el servicio (sin navegador) y servidor HTTP real en un puerto libre."""
import json, os, threading, urllib.error, urllib.request
import pytest
from sph import web

EJEMPLO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "datos", "ejemplo")


@pytest.fixture
def app(tmp_path):
    a = web.Aplicacion(str(tmp_path / "w.db"))
    assert a.estado() == {"vacio": True}
    assert a.importar({"demo": True})["rechazado"] is False
    return a


@pytest.fixture
def servidor(tmp_path):
    srv = web.crear_servidor(str(tmp_path / "h.db"), 0)
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    yield base
    srv.shutdown(); srv.server_close()


def _llamar(base, ruta, datos=None, cabeceras=None):
    req = urllib.request.Request(base + ruta, data=None if datos is None else json.dumps(datos).encode(),
                                 headers={"Content-Type": "application/json", **(cabeceras or {})})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_estado_de_la_demostracion(app):
    e = app.estado()
    assert e["resumen"]["total"] == 11 and len(e["sesiones"]) == 20 and e["propuesta"]["estado"] == "BORRADOR"
    assert {s["id"] for s in e["sesiones"] if s["reglas"]} >= {"S01", "S16", "S19"}
    assert len(e["reglas"]) >= 10 and e["parametros"]["tope_estudiantes"] == 40


def test_mover_bloqueado_no_cambia_nada(app):
    antes = app.estado()
    r = app.mover({"sesion": "S01", "dia": "Miércoles", "hora": 7})
    assert r["bloqueado"] is True and "RD-01" in r["mensaje"]
    assert app.estado()["sesiones"] == antes["sesiones"] and app.estado()["bitacora"] == []


def test_recomendar_aplicar_y_deshacer(app):
    alts = app.recomendar({"sesion": "S16"})["alternativas"]
    assert alts and all(a["delta"] < 0 for a in alts)
    assert app.aplicar({"sesion": "S16", "k": 1})["resumen"]["total"] == 10
    e = app.estado()
    assert e["bitacora"][0]["origen"] == "SUGERENCIA" and e["bitacora"][0]["sesion"] == "S16"
    assert app.deshacer()["resumen"]["total"] == 11
    with pytest.raises(web.ErrorApi):
        app.deshacer(); app.deshacer()


def test_resolver_simula_y_aplica(app):
    sim = app.resolver({"aplicar": False})
    assert sim["finales"] < sim["iniciales"] and app.estado()["resumen"]["total"] == 11
    real = app.resolver({"aplicar": True})
    assert app.estado()["resumen"]["total"] == real["finales"] == 4


def test_parametros_validos_e_invalidos(app):
    assert app.parametros({"valores": {"tope_estudiantes": "35"}})["resumen"]["total"] > 11 - 1
    with pytest.raises(web.ErrorApi):
        app.parametros({"valores": {"tope_estudiantes": "abc"}})
    assert app.estado()["parametros"]["tope_estudiantes"] == 35


def test_regla_desactivada_permite_el_movimiento(app):
    app.regla({"id": "RD-01", "activa": False})
    assert any(r["id"] == "RD-01" and not r["activa"] for r in app.estado()["reglas"])
    assert app.mover({"sesion": "S01", "dia": "Miércoles", "hora": 7})["bloqueado"] is False


def test_importar_csv_enviados_por_el_navegador(tmp_path):
    a = web.Aplicacion(str(tmp_path / "n.db"))
    leer = lambda n: open(os.path.join(EJEMPLO, n + ".csv"), encoding="utf-8", newline="").read()
    ok = a.importar({"docentes": leer("docentes"), "aulas": leer("aulas"), "sesiones": leer("sesiones")})
    assert ok["rechazado"] is False and ok["estado"]["resumen"]["total"] == 11
    malo = a.importar({"docentes": leer("docentes"), "aulas": leer("aulas"), "sesiones": leer("sesiones").replace("D01", "D99", 1)})
    assert malo["rechazado"] is True and any("D99" in e for e in malo["errores"])
    assert a.estado()["resumen"]["total"] == 11 and not os.path.exists(str(tmp_path / "n.db") + ".tmp")


def test_importar_otro_semestre_exige_fechas_validas(tmp_path):
    import sqlite3
    a = web.Aplicacion(str(tmp_path / "s.db"))
    leer = lambda n: open(os.path.join(EJEMPLO, n + ".csv"), encoding="utf-8", newline="").read()
    base = {"docentes": leer("docentes"), "aulas": leer("aulas"), "sesiones": leer("sesiones"), "semestre": "2027-1"}
    for extra in ({}, {"inicio": "2027-01-25", "fin": "2027-01-20"}, {"inicio": "25/01/2027", "fin": "2027-05-30"}):
        with pytest.raises(web.ErrorApi):
            a.importar({**base, **extra})
    assert not os.path.exists(str(tmp_path / "s.db"))                    # nada se escribió
    assert a.importar({**base, "inicio": "2027-01-25", "fin": "2027-05-30"})["rechazado"] is False
    fila = sqlite3.connect(str(tmp_path / "s.db")).execute("SELECT * FROM semestre").fetchall()
    assert fila == [("2027-1", "2027-01-25", "2027-05-30")]


def test_importar_sin_archivos_es_un_error(tmp_path):
    with pytest.raises(web.ErrorApi):
        web.Aplicacion(str(tmp_path / "x.db")).importar({"docentes": "id,nombre\n"})


def test_http_pagina_api_y_exportacion(servidor):
    code, cuerpo = _llamar(servidor, "/")
    assert code == 200 and b"SPH" in cuerpo
    assert _llamar(servidor, "/static/app.js")[0] == 200 and _llamar(servidor, "/static/../schema.sql")[0] == 404
    assert json.loads(_llamar(servidor, "/api/estado")[1]) == {"vacio": True}
    assert _llamar(servidor, "/api/importar", {"demo": True})[0] == 200
    code, cuerpo = _llamar(servidor, "/api/mover", {"sesion": "S01", "dia": "Miércoles", "hora": 7})
    assert code == 200 and json.loads(cuerpo)["bloqueado"] is True
    code, cuerpo = _llamar(servidor, "/api/mover", {"sesion": "S99", "dia": "Lunes"})
    assert code == 400 and "S99" in json.loads(cuerpo)["error"]
    assert _llamar(servidor, "/exportar.csv")[1].startswith(b"codigo,curso")
    assert b"<h1>" in _llamar(servidor, "/exportar.html")[1]


def test_http_rechaza_origen_ajeno_y_json_invalido(servidor):
    code, _ = _llamar(servidor, "/api/validar", {}, {"Origin": "http://sitio-malo.example"})
    assert code == 403
    req = urllib.request.Request(servidor + "/api/validar", data=b"{no es json", headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 400


def test_demostracion_ampliada(tmp_path):
    a = web.Aplicacion(str(tmp_path / "amp.db"))
    r = a.importar({"demo": "ampliada"})
    assert r["rechazado"] is False
    est = r["estado"]
    assert (len(est["docentes"]), len(est["aulas"]), len(est["sesiones"])) == (30, 20, 73)
    assert est["resumen"]["total"] == 14
    assert {c["tipo"] for c in est["conflictos"]} == {f"RD-{n:02d}" for n in range(1, 11)}   # una o más por cada regla dura
    res = a.resolver({"aplicar": True})
    assert res["finales"] < res["iniciales"] and res["finales"] == 5
    assert a.importar({"demo": True})["estado"]["resumen"]["total"] == 11                    # la pequeña sigue disponible
