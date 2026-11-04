"""Repite sobre el código FINAL las mediciones de escalabilidad de M2 (detección, costo por candidato, resolución
incremental, efecto del número de aulas). La línea base ingenua no se repite: es la de M2 (código sin cambios)."""
import json, platform, sys, time
from bench.run_bench import b1_deteccion, b2_candidato, b4_aulas
from bench.sintetico import generar
from sph.parametros import Parametros
from sph.resolutor import Resolutor


def b3_incremental(tamanos=(50, 100, 200, 400, 800)):
    out = []
    for n in tamanos:
        k = max(3, n // 20)
        pr, d, a = generar(n, k_conflictos=k)
        r = Resolutor(pr, d, a, Parametros()).resolver()
        out.append(dict(n=n, k=k, estado=r.estado, it=r.iteraciones, cand=r.candidatos_evaluados, c0=r.conflictos_iniciales,
                        cf=r.conflictos_finales, seg=r.segundos))
        print("B3", out[-1], flush=True)
    return out


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "qa/logs/bench_final.json"
    res = dict(entorno=dict(python=platform.python_version(), maquina=platform.platform(), fecha=time.strftime("%Y-%m-%d %H:%M")),
               b1=b1_deteccion(), b2=b2_candidato(), b3=b3_incremental(), b4=b4_aulas())
    json.dump(res, open(ruta, "w"), indent=1, ensure_ascii=False)
