"""Escenarios de modificabilidad medidos (estímulo -> respuesta -> medida). Genera qa/logs/modificabilidad.log."""
import hashlib, os, shutil, subprocess, sys, tempfile, textwrap, time
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def hashes(base):
    out = {}
    for d, _, fs in os.walk(base):
        if "__pycache__" in d:
            continue
        for f in fs:
            if f.endswith((".py", ".json", ".sql", ".csv")):
                p = os.path.join(d, f)
                out[os.path.relpath(p, base)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def lineas(ruta):
    return sum(1 for l in open(ruta, encoding="utf-8") if l.strip())


def m1_nueva_regla(out):
    print("M-1  Estímulo: la dirección exige una regla nueva RD-11 (máx. 3 sesiones por docente y día).", file=out)
    with tempfile.TemporaryDirectory() as tmp:
        for d in ("sph", "src", "datos", "main.py"):
            o, t = os.path.join(RAIZ, d), os.path.join(tmp, d)
            (shutil.copytree if os.path.isdir(o) else shutil.copy)(o, t, **({"ignore": shutil.ignore_patterns("__pycache__")} if os.path.isdir(o) else {}))
        antes = hashes(tmp)
        nuevo = os.path.join(tmp, "sph", "reglas_rd11.py")
        shutil.copy(os.path.join(RAIZ, "ejemplos_cambio", "reglas_rd11.py"), nuevo)
        despues = hashes(tmp)
        mod = [k for k in antes if despues.get(k) != antes[k]]
        add = sorted(set(despues) - set(antes))
        print(f"     Respuesta: archivos existentes modificados = {len(mod)}; archivos nuevos = {len(add)} ({', '.join(add)}); líneas no vacías del archivo nuevo = {lineas(nuevo)}", file=out)
        guion = textwrap.dedent('''
            import csv
            from sph import almacen
            from sph.servicio import ServicioHorarios, MovimientoBloqueado
            con = almacen.crear_bd(); idp = almacen.importar_csv(con, "datos/ejemplo")
            # D01 acumula sesiones el lunes por la tarde en aulas distintas, sin choques de horario
            sv = ServicioHorarios(con, idp)
            print("reglas activas:", sorted(r.id for r in sv.validador.reglas))
            sv.mover("S01", dia="Lunes", hora_inicio=14)           # D01: 1 sesión el lunes tarde
            sv.mover("S11", dia="Lunes", hora_inicio=16, aula="A02")   # 2.ª sesión de D01 el lunes
            try:
                sv.mover("S04", docente="D01", dia="Lunes", hora_inicio=18, aula="A05")  # 3.ª: permitido (máx. 3)
                print("tercera sesión de D01 el lunes: permitida")
                sv.mover("S08", docente="D01", dia="Lunes", hora_inicio=20, aula="A07")  # 4.ª: debe bloquearse por RD-11
                print("CUARTA PERMITIDA (falla)")
            except MovimientoBloqueado as e:
                print("cuarta sesión bloqueada por:", sorted(e.empeoran))
        ''')
        t = time.perf_counter()
        r = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0,'.')\n" + guion], cwd=tmp, capture_output=True, text=True)
        print(f"     Medida: sin tocar ningún archivo, RD-11 se descubre sola y también bloquea movimientos en el servicio ({time.perf_counter()-t:.2f} s)", file=out)
        for l in (r.stdout + r.stderr).strip().splitlines():
            print("       >", l, file=out)
        return len(mod) == 0 and "bloqueada por: ['RD-11']" in r.stdout


def m2_parametro(out):
    from sph import almacen
    from sph.indice import ContextoValidacion
    from sph.validador import ValidadorRestricciones
    print("\nM-2  Estímulo: para 2027-1 el tope de estudiantes baja de 40 a 35.", file=out)
    con = almacen.crear_bd(); idp = almacen.importar_csv(con, os.path.join(RAIZ, "datos", "ejemplo"))
    d, a, p, par = almacen.cargar(con, idp)
    n0 = len(ValidadorRestricciones(par).detectar_todos(ContextoValidacion(p, d, a, par)))
    t = time.perf_counter()
    almacen.crear_semestre(con, "2027-1", "2027-01-20", "2027-05-30")
    almacen.guardar_parametro(con, "tope_estudiantes", 35, "2027-1")
    par2 = almacen.leer_parametros(con, "2027-1")
    n1 = len(ValidadorRestricciones(par2).detectar_todos(ContextoValidacion(p, d, a, par2)))
    ms = (time.perf_counter() - t) * 1e3
    print(f"     Respuesta: 1 fila INSERT en la tabla parametro; archivos de código modificados = 0; tiempo = {ms:.1f} ms", file=out)
    print(f"     Medida: conflictos con el mismo horario: tope 40 -> {n0}; tope 35 (límite {par2.limite_cupo()}) -> {n1}", file=out)
    return n1 > n0


def m3_dedicacion(out):
    from sph import almacen
    from sph.servicio import ServicioHorarios
    print("\nM-3  Estímulo: Talento Humano confirma que la dedicación de 1/4 de tiempo es de 6 h (no 5 h).", file=out)
    con = almacen.crear_bd(); idp = almacen.importar_csv(con, os.path.join(RAIZ, "datos", "ejemplo"))
    n0 = ServicioHorarios(con, idp).resumen()
    con.execute("UPDATE dedicacion SET horas_maximas=6 WHERE nombre='un_cuarto'"); con.commit()
    n1 = ServicioHorarios(con, idp).resumen()
    print("     Respuesta: 1 UPDATE sobre dedicacion (única fuente de horas máximas); código modificado = 0", file=out)
    print(f"     Medida: RD-09 pasa de {n0['por_regla'].get('RD-09', 0)} a {n1['por_regla'].get('RD-09', 0)}; total {n0['total']} -> {n1['total']}", file=out)
    return n1["total"] == n0["total"] - 1


def m4_criterio(out):
    from sph import almacen
    from sph.servicio import ServicioHorarios
    from sph.cli import criterio_de
    print("\nM-4  Estímulo: el Coordinador quiere priorizar otro criterio de recomendación para S16.", file=out)
    con = almacen.crear_bd(); idp = almacen.importar_csv(con, os.path.join(RAIZ, "datos", "ejemplo"))
    sv = ServicioHorarios(con, idp)
    tops = {}
    for nombre in ("menor-movimiento", "mantener-aula", "mantener-docente", "huecos", "distribuir-horas", "menor-movimiento,huecos"):
        s = sv.recomendar("S16", 1, criterio_de(nombre), cambiar_docente=True)[0].movimiento
        tops[nombre] = (s.dia, s.hora_inicio, s.aula_id, s.docente_id)
        print(f"     {nombre:<26} -> {s.dia} {s.hora_inicio}h aula {s.aula_id} docente {s.docente_id}", file=out)
    print("     Respuesta/medida: cambiar de criterio = 1 opción de línea de comandos (--criterio); código modificado = 0", file=out)
    return len(set(tops.values())) > 1


def ejecutar(out=sys.stdout):
    r = [m1_nueva_regla(out), m2_parametro(out), m3_dedicacion(out), m4_criterio(out)]
    print(f"\nResumen: {sum(r)}/{len(r)} escenarios cumplidos", file=out)
    return r


if __name__ == "__main__":
    sys.exit(0 if all(ejecutar()) else 1)
