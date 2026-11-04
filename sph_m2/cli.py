"""Interfaz de línea de comandos del SPH (python main.py <comando> --bd sph.db ...)."""
from __future__ import annotations
import argparse, os, sys
from datetime import date
from . import almacen, exportar
from .criterios import (MenorMovimiento, MantenerAula, MantenerDocente, EvitarDiasConsecutivos,
                        DistribuirHoras, MinimizarHuecos, Compuesto)
from .servicio import ServicioHorarios, MovimientoBloqueado, SinCambiosParaDeshacer
from .almacen import ErrorImportacion

CRITERIOS = {"menor-movimiento": MenorMovimiento, "mantener-aula": MantenerAula, "mantener-docente": MantenerDocente,
             "dias-consecutivos": EvitarDiasConsecutivos, "distribuir-horas": DistribuirHoras, "huecos": MinimizarHuecos}


def criterio_de(txt):
    if not txt:
        return None
    nombres = [t.strip() for t in txt.split(",") if t.strip()]
    try:
        cs = [CRITERIOS[n]() for n in nombres]
    except KeyError as e:
        raise SystemExit(f"Criterio desconocido {e}. Opciones: {', '.join(CRITERIOS)}")
    return cs[0] if len(cs) == 1 else Compuesto(*cs)


def _servicio(a):
    if not os.path.exists(a.bd):
        raise SystemExit(f"No existe la base de datos {a.bd}. Cree una con: python main.py importar --bd {a.bd} --carpeta datos/ejemplo")
    con = almacen.conectar(a.bd)
    ids = [r[0] for r in con.execute("SELECT id_propuesta FROM propuesta ORDER BY id_propuesta")]
    if not ids:
        raise SystemExit("La base de datos no tiene propuestas. Importe datos primero.")
    return ServicioHorarios(con, a.propuesta or ids[-1])


def _mostrar_resumen(sv, titulo="Conflictos"):
    r = sv.resumen()
    print(f"{titulo}: {r['total']}" + ("" if not r["por_regla"] else "  (" + ", ".join(f"{k}: {v}" for k, v in r["por_regla"].items()) + ")"))


def cmd_importar(a):
    """Importa en un archivo temporal y lo promueve solo si todo es válido: una importación rechazada
    (incluso con --reemplazar) no crea ni borra nada."""
    if os.path.exists(a.bd) and not a.reemplazar:
        print(f"La base de datos {a.bd} ya existe. Use --reemplazar para reemplazarla (se conserva la actual si la "
              f"importación se rechaza) o elija otro archivo con --bd.")
        return 1
    try:
        fechas = almacen.resolver_fechas(a.semestre, a.inicio, a.fin)
    except ValueError as e:
        print(e)
        return 1
    try:
        idp = almacen.importar_a_archivo(a.bd, a.carpeta, a.semestre, a.nombre, fechas)
    except ErrorImportacion as e:
        print("Importación rechazada (no se escribió nada):")
        for m in e.errores:
            print("  -", m)
        return 1
    except Exception as e:   # defensa: ningún fallo inesperado deja un archivo temporal ni una base a medias
        print(f"Error inesperado al importar (no se escribió nada): {type(e).__name__}: {e}")
        return 1
    con = almacen.conectar(a.bd)
    sv = ServicioHorarios(con, idp)
    print(f"Propuesta {idp} importada: {len(sv.docentes)} docentes, {len(sv.aulas)} aulas, {len(sv.propuesta.sesiones)} sesiones.")
    _mostrar_resumen(sv)
    return 0


def cmd_validar(a):
    sv = _servicio(a)
    for c in sv.conflictos():
        print(" ", c)
    _mostrar_resumen(sv)
    ok = sv.validar()
    print("Estado de la propuesta:", "VALIDADA" if ok else "BORRADOR (con conflictos)")
    return 0 if ok else 3


def cmd_recomendar(a):
    sv = _servicio(a)
    sug = sv.recomendar(a.sesion, a.n, criterio_de(a.criterio), a.cambiar_docente)
    if not sug:
        print(f"Sin alternativas válidas para {a.sesion} (no está en conflicto o ningún movimiento local mejora sin empeorar otra regla).")
        return 0
    for i, s in enumerate(sug, 1):
        m = s.movimiento
        print(f"{i}. {m.dia} {m.hora_inicio}-{m.hora_fin}  aula {m.aula_id}  docente {m.docente_id}   (Δ conflictos {s.delta}, {s.criterio})")
    if a.aplicar:
        r = sv.aplicar(a.sesion, sug[a.aplicar - 1])
        print(f"Aplicada la alternativa {a.aplicar}; cambio #{r.id_cambio}.")
        _mostrar_resumen(sv)
    return 0


