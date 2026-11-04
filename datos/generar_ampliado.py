"""Genera datos/ampliado/ (30 docentes, 20 aulas, 64 sesiones): primero un horario limpio y luego siembra
conflictos conocidos (uno o más por regla RD-01..RD-10) para la demostración. Determinista: python datos/generar_ampliado.py"""
import csv, os, random

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
HORAS_MAX = {"tiempo_completo": 20, "tres_cuartos": 15, "medio_tiempo": 10, "un_cuarto": 5}
CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ampliado")

# id, nombre, dedicación, especialidad, disponibilidad
DOCENTES = [
 ("D01", "Ana Torres", "tiempo_completo", "Algoritmos", ""), ("D02", "Carlos Peña", "tiempo_completo", "Bases de Datos", ""),
 ("D03", "Diana Ruiz", "tres_cuartos", "Redes", "Lunes 7-13;Miércoles 7-13;Viernes 7-13"),
 ("D04", "Esteban Gómez", "medio_tiempo", "Matemáticas", "Martes 16-22;Jueves 16-22"),
 ("D05", "Fabiola Nieto", "tiempo_completo", "Ingeniería de Software", ""), ("D06", "Germán Salas", "un_cuarto", "Electiva", ""),
 ("D07", "Helena Prieto", "tres_cuartos", "Sistemas Operativos", ""), ("D08", "Iván Cortés", "tiempo_completo", "Arquitectura de Software", ""),
 ("D09", "Julia Méndez", "medio_tiempo", "Física", ""), ("D10", "Kevin Rojas", "tiempo_completo", "Inteligencia Artificial", ""),
 ("D11", "Laura Beltrán", "tiempo_completo", "Matemáticas", ""), ("D12", "Mauricio Vargas", "tres_cuartos", "Matemáticas", ""),
 ("D13", "Natalia Ospina", "medio_tiempo", "Programación", ""), ("D14", "Oscar Dávila", "tiempo_completo", "Programación", ""),
 ("D15", "Paula Herrera", "medio_tiempo", "Programación", "Lunes 7-18;Martes 7-18;Miércoles 7-18;Jueves 7-18"),
 ("D16", "Ricardo Suárez", "tres_cuartos", "Bases de Datos", ""), ("D17", "Sandra Lozano", "medio_tiempo", "Ingeniería de Software", ""),
 ("D18", "Tomás Arévalo", "un_cuarto", "Ética y Sociedad", ""), ("D19", "Úrsula Mejía", "medio_tiempo", "Redes", ""),
 ("D20", "Víctor Camacho", "tres_cuartos", "Sistemas Operativos", ""), ("D21", "Wendy Castaño", "medio_tiempo", "Inteligencia Artificial", ""),
 ("D22", "Xavier Montoya", "tiempo_completo", "Seguridad Informática", ""), ("D23", "Yuliana Pardo", "medio_tiempo", "Gestión de Proyectos", ""),
 ("D24", "Zulma Forero", "un_cuarto", "Inglés Técnico", ""), ("D25", "Andrés Quintero", "tres_cuartos", "Física", ""),
 ("D26", "Beatriz Navarro", "medio_tiempo", "Algoritmos", "Martes 7-22;Jueves 7-22;Sábado 7-13"),
 ("D27", "Camilo Reyes", "tiempo_completo", "Computación en la Nube", ""), ("D28", "Daniela Ortiz", "medio_tiempo", "Electiva", ""),
 ("D29", "Felipe Granados", "medio_tiempo", "Ingeniería de Requisitos", ""), ("D30", "Gloria Martínez", "tres_cuartos", "Ciencia de Datos", ""),
]
# id, nombre, capacidad, tecnologías, accesible
AULAS = [
 ("A01", "Salón 301", 45, "video_beam", 0), ("A02", "Salón 302", 45, "video_beam", 0),
 ("A03", "Lab. Cómputo 1", 30, "computadores;video_beam", 0), ("A04", "Lab. Cómputo 2", 30, "computadores;video_beam", 0),
 ("A05", "Salón 205", 20, "", 0), ("A06", "Sala Telepresencia", 25, "telepresencia;video_beam", 1),
 ("A07", "Salón 210 (accesible)", 35, "video_beam", 1), ("A08", "Salón 110", 40, "video_beam", 0),
 ("A09", "Salón 303", 40, "video_beam", 0), ("A10", "Salón 304", 40, "video_beam", 0),
 ("A11", "Lab. Cómputo 3", 35, "computadores;video_beam", 0), ("A12", "Lab. Cómputo 4", 35, "computadores;video_beam", 0),
 ("A13", "Lab. Redes", 28, "computadores;video_beam", 0), ("A14", "Salón 401", 50, "video_beam", 0),
 ("A15", "Auditorio Menor", 50, "video_beam;sillas_moviles", 1), ("A16", "Salón 402", 30, "video_beam", 0),
 ("A17", "Sala de Seminarios", 20, "video_beam;sillas_moviles", 0), ("A18", "Salón 105", 32, "video_beam", 0),
 ("A19", "Salón 106", 32, "video_beam", 0), ("A20", "Lab. Cómputo 5", 30, "computadores;video_beam", 0),
]
# semestre -> cursos (nombre, especialidad requerida, tecnologías que exige la sesión)
PLAN = {
 1: [("Cálculo Diferencial", "Matemáticas", ""), ("Física Mecánica", "Física", ""), ("Fundamentos de Programación", "Programación", "computadores"), ("Cátedra Institucional", "Electiva", "")],
 2: [("Cálculo Integral", "Matemáticas", ""), ("Programación Orientada a Objetos", "Programación", "computadores"), ("Álgebra Lineal", "Matemáticas", ""), ("Inglés Técnico I", "Inglés Técnico", "")],
 3: [("Estructuras de Datos", "Algoritmos", ""), ("Bases de Datos I", "Bases de Datos", "computadores"), ("Física Electromagnética", "Física", ""), ("Ética y Sociedad", "Ética y Sociedad", "")],
 4: [("Redes de Computadores", "Redes", ""), ("Sistemas Operativos", "Sistemas Operativos", "computadores"), ("Análisis de Algoritmos", "Algoritmos", ""), ("Bases de Datos II", "Bases de Datos", "computadores")],
 5: [("Ingeniería de Software I", "Ingeniería de Software", ""), ("Arquitectura de Software", "Arquitectura de Software", ""), ("Seguridad Informática", "Seguridad Informática", ""), ("Ingeniería de Requisitos", "Ingeniería de Requisitos", "")],
 6: [("Ingeniería de Software II", "Ingeniería de Software", ""), ("Computación en la Nube", "Computación en la Nube", "computadores"), ("Gestión de Proyectos", "Gestión de Proyectos", ""), ("Electiva de Profundización", "Electiva", "")],
 7: [("Inteligencia Artificial", "Inteligencia Artificial", ""), ("Minería de Datos", "Ciencia de Datos", "computadores"), ("Proyecto de Telepresencia", "Redes", "telepresencia"), ("Redes Avanzadas", "Redes", "")],
 8: [("Aprendizaje Automático", "Inteligencia Artificial", "computadores"), ("Ciencia de Datos Aplicada", "Ciencia de Datos", "computadores"), ("Trabajo de Grado", "Gestión de Proyectos", ""), ("Seminario de Investigación", "Electiva", "")],
}


