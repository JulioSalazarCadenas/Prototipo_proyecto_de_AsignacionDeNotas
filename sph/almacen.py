"""Capa de persistencia (SQLite): creación del esquema, importación CSV, lectura de la propuesta y bitácora.

Convierte entre filas del esquema normalizado y los modelos del dominio (src.models). El dominio no
conoce SQL: ServicioHorarios y el motor trabajan con PropuestaHorario, Docente, Aula y Parametros.
"""
from __future__ import annotations
import csv, os, sqlite3
from datetime import datetime
from src.models import Sesion, PropuestaHorario, Docente, Aula, Dedicacion, Tecnologia, HORAS_MAXIMAS_POR_DEDICACION
from .parametros import Parametros

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
RUTA_ESQUEMA = os.path.join(os.path.dirname(__file__), "schema.sql")

REGLAS = [
    ("RD-01", "DURA", "Cruce de docente", "Un docente no puede tener dos sesiones simultáneas."),
    ("RD-02", "DURA", "Cruce de aula", "Un aula no puede tener dos sesiones simultáneas."),
    ("RD-03", "DURA", "Cruce de grupo", "Un grupo no puede tener dos asignaturas distintas en el mismo bloque."),
    ("RD-04", "DURA", "Franja institucional y receso", "Toda sesión debe estar dentro de la franja y fuera del receso."),
    ("RD-05", "DURA", "Disponibilidad del docente", "La sesión debe caer en una franja declarada por el docente."),
    ("RD-06", "DURA", "Capacidad del aula", "El cupo esperado no puede superar la capacidad del aula."),
    ("RD-07", "DURA", "Duración de la sesión", "La sesión debe durar exactamente la duración parametrizada."),
    ("RD-08", "DURA", "Tope de estudiantes", "El cupo no puede superar el tope parametrizado (más tolerancia)."),
    ("RD-09", "DURA", "Carga vs. dedicación", "Las horas asignadas no pueden superar las de la dedicación."),
    ("RD-10", "DURA", "Tecnología del aula", "El aula debe tener la tecnología que requiere la sección."),
    ("RB-01", "BLANDA", "Evitar días consecutivos", "Evitar sesiones del mismo curso en días consecutivos."),
    ("RB-02", "BLANDA", "Distribuir horas del curso", "Distribuir las sesiones del mismo curso en horas distintas."),
    ("RB-03", "BLANDA", "Minimizar huecos", "Minimizar los huecos del docente en el día."),
]
PARAMS_GLOBALES = [("duracion_sesion", "ENTERO"), ("tope_estudiantes", "ENTERO"), ("tolerancia_tope", "REAL"),
                   ("franja_inicio", "ENTERO"), ("franja_fin", "ENTERO"), ("franja_fin_sabado", "ENTERO"),
                   ("receso_inicio", "ENTERO"), ("receso_fin", "ENTERO")]


class ErrorImportacion(Exception):
    def __init__(self, errores):
        self.errores = list(errores)
        super().__init__("; ".join(self.errores))


def ahora():
    return datetime.now().isoformat(timespec="seconds")


def conectar(ruta=":memory:"):
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def crear_bd(ruta=":memory:"):
    con = conectar(ruta)
    con.executescript(open(RUTA_ESQUEMA, encoding="utf-8").read())
    c = con.cursor()
    for i, d in enumerate(Dedicacion, start=1):
        c.execute("INSERT INTO dedicacion VALUES (?,?,?)", (i, d.value, HORAS_MAXIMAS_POR_DEDICACION[d]))
    for i, t in enumerate(Tecnologia, start=1):
        c.execute("INSERT INTO tecnologia VALUES (?,?)", (i, t.value))
    c.executemany("INSERT INTO regla(id_regla,tipo,nombre,descripcion) VALUES (?,?,?,?)", REGLAS)
    c.execute("INSERT INTO usuario(nombre, correo, rol) VALUES ('Administrador','admin@sph.local','ADMIN')")
    con.commit()
    return con


# ---------------------------------------------------------------- parámetros
def crear_semestre(con, semestre, inicio, fin):
    con.execute("INSERT OR IGNORE INTO semestre VALUES (?,?,?)", (semestre, inicio, fin))
    con.commit()


