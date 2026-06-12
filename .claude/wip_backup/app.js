// approval_ui/app.js — Central de Conteúdo (SPA vanilla, sem deps, multi-brand).
// Router por hash + 4 telas: dashboard, nova campanha, progresso, aprovação.

let pollTimer = null;
let calRef = null; // primeiro dia do mês exibido no calendário
let BRAND = null; // metadata do brand ativo (carregado em loadBrand no boot)

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", async () => {
  setupModal();
  setupTopbar();
  await loadBrand();
  route();
});

// Carrega metadata do brand uma vez no boot. A UI usa BRAND.briefing_fields
// pra renderizar o form de nova campanha. Em caso de falha, segue com schema
// vazio (o usuário vê o form quebrado, mas o resto da SPA continua usável).
async function loadBrand() {
  try {
    BRAND = await fetchJSON("/api/brand");
  } catch (e) {
    console.error("Falha ao carregar brand:", e);
    BRAND = { briefing_fields: [] };
  }
}

// Spotlight gold seguindo o cursor na topbar — luz oblíqua editorial.
// Atualiza CSS vars --mx/--my; o radial-gradient no style.css usa.
function setupTopbar() {
  const topbar = document.querySelector(".topbar");
  if (!topbar) return;
  topbar.addEventListener("mousemove", (e) => {
    const rect = topbar.getBoundingClientRect();
    topbar.style.setProperty("--mx", `${e.clientX - rect.left}px`);
    topbar.style.setProperty("--my", `${e.clientY - rect.top}px`);
  });
  topbar.addEventListener("mouseleave", () => {
    topbar.style.setProperty("--mx", "-400px");
    topbar.style.setProperty("--my", "-400px");
  });
}

function app() { return document.getElementById("app"); }

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

function route() {
  stopPolling();
  const hash = location.hash || "#/";
  const m = hash.match(/^#\/campanha\/(.+)$/);
  if (hash === "#/" || hash === "") return renderDashboard();
  if (hash === "#/novo") return renderNovo();
  if (hash === "#/calendario") return renderCalendario();
  if (hash === "#/historico") return renderHistorico();
  if (m) return renderCampanha(decodeURIComponent(m[1]));
  renderDashboard();
}

// ====================== Dashboard ======================
function dashSkeleton(n = 6) {
  // Placeholder grid: 6 cards shimmer enquanto o fetch completa.
  // Mais agradável que "Carregando..." centralizado — UI parece "quase pronta".
  const cards = Array.from({ length: n }).map(() => `
    <div class="skel-card">
      <span class="skel skel-badge"></span>
      <span class="skel skel-title"></span>
      <span class="skel skel-line"></span>
      <span class="skel skel-line short"></span>
    </div>`).join("");
  return `<h1 class="page-title">Campanhas</h1><div class="skeleton-grid">${cards}</div>`;
}

async function renderDashboard() {
  app().innerHTML = dashSkeleton();
  let campaigns;
  try {
    campaigns = await fetchJSON("/api/campaigns");
  } catch (e) {
    return showError(`Erro ao carregar campanhas: ${e.message}`);
  }

  if (!campaigns.length) {
    app().innerHTML = `
      <div class="empty">
        <h2>Nenhuma campanha ainda</h2>
        <p>Crie a primeira campanha para começar.</p>
        <a class="btn btn-approve" href="#/novo">+ Nova campanha</a>
      </div>`;
    return;
  }

  const grid = el("div", "dash-grid");
  campaigns.forEach((c) => grid.appendChild(dashCard(c)));
  app().innerHTML = `<h1 class="page-title">Campanhas</h1>`;
  app().appendChild(grid);
}

function dashCard(c) {
  const b = c.briefing || {};
  const info = statusInfo(c.status);
  const card = el("a", "dash-card");
  card.href = `#/campanha/${encodeURIComponent(c.campaign_id)}`;

  const tema = b.tema_especifico || b.area_direito || c.campaign_id;
  card.appendChild(textEl("div", `badge ${info.cls}`, info.label));
  card.appendChild(textEl("h3", "dash-card-title", tema));
  const meta = [b.area_direito, b.formato].filter(Boolean).join(" · ");
  card.appendChild(textEl("p", "dash-card-meta", meta));
  if (c.data_agendada) {
    card.appendChild(textEl("p", "dash-card-date", `📅 ${formatDate(c.data_agendada)}`));
  }
  if (c.tokens_used && c.tokens_used > 0) {
    card.appendChild(textEl("p", "dash-card-tokens", `🪙 ${formatTokens(c.tokens_used)} tokens`));
  }
  // Duplicar — só faz sentido em campanhas já finalizadas (aprovada/aguardando/erro)
  if (c.status !== "gerando" && c.status !== "ajuste_solicitado") {
    const dupBtn = textEl("button", "dash-card-dup", "Duplicar");
    dupBtn.type = "button";
    dupBtn.title = "Criar nova campanha com o mesmo briefing";
    dupBtn.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      duplicarCampanha(c.campaign_id);
    });
    card.appendChild(dupBtn);
  }
  // Apagar — disponível em qualquer estado, exceto "gerando" (backend recusa).
  if (c.status !== "gerando") {
    const delBtn = textEl("button", "dash-card-del", "Apagar");
    delBtn.type = "button";
    delBtn.title = "Remove a campanha e seus arquivos do disco";
    delBtn.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      apagarCampanha(c.campaign_id, b.tema_especifico || b.area_direito || c.campaign_id);
    });
    card.appendChild(delBtn);
  }
  return card;
}

