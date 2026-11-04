"""Ablación del Ajuste 1: ¿qué pasa si el resolutor NO reintenta los conflictos atascados?
Instancias aleatorias diminutas y densas (2 días, franja 7-11, 2 aulas, 4 docentes, 8 sesiones), semillas 0..N-1.
Se compara el resolutor con reintento (versión M3) contra el mismo sin reintento. Reproducible."""
import copy, random, sys, time
from src.models import Docente, Aula, Sesion, PropuestaHorario, Dedicacion, Tecnologia
from sph.parametros import Parametros
from sph.resolutor import Resolutor, SIN_SOLUCION

P = Parametros(dias=("Lunes", "Martes"), franja_fin=11, franja_fin_sabado=11)


def instancia(semilla):
    r = random.Random(semilla)
    docs = [Docente(f"D{i}", f"D{i}", Dedicacion.TIEMPO_COMPLETO, "E") for i in range(4)]
    aulas = [Aula(f"A{i}", f"A{i}", 45, {Tecnologia.VIDEO_BEAM}) for i in range(2)]
    ses = []
    for i in range(8):
        hi = r.choice([7, 8, 9])
        ses.append(Sesion(f"S{i}", f"C{i}", f"G{r.randrange(4)}", r.choice(P.dias), hi, hi + 2,
                          f"D{r.randrange(4)}", f"A{r.randrange(2)}", 30))
    return PropuestaHorario("ablacion", ses), docs, aulas


def correr(n=3000, out=sys.stdout):
    usa = mejor = peor = falsos = 0
    t_con = t_sin = 0.0
    pend_con = pend_sin = 0
    c_ini = 0
    for sem in range(n):
        p, d, a = instancia(sem)
        r1 = Resolutor(copy.deepcopy(p), d, a, P).resolver()
        r0 = Resolutor(copy.deepcopy(p), d, a, P, reintentar_atascados=False).resolver()
        c_ini += r1.conflictos_iniciales
        pend_con += r1.conflictos_finales
        pend_sin += r0.conflictos_finales
        t_con += r1.segundos; t_sin += r0.segundos
        if r1.desatascados:
            usa += 1
        if r1.conflictos_finales < r0.conflictos_finales:
            mejor += 1
        if r0.estado == SIN_SOLUCION and r1.conflictos_finales == 0:
            falsos += 1
        if r1.conflictos_finales > r0.conflictos_finales:
            peor += 1
    print(f"instancias: {n}; conflictos iniciales (suma): {c_ini}", file=out)
    print(f"instancias donde el reintento se usó: {usa}", file=out)
    print(f"instancias con menos pendientes gracias al reintento: {mejor}", file=out)
    print(f"instancias con MÁS pendientes con reintento (el camino de descenso difiere): {peor}", file=out)
    print(f"'SIN_SOLUCION falsos' evitados (sin reintento no resuelve; con reintento sí, 0 pendientes): {falsos}", file=out)
    print(f"pendientes totales: con reintento {pend_con}; sin reintento {pend_sin}", file=out)
    print(f"tiempo total del resolutor: con reintento {t_con:.2f} s; sin reintento {t_sin:.2f} s", file=out)
    return dict(n=n, usa=usa, mejor=mejor, peor=peor, falsos=falsos, pend_con=pend_con, pend_sin=pend_sin)


if __name__ == "__main__":
    correr(int(sys.argv[1]) if len(sys.argv) > 1 else 3000)
