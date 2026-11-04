"""Exportación del horario: CSV (sesiones) y HTML (cuadrículas por grupo, docente y aula, con conflictos resaltados)."""
from __future__ import annotations
import csv
from html import escape


def exportar_csv(servicio, ruta):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["codigo", "curso", "grupo", "dia", "hora_inicio", "hora_fin", "docente", "aula", "cupo", "conflictos"])
        en_conflicto = {}
        for c in servicio.conflictos():
            for s in c.sesiones:
                en_conflicto.setdefault(s.id, []).append(c.tipo)
        for s in servicio.ctx.a_propuesta().sesiones:
            w.writerow([s.id, s.curso, s.grupo, s.dia, s.hora_inicio, s.hora_fin,
                        servicio.ctx.docentes[s.docente_id].nombre, servicio.ctx.aulas[s.aula_id].nombre,
                        s.cupo_esperado, ";".join(sorted(set(en_conflicto.get(s.id, []))))])
    return ruta


def _cuadricula(titulo, sesiones, dias, h0, h1, malas):
    filas = [f"<h3>{escape(titulo)}</h3><table><tr><th>Hora</th>" + "".join(f"<th>{d}</th>" for d in dias) + "</tr>"]
    for h in range(h0, h1):
        celdas = []
        for d in dias:
            txt = []
            for s in sesiones:
                if s[1] == d and s[2] <= h < s[3]:
                    cls = ' class="mal"' if s[0] in malas else ""
                    txt.append(f"<span{cls}>{escape(s[0])} · {escape(s[4])}</span>")
            celdas.append(f"<td>{'<br>'.join(txt)}</td>")
        filas.append(f"<tr><th>{h}:00</th>{''.join(celdas)}</tr>")
    filas.append("</table>")
    return "".join(filas)


def exportar_html(servicio, ruta, titulo="Horario SPH"):
    p = servicio.parametros
    malas = {s.id for c in servicio.conflictos() for s in c.sesiones}
    ses = servicio.ctx.a_propuesta().sesiones
    secciones = []
    for etiqueta, clave, nombre in (
            ("Por grupo", lambda s: s.grupo, lambda k: k),
            ("Por docente", lambda s: s.docente_id, lambda k: servicio.ctx.docentes[k].nombre),
            ("Por aula", lambda s: s.aula_id, lambda k: servicio.ctx.aulas[k].nombre)):
        secciones.append(f"<h2>{etiqueta}</h2>")
        for k in sorted({clave(s) for s in ses}):
            datos = [(s.id, s.dia, s.hora_inicio, s.hora_fin, s.curso if etiqueta != "Por grupo" else s.curso)
                     for s in ses if clave(s) == k]
            secciones.append(_cuadricula(nombre(k), datos, p.dias, p.franja_inicio, p.franja_fin, malas))
    css = ("body{font-family:'Times New Roman',serif;margin:1.5rem}table{border-collapse:collapse;margin-bottom:1rem}"
           "th,td{border:1px solid #000;padding:2px 6px;font-size:11px;vertical-align:top}.mal{color:#a00;font-weight:bold}")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(f"<!doctype html><html lang='es'><meta charset='utf-8'><title>{escape(titulo)}</title>"
                f"<style>{css}</style><h1>{escape(titulo)}</h1>"
                f"<p>Conflictos abiertos: {servicio.resumen()['total']}. En rojo: sesiones en conflicto.</p>"
                + "".join(secciones) + "</html>")
    return ruta
