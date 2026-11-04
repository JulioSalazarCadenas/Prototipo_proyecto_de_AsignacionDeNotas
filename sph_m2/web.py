"""Interfaz web local del SPH (solo biblioteca estándar).

`python main.py web --bd sph.db` levanta un servidor en 127.0.0.1 con una página única y una API JSON mínima.
Toda la lógica vive en `ServicioHorarios`: esta capa solo traduce HTTP <-> servicio. Un único usuario,
sin autenticación (el servidor solo escucha en la máquina local)."""
from __future__ import annotations
import json, os, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from . import almacen, exportar
from .cli import CRITERIOS
from .criterios import Compuesto
from .servicio import ServicioHorarios, MovimientoBloqueado, SinCambiosParaDeshacer

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(RAIZ, "datos", "ejemplo")
ESTATICOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
TIPOS = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}
_CERRADURA = threading.Lock()


class ErrorApi(Exception):
    """Error de uso (se devuelve al navegador como mensaje, con código 400)."""


def _criterio(texto):
    if not texto:
        return None
    nombres = [t.strip() for t in str(texto).split(",") if t.strip()]
    malos = [n for n in nombres if n not in CRITERIOS]
    if malos:
        raise ErrorApi(f"Criterio desconocido «{malos[0]}». Opciones: {', '.join(CRITERIOS)}")
    cs = [CRITERIOS[n]() for n in nombres]
    return cs[0] if len(cs) == 1 else Compuesto(*cs)


def _num(d, clave, defecto=None):
    v = d.get(clave, defecto)
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        raise ErrorApi(f"El valor de «{clave}» debe ser un entero") from None


