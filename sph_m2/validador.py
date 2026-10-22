"""Validador: única definición de 'conflicto' (una sola fuente para detección, recomendación y generación)."""
from __future__ import annotations
from collections import Counter
import importlib, pkgutil
from . import reglas as _reglas_base  # noqa: F401  (puebla el REGISTRO con RD-01..RD-10)
from .reglas import REGISTRO, SESION, DOCENTE
from .indice import ContextoValidacion


def descubrir_reglas() -> None:
    """Importa todo módulo sph_m2/reglas_*.py: agregar una regla = crear un archivo nuevo (OCP)."""
    paquete = importlib.import_module(__package__)
    for m in pkgutil.iter_modules(paquete.__path__):
        if m.name.startswith("reglas_"):
            importlib.import_module(f"{__package__}.{m.name}")


def clave(c) -> tuple:
    """Identidad de un conflicto, independiente del orden de los pares."""
    return (c.tipo, tuple(sorted(s.id for s in c.sesiones)), c.descripcion)


class ValidadorRestricciones:
    def __init__(self, parametros, reglas=None):
        self.parametros = parametros
        descubrir_reglas()
        clases = REGISTRO.values() if reglas is None else [REGISTRO[r] for r in reglas]
        self.reglas = [cls(parametros) for cls in clases]
        self._por_sesion = [r for r in self.reglas if r.ambito == SESION]
        self._por_docente = [r for r in self.reglas if r.ambito == DOCENTE]

    def conflictos_de_sesion(self, ctx, s) -> list:
        out = []
        for r in self._por_sesion:
            out.extend(r.evaluar_sesion(ctx, s))
        return out

    def conflictos_de_docente(self, ctx, docente_id) -> list:
        out = []
        for r in self._por_docente:
            out.extend(r.evaluar_docente(ctx, docente_id))
        return out

    def detectar_todos(self, ctx) -> list:
        vistos, out = set(), []
        for s in sorted(ctx.por_id.values(), key=lambda x: ctx.orden[x.id]):
            for c in self.conflictos_de_sesion(ctx, s):
                k = clave(c)
                if k not in vistos:
                    vistos.add(k)
                    out.append(c)
        for did in ctx.docentes:
            out.extend(self.conflictos_de_docente(ctx, did))
        return out

    def contar_afectados(self, ctx, sesion_id, docentes=()) -> int:
        """Conflictos en los que participa la sesión (pares contados una vez) + los agregados de los docentes dados."""
        n = len(self.conflictos_de_sesion(ctx, ctx.por_id[sesion_id]))
        for d in docentes:
            n += len(self.conflictos_de_docente(ctx, d))
        return n


def multiconjunto(conflictos) -> Counter:
    return Counter(clave(c) for c in conflictos)
