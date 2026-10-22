"""La optimización no cambia las decisiones: misma trayectoria que la línea base con copia + revalidación completa."""
from bench.sintetico import generar
from bench.ingenuo import resolver_ingenuo
from sph_m2.parametros import Parametros
from sph_m2.resolutor import Resolutor


def test_misma_trayectoria():
    for n, k, sem in [(12, 3, 1), (24, 3, 2), (30, 4, 5)]:
        pr, d, a = generar(n, k_conflictos=k, semilla=sem)
        r = Resolutor(pr, d, a, Parametros()).resolver()
        x = resolver_ingenuo(pr, d, a)
        assert (r.estado, r.iteraciones, r.candidatos_evaluados) == (x["estado"], x["it"], x["cand"])
