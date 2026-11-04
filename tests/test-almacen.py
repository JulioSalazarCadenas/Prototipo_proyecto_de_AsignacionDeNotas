import csv, os, shutil, sqlite3
import pytest
from sph import almacen
from sph.almacen import ErrorImportacion

EJEMPLO = os.path.join(os.path.dirname(__file__), "..", "datos", "ejemplo")


def copiar(tmp_path):
    for n in ("docentes.csv", "aulas.csv", "sesiones.csv"):
        shutil.copy(os.path.join(EJEMPLO, n), tmp_path)
    return tmp_path


def reescribir(ruta, fn):
    with open(ruta, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
        campos = list(filas[0].keys())
    fn(filas)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, campos); w.writeheader(); w.writerows(filas)


def test_importa_el_ejemplo_completo():
    con = almacen.crear_bd()
    idp = almacen.importar_csv(con, EJEMPLO)
    d, a, p, par = almacen.cargar(con, idp)
    assert (len(d), len(a), len(p.sesiones)) == (10, 8, 20)
    assert par.horas_maximas["un_cuarto"] == 5          # única fuente: tabla dedicacion


def test_importacion_todo_o_nada_con_todos_los_errores(tmp_path):
    carpeta = copiar(tmp_path)
    def romper(filas):
        filas[0]["docente_id"] = "D99"                  # docente inexistente
        filas[1]["dia"] = "Domingo"                     # día inválido
        filas[2]["codigo"] = filas[3]["codigo"]         # código duplicado
    reescribir(carpeta / "sesiones.csv", romper)
    con = almacen.crear_bd()
    with pytest.raises(ErrorImportacion) as e:
        almacen.importar_csv(con, str(carpeta))
    assert len(e.value.errores) == 3
    assert con.execute("SELECT COUNT(*) FROM sesion").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM docente").fetchone()[0] == 0


def test_rechaza_seccion_inconsistente(tmp_path):
    """3FN: cupo y tecnología son de la sección; dos filas de la misma sección no pueden contradecirse."""
    carpeta = copiar(tmp_path)
    def romper(filas):
        for f in filas:
            if f["codigo"] == "S14":
                f["grupo"] = "SIS-5A"                   # misma sección que S05 pero con cupo 46 (S05: 40)
    reescribir(carpeta / "sesiones.csv", romper)
    with pytest.raises(ErrorImportacion) as e:
        almacen.importar_csv(almacen.crear_bd(), str(carpeta))
    assert any("S14" in m and "sección" in m for m in e.value.errores)


def test_bitacora_es_inmutable():
    con = almacen.crear_bd()
    idp = almacen.importar_csv(con, EJEMPLO)
    d, a, p, par = almacen.cargar(con, idp)
    s = p.sesiones[0]
    from dataclasses import replace
    almacen.registrar_cambio(con, idp, s, replace(s, hora_inicio=14, hora_fin=16), "MANUAL")
    con.commit()
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("UPDATE cambio_sesion SET origen='MANUAL' WHERE id_cambio=1")
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("DELETE FROM cambio_sesion")


def test_parametros_con_vigencia_y_unicidad_con_regla_nula():
    con = almacen.crear_bd()
    almacen.importar_csv(con, EJEMPLO)
    almacen.crear_semestre(con, "2027-1", "2027-01-20", "2027-05-30")
    almacen.guardar_parametro(con, "tope_estudiantes", 35, "2027-1")
    assert almacen.leer_parametros(con, "2026-2").tope_estudiantes == 40
    assert almacen.leer_parametros(con, "2027-1").tope_estudiantes == 35
    with pytest.raises(sqlite3.IntegrityError):         # mismo (NULL, clave, vigencia): COALESCE lo detecta
        almacen.guardar_parametro(con, "tope_estudiantes", 36, "2027-1")


def test_tipo_de_valor_se_respeta_en_parametros():
    con = almacen.crear_bd()
    almacen.crear_semestre(con, "2026-2", "2026-07-20", "2026-11-28")
    almacen.sembrar_parametros(con, "2026-2")
    p = almacen.leer_parametros(con, "2026-2")
    assert isinstance(p.tolerancia_tope, float) and isinstance(p.duracion_sesion, int)


def test_claves_foraneas_activas():
    con = almacen.crear_bd()
    almacen.importar_csv(con, EJEMPLO)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO aula_tecnologia VALUES ('A99', 1)")
