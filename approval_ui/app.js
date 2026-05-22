// approval_ui/app.js — Central de Conteúdo Mendes & Vaz (SPA vanilla, sem deps).
// Router por hash + 4 telas: dashboard, nova campanha, progresso, aprovação.

let pollTimer = null;

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", () => {
  setupModal();
  route();
});

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
  if (m) return renderCampanha(decodeURIComponent(m[1]));
  renderDashboard();
}

// ====================== Dashboard ======================
async function renderDashboard() {
  app().innerHTML = `<p class="loading">Carregando campanhas…</p>`;
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
  return card;
}

// ====================== Nova campanha ======================
function renderNovo() {
  app().innerHTML = `
    <a class="back" href="#/">← Campanhas</a>
    <h1 class="page-title">Nova campanha</h1>
    <form id="form-novo" class="form">
      <label>Área do direito *
        <input name="area_direito" required placeholder="ex.: Direito Médico">
      </label>
      <label>Perfil do cliente ideal *
        <textarea name="perfil_cliente_ideal" required rows="2"
          placeholder="ex.: Médicos e clínicas de BH preocupados com processos"></textarea>
      </label>
      <div class="form-row">
        <label>Tom
          <select name="tom">
            <option value="tecnico">Técnico / Autoridade</option>
            <option value="acessivel">Acessível / Educativo</option>
          </select>
        </label>
        <label>Objetivo
          <select name="objetivo">
            <option value="posicionamento">Posicionamento</option>
            <option value="awareness">Awareness</option>
            <option value="captacao">Captação</option>
          </select>
        </label>
      </div>
      <div class="form-row">
        <label>Formato
          <select name="formato" id="sel-formato">
            <option value="square">Square (1080×1080)</option>
            <option value="portrait">Portrait (1080×1350)</option>
            <option value="carousel">Carrossel</option>
          </select>
        </label>
        <label id="wrap-slides" class="hidden">Nº de slides (3–8)
          <input name="num_slides" type="number" min="3" max="8" value="3">
        </label>
      </div>
      <label>Tema específico (opcional)
        <input name="tema_especifico" placeholder="deixe em branco para a IA escolher">
      </label>
      <label>Referências / observações (opcional)
        <textarea name="referencias" rows="2"></textarea>
      </label>
      <div id="form-erro" class="form-erro hidden"></div>
      <button type="submit" class="btn btn-approve" id="btn-gerar">Gerar campanha</button>
      <p class="form-hint">A geração leva ~1-2 min e consome créditos de API.</p>
    </form>`;

  const formato = document.getElementById("sel-formato");
  const wrapSlides = document.getElementById("wrap-slides");
  formato.addEventListener("change", () => {
    wrapSlides.classList.toggle("hidden", formato.value !== "carousel");
  });

  document.getElementById("form-novo").addEventListener("submit", onSubmitNovo);
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

  const sched = el("div", "schedule-bar");
  sched.innerHTML = `
    <label>📅 Agendar publicação para:
      <input type="date" id="data-agendada" min="${todayISO()}">
    </label>
    <span class="schedule-hint">opcional — só registra a data (publicação manual)</span>`;
  app().appendChild(sched);

  const grid = el("div", "cards");
  data.options.forEach((op) => grid.appendChild(approvalCard(op, data.campaign_id)));
  app().appendChild(grid);
}

function approvalCard(op, campaignId) {
  const card = el("div", "card");

  const img = el("img", "card-preview");
  img.src = op.composed_image_url;
  img.alt = `Opção ${op.option_id}`;
  img.addEventListener("click", () => openModal(op.composed_image_url));
  card.appendChild(img);

  const body = el("div", "card-body");
  body.appendChild(textEl("div", "card-tag", `Opção ${op.option_id}`));
  body.appendChild(textEl("h3", "card-headline", op.headline));
  body.appendChild(textEl("p", "card-text", op.body));

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

  const actions = el("div", "card-actions");
  const approveBtn = textEl("button", "btn btn-approve", "✓ Aprovar este post");
  approveBtn.addEventListener("click", () => approve(campaignId, op.option_id));
  actions.appendChild(approveBtn);

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

async function approve(campaignId, optionId) {
  const data = document.getElementById("data-agendada").value || null;
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
  app().innerHTML = `
    <a class="back" href="#/">← Campanhas</a>
    <div class="done-card">
      <div class="done-check">✓</div>
      <h2>Post aprovado</h2>
      <p>A Opção ${op} foi exportada e está pronta para publicação.</p>
      ${dataAg ? `<p class="done-hint">📅 Agendada para ${formatDate(dataAg)}</p>` : ""}
    </div>`;
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

function setupModal() {
  const modal = document.getElementById("modal");
  document.getElementById("modal-close").addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
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