def cmd_mover(a):
    sv = _servicio(a)
    try:
        r = sv.mover(a.sesion, a.dia, a.hora, a.aula, a.docente)
    except MovimientoBloqueado as e:
        print("BLOQUEADO:", e)
        for c in e.conflictos:
            print("   ", c)
        print("La base de datos no fue modificada.")
        return 2
    print(f"Movimiento aplicado; cambio #{r.id_cambio} (Δ conflictos {r.delta}).")
    _mostrar_resumen(sv)
    return 0


def cmd_resolver(a):
    sv = _servicio(a)
    res = sv.resolver_auto(criterio_de(a.criterio), a.cambiar_docente, aplicar=a.aplicar,
                           permitir_regresion=a.permitir_regresion)
    print(f"Estado: {res.estado}; iteraciones: {res.iteraciones}; conflictos {res.conflictos_iniciales} -> {res.conflictos_finales}; "
          f"candidatos evaluados: {res.candidatos_evaluados}; tiempo: {res.segundos:.3f} s")
    for h in res.historial:
        print(f"  mover {h[0]} -> {h[1]} {h[2]}h aula {h[3]} docente {h[4]}  (Δ {h[5]})")
    for c in res.pendientes:
        print("  pendiente:", c)
    print("Cambios guardados." if a.aplicar else "Simulación: no se guardó nada (use --aplicar).")
    return 0


def cmd_deshacer(a):
    sv = _servicio(a)
    try:
        sv.deshacer()
    except SinCambiosParaDeshacer as e:
        print(e)
        return 1
    print("Último cambio deshecho.")
    _mostrar_resumen(sv)
    return 0


def cmd_bitacora(a):
    sv = _servicio(a)
    for f in sv.bitacora():
        print(f"#{f[0]:<3} {f[14]}  {f[1]:<4} {f[2]:<10} {almacen.DIAS[f[5]-1]} {f[6]}h {f[7]}/{f[8]} -> {almacen.DIAS[f[9]-1]} {f[10]}h {f[11]}/{f[12]}"
              + (f"  [{f[3]}]" if f[3] else "") + (f"  deshace #{f[13]}" if f[13] else ""))
    return 0


def cmd_reglas(a):
    sv = _servicio(a)
    if a.desactivar:
        sv.activar_regla(a.desactivar, False)
    if a.activar:
        sv.activar_regla(a.activar, True)
    from .reglas import REGISTRO
    for rid in sorted(REGISTRO):
        print(f"  {rid:<6} {REGISTRO[rid].__name__:<24} {'INACTIVA' if rid in sv.inactivas else 'activa'}")
    return 0


def cmd_parametros(a):
    sv = _servicio(a)
    sem = sv.propuesta.semestre
    if a.fijar:
        desde = a.desde or sem
        actuales = almacen.leer_parametros(sv.con, sem)
        pares = []
        for par in a.fijar:                       # validar todo antes de escribir algo
            if "=" not in par:
                print(f"Formato inválido «{par}»: use clave=valor")
                return 1
            clave, texto = par.split("=", 1)
            try:
                valor, tipo = almacen.validar_parametro(clave, texto, actuales)
            except ValueError as e:
                print("Error:", e)
                return 1
            pares.append((clave, valor, tipo))
        if not sv.con.execute("SELECT 1 FROM semestre WHERE id_semestre=?", (desde,)).fetchone():
            if not (a.inicio and a.fin):
                print(f"El semestre {desde} no existe. Créelo agregando --inicio AAAA-MM-DD --fin AAAA-MM-DD.")
                return 1
            almacen.crear_semestre(sv.con, desde, a.inicio, a.fin)
        for clave, valor, tipo in pares:
            almacen.fijar_parametro(sv.con, clave, valor, desde, tipo)
        sv.recargar()
        print(f"Parámetros actualizados (vigentes desde {desde}).")
    p = almacen.leer_parametros(sv.con, sem)
    print(f"Parámetros vigentes para {sem}:")
    for k in ("duracion_sesion", "tope_estudiantes", "tolerancia_tope", "franja_inicio", "franja_fin", "franja_fin_sabado", "receso_inicio", "receso_fin"):
        print(f"  {k:<20} {getattr(p, k)}")
    for k, v in sorted(p.extra.items()):
        print(f"  {k:<20} {v}")
    print("  horas máximas por dedicación:", ", ".join(f"{k}={v}" for k, v in p.horas_maximas.items()))
    _mostrar_resumen(sv)
    return 0


