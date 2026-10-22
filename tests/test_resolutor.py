import random
from src.datos_prueba import crear_docentes, crear_aulas, crear_propuesta_horario
from sph_m2.parametros import Parametros
from sph_m2.indice import ContextoValidacion
from sph_m2.validador import ValidadorRestricciones, multiconjunto
from sph_m2.resolutor import Resolutor, SIN_CONFLICTOS, SIN_SOLUCION
from sph_m2.criterios import MenorMovimiento, MantenerAula, MantenerDocente, Compuesto, EvitarDiasConsecutivos


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
