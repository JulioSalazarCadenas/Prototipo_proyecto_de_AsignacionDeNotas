"""Pruebas de estrés de extremo a extremo con datos masivos sintéticos (CSV -> SQLite -> validación -> resolución).
Cada configuración corre en un subproceso para medir la memoria máxima (RSS) sin contaminación entre corridas.
Uso: python -m qa.estres [salida.json]   |   python -m qa.estres --uno N AULAS K"""
import csv, json, math, os, platform, resource, subprocess, sys, tempfile, time, statistics

HORAS_SLOT = 32   # bloques de 2 h distintos que usa el generador sintético por aula (5 días x 6 + sábado x 2)


def a_csv(p, docentes, aulas, carpeta):
    with open(os.path.join(carpeta, "docentes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["id", "nombre", "dedicacion", "especialidad", "disponibilidad"])
        for d in docentes: w.writerow([d.id, d.nombre, d.dedicacion.value, d.especialidad, ""])
    with open(os.path.join(carpeta, "aulas.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["id", "nombre", "capacidad", "tecnologias", "accesible"])
        for a in aulas: w.writerow([a.id, a.nombre, a.capacidad, ";".join(sorted(t.value for t in a.tecnologia)), 0])
    with open(os.path.join(carpeta, "sesiones.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["codigo", "curso", "grupo", "dia", "hora_inicio", "hora_fin", "docente_id", "aula_id", "cupo", "tecnologias"])
        for s in p.sesiones:
            w.writerow([s.id, s.curso, s.grupo, s.dia, s.hora_inicio, s.hora_fin, s.docente_id, s.aula_id, s.cupo_esperado, ""])


def uno(n, aulas, k, resolver=True):
    from bench.sintetico import generar
    from sph import almacen
    from sph.servicio import ServicioHorarios
    pr, d, a = generar(n, n_aulas=aulas, k_conflictos=k, semilla=7)
    carpeta = tempfile.mkdtemp(prefix="sph_estres_")
    a_csv(pr, d, a, carpeta)
    ruta = os.path.join(carpeta, "sph.db")
    r = dict(n=n, aulas=aulas, k=k, ocupacion=round(n / (aulas * HORAS_SLOT), 3))
    t = time.perf_counter(); con = almacen.crear_bd(ruta); idp = almacen.importar_csv(con, carpeta); r["importar_s"] = time.perf_counter() - t
    t = time.perf_counter(); sv = ServicioHorarios(con, idp); r["cargar_s"] = time.perf_counter() - t
    ts = []
    for _ in range(3):
        t = time.perf_counter(); cs = sv.conflictos(); ts.append(time.perf_counter() - t)
    r["detectar_s"] = statistics.median(ts); r["conflictos"] = len(cs)
    if resolver:
        t = time.perf_counter(); res = sv.resolver_auto(); r["resolver_s"] = time.perf_counter() - t
        r.update(estado=res.estado, iteraciones=res.iteraciones, candidatos=res.candidatos_evaluados,
                 finales=res.conflictos_finales, desatascados=res.desatascados)
        t = time.perf_counter(); sv2 = sv.resolver_auto(aplicar=True); r["resolver_y_guardar_s"] = time.perf_counter() - t
        t = time.perf_counter(); sv.recargar(); r["recarga_s"] = time.perf_counter() - t
        r["pendientes_tras_guardar"] = len(sv.conflictos())
    r["rss_max_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    r["db_mb"] = round(os.path.getsize(ruta) / 1e6, 2)
    return r


CONFIG = (
    # (n sesiones, aulas, conflictos inyectados, resolver?)
    [(n, max(8, n // 8), 10, True) for n in (100, 500, 1000, 2000)] +
    [(5000, 625, 10, True), (10000, 1250, 10, False)] +
    [(500, math.ceil(500 / (occ * HORAS_SLOT)), 10, True) for occ in (0.25, 0.50, 0.75)]
)


def main(salida):
    entorno = dict(python=platform.python_version(), sistema=platform.platform(), cpus=os.cpu_count(),
                   fecha=time.strftime("%Y-%m-%d %H:%M"))
    try:
        entorno["cpu"] = [l.split(":")[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")][0]
        entorno["ram_mb"] = int([l.split()[1] for l in open("/proc/meminfo") if l.startswith("MemTotal")][0]) // 1024
    except OSError:
        pass
    filas = []
    for n, a, k, res in CONFIG:
        out = subprocess.run([sys.executable, "-m", "qa.estres", "--uno", str(n), str(a), str(k), str(int(res))],
                             capture_output=True, text=True)
        if out.returncode != 0:
            print("ERROR", n, a, out.stderr[-500:], flush=True); continue
        filas.append(json.loads(out.stdout.strip().splitlines()[-1]))
        print(json.dumps(filas[-1], ensure_ascii=False), flush=True)
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(dict(entorno=entorno, filas=filas), f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--uno":
        print(json.dumps(uno(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), bool(int(sys.argv[5])) if len(sys.argv) > 5 else True)))
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else "qa/logs/estres.json")