class Aplicacion:
    """Operaciones de la interfaz web. Cada llamada abre su conexión a SQLite y la cierra al terminar."""

    def __init__(self, bd):
        self.bd = bd

    # -- utilidades -------------------------------------------------------------
    def _servicio(self):
        if not os.path.exists(self.bd):
            raise ErrorApi("Todavía no hay datos: cargue la demostración o sus archivos CSV.")
        con = almacen.conectar(self.bd)
        ids = [r[0] for r in con.execute("SELECT id_propuesta FROM propuesta ORDER BY id_propuesta")]
        if not ids:
            con.close()
            raise ErrorApi("La base de datos no tiene propuestas: importe datos primero.")
        return ServicioHorarios(con, ids[-1])

    def _con_servicio(self, f):
        sv = self._servicio()
        try:
            return f(sv)
        finally:
            sv.con.close()

    @staticmethod
    def _resumen(sv):
        r = sv.resumen()
        return {"total": r["total"], "por_regla": r["por_regla"]}

    # -- lectura ----------------------------------------------------------------
    def estado(self):
        if not os.path.exists(self.bd):
            return {"vacio": True}
        try:
            return self._con_servicio(self._estado)
        except ErrorApi:
            return {"vacio": True}

    def _estado(self, sv):
        p = sv.parametros
        confl = sv.conflictos()
        malas = {}
        for c in confl:
            for s in c.sesiones:
                malas.setdefault(s.id, set()).add(c.tipo)
        fila = sv.con.execute("SELECT nombre, estado, id_semestre FROM propuesta WHERE id_propuesta=?",
                              (sv.id_propuesta,)).fetchone()
        from .reglas import REGISTRO
        return {
            "vacio": False,
            "propuesta": {"id": sv.id_propuesta, "nombre": fila[0], "estado": fila[1], "semestre": fila[2]},
            "resumen": self._resumen(sv),
            "conflictos": [{"tipo": c.tipo, "descripcion": c.descripcion, "sesiones": [s.id for s in c.sesiones]} for c in confl],
            "sesiones": [{"id": s.id, "curso": s.curso, "grupo": s.grupo, "dia": s.dia, "hi": s.hora_inicio, "hf": s.hora_fin,
                          "docente": s.docente_id, "aula": s.aula_id, "cupo": s.cupo_esperado,
                          "reglas": sorted(malas.get(s.id, []))} for s in sv.ctx.a_propuesta().sesiones],
            "docentes": [{"id": d.id, "nombre": d.nombre} for d in sv.docentes],
            "aulas": [{"id": a.id, "nombre": a.nombre, "capacidad": a.capacidad} for a in sv.aulas],
            "dias": list(p.dias),
            "franja": [p.franja_inicio, p.franja_fin, p.receso_inicio, p.receso_fin],
            "reglas": [{"id": r, "nombre": REGISTRO[r].__name__, "activa": r not in sv.inactivas} for r in sorted(REGISTRO)],
            "parametros": {k: getattr(p, k) for k in ("duracion_sesion", "tope_estudiantes", "tolerancia_tope", "franja_inicio",
                                                       "franja_fin", "franja_fin_sabado", "receso_inicio", "receso_fin")},
            "bitacora": [self._fila_bitacora(f) for f in sv.bitacora()],
            "criterios": list(CRITERIOS),
        }

    @staticmethod
    def _fila_bitacora(f):
        (idc, cod, origen, criterio, regla, d0, h0, a0, o0, d1, h1, a1, o1, deshace, cuando) = f
        dia = lambda n: almacen.DIAS[n - 1]
        return {"id": idc, "sesion": cod, "origen": origen, "criterio": criterio, "regla": regla,
                "antes": f"{dia(d0)} {h0}h {a0}/{o0}", "despues": f"{dia(d1)} {h1}h {a1}/{o1}",
                "deshace": deshace, "cuando": cuando}

    # -- acciones ---------------------------------------------------------------
    def recomendar(self, d):
        codigo = d.get("sesion")
        crit, cambiar, n = _criterio(d.get("criterio")), bool(d.get("cambiar_docente")), _num(d, "n", 5) or 5

        def f(sv):
            try:
                sug = sv.recomendar(codigo, n, crit, cambiar)
            except KeyError as e:
                raise ErrorApi(str(e.args[0])) from None
            return {"alternativas": [{"dia": s.movimiento.dia, "hi": s.movimiento.hora_inicio, "hf": s.movimiento.hora_fin,
                                      "aula": s.movimiento.aula_id, "docente": s.movimiento.docente_id,
                                      "delta": s.delta, "criterio": s.criterio} for s in sug]}
        return self._con_servicio(f)

    def aplicar(self, d):
        codigo, k = d.get("sesion"), _num(d, "k")
        crit, cambiar = _criterio(d.get("criterio")), bool(d.get("cambiar_docente"))
        if not k or k < 1:
            raise ErrorApi("Indique la alternativa a aplicar (1, 2, 3…)")

        def f(sv):
            try:
                sug = sv.recomendar(codigo, max(k, 5), crit, cambiar)
            except KeyError as e:
                raise ErrorApi(str(e.args[0])) from None
            if k > len(sug):
                raise ErrorApi("Esa alternativa ya no existe: vuelva a pedir las recomendaciones")
            r = sv.aplicar(codigo, sug[k - 1])
            return {"mensaje": f"Alternativa {k} aplicada (cambio #{r.id_cambio}).", "resumen": self._resumen(sv)}
        return self._con_servicio(f)

    def mover(self, d):
        def f(sv):
            try:
                r = sv.mover(d.get("sesion"), d.get("dia") or None, _num(d, "hora"), d.get("aula") or None, d.get("docente") or None)
            except MovimientoBloqueado as e:
                return {"bloqueado": True, "mensaje": str(e), "conflictos": [str(c) for c in e.conflictos],
                        "empeoran": {k: list(v) for k, v in e.empeoran.items()}}
            except KeyError as e:
                raise ErrorApi(str(e.args[0])) from None
            except ValueError as e:
                raise ErrorApi(str(e)) from None
            return {"bloqueado": False, "mensaje": f"Movimiento aplicado (cambio #{r.id_cambio}, Δ conflictos {r.delta}).",
                    "resumen": self._resumen(sv)}
        return self._con_servicio(f)

    def resolver(self, d):
        crit, cambiar, aplicar = _criterio(d.get("criterio")), bool(d.get("cambiar_docente")), bool(d.get("aplicar"))

        def f(sv):
            res = sv.resolver_auto(crit, cambiar, aplicar=aplicar)
            return {"estado": res.estado, "iteraciones": res.iteraciones, "iniciales": res.conflictos_iniciales,
                    "finales": res.conflictos_finales, "candidatos": res.candidatos_evaluados, "segundos": round(res.segundos, 3),
                    "movimientos": [{"sesion": h[0], "dia": h[1], "hora": h[2], "aula": h[3], "docente": h[4], "delta": h[5]} for h in res.historial],
                    "pendientes": [str(c) for c in res.pendientes], "aplicado": aplicar}
        return self._con_servicio(f)

    def validar(self, d=None):
        def f(sv):
            ok = sv.validar()
            return {"ok": ok, "mensaje": "Sin conflictos: propuesta VALIDADA." if ok else
                    f"Quedan {sv.resumen()['total']} conflictos: la propuesta sigue en BORRADOR.", "resumen": self._resumen(sv)}
        return self._con_servicio(f)

    def deshacer(self, d=None):
        def f(sv):
            try:
                sv.deshacer()
            except SinCambiosParaDeshacer:
                raise ErrorApi("No hay cambios para deshacer") from None
            return {"mensaje": "Último cambio deshecho.", "resumen": self._resumen(sv)}
        return self._con_servicio(f)

    def regla(self, d):
        activa = bool(d.get("activa"))

        def f(sv):
            try:
                sv.activar_regla(d.get("id"), activa)
            except KeyError as e:
                raise ErrorApi(str(e.args[0])) from None
            return {"mensaje": f"Regla {d.get('id')} {'activada' if activa else 'desactivada'}.", "resumen": self._resumen(sv)}
        return self._con_servicio(f)

    def parametros(self, d):
        pares = d.get("valores") or {}
        if not pares:
            raise ErrorApi("No hay valores para guardar")

        def f(sv):
            sem = sv.propuesta.semestre
            actuales = almacen.leer_parametros(sv.con, sem)
            listos = []
            for clave, texto in pares.items():          # validar todo antes de escribir algo
                try:
                    valor, tipo = almacen.validar_parametro(clave, str(texto), actuales)
                except ValueError as e:
                    raise ErrorApi(str(e)) from None
                listos.append((clave, valor, tipo))
            for clave, valor, tipo in listos:
                almacen.fijar_parametro(sv.con, clave, valor, sem, tipo)
            sv.recargar()
            return {"mensaje": f"Parámetros actualizados (vigentes desde {sem}).", "resumen": self._resumen(sv)}
        return self._con_servicio(f)

    def importar(self, d):
        """Importa la demostración o tres CSV enviados por el navegador. Todo o nada; no pisa la base si se rechaza."""
        semestre = "2026-2" if d.get("demo") else (d.get("semestre") or "2026-2")
        try:
            fechas = almacen.resolver_fechas(semestre, d.get("inicio") or None, d.get("fin") or None)
        except ValueError as e:
            raise ErrorApi(str(e)) from None
        if d.get("demo"):
            carpeta, tmp = DEMO, None
        else:
            tmp = tempfile.TemporaryDirectory()
            carpeta = tmp.name
            for nombre in ("docentes", "aulas", "sesiones"):
                texto = d.get(nombre)
                if not isinstance(texto, str) or not texto.strip():
                    tmp.cleanup()
                    raise ErrorApi(f"Falta el archivo {nombre}.csv")
                with open(os.path.join(carpeta, nombre + ".csv"), "w", encoding="utf-8", newline="") as fh:
                    fh.write(texto)
        try:
            idp = almacen.importar_a_archivo(self.bd, carpeta, semestre,
                                             d.get("nombre") or ("Demostración" if d.get("demo") else "Propuesta importada"), fechas)
        except almacen.ErrorImportacion as e:
            return {"rechazado": True, "errores": list(e.errores)}
        finally:
            if tmp:
                tmp.cleanup()
        return {"rechazado": False, "mensaje": f"Propuesta {idp} importada.", "estado": self.estado()}

    def exportar(self, formato):
        def f(sv):
            with tempfile.TemporaryDirectory() as t:
                ruta = os.path.join(t, "horario." + formato)
                (exportar.exportar_csv if formato == "csv" else exportar.exportar_html)(sv, ruta)
                with open(ruta, "rb") as fh:
                    return fh.read()
        return self._con_servicio(f)


