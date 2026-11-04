"use strict";
/* Frontend del SPH: página única que consume la API JSON del servidor (/api/*). Sin dependencias externas. */
const HORA = 34; // px por hora (debe coincidir con --hora en estilos.css)
const $ = (s, r = document) => r.querySelector(s);
const esc = t => String(t ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let S = null;                       // estado completo devuelto por /api/estado
const V = { vista: "grupo", clave: null, sel: null, pestana: "conflictos", alt: null, msj: null, criterio: "", cambiarDocente: false };

async function api(ruta, datos) {
  const opc = datos === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) };
  try {
    const r = await fetch(ruta, opc);
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "Error del servidor");
    return j;
  } catch (e) { aviso(e.message || "No se pudo contactar al servidor", true); throw e; }
}
function aviso(t, mal) {
  const d = document.createElement("div"); d.className = "toast" + (mal ? " mal" : ""); d.textContent = t;
  $("#toasts").appendChild(d); setTimeout(() => d.remove(), mal ? 6000 : 3500);
}
function modal(html) { $("#modal-cuerpo").innerHTML = html; $("#modal").hidden = false; }
function cerrarModal() { $("#modal").hidden = true; }
$("#modal-cerrar").onclick = cerrarModal;
$("#modal").addEventListener("click", e => { if (e.target.id === "modal") cerrarModal(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") cerrarModal(); });

async function recargar(msj) {
  S = await api("/api/estado");
  if (!S.vacio) {
    const claves = clavesVista();
    if (!claves.includes(V.clave)) V.clave = claves[0] ?? null;
    if (V.sel && !S.sesiones.find(s => s.id === V.sel)) V.sel = null;
  }
  pintar();
  if (msj) aviso(msj);
}
const docente = id => (S.docentes.find(d => d.id === id) || {}).nombre || id;
const aula = id => (S.aulas.find(a => a.id === id) || {}).nombre || id;
const sesion = id => S.sesiones.find(s => s.id === id);
function clavesVista() {
  const f = { grupo: s => s.grupo, docente: s => s.docente, aula: s => s.aula }[V.vista];
  return [...new Set(S.sesiones.map(f))].sort((a, b) => nombreClave(a).localeCompare(nombreClave(b), "es"));
}
function nombreClave(k) { return V.vista === "docente" ? docente(k) : V.vista === "aula" ? aula(k) : k; }

/* ---------- pintado ---------- */
function pintar() {
  const acc = $("#acciones"), est = $("#estado"), app = $("#app");
  if (S.vacio) { est.innerHTML = ""; acc.innerHTML = ""; app.innerHTML = vacio(); return; }
  const n = S.resumen.total, p = S.propuesta;
  est.innerHTML = `<span class="chip">${esc(p.semestre)}</span><span class="chip ${n ? "mal" : "ok"}">${n ? n + " conflicto" + (n === 1 ? "" : "s") : "Sin conflictos"}</span><span class="chip">${esc(p.estado)}</span><span class="chip">${S.sesiones.length} sesiones</span>`;
  acc.innerHTML = `<button class="btn primario" data-a="resolver">Resolver automáticamente</button><button class="btn" data-a="deshacer">Deshacer</button><button class="btn" data-a="validar">Validar</button><button class="btn" data-a="cargar">Cargar datos</button><a class="btn" href="/exportar.csv">CSV</a><a class="btn" href="/exportar.html">HTML</a>`;
  app.innerHTML = `<div class="disposicion"><section class="tarjeta" id="izq">${vistaHorario()}</section><aside class="tarjeta panel" id="der">${panelSesion()}</aside></div>
    <section class="tarjeta" style="margin-top:1rem">${pestanas()}</section>`;
  ligarHorario();
}
function vacio() {
  return `<div class="tarjeta vacio"><h1>Sistema de Planeación de Horarios</h1><p>Todavía no hay datos cargados. Cargue una demostración (la ampliada trae 30 docentes, 20 aulas y 73 sesiones con 14 conflictos sembrados) o sus propios archivos CSV.</p>
  <p><button class="btn primario" data-a="demo-ampliada">Demostración ampliada (30 docentes, 20 aulas, 73 sesiones)</button> <button class="btn" data-a="demo">Demostración pequeña (10 / 8 / 20)</button> <button class="btn" data-a="cargar">Subir mis CSV</button></p></div>`;
}
function vistaHorario() {
  const claves = clavesVista();
  const opciones = claves.map(k => `<option value="${esc(k)}" ${k === V.clave ? "selected" : ""}>${esc(nombreClave(k))}</option>`).join("");
  return `<div class="controles"><div class="seg">${["grupo", "docente", "aula"].map(v => `<button data-vista="${v}" class="${V.vista === v ? "act" : ""}">Por ${v}</button>`).join("")}</div>
   <select id="clave" aria-label="Elemento a mostrar">${opciones}</select><span class="leyenda">Arrastre una sesión a otro día u hora para moverla · rojo = en conflicto</span></div>
   <div class="horario" id="horario">${cuadricula()}</div>
   <p class="pie">Las franjas rayadas son el receso institucional. Un movimiento que crea un conflicto nuevo es <b>bloqueado</b> y no se guarda.</p>`;
}
function cuadricula() {
  const [h0, h1, r0, r1] = S.franja, dias = S.dias, alto = (h1 - h0) * HORA;
  let html = `<div class="cab"></div>` + dias.map(d => `<div class="cab">${esc(d)}</div>`).join("");
  html += `<div class="horas" style="height:${alto}px">${Array.from({ length: h1 - h0 }, (_, i) => `<span style="top:${i * HORA}px">${h0 + i}:00</span>`).join("")}</div>`;
  const f = { grupo: s => s.grupo, docente: s => s.docente, aula: s => s.aula }[V.vista];
  const ses = S.sesiones.filter(s => f(s) === V.clave);
  for (const d of dias) {
    const delDia = ses.filter(s => s.dia === d).sort((a, b) => a.hi - b.hi || a.hf - b.hf);
    const carriles = []; // asigna carril a las sesiones que se traslapan
    for (const s of delDia) { let c = carriles.findIndex(fin => fin <= s.hi); if (c < 0) { c = carriles.length; carriles.push(0); } carriles[c] = s.hf; s._c = c; }
    // el ancho depende del máximo de carriles simultáneos del grupo de traslape
    for (const s of delDia) { s._n = Math.max(...delDia.filter(o => o.hi < s.hf && s.hi < o.hf).map(o => o._c)) + 1; }
    const receso = (r0 >= h0 && r1 <= h1) ? `<div class="receso" style="top:${(r0 - h0) * HORA}px;height:${(r1 - r0) * HORA}px"></div>` : "";
    html += `<div class="dia" data-dia="${esc(d)}" style="height:${alto}px">${receso}` + delDia.map(s => {
      const ancho = 100 / s._n, top = (Math.max(s.hi, h0) - h0) * HORA, alt = (Math.min(s.hf, h1) - Math.max(s.hi, h0)) * HORA;
      const aux = V.vista === "docente" ? aula(s.aula) : V.vista === "aula" ? docente(s.docente) : docente(s.docente) + " · " + aula(s.aula);
      return `<div class="ses ${s.reglas.length ? "mal" : ""} ${V.sel === s.id ? "sel" : ""}" draggable="true" data-id="${esc(s.id)}" title="${esc(s.id + " · " + s.curso + " · " + s.hi + "-" + s.hf + "h" + (s.reglas.length ? " · " + s.reglas.join(", ") : ""))}"
        style="top:${top}px;height:${Math.max(alt - 2, 16)}px;left:calc(${s._c * ancho}% + 1px);width:calc(${ancho}% - 3px)"><b>${esc(s.id)} · ${esc(s.curso)}</b><small>${esc(aux)}</small></div>`;
    }).join("") + `</div>`;
  }
  return html;
}
function ligarHorario() {
  const sel = $("#clave"); if (sel) sel.onchange = () => { V.clave = sel.value; pintarIzq(); };
  document.querySelectorAll(".ses").forEach(el => {
    el.onclick = () => { V.sel = el.dataset.id; V.alt = null; V.msj = null; pintar(); };
    el.ondragstart = e => { e.dataTransfer.setData("text/plain", el.dataset.id); e.dataTransfer.effectAllowed = "move"; el.classList.add("arrastrando"); };
    el.ondragend = () => el.classList.remove("arrastrando");
  });
  document.querySelectorAll(".dia").forEach(col => {
    col.ondragover = e => { e.preventDefault(); col.classList.add("sobre"); };
    col.ondragleave = () => col.classList.remove("sobre");
    col.ondrop = async e => {
      e.preventDefault(); col.classList.remove("sobre");
      const id = e.dataTransfer.getData("text/plain"); if (!id) return;
      const hora = S.franja[0] + Math.floor((e.clientY - col.getBoundingClientRect().top) / HORA);
      V.sel = id; V.alt = null;
      await mover({ sesion: id, dia: col.dataset.dia, hora });
    };
  });
}
function pintarIzq() { $("#izq").innerHTML = vistaHorario(); ligarHorario(); }

function panelSesion() {
  if (!V.sel) return `<h2>Sesión</h2><p>Seleccione una sesión del horario para ver sus conflictos, pedir alternativas o moverla.</p>${msj()}`;
  const s = sesion(V.sel);
  const cs = S.conflictos.filter(c => c.sesiones.includes(s.id));
  const opt = (arr, v, f) => arr.map(x => `<option value="${esc(x.id ?? x)}" ${(x.id ?? x) === v ? "selected" : ""}>${esc(f(x))}</option>`).join("");
  return `<h2>${esc(s.id)} · ${esc(s.curso)}</h2>
  <dl><dt>Grupo</dt><dd>${esc(s.grupo)} (${s.cupo} estudiantes)</dd><dt>Horario</dt><dd>${esc(s.dia)} ${s.hi}:00–${s.hf}:00</dd><dt>Docente</dt><dd>${esc(docente(s.docente))}</dd><dt>Aula</dt><dd>${esc(aula(s.aula))}</dd></dl>
  ${cs.length ? cs.map(c => `<div class="msj mal"><b>${esc(c.tipo)}</b> ${esc(c.descripcion)}</div>`).join("") : `<div class="msj ok">Esta sesión no tiene conflictos.</div>`}
  <h3>Alternativas recomendadas</h3>
  <div class="fila"><select id="crit" aria-label="Criterio"><option value="">Menor movimiento</option>${S.criterios.filter(c => c !== "menor-movimiento").map(c => `<option ${V.criterio === c ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>
   <label><input type="checkbox" id="cdoc" ${V.cambiarDocente ? "checked" : ""}> permitir cambiar docente</label>
   <button class="btn" data-a="alternativas">Ver alternativas</button></div>
  ${V.alt === null ? "" : V.alt.length ? V.alt.map((a, i) => `<div class="alt"><span><b>${i + 1}.</b> ${esc(a.dia)} ${a.hi}–${a.hf}h · ${esc(aula(a.aula))} · ${esc(docente(a.docente))} <small>(Δ ${a.delta})</small></span><button class="btn chico primario" data-aplicar="${i + 1}">Aplicar</button></div>`).join("") : `<div class="msj aviso">Sin alternativas válidas: la sesión no está en conflicto o ningún movimiento la mejora sin empeorar otra regla.</div>`}
  <h3>Mover manualmente</h3>
  <div class="fila"><select id="m-dia">${opt(S.dias, s.dia, x => x)}</select><input type="number" id="m-hora" min="0" max="23" value="${s.hi}" style="width:4.5rem" aria-label="Hora de inicio"></div>
  <div class="fila"><select id="m-aula">${opt(S.aulas, s.aula, a => a.nombre + " (" + a.capacidad + ")")}</select></div>
  <div class="fila"><select id="m-doc">${opt(S.docentes, s.docente, d => d.nombre)}</select><button class="btn primario" data-a="mover">Mover</button></div>
  ${msj()}`;
}
function msj() {
  if (!V.msj) return "";
  const m = V.msj;
  return `<div class="msj ${m.tipo}">${esc(m.texto)}${(m.detalle || []).map(d => `\n• ${esc(d)}`).join("")}</div>`;
}

function pestanas() {
  const t = V.pestana;
  const botones = [["conflictos", `Conflictos (${S.resumen.total})`], ["bitacora", `Bitácora (${S.bitacora.length})`], ["config", "Parámetros y reglas"]]
    .map(([k, n]) => `<button data-pest="${k}" class="${t === k ? "act" : ""}">${n}</button>`).join("");
  let cuerpo = "";
  if (t === "conflictos") {
    cuerpo = S.conflictos.length ? `<table class="t"><tr><th>Regla</th><th>Descripción</th><th>Sesiones</th></tr>${S.conflictos.map(c => `<tr><td class="cod">${esc(c.tipo)}</td><td>${esc(c.descripcion)}</td><td>${c.sesiones.map(id => `<button class="btn chico" data-ir="${esc(id)}">${esc(id)}</button>`).join(" ")}</td></tr>`).join("")}</table>`
      : `<div class="msj ok">No hay conflictos abiertos. Puede pulsar «Validar» para marcar la propuesta como VALIDADA.</div>`;
  } else if (t === "bitacora") {
    cuerpo = S.bitacora.length ? `<table class="t"><tr><th>#</th><th>Cuándo</th><th>Sesión</th><th>Origen</th><th>Antes</th><th>Después</th><th>Criterio</th></tr>${S.bitacora.slice().reverse().map(b => `<tr><td>${b.id}</td><td>${esc(b.cuando.replace("T", " "))}</td><td class="cod">${esc(b.sesion)}</td><td>${esc(b.origen)}${b.deshace ? " (#" + b.deshace + ")" : ""}</td><td>${esc(b.antes)}</td><td>${esc(b.despues)}</td><td>${esc(b.criterio || "")}</td></tr>`).join("")}</table>` : `<p>Todavía no hay cambios registrados. Cada movimiento que se guarde aparecerá aquí y no puede editarse.</p>`;
  } else {
    const P = S.parametros, nombres = { duracion_sesion: "Duración de la sesión (h)", tope_estudiantes: "Tope de estudiantes", tolerancia_tope: "Tolerancia del tope (0–1)", franja_inicio: "Inicio de la jornada", franja_fin: "Fin de la jornada", franja_fin_sabado: "Fin del sábado", receso_inicio: "Inicio del receso", receso_fin: "Fin del receso" };
    cuerpo = `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:1.5rem"><div><h3>Parámetros de negocio</h3>
      ${Object.keys(nombres).map(k => `<div class="fila"><label style="width:13rem">${nombres[k]}</label><input type="text" data-par="${k}" value="${esc(P[k])}" size="6"></div>`).join("")}
      <button class="btn primario" data-a="parametros">Guardar parámetros</button></div>
      <div><h3>Restricciones</h3><table class="t">${S.reglas.map(r => `<tr><td class="cod">${esc(r.id)}</td><td>${esc(r.nombre)}</td><td><label><input type="checkbox" data-regla="${esc(r.id)}" ${r.activa ? "checked" : ""}> activa</label></td></tr>`).join("")}</table>
      <p class="pie">Una regla desactivada no se evalúa ni bloquea movimientos. Reactívela antes de dar el horario por bueno.</p></div></div>`;
  }
  return `<div class="pestanas">${botones}</div>${cuerpo}`;
}

/* ---------- acciones ---------- */
async function mover(d) {
  const r = await api("/api/mover", d);
  if (r.bloqueado) {
    V.msj = { tipo: "mal", texto: "BLOQUEADO: " + r.mensaje + ". No se guardó nada.", detalle: r.conflictos };
    pintar(); aviso("Movimiento bloqueado: crearía un conflicto", true);
  } else { V.msj = { tipo: "ok", texto: r.mensaje }; await recargar(); }
}
async function resolver(aplicar) {
  const r = await api("/api/resolver", { aplicar, criterio: $("#r-crit")?.value || "", cambiar_docente: $("#r-doc")?.checked || false });
  const lista = r.movimientos.map(m => `<tr><td class="cod">${esc(m.sesion)}</td><td>${esc(m.dia)} ${m.hora}:00</td><td>${esc(aula(m.aula))}</td><td>${esc(docente(m.docente))}</td><td>${m.delta}</td></tr>`).join("");
  modal(`<h2>Resolución automática ${r.aplicado ? "(aplicada)" : "(simulación)"}</h2>
   <p><b>${esc(r.estado)}</b> · ${r.iniciales} → ${r.finales} conflictos · ${r.iteraciones} movimientos · ${r.candidatos} alternativas evaluadas · ${r.segundos} s</p>
   ${r.movimientos.length ? `<table class="t"><tr><th>Sesión</th><th>Nuevo horario</th><th>Aula</th><th>Docente</th><th>Δ</th></tr>${lista}</table>` : ""}
   ${r.pendientes.length ? `<h3>Pendientes (requieren su decisión)</h3>${r.pendientes.map(p => `<div class="msj aviso">${esc(p)}</div>`).join("")}` : `<div class="msj ok">No quedan conflictos.</div>`}
   ${r.aplicado ? "" : `<p class="pie">Es una simulación: no se guardó nada.</p><p><button class="btn primario" data-a="resolver-aplicar">Aplicar estos movimientos</button> <button class="btn" data-a="cerrar">Cancelar</button></p>`}`);
  if (r.aplicado) await recargar();
}
function ventanaResolver() {
  modal(`<h2>Resolver automáticamente</h2><p>El sistema busca movimientos que reducen los conflictos sin empeorar ninguna restricción. Primero verá una simulación; nada se guarda hasta que la aplique.</p>
   <div class="fila"><label>Criterio</label><select id="r-crit"><option value="">menor-movimiento</option>${S.criterios.filter(c => c !== "menor-movimiento").map(c => `<option>${esc(c)}</option>`).join("")}</select>
   <label><input type="checkbox" id="r-doc"> permitir cambiar docente</label></div><p><button class="btn primario" data-a="resolver-simular">Simular</button></p>`);
}
function ventanaCargar() {
  modal(`<h2>Cargar datos</h2><p><button class="btn primario" data-a="demo-ampliada">Demostración ampliada: 30 docentes, 20 aulas, 73 sesiones (14 conflictos)</button></p>
   <p><button class="btn" data-a="demo">Demostración pequeña: 10 docentes, 8 aulas, 20 sesiones (11 conflictos)</button> <span class="pie">(cualquiera de las dos reemplaza los datos actuales)</span></p><hr>
   <p>O suba sus tres archivos CSV (UTF-8). Si hay errores se listan todos y <b>no se cambia nada</b>.</p>
   <div class="fila"><label style="width:7rem">docentes.csv</label><input type="file" id="f-docentes" accept=".csv"></div>
   <div class="fila"><label style="width:7rem">aulas.csv</label><input type="file" id="f-aulas" accept=".csv"></div>
   <div class="fila"><label style="width:7rem">sesiones.csv</label><input type="file" id="f-sesiones" accept=".csv"></div>
   <div class="fila"><label style="width:7rem">Semestre</label><input type="text" id="f-sem" value="2026-2" size="8"></div>
   <div class="fila"><label style="width:7rem">Inicio</label><input type="text" id="f-ini" placeholder="AAAA-MM-DD" size="12"> <label>Fin</label><input type="text" id="f-fin" placeholder="AAAA-MM-DD" size="12"></div>
   <p class="pie">Las fechas solo son obligatorias si el semestre no es 2026-2. Importar reemplaza los datos actuales.</p>
   <p><button class="btn primario" data-a="subir">Importar</button></p><div id="imp-res"></div>`);
}
async function importar(d) {
  const r = await api("/api/importar", d);
  if (r.rechazado) { $("#imp-res").innerHTML = `<div class="msj mal"><b>Importación rechazada (no se escribió nada):</b>${r.errores.map(e => `\n• ${esc(e)}`).join("")}</div>`; return; }
  cerrarModal(); V.sel = null; V.alt = null; V.msj = null; V.clave = null; await recargar(r.mensaje);
}
async function subir() {
  const leer = id => { const f = $(id).files[0]; return f ? f.text() : Promise.resolve(""); };
  const [docentes, aulas, sesiones] = await Promise.all([leer("#f-docentes"), leer("#f-aulas"), leer("#f-sesiones")]);
  await importar({ docentes, aulas, sesiones, semestre: $("#f-sem").value.trim(), inicio: $("#f-ini").value.trim(), fin: $("#f-fin").value.trim(), nombre: "Propuesta importada desde la web" });
}

document.addEventListener("click", async e => {
  const el = e.target.closest("[data-a],[data-vista],[data-pest],[data-ir],[data-aplicar]"); if (!el) return;
  if (el.dataset.vista) { V.vista = el.dataset.vista; V.clave = clavesVista()[0] ?? null; pintarIzq(); return; }
  if (el.dataset.pest) { V.pestana = el.dataset.pest; pintar(); return; }
  if (el.dataset.ir) { V.sel = el.dataset.ir; V.alt = null; V.msj = null; const s = sesion(V.sel);
    V.clave = { grupo: s.grupo, docente: s.docente, aula: s.aula }[V.vista]; pintar(); window.scrollTo({ top: 0, behavior: "smooth" }); return; }
  if (el.dataset.aplicar) {
    const r = await api("/api/aplicar", { sesion: V.sel, k: +el.dataset.aplicar, criterio: V.criterio, cambiar_docente: V.cambiarDocente });
    V.alt = null; V.msj = { tipo: "ok", texto: r.mensaje }; await recargar(); return;
  }
  switch (el.dataset.a) {
    case "alternativas": V.criterio = $("#crit").value; V.cambiarDocente = $("#cdoc").checked;
      V.alt = (await api("/api/recomendar", { sesion: V.sel, criterio: V.criterio, cambiar_docente: V.cambiarDocente, n: 5 })).alternativas; V.msj = null; pintar(); break;
    case "mover": await mover({ sesion: V.sel, dia: $("#m-dia").value, hora: $("#m-hora").value, aula: $("#m-aula").value, docente: $("#m-doc").value }); break;
    case "resolver": ventanaResolver(); break;
    case "resolver-simular": await resolver(false); break;
    case "resolver-aplicar": await resolver(true); break;
    case "cerrar": cerrarModal(); break;
    case "deshacer": { const r = await api("/api/deshacer", {}); V.alt = null; V.msj = null; await recargar(r.mensaje); break; }
    case "validar": { const r = await api("/api/validar", {}); await recargar(r.mensaje); break; }
    case "cargar": ventanaCargar(); break;
    case "demo": await importar({ demo: true }); break;
    case "demo-ampliada": await importar({ demo: "ampliada" }); break;
    case "subir": await subir(); break;
    case "parametros": {
      const valores = {}; document.querySelectorAll("[data-par]").forEach(i => valores[i.dataset.par] = i.value.trim());
      const r = await api("/api/parametros", { valores }); V.msj = null; await recargar(r.mensaje); break; }
  }
});
document.addEventListener("change", async e => {
  const r = e.target.closest("[data-regla]"); if (!r) return;
  const resp = await api("/api/regla", { id: r.dataset.regla, activa: r.checked }); await recargar(resp.mensaje);
});
recargar().catch(() => { $("#app").innerHTML = `<p class="cargando">No se pudo contactar al servidor del SPH.</p>`; });