async function apagarCampanha(campaignId, rotulo) {
  if (!confirm(`Apagar "${rotulo}"?\n\nIsto remove a campanha do banco e os PNGs/exports do disco. Não dá pra desfazer.`)) {
    return;
  }
  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campaignId)}`, {
      method: "DELETE",
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.erro || `Erro ao apagar (HTTP ${res.status}).`);
      return;
    }
    renderDashboard();
  } catch (e) {
    alert(`Falha ao apagar: ${e.message}`);
  }
}

async function duplicarCampanha(campaignId) {
  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campaignId)}/duplicate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.erro || `Erro ao duplicar (HTTP ${res.status}).`);
      return;
    }
    location.hash = `#/campanha/${encodeURIComponent(data.campaign_id)}`;
  } catch (e) {
    alert(`Falha ao duplicar: ${e.message}`);
  }
}

// ====================== Histórico (aprovadas) ======================
async function renderHistorico() {
  app().innerHTML = dashSkeleton(4);
  let campaigns;
  try {
    campaigns = await fetchJSON("/api/campaigns");
  } catch (e) {
    return showError(`Erro ao carregar histórico: ${e.message}`);
  }
  const aprovadas = campaigns.filter((c) => c.status === "aprovada");

  if (!aprovadas.length) {
    app().innerHTML = `
      <a class="back" href="#/">← Campanhas</a>
      <div class="empty">
        <h2>Nenhuma campanha aprovada ainda</h2>
        <p>Quando você aprovar campanhas, elas aparecem aqui pra revisitar e baixar.</p>
      </div>`;
    return;
  }

  app().innerHTML = `<h1 class="page-title">Histórico de aprovadas</h1>`;
  const grid = el("div", "dash-grid");
  aprovadas.forEach((c) => grid.appendChild(historicoCard(c)));
  app().appendChild(grid);
}

function historicoCard(c) {
  const b = c.briefing || {};
  const tema = b.tema_especifico || b.area_direito || c.campaign_id;
  const card = el("div", "dash-card");

  card.appendChild(textEl("div", "badge badge-approved", "Aprovada"));
  card.appendChild(textEl("h3", "dash-card-title", tema));
  const meta = [b.area_direito, b.formato].filter(Boolean).join(" · ");
  card.appendChild(textEl("p", "dash-card-meta", meta));
  if (c.data_agendada) {
    card.appendChild(textEl("p", "dash-card-date", `📅 ${formatDate(c.data_agendada)}`));
  }

  const actions = el("div", "historico-actions");

  const verBtn = textEl("a", "btn btn-adjust", "Ver detalhes");
  verBtn.href = `#/campanha/${encodeURIComponent(c.campaign_id)}`;
  actions.appendChild(verBtn);

  const dlBtn = textEl("a", "btn btn-approve", "⬇ Baixar .zip");
  dlBtn.href = `/api/campaigns/${encodeURIComponent(c.campaign_id)}/download`;
  dlBtn.setAttribute("download", "");
  actions.appendChild(dlBtn);

  card.appendChild(actions);
  return card;
}

// ====================== Nova campanha ======================
// Renderiza o form a partir de BRAND.briefing_fields (schema declarativo).
// Pareamento visual: tom + objetivo e formato + num_slides ficam em form-row
// (lado a lado). num_slides arranca escondido — só aparece se formato="carousel".
function renderNovo() {
  const fields = (BRAND && BRAND.briefing_fields) || [];
  const html = renderBriefingFieldsHtml(fields);

  app().innerHTML = `
    <a class="back" href="#/">← Campanhas</a>
    <h1 class="page-title">Nova campanha</h1>
    <form id="form-novo" class="form">
      ${html}
      <div id="form-erro" class="form-erro hidden"></div>
      <div class="form-actions">
        <button type="submit" class="btn btn-approve" id="btn-gerar">Gerar campanha</button>
      </div>
      <p class="form-hint">A geração leva ~1-2 min e consome créditos de API.</p>
    </form>`;

  // Toggle de num_slides conforme formato (interação intrínseca, não declarada
  // no schema — formato=carousel é a única que precisa de slides).
  const formato = document.querySelector('#form-novo [name="formato"]');
  const wrapSlides = document.getElementById("wrap-num_slides");
  const sync = () => {
    if (!formato || !wrapSlides) return;
    wrapSlides.classList.toggle("hidden", formato.value !== "carousel");
  };
  if (formato) formato.addEventListener("change", sync);
  sync();

  document.getElementById("form-novo").addEventListener("submit", onSubmitNovo);
}

