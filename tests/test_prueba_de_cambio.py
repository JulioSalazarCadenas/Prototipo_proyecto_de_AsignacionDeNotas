"""Prueba de cambio (modificabilidad): RD-11 + tope 40 -> 35 sin modificar ningún archivo existente."""
import hashlib, os, shutil, subprocess, sys, tempfile, textwrap

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _hashes(base):
    out = {}
    for d, _, fs in os.walk(base):
        if "__pycache__" in d:
            continue
        for f in fs:
            if f.endswith((".py", ".json")):
                p = os.path.join(d, f)
                out[os.path.relpath(p, base)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def test_agregar_regla_y_cambiar_parametro_sin_editar_codigo_existente():
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(os.path.join(RAIZ, "sph_m2"), os.path.join(tmp, "sph_m2"), ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(os.path.join(RAIZ, "src"), os.path.join(tmp, "src"), ignore=shutil.ignore_patterns("__pycache__"))
        antes = _hashes(tmp)
        shutil.copy(os.path.join(RAIZ, "ejemplos_cambio", "reglas_rd11.py"), os.path.join(tmp, "sph_m2", "reglas_rd11.py"))
        shutil.copy(os.path.join(RAIZ, "ejemplos_cambio", "parametros_2027-1.json"), os.path.join(tmp, "parametros_2027-1.json"))
        despues = _hashes(tmp)
        modificados = [k for k in antes if despues.get(k) != antes[k]]
        nuevos = sorted(set(despues) - set(antes))
        assert modificados == [] and set(nuevos) == {os.path.join("sph_m2", "reglas_rd11.py"), "parametros_2027-1.json"}
        guion = textwrap.dedent('''
            import random
            from dataclasses import replace
            from src.datos_prueba import crear_docentes, crear_aulas, crear_propuesta_horario
            from src.models import Sesion
            from sph_m2.parametros import Parametros
            from sph_m2.indice import ContextoValidacion
            from sph_m2.validador import ValidadorRestricciones
            from sph_m2.resolutor import Resolutor
            P = Parametros.desde_json("parametros_2027-1.json")
            assert P.limite_cupo() == 38
            docs, aulas, prop = crear_docentes(), crear_aulas(), crear_propuesta_horario()
            for i in range(4):   # 4 sesiones de D01 el lunes por la tarde -> viola RD-11 (max 3)
                prop.sesiones.append(Sesion(f"N{i}", "Curso N", f"GN{i}", "Lunes", 14 + 0, 16, "D01", f"A0{i+1}", 20))
            ctx = ContextoValidacion(prop, docs, aulas, P)
            tipos = sorted({c.tipo for c in ValidadorRestricciones(P).detectar_todos(ctx)})
            assert "RD-11" in tipos, tipos
            assert "RD-08" in tipos   # S05 (40) ahora excede 38
            r = Resolutor(prop, docs, aulas, P)
            base = len(r.val.detectar_todos(r.ctx)); rnd = random.Random(1)
            for _ in range(300):
                s = rnd.choice(r.ctx.sesiones()); mov = rnd.choice(list(r.candidatos(s)))
                d = r.delta(mov); v = r.ctx.mover(s.id, **mov.como_cambios())
                real = len(r.val.detectar_todos(r.ctx)) - base
                r.ctx.mover(s.id, **{k: getattr(v, k) for k in ("dia","hora_inicio","hora_fin","aula_id","docente_id")})
                assert d == real, (d, real)
            print("OK", tipos)
        ''')
        out = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, '.')\n" + guion], cwd=tmp,
                             capture_output=True, text=True)
        assert out.returncode == 0, out.stderr + out.stdout