def sembrar_parametros(con, semestre, p: Parametros | None = None):
    p = p or Parametros()
    for clave, tipo in PARAMS_GLOBALES:
        con.execute("INSERT OR IGNORE INTO parametro(id_regla,id_semestre_desde,clave,tipo_valor,valor) VALUES (NULL,?,?,?,?)",
                    (semestre, clave, tipo, str(getattr(p, clave))))
    con.commit()


def guardar_parametro(con, clave, valor, desde, tipo=None, id_regla=None):
    tipo = tipo or ("ENTERO" if isinstance(valor, int) else "REAL" if isinstance(valor, float) else "TEXTO")
    con.execute("INSERT INTO parametro(id_regla,id_semestre_desde,clave,tipo_valor,valor) VALUES (?,?,?,?,?)",
                (id_regla, desde, clave, tipo, str(valor)))
    con.commit()


def fijar_parametro(con, clave, valor, desde, tipo=None):
    """Crea o actualiza el valor global de un parámetro con vigencia desde un semestre existente."""
    tipo = tipo or ("ENTERO" if isinstance(valor, int) else "REAL" if isinstance(valor, float) else "TEXTO")
    cur = con.execute("UPDATE parametro SET valor=?, tipo_valor=? WHERE id_regla IS NULL AND clave=? AND id_semestre_desde=?",
                      (str(valor), tipo, clave, desde))
    if cur.rowcount == 0:
        con.execute("INSERT INTO parametro(id_regla,id_semestre_desde,clave,tipo_valor,valor) VALUES (NULL,?,?,?,?)",
                    (desde, clave, tipo, str(valor)))
    con.commit()


def leer_parametros(con, semestre) -> Parametros:
    """Última definición de cada clave con vigencia <= semestre. Las horas máximas salen de DEDICACION."""
    campos = set(Parametros.__dataclass_fields__) - {"extra", "horas_maximas", "dias"}
    vals, extra = {}, {}
    q = "SELECT clave,tipo_valor,valor FROM parametro WHERE id_semestre_desde <= ? ORDER BY id_semestre_desde, id_parametro"
    for clave, tipo, valor in con.execute(q, (semestre,)):
        v = int(valor) if tipo == "ENTERO" else float(valor) if tipo == "REAL" else valor
        (vals if clave in campos else extra)[clave] = v
    horas = {n: h for n, h in con.execute("SELECT nombre, horas_maximas FROM dedicacion")}
    return Parametros(**vals, horas_maximas=horas, extra=extra)


# ---------------------------------------------------------------- importación CSV
def _leer(ruta):
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _disponibilidad(txt, ctx, errores):
    out = []
    for parte in filter(None, (x.strip() for x in (txt or "").split(";"))):
        try:
            dia, rango = parte.rsplit(" ", 1)
            hi, hf = (int(x) for x in rango.split("-"))
            if dia not in DIAS or not 0 <= hi < hf <= 24:
                raise ValueError
            out.append((dia, hi, hf))
        except ValueError:
            errores.append(f"{ctx}: disponibilidad inválida «{parte}» (formato: «Lunes 7-13;Martes 14-18», con 0 <= inicio < fin <= 24)")
    return out


COLUMNAS_CSV = {"docentes.csv": ["id", "nombre", "dedicacion", "especialidad", "disponibilidad"],
                "aulas.csv": ["id", "nombre", "capacidad", "tecnologias", "accesible"],
                "sesiones.csv": ["codigo", "curso", "grupo", "dia", "hora_inicio", "hora_fin", "docente_id", "aula_id", "cupo", "tecnologias"]}


def _vacios(archivo, filas, obligatorias, errores):
    """Registra las filas con campos obligatorios ausentes o en blanco."""
    for i, r in enumerate(filas, 2):
        faltan = [c for c in obligatorias if r.get(c) is None or not str(r[c]).strip()]
        if faltan:
            errores.append(f"{archivo} fila {i}: campo(s) obligatorio(s) vacío(s) o ausente(s): {', '.join(faltan)}")


def _revisar_archivos(carpeta):
    """Errores de existencia de la carpeta, de los tres archivos y de sus encabezados (antes de leer filas)."""
    if not os.path.isdir(carpeta):
        return [f"La carpeta «{carpeta}» no existe"]
    errores = []
    for nombre, cols in COLUMNAS_CSV.items():
        ruta = os.path.join(carpeta, nombre)
        if not os.path.isfile(ruta):
            errores.append(f"Falta {nombre} en la carpeta «{carpeta}»")
            continue
        with open(ruta, newline="", encoding="utf-8") as f:
            enc = next(csv.reader(f), [])
        faltan = [c for c in cols if c not in enc]
        if faltan:
            errores.append(f"{nombre}: faltan las columnas {', '.join(faltan)} (encabezado esperado: {','.join(cols)})")
    return errores


