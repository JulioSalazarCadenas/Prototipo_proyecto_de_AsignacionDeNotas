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


_HORA = 34   # alto en píxeles de una hora en la cuadrícula

_CSS = """
:root{--c:#0b6e6e;--cl:#e2f1f0;--bd:#cfdcdb;--tx:#1b2a2a;--mu:#5c6f6e;--mal:#b3261e;--mall:#fde8e6;--bg:#f4f8f8}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:var(--tx);background:var(--bg)}
header{background:var(--c);color:#fff;padding:1.1rem 1.5rem;display:flex;flex-wrap:wrap;gap:.8rem 1.5rem;align-items:center}
header h1{margin:0;font-size:1.25rem;font-weight:650}header small{opacity:.85;display:block;font-weight:400;font-size:.8rem}
.chips{display:flex;gap:.5rem;flex-wrap:wrap;margin-left:auto}.chip{background:rgba(255,255,255,.18);border-radius:999px;padding:.2rem .75rem;font-size:.8rem}
.chip.mal{background:#fff;color:var(--mal);font-weight:650}.chip.ok{background:#fff;color:var(--c);font-weight:650}
main{max-width:1100px;margin:1.2rem auto;padding:0 1rem}
.barra{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin-bottom:1rem}
.seg{display:inline-flex;border:1px solid var(--bd);border-radius:8px;overflow:hidden;background:#fff}
.seg button{border:0;background:#fff;padding:.5rem 1rem;font:inherit;cursor:pointer;color:var(--tx)}
.seg button.act{background:var(--c);color:#fff}select{font:inherit;padding:.45rem .6rem;border:1px solid var(--bd);border-radius:8px;background:#fff}
.nota{color:var(--mu);font-size:.8rem;margin-left:auto}
.vista{display:none}.vista.act{display:block}.unidad{background:#fff;border:1px solid var(--bd);border-radius:12px;padding:1rem;margin-bottom:1rem;display:none}
.unidad.act{display:block}.unidad h3{margin:.1rem 0 .7rem;font-size:1rem}
.rej{display:grid;grid-template-columns:3rem repeat(var(--nd),1fr);border:1px solid var(--bd);border-radius:8px;overflow:hidden}
.rej .cab{background:var(--cl);font-weight:600;text-align:center;padding:.4rem 0;border-bottom:1px solid var(--bd);font-size:.85rem}
.horas div{height:var(--h);font-size:.7rem;color:var(--mu);text-align:right;padding-right:.35rem;border-top:1px solid #e6eeee}
.dia{position:relative;border-left:1px solid var(--bd);height:calc(var(--h) * var(--nh));
 background:repeating-linear-gradient(to bottom,transparent 0,transparent calc(var(--h) - 1px),#e6eeee calc(var(--h) - 1px),#e6eeee var(--h))}
.receso{position:absolute;left:0;right:0;background:repeating-linear-gradient(135deg,#eef3f3 0 6px,#e1e9e9 6px 12px)}
.ses{position:absolute;left:3px;right:3px;background:var(--cl);border:1px solid var(--c);border-radius:6px;padding:2px 5px;overflow:hidden;font-size:.72rem;line-height:1.25}
.ses b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ses span{color:var(--mu)}
.ses.mal{background:var(--mall);border-color:var(--mal);color:var(--mal)}.ses.mal span{color:var(--mal)}
.leyenda{display:flex;gap:1rem;flex-wrap:wrap;color:var(--mu);font-size:.8rem;margin:.6rem 0 0}.leyenda i{display:inline-block;width:.8rem;height:.8rem;border-radius:3px;vertical-align:-1px;margin-right:.3rem}
table.cf{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--bd);border-radius:12px;overflow:hidden}
table.cf th,table.cf td{padding:.5rem .8rem;text-align:left;border-bottom:1px solid #e6eeee;font-size:.85rem}table.cf th{background:var(--cl)}
h2.t{font-size:1rem;margin:1.5rem 0 .6rem}
@media print{body{background:#fff}header{background:#fff;color:#000;border-bottom:2px solid #000}.barra{display:none}.vista,.unidad{display:block!important;break-inside:avoid}}
"""

_JS = """
const V=document.querySelectorAll('.vista'),B=document.querySelectorAll('[data-v]'),S=document.getElementById('sel');
function mostrar(v){V.forEach(e=>e.classList.toggle('act',e.dataset.vista===v));B.forEach(b=>b.classList.toggle('act',b.dataset.v===v));
 const us=[...document.querySelectorAll('.vista[data-vista="'+v+'"] .unidad')];S.innerHTML=us.map((u,i)=>'<option value="'+i+'">'+u.dataset.n+'</option>').join('');S.onchange=()=>us.forEach((u,i)=>u.classList.toggle('act',i==S.value));S.value=0;S.onchange();}
B.forEach(b=>b.onclick=()=>mostrar(b.dataset.v));mostrar('grupo');
"""


