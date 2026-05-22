// approval_ui/app.js — Lógica da interface de aprovação (vanilla JS, sem deps).
// Fluxo: descobre a campanha atual -> carrega dados -> renderiza 3 cards ->
// trata aprovar / solicitar ajuste / ampliar imagem.

let CAMPAIGN_ID = null;

document.addEventListener("DOMContentLoaded", init);

async function init() {
  try {
    const current = await fetch("/api/current").then((r) => r.json());
    CAMPAIGN_ID = current.campaign_id;
    const data = await fetch(`/api/campaign/${CAMPAIGN_ID}`).then((r) => r.json());
    renderMeta(data);
    renderCards(data.options);
    setBadge(data.status);
  } catch (err) {
    document.getElementById("cards").innerHTML =
      `<p class="loading">Erro ao carregar a campanha: ${escapeHtml(String(err))}</p>`;
  }
  setupModal();
}

function renderMeta(data) {
  const b = data.briefing || {};
  const partes = [
    data.campaign_id,
    b.area_direito,
    b.formato,
    `objetivo: ${b.objetivo || "-"}`,
  ].filter(Boolean);
  document.getElementById("campaign-meta").textContent = partes.join("  ·  ");
}

function renderCards(options) {
  const container = document.getElementById("cards");
  container.innerHTML = "";
  options.forEach((op) => container.appendChild(buildCard(op)));
}

function buildCard(op) {
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

  // Caption expansível
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

  // Hashtags
  if (op.hashtags && op.hashtags.length) {
    const tags = el("div", "hashtags");
    op.hashtags.forEach((h) => tags.appendChild(textEl("span", "hashtag", `#${h}`)));
    body.appendChild(tags);
  }

  // Ações
  const actions = el("div", "card-actions");

  const approveBtn = textEl("button", "btn btn-approve", "✓ Aprovar este post");
  approveBtn.addEventListener("click", () => approve(op.option_id));
  actions.appendChild(approveBtn);

  const adjustBtn = textEl("button", "btn btn-adjust", "Solicitar ajuste");
  const adjustBox = el("div", "adjust-box hidden");
  const ta = el("textarea");
  ta.placeholder = "Descreva o ajuste desejado…";
  const sendAdjust = textEl("button", "btn btn-adjust", "Enviar pedido de ajuste");
  sendAdjust.addEventListener("click", () => requestAdjustment(op.option_id, ta.value));
  adjustBox.appendChild(ta);
  adjustBox.appendChild(sendAdjust);
  adjustBtn.addEventListener("click", () => adjustBox.classList.toggle("hidden"));
  actions.appendChild(adjustBtn);
  actions.appendChild(adjustBox);

  body.appendChild(actions);
  card.appendChild(body);
  return card;
}

async function approve(optionId) {
  if (!confirm(`Confirmar aprovação da Opção ${optionId}? Ela será exportada para publicação.`)) {
    return;
  }
  try {
    const res = await fetch("/api/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ campaign_id: CAMPAIGN_ID, option_id: optionId }),
    }).then((r) => r.json());
    setBadge("approved");
    showDone(res.option_id);
  } catch (err) {
    alert("Erro ao aprovar: " + err);
  }
}

async function requestAdjustment(optionId, notes) {
  if (!notes.trim()) { alert("Descreva o ajuste antes de enviar."); return; }
  try {
    await fetch("/api/request_adjustment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ campaign_id: CAMPAIGN_ID, option_id: optionId, notes }),
    });
    setBadge("adjustment");
    alert(`Pedido de ajuste registrado para a Opção ${optionId}.`);
  } catch (err) {
    alert("Erro ao registrar ajuste: " + err);
  }
}

function setBadge(status) {
  const badge = document.getElementById("status-badge");
  badge.className = "badge";
  if (status === "approved") {
    badge.classList.add("badge-approved");
    badge.textContent = "Aprovado";
  } else if (status === "adjustment_requested" || status === "adjustment") {
    badge.classList.add("badge-adjustment");
    badge.textContent = "Ajuste solicitado";
  } else {
    badge.classList.add("badge-pending");
    badge.textContent = "Aguardando aprovação";
  }
}

function showDone(optionId) {
  document.getElementById("done-text").textContent =
    `A Opção ${optionId} foi exportada e está pronta para publicação.`;
  document.getElementById("done-overlay").classList.remove("hidden");
}

// ---------- Modal de imagem ----------
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

// ---------- Helpers ----------
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