def importar_csv(con, carpeta, semestre="2026-2", nombre_propuesta="Propuesta importada", fechas=("2026-07-20", "2026-11-28")):
    """Importa docentes.csv, aulas.csv y sesiones.csv. Valida todo antes de escribir (todo o nada).
    Devuelve el id de la propuesta creada. Lanza ErrorImportacion con la lista completa de errores."""
    errores = _revisar_archivos(carpeta)
    if errores:
        raise ErrorImportacion(errores)
    docs = _leer(os.path.join(carpeta, "docentes.csv"))
    aulas = _leer(os.path.join(carpeta, "aulas.csv"))
    ses = _leer(os.path.join(carpeta, "sesiones.csv"))
    _vacios("docentes.csv", docs, ["id", "nombre", "dedicacion"], errores)
    _vacios("aulas.csv", aulas, ["id", "nombre", "capacidad"], errores)
    _vacios("sesiones.csv", ses, ["codigo", "curso", "grupo", "dia", "hora_inicio", "hora_fin", "docente_id", "aula_id", "cupo"], errores)
    if errores:
        raise ErrorImportacion(errores)
    ded_ok = {d.value for d in Dedicacion}
    tec_ok = {t.value for t in Tecnologia}
    ids_doc, ids_aula, codigos = set(), set(), set()
    for i, r in enumerate(docs, 2):
        if r["id"] in ids_doc: errores.append(f"docentes.csv fila {i}: id duplicado {r['id']}")
        ids_doc.add(r["id"])
        if r["dedicacion"] not in ded_ok: errores.append(f"docentes.csv fila {i}: dedicación desconocida «{r['dedicacion']}»")
        _disponibilidad(r.get("disponibilidad"), f"docentes.csv fila {i}", errores)
    for i, r in enumerate(aulas, 2):
        if r["id"] in ids_aula: errores.append(f"aulas.csv fila {i}: id duplicado {r['id']}")
        ids_aula.add(r["id"])
        if not r["capacidad"].isdigit() or int(r["capacidad"]) <= 0: errores.append(f"aulas.csv fila {i}: capacidad inválida")
        for t in filter(None, r.get("tecnologias", "").split(";")):
            if t not in tec_ok: errores.append(f"aulas.csv fila {i}: tecnología desconocida «{t}»")
    secciones = {}
    for i, r in enumerate(ses, 2):
        ctx = f"sesiones.csv fila {i}"
        if r["codigo"] in codigos: errores.append(f"{ctx}: código duplicado {r['codigo']}")
        codigos.add(r["codigo"])
        if r["dia"] not in DIAS: errores.append(f"{ctx}: día inválido «{r['dia']}»")
        if r["docente_id"] not in ids_doc: errores.append(f"{ctx}: docente inexistente {r['docente_id']}")
        if r["aula_id"] not in ids_aula: errores.append(f"{ctx}: aula inexistente {r['aula_id']}")
        try:
            hi, hf, cupo = int(r["hora_inicio"]), int(r["hora_fin"]), int(r["cupo"])
            if not (0 <= hi < hf <= 24) or cupo <= 0: raise ValueError
        except ValueError:
            errores.append(f"{ctx}: horas o cupo inválidos"); continue
        tecs = frozenset(filter(None, r.get("tecnologias", "").split(";")))
        for t in tecs:
            if t not in tec_ok: errores.append(f"{ctx}: tecnología desconocida «{t}»")
        clave = (r["curso"], r["grupo"])
        previo = secciones.setdefault(clave, (cupo, tecs, r["codigo"]))
        if previo[:2] != (cupo, tecs):   # 3FN: cupo y tecnología pertenecen a la sección, no a la sesión
            errores.append(f"{ctx} ({r['codigo']}): la sección {clave[0]} / {clave[1]} ya se definió en {previo[2]} con otro cupo o "
                           f"tecnología; cupo y tecnología son de la sección (use otro grupo si es otra sección)")
    if errores:
        raise ErrorImportacion(errores)
    c = con.cursor()
    c.execute("INSERT OR IGNORE INTO semestre VALUES (?,?,?)", (semestre, *fechas))
    sembrar_parametros(con, semestre)
    ded = {n: i for i, n in c.execute("SELECT id_dedicacion, nombre FROM dedicacion")}
    tec = {n: i for i, n in c.execute("SELECT id_tecnologia, nombre FROM tecnologia")}
    esp = {}
    for r in docs:
        e = r.get("especialidad") or None
        if e and e not in esp:
            c.execute("INSERT INTO especialidad(nombre) VALUES (?)", (e,)); esp[e] = c.lastrowid
        c.execute("INSERT INTO docente VALUES (?,?,?,?)", (r["id"], r["nombre"], ded[r["dedicacion"]], esp.get(e)))
        for dia, hi, hf in _disponibilidad(r.get("disponibilidad"), "", []):
            c.execute("INSERT INTO disponibilidad_docente(id_docente,dia,hora_inicio,hora_fin) VALUES (?,?,?,?)",
                      (r["id"], DIAS.index(dia) + 1, hi, hf))
    for r in aulas:
        c.execute("INSERT INTO aula VALUES (?,?,?,?)", (r["id"], r["nombre"], int(r["capacidad"]), int(r.get("accesible", "0") in ("1", "true", "True", "sí"))))
        for t in filter(None, r.get("tecnologias", "").split(";")):
            c.execute("INSERT INTO aula_tecnologia VALUES (?,?)", (r["id"], tec[t]))
    c.execute("INSERT INTO propuesta(id_semestre,id_usuario,nombre,estado,creada_en) VALUES (?,1,?,'BORRADOR',?)",
              (semestre, nombre_propuesta, ahora()))
    idp = c.lastrowid
    ofertas = {}
    for r in ses:
        clave = (r["curso"], r["grupo"])
        if clave not in ofertas:
            c.execute("INSERT OR IGNORE INTO curso VALUES (?,?)", (r["curso"], r["curso"]))
            c.execute("INSERT OR IGNORE INTO grupo VALUES (?)", (r["grupo"],))
            cupo, tecs, _ = secciones[clave]
            c.execute("INSERT OR IGNORE INTO oferta(id_semestre,id_curso,id_grupo,cupo_esperado) VALUES (?,?,?,?)",
                      (semestre, *clave, cupo))
            ofertas[clave] = c.execute("SELECT id_oferta FROM oferta WHERE id_semestre=? AND id_curso=? AND id_grupo=?",
                                       (semestre, *clave)).fetchone()[0]
            for t in tecs:
                c.execute("INSERT OR IGNORE INTO oferta_tecnologia VALUES (?,?)", (ofertas[clave], tec[t]))
        c.execute("INSERT INTO sesion(id_propuesta,codigo,id_oferta,id_docente,id_aula,dia,hora_inicio,hora_fin) VALUES (?,?,?,?,?,?,?,?)",
                  (idp, r["codigo"], ofertas[clave], r["docente_id"], r["aula_id"], DIAS.index(r["dia"]) + 1,
                   int(r["hora_inicio"]), int(r["hora_fin"])))
    con.commit()
    return idp