def _bloques(sesiones, dia, h0, receso, malas):
    """Bloques absolutos de un día: receso (rayado) y sesiones (rojas si están en conflicto)."""
    out = []
    if receso:
        out.append(f'<div class="receso" style="top:{(receso[0] - h0) * _HORA}px;height:{(receso[1] - receso[0]) * _HORA}px"></div>')
    for cod, d, hi, hf, curso, detalle in sesiones:
        if d != dia:
            continue
        cls = "ses mal" if cod in malas else "ses"
        out.append(f'<div class="{cls}" style="top:{(hi - h0) * _HORA}px;height:{(hf - hi) * _HORA - 2}px" title="{escape(cod)} · {escape(curso)} · {escape(detalle)}">'
                   f'<b>{escape(cod)} · {escape(curso)}</b><span>{escape(detalle)}</span></div>')
    return "".join(out)


def _cuadricula(nombre, sesiones, dias, h0, h1, malas, receso):
    horas = "".join(f"<div>{h}:00</div>" for h in range(h0, h1))
    cabs = '<div class="cab"></div>' + "".join(f'<div class="cab">{escape(d)}</div>' for d in dias)
    cols = "".join(f'<div class="dia">{_bloques(sesiones, d, h0, receso, malas)}</div>' for d in dias)
    return (f'<section class="unidad" data-n="{escape(nombre)}"><h3>{escape(nombre)}</h3>'
            f'<div class="rej">{cabs}<div class="horas">{horas}</div>{cols}</div></section>')


def exportar_html(servicio, ruta, titulo="Horario SPH"):
    p = servicio.parametros
    conflictos = servicio.conflictos()
    malas = {s.id for c in conflictos for s in c.sesiones}
    ses = servicio.ctx.a_propuesta().sesiones
    total = servicio.resumen()["total"]
    receso = (p.receso_inicio, p.receso_fin)
    h0, h1 = p.franja_inicio, p.franja_fin
    estilo_var = f"--h:{_HORA}px;--nh:{h1 - h0};--nd:{len(p.dias)}"
    vistas = []
    for clave_v, etiqueta, clave, nombre, detalle in (
            ("grupo", "Por grupo", lambda s: s.grupo, lambda k: k,
             lambda s: f"{servicio.ctx.docentes[s.docente_id].nombre} · {servicio.ctx.aulas[s.aula_id].nombre}"),
            ("docente", "Por docente", lambda s: s.docente_id, lambda k: servicio.ctx.docentes[k].nombre,
             lambda s: f"{s.grupo} · {servicio.ctx.aulas[s.aula_id].nombre}"),
            ("aula", "Por aula", lambda s: s.aula_id, lambda k: servicio.ctx.aulas[k].nombre,
             lambda s: f"{s.grupo} · {servicio.ctx.docentes[s.docente_id].nombre}")):
        unidades = []
        for k in sorted({clave(s) for s in ses}, key=lambda k: nombre(k)):
            datos = [(s.id, s.dia, s.hora_inicio, s.hora_fin, s.curso, detalle(s)) for s in ses if clave(s) == k]
            unidades.append(_cuadricula(nombre(k), datos, p.dias, h0, h1, malas, receso))
        vistas.append(f'<div class="vista" data-vista="{clave_v}" style="{estilo_var}">{"".join(unidades)}</div>')
    botones = "".join(f'<button data-v="{v}">{t}</button>' for v, t in (("grupo", "Por grupo"), ("docente", "Por docente"), ("aula", "Por aula")))
    filas = "".join(f"<tr><td>{escape(c.tipo)}</td><td>{escape(c.descripcion)}</td><td>{escape(', '.join(s.id for s in c.sesiones))}</td></tr>"
                    for c in conflictos)
    tabla = (f'<h2 class="t">Conflictos abiertos</h2><table class="cf"><tr><th>Regla</th><th>Descripción</th><th>Sesiones</th></tr>{filas}</table>'
             if conflictos else '<p class="chip ok" style="display:inline-block;color:#0b6e6e;background:#e2f1f0">No hay conflictos abiertos.</p>')
    chip = (f'<span class="chip mal">Conflictos abiertos: {total}</span>' if total else '<span class="chip ok">Conflictos abiertos: 0</span>')
    pagina = (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
              f"<title>{escape(titulo)}</title><style>{_CSS}</style></head><body>"
              f"<header><div><h1>{escape(titulo)}</h1><small>Sistema de Planeación de Horarios · Universidad El Bosque</small></div>"
              f"<div class='chips'>{chip}<span class='chip'>{len(ses)} sesiones</span></div></header><main>"
              f"<div class='barra'><div class='seg'>{botones}</div><select id='sel' aria-label='Elegir'></select>"
              f"<span class='nota'>Rojo = sesión en conflicto · franja rayada = receso</span></div>"
              + "".join(vistas) + tabla +
              f"</main><script>{_JS}</script></body></html>")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(pagina)
    return ruta
