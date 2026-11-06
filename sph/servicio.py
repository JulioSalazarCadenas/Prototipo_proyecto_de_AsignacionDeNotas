"""Servicio de aplicación del SPH: orquesta persistencia, validación, recomendación y bitácora.

Flujo del Coordinador (M1/M2): detectar -> recomendar -> decidir -> revalidar.
Bloqueo de choques: ningún movimiento puede AUMENTAR el número de conflictos de ninguna regla dura
(RD-01 docente, RD-02 aula, RD-03 grupo, ...). Un movimiento bloqueado no modifica la base de datos
ni la bitácora. La base de datos no impone exclusión: la propuesta de partida puede traer conflictos y
el servicio solo deja pasar movimientos que no empeoren ninguna regla.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from . import almacen
from .criterios import Movimiento, MenorMovimiento
from .indice import ContextoValidacion
from .resolutor import Resolutor
from .reglas import REGISTRO
from .validador import ValidadorRestricciones, por_tipo, descubrir_reglas

class MovimientoBloqueado(Exception):
    """El movimiento crea (o agrava) conflictos de al menos una regla dura."""

    def __init__(self, codigo, empeoran, conflictos):
        self.codigo, self.empeoran, self.conflictos = codigo, empeoran, conflictos
        det = ", ".join(f"{r}: {a}->{b}" for r, (a, b) in sorted(empeoran.items()))
        super().__init__(f"Movimiento de {codigo} bloqueado ({det})")


class SinCambiosParaDeshacer(Exception):
    pass


@dataclass
class ResultadoMovimiento:
    id_cambio: int
    antes: Counter
    despues: Counter

    @property
    def delta(self):
        return sum(self.despues.values()) - sum(self.antes.values())


@dataclass
class Sugerencia:
    movimiento: Movimiento
    delta: int
    costo: tuple
    criterio: str


class ServicioHorarios:
    def __init__(self, con, id_propuesta, usuario=1):
        self.con, self.id_propuesta, self.usuario = con, id_propuesta, usuario
        self.recargar()

    # ------------------------------------------------------------------ estado
    def recargar(self):
        self.docentes, self.aulas, self.propuesta, self.parametros = almacen.cargar(self.con, self.id_propuesta)
        descubrir_reglas()
        self.inactivas = almacen.reglas_inactivas(self.con)
        self.validador = ValidadorRestricciones(self.parametros, [r for r in REGISTRO if r not in self.inactivas])
        self.ctx = ContextoValidacion(self.propuesta, self.docentes, self.aulas, self.parametros)

    def sesion(self, codigo):
        try:
            return self.ctx.por_id[codigo]
        except KeyError:
            raise KeyError(f"No existe la sesión {codigo}") from None

    def conflictos(self) -> list:
        return self.validador.detectar_todos(self.ctx)

    def resumen(self) -> dict:
        cs = self.conflictos()
        return {"total": len(cs), "por_regla": dict(sorted(por_tipo(cs).items()))}

    def validar(self) -> bool:
        """Revalida la propuesta; la marca VALIDADA solo si no tiene conflictos duros."""
        ok = not self.conflictos()
        self.con.execute("UPDATE propuesta SET estado=? WHERE id_propuesta=?",
                         ("VALIDADA" if ok else "BORRADOR", self.id_propuesta))
        self.con.commit()
        return ok

    def activar_regla(self, id_regla, activa=True):
        """Activa o desactiva una regla registrada (persistente en la tabla regla) y recarga el validador."""
        if id_regla not in REGISTRO:
            raise KeyError(f"La regla {id_regla} no está registrada")
        cls = REGISTRO[id_regla]
        almacen.fijar_regla_activa(self.con, id_regla, activa, cls.__name__, (cls.__doc__ or "").strip().splitlines()[0] if cls.__doc__ else None)
        self.recargar()

    # ------------------------------------------------------------------ movimiento con bloqueo
    def _contar(self, sid, docs):
        return self.validador.contar_por_tipo(self.ctx, sid, docs)

    def mover(self, codigo, dia=None, hora_inicio=None, aula=None, docente=None, hora_fin=None,
              origen="MANUAL", criterio=None, regla=None) -> ResultadoMovimiento:
        s = self.sesion(codigo)
        dia = dia or s.dia
        if dia not in self.parametros.dias:
            raise ValueError(f"Día inválido «{dia}»")
        hi = s.hora_inicio if hora_inicio is None else int(hora_inicio)
        hf = int(hora_fin) if hora_fin is not None else hi + s.duracion()
        aula = aula or s.aula_id
        docente = docente or s.docente_id
        if aula not in self.ctx.aulas:
            raise ValueError(f"No existe el aula {aula}")
        if docente not in self.ctx.docentes:
            raise ValueError(f"No existe el docente {docente}")
        if (dia, hi, hf, aula, docente) == (s.dia, s.hora_inicio, s.hora_fin, s.aula_id, s.docente_id):
            raise ValueError("El movimiento no cambia nada")
        docs = {s.docente_id, docente}
        antes = self._contar(codigo, docs)
        vieja = self.ctx.mover(codigo, dia=dia, hora_inicio=hi, hora_fin=hf, aula_id=aula, docente_id=docente)
        despues = self._contar(codigo, docs)
        empeoran = {r: (antes[r], despues[r]) for r in despues if despues[r] > antes[r]}
        if empeoran:
            nuevos = [str(c) for c in self.validador.conflictos_de_sesion(self.ctx, self.ctx.por_id[codigo])
                      if c.tipo in empeoran]
            for d in docs:
                nuevos += [str(c) for c in self.validador.conflictos_de_docente(self.ctx, d) if c.tipo in empeoran]
            self.ctx.mover(codigo, dia=vieja.dia, hora_inicio=vieja.hora_inicio, hora_fin=vieja.hora_fin,
                           aula_id=vieja.aula_id, docente_id=vieja.docente_id)   # revertir en memoria; BD intacta
            raise MovimientoBloqueado(codigo, empeoran, nuevos)
        try:
            idc = almacen.registrar_cambio(self.con, self.id_propuesta, vieja, self.ctx.por_id[codigo], origen,
                                           criterio, regla, self.usuario)
            self.con.commit()
        except Exception:
            self.con.rollback()
            self.ctx.mover(codigo, dia=vieja.dia, hora_inicio=vieja.hora_inicio, hora_fin=vieja.hora_fin,
                           aula_id=vieja.aula_id, docente_id=vieja.docente_id)
            raise
        return ResultadoMovimiento(idc, antes, despues)

    # ------------------------------------------------------------------ recomendación
    def _resolutor(self, criterio=None, cambiar_docente=False, **kw):
        return Resolutor(self.ctx.a_propuesta(self.propuesta.semestre), self.docentes, self.aulas,
                         self.parametros, criterio=criterio, validador=self.validador,
                         cambiar_docente=cambiar_docente, **kw)

    def recomendar(self, codigo, n=3, criterio=None, cambiar_docente=False) -> list:
        """Hasta n alternativas válidas (reducen conflictos y no empeoran ninguna regla), ordenadas por criterio."""
        s = self.sesion(codigo)
        if not self.validador.conflictos_de_sesion(self.ctx, s) and not any(
                c for c in self.validador.conflictos_de_docente(self.ctx, s.docente_id)
                if any(x.id == codigo for x in c.sesiones)):
            return []
        r = self._resolutor(criterio, cambiar_docente)
        crit = r.criterio
        out = []
        for mov in r.candidatos(r.ctx.por_id[codigo]):
            d, regresion = r.evaluar(mov)
            if d < 0 and not regresion:
                out.append(Sugerencia(mov, d, crit.costo(r.ctx.por_id[codigo], mov, r.ctx), crit.nombre))
        out.sort(key=lambda x: (x.costo, x.delta, x.movimiento.dia, x.movimiento.hora_inicio,
                                x.movimiento.aula_id, x.movimiento.docente_id))
        return out[:n]

    def aplicar(self, codigo, sugerencia: Sugerencia):
        m = sugerencia.movimiento
        return self.mover(codigo, m.dia, m.hora_inicio, m.aula_id, m.docente_id, m.hora_fin,
                          origen="SUGERENCIA", criterio=sugerencia.criterio)

    def resolver_auto(self, criterio=None, cambiar_docente=False, aplicar=False, **kw):
        """Ejecuta el resolutor sobre una copia. Con aplicar=True persiste cada movimiento (origen SUGERENCIA)."""
        r = self._resolutor(criterio, cambiar_docente, **kw)
        res = r.resolver()
        if aplicar:
            for sid, dia, hi, aula, doc, _ in res.historial:
                self.mover(sid, dia, hi, aula, doc, origen="SUGERENCIA", criterio=r.criterio.nombre)
        return res

    # ------------------------------------------------------------------ deshacer
    def deshacer(self) -> int:
        """Revierte el último cambio no deshecho (restaura el estado anterior); queda registrado como DESHACER."""
        fila = self.con.execute(
            """SELECT c.id_cambio, s.codigo, c.dia_ant, c.hora_ini_ant, c.hora_fin_ant, c.id_aula_ant, c.id_docente_ant
               FROM cambio_sesion c JOIN sesion s USING(id_sesion)
               WHERE c.id_propuesta=? AND c.origen<>'DESHACER'
                 AND c.id_cambio NOT IN (SELECT deshace_id FROM cambio_sesion WHERE deshace_id IS NOT NULL)
               ORDER BY c.id_cambio DESC LIMIT 1""", (self.id_propuesta,)).fetchone()
        if fila is None:
            raise SinCambiosParaDeshacer("No hay cambios para deshacer")
        idc, cod, dia, hi, hf, aula, doc = fila
        actual = self.ctx.por_id[cod]
        previa = self.ctx.mover(cod, dia=almacen.DIAS[dia - 1], hora_inicio=hi, hora_fin=hf, aula_id=aula, docente_id=doc)
        nuevo = self.ctx.por_id[cod]
        self.ctx.mover(cod, **{k: getattr(actual, k) for k in ("dia", "hora_inicio", "hora_fin", "aula_id", "docente_id")})
        try:
            nid = almacen.registrar_cambio(self.con, self.id_propuesta, actual, nuevo, "DESHACER", None, None,
                                           self.usuario, deshace=idc)
            self.con.commit()
        except Exception:
            self.con.rollback()
            raise
        self.ctx.mover(cod, **{k: getattr(nuevo, k) for k in ("dia", "hora_inicio", "hora_fin", "aula_id", "docente_id")})
        return nid

    def bitacora(self):
        return almacen.bitacora(self.con, self.id_propuesta)