// Renderiza a lista de BriefingFields como HTML do form. Agrupa pares
// (tom+objetivo) e (formato+num_slides) em form-row se aparecerem em
// sequência no schema — heurística simples que casa com o layout original.
function renderBriefingFieldsHtml(fields) {
  const pares = new Set(["tom:objetivo", "formato:num_slides"]);
  let html = "";
  let i = 0;
  while (i < fields.length) {
    const a = fields[i];
    const b = fields[i + 1];
    if (b && pares.has(`${a.name}:${b.name}`)) {
      html += `<div class="form-row">${renderField(a)}${renderField(b)}</div>`;
      i += 2;
    } else {
      html += renderField(a);
      i += 1;
    }
  }
  return html;
}

function renderField(f) {
  const req = f.required ? " *" : "";
  const wrapId = `wrap-${f.name}`;
  const wrapCls = f.name === "num_slides" ? " class=\"hidden\"" : "";
  const reqAttr = f.required ? " required" : "";
  const phAttr = f.placeholder ? ` placeholder="${escapeAttr(f.placeholder)}"` : "";
  const maxAttr = f.max_chars ? ` maxlength="${f.max_chars}"` : "";
  const def = f.default || "";

  let input;
  if (f.kind === "textarea") {
    const rows = f.rows || 2;
    input = `<textarea name="${f.name}" rows="${rows}"${reqAttr}${phAttr}${maxAttr}>${escapeHtml(def)}</textarea>`;
  } else if (f.kind === "enum") {
    const opts = (f.enum_values || []).map((v, idx) => {
      const lbl = (f.enum_labels && f.enum_labels[idx]) || v;
      const sel = v === def ? " selected" : "";
      return `<option value="${escapeAttr(v)}"${sel}>${escapeHtml(lbl)}</option>`;
    }).join("");
    input = `<select name="${f.name}"${reqAttr}>${opts}</select>`;
  } else if (f.kind === "int") {
    const minA = (f.min_int !== null && f.min_int !== undefined) ? ` min="${f.min_int}"` : "";
    const maxA = (f.max_int !== null && f.max_int !== undefined) ? ` max="${f.max_int}"` : "";
    input = `<input name="${f.name}" type="number"${minA}${maxA} value="${escapeAttr(def)}"${reqAttr}>`;
  } else if (f.kind === "date") {
    input = `<input name="${f.name}" type="date"${reqAttr} value="${escapeAttr(def)}">`;
  } else { // text
    input = `<input name="${f.name}" type="text"${reqAttr}${phAttr}${maxAttr} value="${escapeAttr(def)}">`;
  }

  const help = f.help ? `<small class="form-help">${escapeHtml(f.help)}</small>` : "";
  return `<label id="${wrapId}"${wrapCls}>${escapeHtml(f.label)}${req}${input}${help}</label>`;
}

function escapeAttr(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ---- Templates de briefing ----
async function carregarTemplates() {
  const sel = document.getElementById("template-select");
  if (!sel) return;
  try {
    const lista = await fetchJSON("/api/templates");
    // Mantém só a opção "em branco" e repopula
    sel.innerHTML = '<option value="">— em branco —</option>';
    for (const t of lista) {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.nome;
      sel.appendChild(opt);
    }
  } catch (e) {
    console.error("Falha ao carregar templates:", e);
  }
}

function onTemplateSelect(e) {
  const id = e.target.value;
  const btnDel = document.getElementById("btn-template-delete");
  btnDel.disabled = !id;
  if (!id) return;
  // Acha o template na lista carregada e popula o form (itera os campos do
  // brand pra não acoplar a nomes específicos).
  fetchJSON("/api/templates").then(lista => {
    const t = lista.find(x => String(x.id) === String(id));
    if (!t) return;
    const form = document.getElementById("form-novo");
    const fields = (BRAND && BRAND.briefing_fields) || [];
    for (const f of fields) {
      const el = form.elements[f.name];
      if (el && t[f.name] !== undefined && t[f.name] !== null) {
        el.value = t[f.name];
      }
    }
    // Mostra/esconde campo de slides conforme formato
    const wrap = document.getElementById("wrap-num_slides");
    if (wrap) wrap.classList.toggle("hidden", t.formato !== "carousel");
  });
}

async function onTemplateSave() {
  const nome = prompt("Nome do template:");
  if (!nome || !nome.trim()) return;
  const form = document.getElementById("form-novo");
  const fd = new FormData(form);
  const body = Object.fromEntries(fd.entries());
  body.nome = nome.trim();
  if (body.formato !== "carousel") body.num_slides = 1;
  else body.num_slides = parseInt(body.num_slides, 10);
  try {
    const res = await fetch("/api/templates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.erro || "Falha ao salvar template");
    await carregarTemplates();
    document.getElementById("template-select").value = data.id;
    document.getElementById("btn-template-delete").disabled = false;
  } catch (err) {
    alert("Erro ao salvar template: " + err.message);
  }
}

async function onTemplateDelete() {
  const sel = document.getElementById("template-select");
  const id = sel.value;
  if (!id) return;
  const nome = sel.options[sel.selectedIndex].textContent;
  if (!confirm(`Apagar template "${nome}"?`)) return;
  try {
    const res = await fetch(`/api/templates/${id}`, { method: "DELETE" });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.erro || "Falha ao apagar template");
    }
    await carregarTemplates();
    document.getElementById("btn-template-delete").disabled = true;
  } catch (err) {
    alert("Erro ao apagar template: " + err.message);
  }
}

