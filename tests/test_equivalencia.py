"""El validador nuevo debe producir EXACTAMENTE los mismos conflictos que src.restricciones.detectar_todos."""
import random
from src.datos_prueba import crear_docentes, crear_aulas, crear_propuesta_horario
from src.restricciones import detectar_todos
from src.models import PropuestaHorario, Sesion, Tecnologia
from sph_m2.parametros import Parametros
from sph_m2.indice import ContextoValidacion
from sph_m2.validador import ValidadorRestricciones, multiconjunto


def _comparar(prop, docs, aulas):
    esperado = multiconjunto(detectar_todos(prop, docs, aulas))
    ctx = ContextoValidacion(prop, docs, aulas, Parametros())
    obtenido = multiconjunto(ValidadorRestricciones(Parametros()).detectar_todos(ctx))
    assert obtenido == esperado, (obtenido - esperado, esperado - obtenido)
    return sum(esperado.values())


def test_dataset_del_prototipo():
    n = _comparar(crear_propuesta_horario(), crear_docentes(), crear_aulas())
    assert n >= 10


def test_aleatorio_cubre_todas_las_reglas():
    rnd = random.Random(7)
    docs, aulas = crear_docentes(), crear_aulas()
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
    techs = list(Tecnologia)
    total = 0
    for caso in range(300):
        ses = []
        for i in range(rnd.randint(5, 40)):
            hi = rnd.randint(5, 21)
            ses.append(Sesion(f"X{i:03d}", rnd.choice(["C1", "C2", "C3", "C4"]), rnd.choice(["G1", "G2", "G3"]),
                              rnd.choice(dias), hi, hi + rnd.choice([1, 2, 2, 2, 3]),
                              rnd.choice(docs).id, rnd.choice(aulas).id, rnd.randint(10, 50),
                              set(rnd.sample(techs, rnd.randint(0, 2)))))
        total += _comparar(PropuestaHorario("t", ses), docs, aulas)
    assert total > 1000