def resolver_fechas(semestre, inicio=None, fin=None):
    """Fechas (inicio, fin) del semestre. El 2026-2 tiene las de la demostración; cualquier otro semestre
    exige ambas fechas (AAAA-MM-DD, con fin posterior a inicio). Lanza ValueError con un mensaje legible."""
    from datetime import date
    if not (inicio or fin) and semestre == "2026-2":
        return ("2026-07-20", "2026-11-28")
    if not (inicio and fin):
        raise ValueError(f"Para el semestre {semestre} indique las fechas de inicio y fin (AAAA-MM-DD).")
    try:
        ini, fi = date.fromisoformat(inicio), date.fromisoformat(fin)
    except ValueError:
        raise ValueError("Las fechas deben tener el formato AAAA-MM-DD (por ejemplo, 2027-01-25).") from None
    if fi <= ini:
        raise ValueError("La fecha de fin debe ser posterior a la de inicio.")
    return (inicio, fin)


def importar_a_archivo(ruta_bd, carpeta, semestre="2026-2", nombre_propuesta="Propuesta importada", fechas=("2026-07-20", "2026-11-28")):
    """Importa en un archivo temporal y lo promueve a `ruta_bd` solo si todo es válido: una importación rechazada
    (incluso sobre una base existente) no crea ni borra nada. Devuelve el id de la propuesta creada."""
    tmp = ruta_bd + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = crear_bd(tmp)
    try:
        idp = importar_csv(con, carpeta, semestre, nombre_propuesta, fechas)
    except BaseException:
        con.close()
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    con.close()
    os.replace(tmp, ruta_bd)
    return idp