async function onSubmitNovo(e) {
  e.preventDefault();
  const btn = document.getElementById("btn-gerar");
  const erro = document.getElementById("form-erro");
  erro.classList.add("hidden");
  btn.disabled = true;
  btn.textContent = "Gerando…";

  const fd = new FormData(e.target);
  const body = Object.fromEntries(fd.entries());
  if (body.formato !== "carousel") body.num_slides = 1;
  else body.num_slides = parseInt(body.num_slides, 10);

  try {
    const res = await fetch("/api/campaigns", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.erro || "Falha ao criar campanha");
    location.hash = `#/campanha/${encodeURIComponent(data.campaign_id)}`;
  } catch (err) {
    erro.textContent = err.message;
    erro.classList.remove("hidden");
    btn.disabled = false;
    btn.textContent = "Gerar campanha";
  }
}

// ====================== Campanha (despacha por estado) ======================
async function renderCampanha(id) {
  let data;
  try {
    data = await fetchJSON(`/api/campaigns/${encodeURIComponent(id)}`);
  } catch (e) {
    return showError(`Erro ao carregar a campanha: ${e.message}`);
  }
  const status = data.state.status;
  if (status === "gerando" || status === "ajuste_solicitado") {
    renderProgresso(data);
    startPolling(id);
  } else if (status === "erro") {
    renderErro(data);
  } else if (status === "aguardando_aprovacao") {
    renderAprovacao(data);
  } else if (status === "aprovada") {
    renderAprovada(data);
  } else {
    showError(`Estado desconhecido: ${status}`);
  }
}

function startPolling(id) {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const data = await fetchJSON(`/api/campaigns/${encodeURIComponent(id)}`);
      const status = data.state.status;
      if (status === "gerando" || status === "ajuste_solicitado") {
        updateProgresso(data);
      } else {
        stopPolling();
        renderCampanha(id); // troca de tela quando termina
      }
    } catch (_) { /* mantém tentando */ }
  }, 2000);
}

// ---------- Progresso ----------
const ETAPAS = [
  ["copy", "Gerando textos (copy)"],
  ["arte", "Gerando arte (Ideogram)"],
  ["composicao", "Compondo os posts"],
];

function renderProgresso(data) {
  const b = data.briefing || {};
  app().innerHTML = `
    <a class="back" href="#/">← Campanhas</a>
    <h1 class="page-title">${escapeHtml(b.tema_especifico || b.area_direito || "Campanha")}</h1>
    <div class="progress">
      <div class="spinner"></div>
      <ul class="steps" id="steps"></ul>
      <p class="progress-hint">Você pode voltar às campanhas; ela continua gerando.</p>
    </div>`;
  updateProgresso(data);
}

function updateProgresso(data) {
  const steps = document.getElementById("steps");
  if (!steps) return;
  const etapaAtual = data.state.etapa;
  const idxAtual = ETAPAS.findIndex(([k]) => k === etapaAtual);
  steps.innerHTML = "";
  ETAPAS.forEach(([key, label], i) => {
    let cls = "step";
    if (i < idxAtual) cls += " done";
    else if (i === idxAtual) cls += " active";
    const li = textEl("li", cls, label);
    steps.appendChild(li);
  });
}

// ---------- Erro ----------
function renderErro(data) {
  app().innerHTML = `
    <a class="back" href="#/">← Campanhas</a>
    <h1 class="page-title">Erro na geração</h1>
    <div class="erro-box">
      <p>${escapeHtml(data.state.erro || "Falha desconhecida.")}</p>
      <button class="btn btn-approve" id="btn-retry">Tentar novamente</button>
    </div>`;
  document.getElementById("btn-retry").addEventListener("click", async () => {
    await fetch(`/api/campaigns/${encodeURIComponent(data.campaign_id)}/adjust`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ option_id: 1, nota: "" }),
    });
    renderCampanha(data.campaign_id);
  });
}

