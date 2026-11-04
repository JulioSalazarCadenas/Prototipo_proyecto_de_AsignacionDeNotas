import random
from src.datos_prueba import crear_docentes, crear_aulas, crear_propuesta_horario
from sph.parametros import Parametros
from sph.indice import ContextoValidacion
from sph.validador import ValidadorRestricciones, multiconjunto
from sph.resolutor import Resolutor, SIN_CONFLICTOS, SIN_SOLUCION
from sph.criterios import MenorMovimiento, MantenerAula, MantenerDocente, Compuesto, EvitarDiasConsecutivos


def test_delta_incremental_igual_a_recalculo_completo():
    docs, aulas, prop = crear_docentes(), crear_aulas(), crear_propuesta_horario()
    r = Resolutor(prop, docs, aulas, Parametros(), cambiar_docente=True)
    rnd = random.Random(3)
    base = len(r.val.detectar_todos(r.ctx))
    for _ in range(400):
        s = rnd.choice(r.ctx.sesiones())
        cands = list(r.candidatos(s))
        mov = rnd.choice(cands)
        d = r.delta(mov)
        vieja = r.ctx.mover(s.id, **mov.como_cambios())
        real = len(r.val.detectar_todos(r.ctx)) - base
        r.ctx.mover(s.id, **{k: getattr(vieja, k) for k in ("dia", "hora_inicio", "hora_fin", "aula_id", "docente_id")})
        assert d == real, (mov, d, real)


def test_termina_y_nunca_empeora():
    docs, aulas, prop = crear_docentes(), crear_aulas(), crear_propuesta_horario()
    res = Resolutor(prop, docs, aulas, Parametros()).resolver()
    assert res.iteraciones <= res.conflictos_iniciales
    assert res.conflictos_finales < res.conflictos_iniciales
    assert all(h[-1] < 0 for h in res.historial)


def test_los_criterios_se_intercambian_sin_tocar_el_resolutor():
    docs, aulas = crear_docentes(), crear_aulas()
    estados = set()
    for crit in (MenorMovimiento(), MantenerAula(), MantenerDocente(), Compuesto(EvitarDiasConsecutivos(), MenorMovimiento())):
        res = Resolutor(crear_propuesta_horario(), docs, aulas, Parametros(), criterio=crit).resolver()
        estados.add((crit.nombre, res.estado, res.conflictos_finales))
    assert len(estados) == 4


# ---------------------------------------------------------------------------------------------
# Ajuste 1 (M3): alternativa válida sin regresión y reintento de conflictos atascados
# ---------------------------------------------------------------------------------------------
import copy as _copy
from qa.ablacion import instancia as _inst_ablacion, P as _P_ablacion
from sph.validador import por_tipo as _por_tipo


def test_conflicto_atascado_se_reintenta_tras_otro_movimiento():
    """Semilla 19 de la ablación: sin reintento queda 1 conflicto pendiente (SIN_SOLUCION falso); con reintento, 0."""
    p, d, a = _inst_ablacion(19)
    con = Resolutor(_copy.deepcopy(p), d, a, _P_ablacion).resolver()
    sin = Resolutor(_copy.deepcopy(p), d, a, _P_ablacion, reintentar_atascados=False).resolver()
    assert con.desatascados >= 1
    assert con.conflictos_finales == 0 and sin.conflictos_finales == 1
    assert sin.estado == "SIN_SOLUCION"


def test_ningun_paso_del_resolutor_aumenta_conflictos_de_una_regla():
    from sph.indice import ContextoValidacion
    from sph.validador import ValidadorRestricciones
    for semilla in range(0, 150):
        p, d, a = _inst_ablacion(semilla)
        res = Resolutor(_copy.deepcopy(p), d, a, _P_ablacion).resolver()
        ctx = ContextoValidacion(_copy.deepcopy(p), d, a, _P_ablacion)
        val = ValidadorRestricciones(_P_ablacion)
        previo = _por_tipo(val.detectar_todos(ctx))
        for sid, dia, hi, aula, doc, _ in res.historial:
            ctx.mover(sid, dia=dia, hora_inicio=hi, hora_fin=hi + 2, aula_id=aula, docente_id=doc)
            ahora = _por_tipo(val.detectar_todos(ctx))
            assert all(ahora[t] <= previo[t] for t in ahora), (semilla, sid, previo, ahora)
            assert sum(ahora.values()) < sum(previo.values())
            previo = ahora


def test_prefiltro_unario_no_cambia_el_resultado():
    from bench.sintetico import generar
    from sph.parametros import Parametros
    for semilla in (1, 2, 3):
        p, d, a = generar(60, k_conflictos=6, semilla=semilla)
        con = Resolutor(_copy.deepcopy(p), d, a, Parametros()).resolver()
        sin = Resolutor(_copy.deepcopy(p), d, a, Parametros(), prefiltro=False).resolver()
        assert con.historial == sin.historial and con.conflictos_finales == sin.conflictos_finales
        assert con.candidatos_evaluados <= sin.candidatos_evaluados