ACCIONES_POST = {"/api/recomendar": "recomendar", "/api/aplicar": "aplicar", "/api/mover": "mover", "/api/resolver": "resolver",
                 "/api/deshacer": "deshacer", "/api/validar": "validar", "/api/regla": "regla", "/api/parametros": "parametros", "/api/importar": "importar"}


def crear_manejador(app: Aplicacion):
    class Manejador(BaseHTTPRequestHandler):
        server_version = "SPH/1.0"

        def log_message(self, formato, *args):    # silencioso: la consola queda limpia
            pass

        def _responder(self, codigo, cuerpo: bytes, tipo="application/json; charset=utf-8", extra=None):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(cuerpo)

        def _json(self, codigo, datos):
            self._responder(codigo, json.dumps(datos, ensure_ascii=False).encode("utf-8"))

        def do_GET(self):
            ruta = urlparse(self.path).path
            try:
                if ruta in ("/", "/index.html") or ruta.startswith("/static/"):
                    nombre = "index.html" if ruta in ("/", "/index.html") else os.path.basename(ruta)
                    arch = os.path.join(ESTATICOS, nombre)
                    if nombre in ("index.html", "app.js", "estilos.css") and os.path.isfile(arch):
                        with open(arch, "rb") as f:
                            return self._responder(200, f.read(), TIPOS[os.path.splitext(nombre)[1]])
                if ruta == "/api/estado":
                    with _CERRADURA:
                        return self._json(200, app.estado())
                if ruta in ("/exportar.csv", "/exportar.html"):
                    formato = ruta.rsplit(".", 1)[1]
                    with _CERRADURA:
                        datos = app.exportar(formato)
                    tipo = "text/csv; charset=utf-8" if formato == "csv" else "text/html; charset=utf-8"
                    return self._responder(200, datos, tipo, {"Content-Disposition": f'attachment; filename="horario.{formato}"'})
            except ErrorApi as e:
                return self._json(400, {"error": str(e)})
            self._json(404, {"error": "No encontrado"})

        def do_POST(self):
            ruta = urlparse(self.path).path
            origen = self.headers.get("Origin")
            if origen and origen.split("://", 1)[-1] != self.headers.get("Host"):
                return self._json(403, {"error": "Origen no permitido"})
            if ruta not in ACCIONES_POST:
                return self._json(404, {"error": "No encontrado"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                datos = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(datos, dict):
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                return self._json(400, {"error": "Solicitud inválida"})
            try:
                with _CERRADURA:
                    resp = getattr(app, ACCIONES_POST[ruta])(datos)
                self._json(200, resp)
            except ErrorApi as e:
                self._json(400, {"error": str(e)})
            except Exception as e:  # nunca dejar al navegador sin respuesta
                self._json(500, {"error": f"Error interno: {type(e).__name__}: {e}"})

    return Manejador


def crear_servidor(bd, puerto=8000, anfitrion="127.0.0.1"):
    return ThreadingHTTPServer((anfitrion, puerto), crear_manejador(Aplicacion(bd)))


def servir(bd, puerto=8000, abrir=True):
    srv = crear_servidor(bd, puerto)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"SPH en {url}   (base de datos: {bd})   Ctrl+C para detener")
    if abrir:
        import webbrowser
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        srv.server_close()