# ---------------------------------------------------------------- lectura
def cargar(con, id_propuesta):
    """(docentes, aulas, PropuestaHorario, Parametros) de una propuesta guardada."""
    sem = con.execute("SELECT id_semestre FROM propuesta WHERE id_propuesta=?", (id_propuesta,)).fetchone()
    if sem is None:
        raise KeyError(f"No existe la propuesta {id_propuesta}")
    sem = sem[0]
    tec = {i: Tecnologia(v) for i, v in con.execute("SELECT id_tecnologia, nombre FROM tecnologia")}
    ded = {i: Dedicacion(n) for i, n in con.execute("SELECT id_dedicacion, nombre FROM dedicacion")}
    docentes, aulas, sesiones = [], [], []
    for did, nom, idd, esp in con.execute(
            "SELECT d.id_docente,d.nombre,d.id_dedicacion,e.nombre FROM docente d LEFT JOIN especialidad e USING(id_especialidad) ORDER BY 1"):
        fr = [(DIAS[dia - 1], hi, hf) for dia, hi, hf in con.execute(
            "SELECT dia,hora_inicio,hora_fin FROM disponibilidad_docente WHERE id_docente=? ORDER BY id_disponibilidad", (did,))]
        docentes.append(Docente(did, nom, ded[idd], esp or "", fr))
    atec = {}
    for aid, t in con.execute("SELECT id_aula,id_tecnologia FROM aula_tecnologia"):
        atec.setdefault(aid, set()).add(tec[t])
    for aid, nom, cap, acc in con.execute("SELECT id_aula,nombre,capacidad,accesible FROM aula ORDER BY 1"):
        aulas.append(Aula(aid, nom, cap, atec.get(aid, set()), bool(acc)))
    otec = {}
    for io, t in con.execute("SELECT id_oferta,id_tecnologia FROM oferta_tecnologia"):
        otec.setdefault(io, set()).add(tec[t])
    q = """SELECT s.codigo,o.id_curso,o.id_grupo,s.dia,s.hora_inicio,s.hora_fin,s.id_docente,s.id_aula,o.cupo_esperado,o.id_oferta
           FROM sesion s JOIN oferta o USING(id_oferta) WHERE s.id_propuesta=? ORDER BY s.id_sesion"""
    for cod, cur, gr, dia, hi, hf, did, aid, cupo, io in con.execute(q, (id_propuesta,)):
        sesiones.append(Sesion(cod, cur, gr, DIAS[dia - 1], hi, hf, did, aid, cupo, set(otec.get(io, set()))))
    return docentes, aulas, PropuestaHorario(sem, sesiones), leer_parametros(con, sem)