// ---------- Aprovação ----------
function renderAprovacao(data) {
  app().innerHTML = `<a class="back" href="#/">← Campanhas</a>`;
  const b = data.briefing || {};
  app().appendChild(textEl("h1", "page-title", b.tema_especifico || b.area_direito || "Aprovação"));

  const tokens = data.state && data.state.tokens_used;
  if (tokens && tokens > 0) {
    app().appendChild(textEl("p", "approval-tokens", `🪙 Tokens consumidos nesta campanha: ${tokens.toLocaleString("pt-BR")}`));
  }

  const sched = el("div", "schedule-bar");
  sched.innerHTML = `
    <label>📅 Agendar publicação para:
      <input type="text" id="data-agendada" placeholder="dd/mm/aaaa"
             maxlength="10" inputmode="numeric"
             pattern="\\d{2}/\\d{2}/\\d{4}">
    </label>
    <span class="schedule-hint">opcional — só registra a data (publicação manual)</span>`;
  app().appendChild(sched);

  // Máscara dd/mm/aaaa: insere as barras conforme o usuário digita números.
  // Backspace funciona normalmente porque só reescrevemos quando há mudança.
  const dataInput = document.getElementById("data-agendada");
  dataInput.addEventListener("input", () => {
    const digitos = dataInput.value.replace(/\D/g, "").slice(0, 8);
    let saida = digitos;
    if (digitos.length > 4) saida = `${digitos.slice(0,2)}/${digitos.slice(2,4)}/${digitos.slice(4)}`;
    else if (digitos.length > 2) saida = `${digitos.slice(0,2)}/${digitos.slice(2)}`;
    if (dataInput.value !== saida) dataInput.value = saida;
  });

  const grid = el("div", "cards");
  data.options.forEach((op) => grid.appendChild(approvalCard(op, data.campaign_id)));
  app().appendChild(grid);
}

function approvalCard(op, campaignId) {
  const card = el("div", "card");
  const isCarousel = Array.isArray(op.slides);

  if (isCarousel) {
    card.appendChild(carouselPreview(op));
  } else {
    const img = el("img", "card-preview");
    img.src = op.composed_image_url;
    img.alt = `Opção ${op.option_id}`;
    img.addEventListener("click", () => openModal(op.composed_image_url));
    card.appendChild(img);
  }

  const body = el("div", "card-body");
  body.appendChild(textEl("div", "card-tag",
    isCarousel
      ? `Opção ${op.option_id} · Carrossel (${op.slides.length} slides)`
      : `Opção ${op.option_id}`,
  ));

  if (!isCarousel) {
    body.appendChild(textEl("h3", "card-headline", op.headline));
    body.appendChild(textEl("p", "card-text", op.body));
  }

  const capBlock = el("div", "caption-block");
  const capText = textEl("div", "caption-text collapsed", op.caption || "(sem legenda)");
  capBlock.appendChild(capText);
  if ((op.caption || "").length > 140) {
    const toggle = textEl("button", "caption-toggle", "Ver mais");
    toggle.addEventListener("click", () => {
      const collapsed = capText.classList.toggle("collapsed");
      toggle.textContent = collapsed ? "Ver mais" : "Ver menos";
    });
    capBlock.appendChild(toggle);
  }
  body.appendChild(capBlock);

  if (op.hashtags && op.hashtags.length) {
    const tags = el("div", "hashtags");
    op.hashtags.forEach((h) => tags.appendChild(textEl("span", "hashtag", `#${h}`)));
    body.appendChild(tags);
  }

  // Utilitários: baixar imagem + copiar legenda (custo zero, pra postar manual)
  const utils = el("div", "card-utils");
  if (isCarousel) {
    const dlAll = textEl("button", "util-btn", `⬇ Baixar ${op.slides.length} slides`);
    dlAll.addEventListener("click", () => baixarSlides(op, campaignId));
    utils.appendChild(dlAll);
  } else {
    const dl = el("a", "util-btn");
    dl.href = op.composed_image_url;
    dl.download = `${campaignId}_option${op.option_id}.png`;
    dl.textContent = "⬇ Baixar imagem";
    utils.appendChild(dl);
  }
  const copyBtn = textEl("button", "util-btn", "⧉ Copiar legenda");
  copyBtn.addEventListener("click", () => copyLegenda(op, copyBtn));
  utils.appendChild(copyBtn);
  body.appendChild(utils);

  const actions = el("div", "card-actions");
  const approveBtn = textEl(
    "button", "btn btn-approve",
    isCarousel ? "✓ Aprovar este carrossel" : "✓ Aprovar este post",
  );
  approveBtn.addEventListener("click", () => approve(campaignId, op.option_id));
  actions.appendChild(approveBtn);

  const editBtn = textEl("button", "btn btn-adjust", "✎ Editar copy");
  editBtn.addEventListener("click", () => openEditModal(campaignId, op, isCarousel));
  actions.appendChild(editBtn);

  const adjustBtn = textEl("button", "btn btn-adjust", "Solicitar ajuste");
  const adjustBox = el("div", "adjust-box hidden");
  const ta = el("textarea");
  ta.placeholder = "Descreva o ajuste (ex.: deixe o tom mais acessível)…";
  const sendAdjust = textEl("button", "btn btn-adjust", "Enviar e regerar");
  sendAdjust.addEventListener("click", () => adjust(campaignId, op.option_id, ta.value));
  adjustBox.appendChild(ta);
  adjustBox.appendChild(sendAdjust);
  adjustBtn.addEventListener("click", () => adjustBox.classList.toggle("hidden"));
  actions.appendChild(adjustBtn);
  actions.appendChild(adjustBox);

  body.appendChild(actions);
  card.appendChild(body);
  return card;
}