def disponible(doc, dia, hi, hf):
    disp = doc[4]
    if not disp:
        return True
    for p in disp.split(";"):
        d, rango = p.split(" ")
        a, b = map(int, rango.split("-"))
        if d == dia and a <= hi and hf <= b:
            return True
    return False


def main():
    rnd = random.Random(2026)
    docs = {d[0]: d for d in DOCENTES}
    aulas = {a[0]: a for a in AULAS}
    ses = []                                   # dicts

    def choques(dia, hi, hf, grupo, doc, aula, ignorar=None):
        out = set()
        for s in ses:
            if (ignorar is not None and s.get("codigo") == ignorar) or s["dia"] != dia or not (hi < s["hf"] and s["hi"] < hf):
                continue
            if s["doc"] == doc: out.add("doc")
            if s["grupo"] == grupo: out.add("grupo")
            if s["aula"] == aula: out.add("aula")
        return out

    def horas(doc):
        return sum(s["hf"] - s["hi"] for s in ses if s["doc"] == doc)

    def valido_franja(dia, hi, hf):
        fin = 13 if dia == "Sábado" else 22
        return 7 <= hi and hf <= fin and (hf <= 12 or hi >= 13)

    # --- horario limpio
    grupos = [(s, f"SIS-{s}A") for s in range(1, 9)] + [(1, "SIS-1B"), (3, "SIS-3B")]
    for sem, grupo in grupos:
        for curso, esp, tec in PLAN[sem]:
            if grupo.endswith("B") and curso not in {c[0] for c in PLAN[sem][:2]}:
                continue
            cands = [d for d in DOCENTES if d[3] == esp and horas(d[0]) + 4 <= HORAS_MAX[d[2]]]
            cands.sort(key=lambda d: horas(d[0]))
            if not cands:
                raise SystemExit(f"sin docente para {curso}")
            doc = cands[0]
            cupo = rnd.randint(18, 28) if tec else rnd.randint(24, 40)
            if "telepresencia" in tec: cupo = 22
            usados = []
            for _ in range(2):
                ok = False
                for dia in rnd.sample(DIAS, len(DIAS)):
                    if dia in usados:
                        continue
                    for hi in rnd.sample(range(7, 21), 14):
                        hf = hi + 2
                        if not valido_franja(dia, hi, hf) or not disponible(doc, dia, hi, hf):
                            continue
                        for a in sorted(AULAS, key=lambda a: a[2]):
                            req = {t for t in tec.split(";") if t}
                            if a[2] < cupo or not req <= set(a[3].split(";")):
                                continue
                            if choques(dia, hi, hf, grupo, doc[0], a[0]):
                                continue
                            ses.append(dict(curso=curso, grupo=grupo, dia=dia, hi=hi, hf=hf, doc=doc[0], aula=a[0], cupo=cupo, tec=tec))
                            usados.append(dia); ok = True; break
                        if ok: break
                    if ok: break
                if not ok:
                    raise SystemExit(f"no se pudo ubicar {curso} {grupo}")
    ses.sort(key=lambda s: (DIAS.index(s["dia"]), s["hi"], s["grupo"]))
    for i, s in enumerate(ses, 1):
        s["codigo"] = f"S{i:02d}"

    # --- conflictos sembrados (cada uno deja violada solo la regla indicada)
    sembrados = []

    def buscar(rd, s, **cambio):
        sembrados.append((rd, s["codigo"]))
        s.update(cambio)

    def libre_para(s, cond=lambda dia, hi, hf: True, **fijo):
        for dia in ([fijo["dia"]] if "dia" in fijo else rnd.sample(DIAS, 6)):
            for hi in range(7, 21):
                hf = hi + (fijo.get("dur", 2))
                if not valido_franja(dia, hi, hf) or not cond(dia, hi, hf):
                    continue
                if choques(dia, hi, hf, s["grupo"], s["doc"], s["aula"], ignorar=s["codigo"]):
                    continue
                if not disponible(docs[s["doc"]], dia, hi, hf):
                    continue
                return dia, hi, hf
        raise SystemExit("sin hueco para sembrar")

    por_doc = {}
    for s in ses: por_doc.setdefault(s["doc"], []).append(s)
    usado = set()

    def elegir(pred):
        for s in ses:
            if s["codigo"] not in usado and pred(s):
                usado.add(s["codigo"]); return s
        raise SystemExit("sin sesión candidata")

    def sembrar(n, pred, intento):
        """Aplica `intento` a sesiones que cumplan `pred` hasta lograr `n` siembras."""
        hechas = 0
        for s in rnd.sample(ses, len(ses)):
            if hechas == n:
                return
            if s["codigo"] in usado or not pred(s):
                continue
            if intento(s):
                usado.add(s["codigo"]); hechas += 1
        raise SystemExit("no se pudieron sembrar todos los conflictos")

    # RD-01 docente cruzado (2): mover s a la hora de otra sesión del mismo docente, con grupo y aula libres
    def rd01(s):
        for otra in por_doc[s["doc"]]:
            if otra is s or otra["dia"] == s["dia"] and (otra["hi"], otra["hf"]) == (s["hi"], s["hf"]):
                continue
            if choques(otra["dia"], otra["hi"], otra["hf"], s["grupo"], "-", "-", ignorar=s["codigo"]):
                continue
            for aula in aulas.values():
                req = {t for t in s["tec"].split(";") if t}
                if aula[2] >= s["cupo"] and req <= set(aula[3].split(";")) and aula[0] != otra["aula"] and \
                        not choques(otra["dia"], otra["hi"], otra["hf"], "-", "-", aula[0], ignorar=s["codigo"]):
                    buscar("RD-01", s, dia=otra["dia"], hi=otra["hi"], hf=otra["hf"], aula=aula[0]); return True
        return False
    sembrar(2, lambda s: len(por_doc[s["doc"]]) >= 2 and s["doc"] != "D03", rd01)
    # RD-02 aula cruzada (2)
    for _ in range(2):
        s = elegir(lambda s: not s["tec"])
        for t in ses:
            if t is s or t["aula"] == s["aula"] or aulas[t["aula"]][2] < s["cupo"] or t["doc"] == s["doc"] or t["grupo"] == s["grupo"]:
                continue
            if not choques(t["dia"], t["hi"], t["hf"], s["grupo"], s["doc"], "-", ignorar=s["codigo"]) and disponible(docs[s["doc"]], t["dia"], t["hi"], t["hf"]) \
                    and not (t["tec"] and not s["tec"] and False):
                buscar("RD-02", s, dia=t["dia"], hi=t["hi"], hf=t["hf"], aula=t["aula"]); break
    # RD-03 grupo cruzado (2)
    for _ in range(2):
        s = elegir(lambda s: not s["tec"])
        for t in ses:
            if t is s or t["grupo"] != s["grupo"] or t["doc"] == s["doc"] or t["aula"] == s["aula"]:
                continue
            for aula in aulas.values():
                if aula[2] >= s["cupo"] and aula[0] != t["aula"] and "video_beam" in aula[3] and \
                        not choques(t["dia"], t["hi"], t["hf"], "-", s["doc"], aula[0], ignorar=s["codigo"]) and disponible(docs[s["doc"]], t["dia"], t["hi"], t["hf"]):
                    buscar("RD-03", s, dia=t["dia"], hi=t["hi"], hf=t["hf"], aula=aula[0]); break
            else:
                continue
            break
    # RD-04 franja (receso 11-13)
    s = elegir(lambda s: not s["tec"] and s["dia"] != "Sábado")
    for hi in (11, 12):
        if not choques(s["dia"], hi, hi + 2, s["grupo"], s["doc"], s["aula"], ignorar=s["codigo"]) and disponible(docs[s["doc"]], s["dia"], hi, hi + 2):
            buscar("RD-04", s, hi=hi, hf=hi + 2); break
    # RD-05 fuera de disponibilidad: D03 (Lun/Mié/Vie 7-13) un jueves tarde
    s = elegir(lambda s: s["doc"] == "D03")
    for dia in ("Jueves", "Martes"):
        for hi in (14, 15, 16):
            if not choques(dia, hi, hi + 2, s["grupo"], s["doc"], s["aula"], ignorar=s["codigo"]):
                buscar("RD-05", s, dia=dia, hi=hi, hf=hi + 2); break
        else:
            continue
        break
    # RD-06 capacidad (2): cupo mayor que el aula
    for _ in range(2):
        s = elegir(lambda s: not s["tec"] and s["cupo"] >= 30)
        peq = [a for a in AULAS if a[2] < s["cupo"] - 2 and "video_beam" in a[3] and not choques(s["dia"], s["hi"], s["hf"], "-", "-", a[0], ignorar=s["codigo"])]
        buscar("RD-06", s, aula=peq[0][0])
    # RD-07 duración 3 h (2)
    def rd07(s):
        if choques(s["dia"], s["hi"], s["hf"] + 1, s["grupo"], s["doc"], s["aula"], ignorar=s["codigo"]) or not valido_franja(s["dia"], s["hi"], s["hf"] + 1):
            return False
        buscar("RD-07", s, hf=s["hf"] + 1); return True
    sembrar(2, lambda s: not s["tec"] and s["dia"] != "Sábado", rd07)
    # RD-08 tope de estudiantes: la sección completa con cupo 47 (aulas de 50)
    def rd08(s):
        hermanas = [t for t in ses if t["curso"] == s["curso"] and t["grupo"] == s["grupo"]]
        elegidas = []
        for t in hermanas:
            ok = [a for a in ("A14", "A15") if not choques(t["dia"], t["hi"], t["hf"], "-", "-", a, ignorar=t["codigo"])]
            if not ok:
                return False
            elegidas.append(ok[0])
        for t, a in zip(hermanas, elegidas):
            t.update(cupo=47, aula=a)
        sembrados.append(("RD-08", s["codigo"])); return True
    sembrar(1, lambda s: not s["tec"] and s["hi"] >= 7, rd08)
    # RD-09 dedicación: D06 (un cuarto, 5 h) con una tercera sesión de 2 h
    base = next(s for s in ses if s["doc"] == "D06")
    # D06 queda con 4 h; se le agrega una sesión de 2 h (6 h > 5 h)
    dia, hi, hf = libre_para({"codigo": "-", "grupo": base["grupo"], "doc": "D06", "aula": "A09"}, cond=lambda d, h, f: d != base["dia"])
    ses.append(dict(curso=base["curso"], grupo=base["grupo"], dia=dia, hi=hi, hf=hf, doc="D06", aula="A09", cupo=base["cupo"], tec=base["tec"], codigo=f"S{len(ses)+1:02d}"))
    sembrados.append(("RD-09", ses[-1]["codigo"]))
    # RD-10 tecnología: una sesión que exige computadores en un salón sin ellos
    s = elegir(lambda s: s["tec"] == "computadores")
    for a in AULAS:
        if "computadores" not in a[3] and a[2] >= s["cupo"] and not choques(s["dia"], s["hi"], s["hf"], "-", "-", a[0], ignorar=s["codigo"]):
            buscar("RD-10", s, aula=a[0]); break

    os.makedirs(CARPETA, exist_ok=True)
    with open(os.path.join(CARPETA, "docentes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["id", "nombre", "dedicacion", "especialidad", "disponibilidad"]); w.writerows(DOCENTES)
    with open(os.path.join(CARPETA, "aulas.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["id", "nombre", "capacidad", "tecnologias", "accesible"]); w.writerows(AULAS)
    ses.sort(key=lambda s: s["codigo"])
    with open(os.path.join(CARPETA, "sesiones.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["codigo", "curso", "grupo", "dia", "hora_inicio", "hora_fin", "docente_id", "aula_id", "cupo", "tecnologias"])
        for s in ses:
            w.writerow([s["codigo"], s["curso"], s["grupo"], s["dia"], s["hi"], s["hf"], s["doc"], s["aula"], s["cupo"], s["tec"]])
    print(len(DOCENTES), "docentes,", len(AULAS), "aulas,", len(ses), "sesiones; sembrados:", sorted(sembrados))


if __name__ == "__main__":
    main()