# ---------------------------------------------------------------- escritura de cambios (bitácora)
def registrar_cambio(con, id_propuesta, anterior: Sesion, nueva: Sesion, origen, criterio=None, regla=None,
                     usuario=1, deshace=None):
    """Actualiza la sesión y agrega una fila a la bitácora en la misma transacción. Devuelve id_cambio."""
    d = DIAS.index
    id_sesion = con.execute("SELECT id_sesion FROM sesion WHERE id_propuesta=? AND codigo=?",
                            (id_propuesta, anterior.id)).fetchone()[0]
    con.execute("UPDATE sesion SET id_docente=?,id_aula=?,dia=?,hora_inicio=?,hora_fin=? WHERE id_sesion=?",
                (nueva.docente_id, nueva.aula_id, d(nueva.dia) + 1, nueva.hora_inicio, nueva.hora_fin, id_sesion))
    cur = con.execute(
        """INSERT INTO cambio_sesion(id_propuesta,id_sesion,id_usuario,id_regla_origen,origen,criterio,
           dia_ant,hora_ini_ant,hora_fin_ant,id_aula_ant,id_docente_ant,dia_nue,hora_ini_nue,hora_fin_nue,id_aula_nue,id_docente_nue,
           deshace_id,realizado_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (id_propuesta, id_sesion, usuario, regla, origen, criterio,
         d(anterior.dia) + 1, anterior.hora_inicio, anterior.hora_fin, anterior.aula_id, anterior.docente_id,
         d(nueva.dia) + 1, nueva.hora_inicio, nueva.hora_fin, nueva.aula_id, nueva.docente_id, deshace, ahora()))
    return cur.lastrowid


def bitacora(con, id_propuesta):
    q = """SELECT c.id_cambio,s.codigo,c.origen,c.criterio,c.id_regla_origen,c.dia_ant,c.hora_ini_ant,c.id_aula_ant,c.id_docente_ant,
                   c.dia_nue,c.hora_ini_nue,c.id_aula_nue,c.id_docente_nue,c.deshace_id,c.realizado_en
           FROM cambio_sesion c JOIN sesion s USING(id_sesion) WHERE c.id_propuesta=? ORDER BY c.id_cambio"""
    return con.execute(q, (id_propuesta,)).fetchall()


# ---------------------------------------------------------------- activación de reglas
def reglas_inactivas(con) -> set:
    return {r for (r,) in con.execute("SELECT id_regla FROM regla WHERE activa=0")}


def fijar_regla_activa(con, id_regla, activa, nombre=None, descripcion=None):
    """Activa o desactiva una regla. Las reglas descubiertas por archivo (p. ej. RD-11) se registran al vuelo."""
    fila = con.execute("SELECT 1 FROM regla WHERE id_regla=?", (id_regla,)).fetchone()
    if fila is None:
        con.execute("INSERT INTO regla(id_regla,tipo,nombre,descripcion,activa) VALUES (?,?,?,?,?)",
                    (id_regla, "BLANDA" if id_regla.startswith("RB") else "DURA", nombre or id_regla,
                     descripcion or nombre or id_regla, int(activa)))
    else:
        con.execute("UPDATE regla SET activa=? WHERE id_regla=?", (int(activa), id_regla))
    con.commit()


# ---------------------------------------------------------------- validación de parámetros fijados por el usuario
def validar_parametro(clave, texto, actuales: Parametros):
    """Convierte `texto` al tipo del parámetro y verifica su coherencia. Devuelve (valor, tipo) o lanza ValueError.
    Las claves desconocidas se aceptan solo si son numéricas (parámetros de reglas añadidas, p. ej. RD-11)."""
    tipos = dict(PARAMS_GLOBALES)
    if clave in tipos:
        tipo = tipos[clave]
        try:
            valor = int(texto) if tipo == "ENTERO" else float(texto)
        except ValueError:
            raise ValueError(f"El valor de {clave} debe ser {'un entero' if tipo == 'ENTERO' else 'un número'}: recibido «{texto}»") from None
    else:
        tipo = "ENTERO" if texto.isdigit() else "REAL"
        try:
            valor = int(texto) if tipo == "ENTERO" else float(texto)
        except ValueError:
            raise ValueError(f"Parámetro desconocido «{clave}» con valor no numérico «{texto}». "
                             f"Claves de negocio: {', '.join(k for k, _ in PARAMS_GLOBALES)}") from None
    if valor < 0:
        raise ValueError(f"El valor de {clave} no puede ser negativo")
    prop = {k: getattr(actuales, k) for k, _ in PARAMS_GLOBALES}
    if clave in prop:
        prop[clave] = valor
        if prop["duracion_sesion"] < 1 or prop["tope_estudiantes"] < 1:
            raise ValueError("duracion_sesion y tope_estudiantes deben ser al menos 1")
        if not 0 <= prop["tolerancia_tope"] <= 1:
            raise ValueError("tolerancia_tope debe estar entre 0 y 1 (0.10 = 10 %)")
        if not 0 <= prop["franja_inicio"] < prop["franja_fin"] <= 24 or not prop["franja_inicio"] < prop["franja_fin_sabado"] <= 24:
            raise ValueError("La franja debe cumplir 0 <= franja_inicio < franja_fin <= 24 (y franja_fin_sabado dentro de ella)")
        if not prop["receso_inicio"] < prop["receso_fin"] <= 24:
            raise ValueError("El receso debe cumplir receso_inicio < receso_fin <= 24")
    return valor, tipo