function carouselPreview(op) {
  // Stack vertical: cada slide com badge "X/N" e seu headline/body próprios.
  const wrap = el("div", "slides-stack");
  const total = op.slides.length;
  op.slides.forEach((s) => {
    const slide = el("div", "slide-item");
    const img = el("img", "slide-img");
    img.src = s.image_url;
    img.alt = `Slide ${s.slide_id}`;
    img.addEventListener("click", () => openModal(s.image_url));
    slide.appendChild(img);
    slide.appendChild(textEl("div", "slide-badge", `Slide ${s.slide_id}/${total}`));
    wrap.appendChild(slide);
  });
  return wrap;
}

async function baixarSlides(op, campaignId) {
  // Baixa cada slide sequencialmente (anchor clicks) — sem dependência de zip.
  for (const s of op.slides) {
    const a = document.createElement("a");
    a.href = s.image_url;
    a.download = `${campaignId}_option${op.option_id}_slide${s.slide_id}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    // Pequena pausa para o navegador não suprimir downloads consecutivos
    await new Promise((r) => setTimeout(r, 150));
  }
}

async function approve(campaignId, optionId) {
  const rawData = document.getElementById("data-agendada").value.trim();
  let data = null;
  if (rawData) {
    data = dateBRtoISO(rawData);
    if (!data) {
      alert("Data inválida. Use o formato dd/mm/aaaa (ex.: 05/06/2026).");
      return;
    }
  }
  if (!confirm(`Aprovar a Opção ${optionId}? Ela será exportada para publicação.`)) return;
  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campaignId)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ option_id: optionId, data_agendada: data }),
    });
    const out = await res.json();
    if (!res.ok) throw new Error(out.erro || "Falha ao aprovar");
    renderCampanha(campaignId);
  } catch (err) {
    alert("Erro ao aprovar: " + err.message);
  }
}

async function adjust(campaignId, optionId, nota) {
  if (!nota.trim()) { alert("Descreva o ajuste antes de enviar."); return; }
  try {
    await fetch(`/api/campaigns/${encodeURIComponent(campaignId)}/adjust`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ option_id: optionId, nota }),
    });
    renderCampanha(campaignId); // volta a gerar -> tela de progresso
  } catch (err) {
    alert("Erro ao solicitar ajuste: " + err.message);
  }
}

// ---------- Aprovada ----------
function renderAprovada(data) {
  const op = data.state.option_aprovada;
  const dataAg = data.state.data_agendada;
  const exp = data.exports || {};
  const allPngs = exp.all_pngs || (exp.png ? [exp.png] : []);
  const cid = data.briefing.campaign_id;
  const dlUrl = `/api/campaigns/${encodeURIComponent(cid)}/download`;

  app().innerHTML = `
    <a class="back" href="#/">← Campanhas</a>
    <div class="done-card">
      <div class="done-check">✓</div>
      <h2>Post aprovado</h2>
      <p>A Opção ${op} foi exportada e está pronta para publicação.</p>
      ${dataAg ? `<p class="done-hint">📅 Agendada para ${formatDate(dataAg)}</p>` : ""}
      <a class="btn btn-approve done-download" href="${dlUrl}" download>
        ⬇ Baixar pacote (.zip) — imagens + legendas + briefing
      </a>
    </div>

    <details class="export-paths">
      <summary class="export-paths-title">Arquivos no servidor (avançado)</summary>
      <div class="export-list" id="export-list"></div>
    </details>`;

  const list = document.getElementById("export-list");
  if (exp.post_txt) list.appendChild(exportRow("Texto pra postar (post.txt)", exp.post_txt));
  if (exp.metadata) list.appendChild(exportRow("Metadata (JSON)", exp.metadata));
  allPngs.forEach((p, i) => {
    const label = allPngs.length > 1 ? `Imagem — slide ${i + 1}` : "Imagem (PNG)";
    list.appendChild(exportRow(label, p));
  });
}

function exportRow(label, path) {
  const row = el("div", "export-row");
  row.appendChild(textEl("div", "export-row-label", label));
  const pathEl = textEl("code", "export-row-path", path);
  row.appendChild(pathEl);
  const btn = textEl("button", "util-btn export-row-copy", "Copiar caminho");
  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(path);
      const old = btn.textContent;
      btn.textContent = "✓ Copiado!";
      setTimeout(() => { btn.textContent = old; }, 1500);
    } catch (_) {
      alert("Não consegui copiar — selecione e copie manual.");
    }
  });
  row.appendChild(btn);
  return row;
}

// ====================== Calendário ======================
const MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const DIAS_SEMANA = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

async function renderCalendario() {
  if (!calRef) {
    const n = new Date();
    calRef = new Date(n.getFullYear(), n.getMonth(), 1);
  }
  app().innerHTML = `<p class="loading">Carregando calendário…</p>`;
  let campaigns;
  try {
    campaigns = await fetchJSON("/api/campaigns");
  } catch (e) {
    return showError(`Erro ao carregar o calendário: ${e.message}`);
  }

  // Mapeia data ISO (YYYY-MM-DD) -> campanhas agendadas naquele dia
  const porDia = {};
  campaigns.filter((c) => c.data_agendada).forEach((c) => {
    (porDia[c.data_agendada] = porDia[c.data_agendada] || []).push(c);
  });

  const ano = calRef.getFullYear();
  const mes = calRef.getMonth();

  app().innerHTML = "";
  const header = el("div", "cal-header");
  const prev = textEl("button", "cal-nav", "←");
  prev.addEventListener("click", () => { calRef = new Date(ano, mes - 1, 1); renderCalendario(); });
  const next = textEl("button", "cal-nav", "→");
  next.addEventListener("click", () => { calRef = new Date(ano, mes + 1, 1); renderCalendario(); });
  header.appendChild(prev);
  header.appendChild(textEl("h1", "cal-title", `${MESES[mes]} ${ano}`));
  header.appendChild(next);
  app().appendChild(header);

  const grid = el("div", "cal-grid");
  DIAS_SEMANA.forEach((d) => grid.appendChild(textEl("div", "cal-weekday", d)));

  const primeiroDiaSemana = new Date(ano, mes, 1).getDay(); // 0=Dom
  const diasNoMes = new Date(ano, mes + 1, 0).getDate();

  for (let i = 0; i < primeiroDiaSemana; i++) {
    grid.appendChild(el("div", "cal-cell cal-empty"));
  }
  for (let dia = 1; dia <= diasNoMes; dia++) {
    const cell = el("div", "cal-cell");
    cell.appendChild(textEl("div", "cal-day-num", String(dia)));
    const iso = `${ano}-${String(mes + 1).padStart(2, "0")}-${String(dia).padStart(2, "0")}`;
    (porDia[iso] || []).forEach((c) => {
      const b = c.briefing || {};
      const chip = textEl("a", "cal-chip", b.tema_especifico || b.area_direito || "Campanha");
      chip.href = `#/campanha/${encodeURIComponent(c.campaign_id)}`;
      cell.appendChild(chip);
    });
    grid.appendChild(cell);
  }
  app().appendChild(grid);

  const total = Object.values(porDia).reduce((a, l) => a + l.length, 0);
  if (!total) {
    app().appendChild(textEl("p", "cal-vazio",
      "Nenhuma campanha agendada. Aprove uma campanha com data para vê-la aqui."));
  }
}