def cmd_web(a):
    from . import web
    try:
        web.servir(a.bd, a.puerto, abrir=not a.no_abrir)
    except OSError as e:
        print(f"No se pudo abrir el puerto {a.puerto} ({e.strerror}). Use otro con --puerto.")
        return 1
    return 0


def cmd_exportar(a):
    sv = _servicio(a)
    salida = a.salida or f"horario.{a.formato}"
    (exportar.exportar_csv if a.formato == "csv" else exportar.exportar_html)(sv, salida)
    print("Archivo generado:", salida)
    return 0


def construir():
    p = argparse.ArgumentParser(prog="sph", description="Sistema de Planeación de Horarios (SPH) – línea de comandos")
    sub = p.add_subparsers(dest="cmd", required=True)

    def comun(sp):
        sp.add_argument("--bd", default="sph.db", help="archivo SQLite (por defecto sph.db)")
        sp.add_argument("--propuesta", type=int, help="id de la propuesta (por defecto, la última)")
        return sp
    s = comun(sub.add_parser("importar", help="crea la BD e importa docentes.csv, aulas.csv y sesiones.csv"))
    s.add_argument("--carpeta", required=True); s.add_argument("--semestre", default="2026-2")
    s.add_argument("--nombre", default="Propuesta importada"); s.add_argument("--reemplazar", action="store_true", help="reemplaza la BD si existe (solo si la importación es válida)")
    s.add_argument("--inicio", help="inicio del semestre AAAA-MM-DD (obligatorio si el semestre no es 2026-2)"); s.add_argument("--fin", help="fin del semestre AAAA-MM-DD")
    s.set_defaults(f=cmd_importar)
    s = comun(sub.add_parser("validar", help="detecta conflictos y revalida")); s.set_defaults(f=cmd_validar)
    s = comun(sub.add_parser("recomendar", help="alternativas válidas para una sesión en conflicto"))
    s.add_argument("sesion"); s.add_argument("-n", type=int, default=3); s.add_argument("--criterio", help=",".join(CRITERIOS))
    s.add_argument("--cambiar-docente", action="store_true"); s.add_argument("--aplicar", type=int, metavar="K", help="aplica la alternativa K")
    s.set_defaults(f=cmd_recomendar)
    s = comun(sub.add_parser("mover", help="mueve una sesión (se bloquea si crea choques)"))
    s.add_argument("sesion"); s.add_argument("--dia"); s.add_argument("--hora", type=int); s.add_argument("--aula"); s.add_argument("--docente")
    s.set_defaults(f=cmd_mover)
    s = comun(sub.add_parser("resolver", help="resuelve automáticamente (simulación salvo --aplicar)"))
    s.add_argument("--criterio"); s.add_argument("--cambiar-docente", action="store_true"); s.add_argument("--aplicar", action="store_true")
    s.add_argument("--permitir-regresion", action="store_true", help="comportamiento de M2 (solo exige Δ total < 0)")
    s.set_defaults(f=cmd_resolver)
    s = comun(sub.add_parser("deshacer", help="revierte el último cambio")); s.set_defaults(f=cmd_deshacer)
    s = comun(sub.add_parser("bitacora", help="lista los cambios registrados")); s.set_defaults(f=cmd_bitacora)
    s = comun(sub.add_parser("reglas", help="lista, activa o desactiva reglas"))
    s.add_argument("--activar"); s.add_argument("--desactivar"); s.set_defaults(f=cmd_reglas)
    s = comun(sub.add_parser("parametros", help="muestra o fija parámetros de negocio con vigencia por semestre"))
    s.add_argument("--fijar", nargs="+", metavar="CLAVE=VALOR"); s.add_argument("--desde", help="semestre desde el que rige (por defecto, el de la propuesta)")
    s.add_argument("--inicio"); s.add_argument("--fin")
    s.set_defaults(f=cmd_parametros)
    s = comun(sub.add_parser("web", help="abre la interfaz web local (horario, recomendaciones, mover, resolver, deshacer…)"))
    s.add_argument("--puerto", type=int, default=8000); s.add_argument("--no-abrir", action="store_true", help="no abre el navegador")
    s.set_defaults(f=cmd_web)

    s = comun(sub.add_parser("exportar", help="exporta el horario a CSV o HTML"))
    s.add_argument("--formato", choices=["csv", "html"], default="html"); s.add_argument("--salida"); s.set_defaults(f=cmd_exportar)
    return p


def main(argv=None):
    a = construir().parse_args(argv)
    try:
        return a.f(a)
    except (KeyError, ValueError) as e:
        print("Error:", e.args[0] if e.args else e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
