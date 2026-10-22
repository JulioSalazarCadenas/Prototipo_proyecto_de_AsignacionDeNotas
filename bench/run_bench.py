"""Mediciones de escalabilidad. Uso: python -m bench.run_bench [salida.json]"""
import json, sys, time, statistics, platform
from dataclasses import replace
from src.restricciones import detectar_todos
from sph_m2.parametros import Parametros
from sph_m2.indice import ContextoValidacion
from sph_m2.validador import ValidadorRestricciones
from sph_m2.resolutor import Resolutor
from .sintetico import generar
from .ingenuo import evaluar_candidato, resolver_ingenuo


def mediana(f, rep=3):
    ts = []
    for _ in range(rep):
        t = time.perf_counter(); f(); ts.append(time.perf_counter() - t)
    return statistics.median(ts)


def b1_deteccion(tamanos=(50, 100, 200, 400, 800, 1600, 3200)):
    out = []
    for n in tamanos:
        pr, d, a = generar(n, k_conflictos=max(3, n // 20))
        t_repo = mediana(lambda: detectar_todos(pr, d, a), 3 if n <= 1600 else 1)
        def nuevo():
            ctx = ContextoValidacion(pr, d, a, Parametros())
            return ValidadorRestricciones(Parametros()).detectar_todos(ctx)
        t_new = mediana(nuevo, 3)
        out.append(dict(n=n, repo_ms=t_repo * 1e3, nuevo_ms=t_new * 1e3))
        print("B1", out[-1], flush=True)
    return out


def b2_candidato(tamanos=(12, 24, 48, 96, 192, 384, 768)):
    out = []
    for n in tamanos:
        pr, d, a = generar(n, k_conflictos=max(3, n // 20))
        r = Resolutor(pr, d, a, Parametros())
        s = r.ctx.sesiones()[n // 2]
        movs = list(r.candidatos(s))[:200]
        t_ing = mediana(lambda: [evaluar_candidato(pr, d, a, m) for m in movs[:20]], 3) / 20
        t_inc = mediana(lambda: [r.delta(m) for m in movs], 3) / len(movs)
        out.append(dict(n=n, ingenuo_ms=t_ing * 1e3, incremental_ms=t_inc * 1e3, candidatos_por_sesion=len(list(r.candidatos(s)))))
        print("B2", out[-1], flush=True)
    return out


def b3_resolver(tamanos_inc=(50, 100, 200, 400, 800), tamanos_ing=(6, 12, 24, 48)):
    out = []
    for n in tamanos_ing:
        pr, d, a = generar(n, k_conflictos=3)
        x = resolver_ingenuo(pr, d, a, tiempo_max=900)
        r = Resolutor(pr, d, a, Parametros()).resolver()
        out.append(dict(n=n, k=3, ing=x, inc=dict(estado=r.estado, it=r.iteraciones, cand=r.candidatos_evaluados,
                                                   c0=r.conflictos_iniciales, cf=r.conflictos_finales, seg=r.segundos)))
        print("B3a", out[-1], flush=True)
    for n in tamanos_inc:
        k = max(3, n // 20)
        pr, d, a = generar(n, k_conflictos=k)
        r = Resolutor(pr, d, a, Parametros()).resolver()
        out.append(dict(n=n, k=k, ing=None, inc=dict(estado=r.estado, it=r.iteraciones, cand=r.candidatos_evaluados,
                                                      c0=r.conflictos_iniciales, cf=r.conflictos_finales, seg=r.segundos)))
        print("B3b", out[-1], flush=True)
    return out


def b4_aulas(n=200, aulas=(8, 16, 32, 64, 80, 128)):
    out = []
    for A in aulas:
        pr, d, a = generar(n, n_aulas=A, k_conflictos=10)
        r = Resolutor(pr, d, a, Parametros()).resolver()
        out.append(dict(n=n, aulas=A, estado=r.estado, it=r.iteraciones, cand=r.candidatos_evaluados, seg=r.segundos))
        print("B4", out[-1], flush=True)
    return out


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "resultados.json"
    res = dict(entorno=dict(python=platform.python_version(), maquina=platform.platform(), fecha=time.strftime("%Y-%m-%d %H:%M")),
               b1=b1_deteccion(), b2=b2_candidato(), b3=b3_resolver(), b4=b4_aulas())
    json.dump(res, open(ruta, "w"), indent=1)