async function copyLegenda(op, btn) {
  const tags = (op.hashtags || []).map((h) => `#${h}`).join(" ");
  const texto = (op.caption || "") + (tags ? `\n\n${tags}` : "");
  try {
    await navigator.clipboard.writeText(texto);
  } catch (_) {
    const ta = document.createElement("textarea");
    ta.value = texto;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) { /* ignora */ }
    ta.remove();
  }
  const orig = btn.textContent;
  btn.textContent = "✓ Copiado!";
  setTimeout(() => { btn.textContent = orig; }, 1500);
}

// ====================== Helpers ======================
function statusInfo(status) {
  switch (status) {
    case "aprovada": return { label: "Aprovada", cls: "badge-approved" };
    case "erro": return { label: "Erro", cls: "badge-error" };
    case "gerando": return { label: "Gerando…", cls: "badge-pending" };
    case "ajuste_solicitado": return { label: "Regerando…", cls: "badge-pending" };
    default: return { label: "Aguardando aprovação", cls: "badge-pending" };
  }
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function showError(msg) {
  app().innerHTML = `<p class="loading">${escapeHtml(msg)}</p>`;
}

function todayISO() { return new Date().toISOString().slice(0, 10); }
function formatDate(iso) {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}
// Formata contagem de tokens: < 1000 = exato, >= 1000 = "12,3k" (BR).
function formatTokens(n) {
  n = Number(n) || 0;
  if (n < 1000) return String(n);
  return (n / 1000).toFixed(1).replace(".", ",") + "k";
}
// Converte "dd/mm/aaaa" -> "aaaa-mm-dd" (ISO). Retorna null se for inválido
// ou se a data não existir no calendário (ex.: 31/02/2026).
function dateBRtoISO(br) {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(br);
  if (!m) return null;
  const [, dd, mm, yyyy] = m;
  const d = new Date(`${yyyy}-${mm}-${dd}T00:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  // Sanity: dia/mês/ano de volta tem que bater com o input (rejeita 31/02 etc).
  if (d.getDate() !== Number(dd) || d.getMonth() + 1 !== Number(mm) || d.getFullYear() !== Number(yyyy)) {
    return null;
  }
  return `${yyyy}-${mm}-${dd}`;
}

function setupModal() {
  const modal = document.getElementById("modal");
  document.getElementById("modal-close").addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });

  // Modal de edição manual de copy
  const edit = document.getElementById("edit-modal");
  document.getElementById("edit-modal-close").addEventListener("click", closeEditModal);
  document.getElementById("edit-cancel").addEventListener("click", closeEditModal);
  edit.addEventListener("click", (e) => { if (e.target === edit) closeEditModal(); });
  document.getElementById("edit-save").addEventListener("click", saveEdit);
}

// --- Edição manual de copy ---
let editContext = null; // { campaignId, optionId, isCarousel }

function openEditModal(campaignId, op, isCarousel) {
  editContext = { campaignId, optionId: op.option_id, isCarousel };
  const form = document.getElementById("edit-form");
  form.innerHTML = "";

  if (isCarousel) {
    // Metadados da publicação (1 conjunto pra todo o carrossel)
    form.appendChild(fieldGroup("Caption", "caption", op.caption || "", "textarea", 2200));
    form.appendChild(fieldGroup("CTA", "cta", op.cta || "", "input", 40));
    form.appendChild(fieldGroup(
      "Hashtags (separadas por vírgula ou espaço)", "hashtags",
      (op.hashtags || []).join(", "), "input",
    ));
    // Cada slide tem seu próprio bloco
    op.slides.forEach((s) => {
      const block = el("fieldset", "edit-slide-block");
      block.appendChild(textEl("legend", "edit-slide-legend", `Slide ${s.slide_id}/${op.slides.length}`));
      block.appendChild(fieldGroup("Headline", `slide-${s.slide_id}-headline`, s.headline || "", "input", 60));
      block.appendChild(fieldGroup("Subheadline", `slide-${s.slide_id}-subheadline`, s.subheadline || "", "input", 80));
      block.appendChild(fieldGroup("Body", `slide-${s.slide_id}-body`, s.body || "", "textarea", 150));
      form.appendChild(block);
    });
  } else {
    form.appendChild(fieldGroup("Headline", "headline", op.headline || "", "input", 60));
    form.appendChild(fieldGroup("Subheadline", "subheadline", op.subheadline || "", "input", 80));
    form.appendChild(fieldGroup("Body", "body", op.body || "", "textarea", 150));
    form.appendChild(fieldGroup("Caption", "caption", op.caption || "", "textarea", 2200));
    form.appendChild(fieldGroup("CTA", "cta", op.cta || "", "input", 40));
    form.appendChild(fieldGroup(
      "Hashtags (separadas por vírgula ou espaço)", "hashtags",
      (op.hashtags || []).join(", "), "input",
    ));
  }

  document.getElementById("edit-modal-title").textContent =
    `Editar copy — Opção ${op.option_id}`;
  document.getElementById("edit-modal").classList.remove("hidden");
}

function fieldGroup(label, name, value, kind, maxlen) {
  const wrap = el("label", "edit-field");
  wrap.appendChild(textEl("span", "edit-field-label", label));
  const input = el(kind === "textarea" ? "textarea" : "input", "edit-field-input");
  input.name = name;
  if (kind === "input") input.type = "text";
  else input.rows = kind === "textarea" && name === "caption" ? 5 : 2;
  input.value = value;
  if (maxlen) input.maxLength = maxlen;
  wrap.appendChild(input);
  return wrap;
}

function closeEditModal() {
  document.getElementById("edit-modal").classList.add("hidden");
  editContext = null;
}

async function saveEdit() {
  if (!editContext) return;
  const { campaignId, optionId, isCarousel } = editContext;
  const form = document.getElementById("edit-form");
  const data = new FormData(form);

  const fields = {};
  const slidesMap = {};

  for (const [name, raw] of data.entries()) {
    const value = String(raw);
    const slideMatch = name.match(/^slide-(\d+)-(headline|subheadline|body)$/);
    if (slideMatch) {
      const sid = parseInt(slideMatch[1], 10);
      slidesMap[sid] = slidesMap[sid] || { slide_id: sid };
      slidesMap[sid][slideMatch[2]] = value;
    } else if (name === "hashtags") {
      fields.hashtags = value.split(/[,\s]+/).filter(Boolean);
    } else {
      fields[name] = value;
    }
  }

  if (isCarousel && Object.keys(slidesMap).length) {
    fields.slides = Object.values(slidesMap);
  }

  const saveBtn = document.getElementById("edit-save");
  saveBtn.disabled = true;
  saveBtn.textContent = "Salvando…";

  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campaignId)}/edit-copy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ option_id: optionId, fields }),
    });
    const out = await res.json();
    if (!res.ok) throw new Error(out.erro || "Falha ao salvar edição");
    closeEditModal();
    renderCampanha(campaignId); // recarrega card (preview do PNG recomposto)
  } catch (err) {
    alert("Erro ao salvar: " + err.message);
  } finally {
    // Sempre reseta o botão — sem isso ele fica "Salvando…" eternamente após sucesso
    saveBtn.disabled = false;
    saveBtn.textContent = "Salvar e recompor";
  }
}
function openModal(src) {
  document.getElementById("modal-img").src = src;
  document.getElementById("modal").classList.remove("hidden");
}
function closeModal() {
  document.getElementById("modal").classList.add("hidden");
}

function el(tag, className) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  return e;
}
function textEl(tag, className, text) {
  const e = el(tag, className);
  e.textContent = text;
  return e;
}
function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
