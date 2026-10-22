"""RD-11 (ejemplo de cambio 2027-1): un docente no puede dictar más de N sesiones el mismo día."""
from sph_m2.reglas import regla, ReglaRestriccion, DOCENTE
from src.restricciones import Conflicto


@regla("RD-11")
class SesionesPorDia(ReglaRestriccion):
    ambito = DOCENTE

    def evaluar_docente(self, ctx, docente_id):
        maximo = self.p.extra.get("max_sesiones_por_dia", 3)
        por_dia = {}
        for s in ctx.sesiones_de_docente(docente_id):
            por_dia.setdefault(s.dia, []).append(s)
        return [Conflicto(self.id, f"El docente {docente_id} tiene {len(g)} sesiones el {dia} (máximo {maximo})", g)
                for dia, g in por_dia.items() if len(g) > maximo]
