// approval_ui/admin.js — Página de admin (stats + cadastro de clientes/usuários).
// Standalone: não carrega app.js, não tem topbar, não é brand-themed.

window.addEventListener("DOMContentLoaded", async () => {
  await carregarStats();
  await carregarSolicitacoes();
  wireFormNovoUsuario();
  wireSair();
});

function wireSair() {
  document.getElementById("btn-sair-admin").addEventListener("click", async () => {
    await fetch("/logout", { method: "POST" });
    location.href = "/login";
  });
}

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (res.status === 401) {
    location.href = "/login";
    throw new Error("sessão expirada");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.erro || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

let STATS = null;

async function carregarStats() {
  try {
    STATS = await fetchJSON("/api/admin/stats");
  } catch (e) {
    document.getElementById("brand-stats").innerHTML = `<p class="loading">Erro: ${escapeHtml(e.message)}</p>`;
    return;
  }
  renderBrandStats(STATS.brands);
  renderUsersTable(STATS.usuarios);
  popularSelectBrand(STATS.brands.map(b => b.slug));
}

function renderBrandStats(brands) {
  const el = document.getElementById("brand-stats");
  if (!brands.length) {
    el.innerHTML = `<p class="loading">Nenhum brand ainda.</p>`;
    return;
  }
  el.innerHTML = brands.map(b => {
    const quotaRows = b.quota.itens.map(item => `
      <div class="quota-row ${item.nivel}">
        <span>${escapeHtml(item.rotulo)}</span>
        <span>${item.atual}/${item.limite}</span>
      </div>
    `).join("");
    return `
      <div class="brand-stats-card">
        <h3>${escapeHtml(b.slug)}</h3>
        ${quotaRows}
        <div class="brand-tokens">Tokens usados: <strong>${formatTokens(b.tokens_used)}</strong></div>
      </div>
    `;
  }).join("");
}

function formatTokens(n) {
  n = Number(n) || 0;
  if (n < 1000) return String(n);
  return (n / 1000).toFixed(1).replace(".", ",") + "k";
}

function renderUsersTable(usuarios) {
  const el = document.getElementById("users-table");
  if (!usuarios.length) {
    el.innerHTML = `<p class="loading">Nenhum usuário ainda.</p>`;
    return;
  }
  const linhas = usuarios.map(u => `
    <tr>
      <td>${escapeHtml(u.email)}</td>
      <td>${escapeHtml(u.role)}</td>
      <td>${escapeHtml(u.brand_slug || "—")}</td>
      <td>${escapeHtml(u.created_at)}</td>
    </tr>
  `).join("");
  el.innerHTML = `
    <table class="admin-table">
      <thead><tr><th>Email</th><th>Role</th><th>Brand</th><th>Criado em</th></tr></thead>
      <tbody>${linhas}</tbody>
    </table>
  `;
}

function popularSelectBrand(slugs) {
  const select = document.getElementById("novo-usuario-brand");
  select.innerHTML = slugs.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
}

function mostrarSenhaGerada(elOuId, email, senha) {
  const el = typeof elOuId === "string" ? document.getElementById(elOuId) : elOuId;
  el.style.display = "block";
  el.innerHTML = `
    <p><strong>${escapeHtml(email)}</strong> criado. Senha temporária (mostrada uma única vez):</p>
    <p><code>${escapeHtml(senha)}</code></p>
    <p style="color: var(--ink-3);">Copie e repasse com segurança — não fica salva em lugar nenhum.</p>
  `;
}

// ---------- Solicitações de cadastro (fluxo público /signup + revisão) ----------
async function carregarSolicitacoes() {
  const el = document.getElementById("signup-requests-list");
  let solicitacoes;
  try {
    solicitacoes = await fetchJSON("/api/admin/signup-requests");
  } catch (e) {
    el.innerHTML = `<p class="loading">Erro: ${escapeHtml(e.message)}</p>`;
    return;
  }
  if (!solicitacoes.length) {
    el.innerHTML = `<p class="loading">Nenhuma solicitação ainda.</p>`;
    return;
  }
  el.innerHTML = "";
  solicitacoes.forEach(s => el.appendChild(renderSolicitacaoItem(s)));
}

function renderSolicitacaoItem(s) {
  const details = document.createElement("details");
  details.className = "signup-request-item";
  details.dataset.status = s.status;

  const summary = document.createElement("summary");
  summary.innerHTML = `
    <span><strong>${escapeHtml(s.nome)}</strong> — ${escapeHtml(s.email)}</span>
    <span>${escapeHtml(s.status)} · ${escapeHtml(s.created_at)}</span>
  `;
  details.appendChild(summary);

  const tpl = document.getElementById("tpl-review-form");
  const form = tpl.content.firstElementChild.cloneNode(true);

  // Pré-preenche com o que veio na solicitação — admin completa o resto.
  const colors = JSON.parse(s.colors_json);
  form.nome.value = s.nome;
  form.slug.value = s.slug_sugerido || "";
  form.email.value = s.email;
  form.theme.value = s.theme;
  form.use_image_logo.checked = !!s.use_image_logo;
  form.navy.value = colors.navy || "#272D4D";
  form.gold.value = colors.gold || "#E3B644";
  form.white.value = colors.white || "#FFFFFF";
  form.cream.value = colors.cream || "#F5F0E8";
  form.navy_dark.value = colors.navy_dark || "#1A2038";
  form.sobre_negocio.value = s.sobre_negocio || "";
  form.google_fonts_url.value = s.google_fonts_url || "";
  form.ui_heading_font.value = s.ui_heading_font || "";
  form.ui_body_font.value = s.ui_body_font || "";
  form.image_prompt_suffix.value = s.image_prompt_suffix || "";
  form.ideogram_negative_prompt.value = s.ideogram_negative_prompt || "";
  form.approved_by.value = s.approved_by || "";
  form.system_prompt.value = s.system_prompt || "";
  form.system_prompt_carousel.value = s.system_prompt_carousel || "";
  if (s.motivo_rejeicao) form.motivo_rejeicao.value = s.motivo_rejeicao;

  const erro = form.querySelector(".admin-erro");
  const senhaBox = form.querySelector(".senha-gerada");

  if (s.status !== "pendente") {
    form.querySelectorAll("input, select, textarea, button").forEach(el => { el.disabled = true; });
  } else {
    form.querySelector(".review-aprovar").addEventListener("click", async () => {
      erro.style.display = "none";
      try {
        const data = await fetchJSON(`/api/admin/signup-requests/${s.id}/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(camposRevisaoParaJSON(form)),
        });
        mostrarSenhaGerada(senhaBox, data.email, data.senha_temporaria);
        await carregarStats();
      } catch (e) {
        erro.textContent = e.message;
        erro.style.display = "block";
      }
    });

    form.querySelector(".review-rejeitar").addEventListener("click", async () => {
      erro.style.display = "none";
      try {
        await fetchJSON(`/api/admin/signup-requests/${s.id}/reject`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ motivo: form.motivo_rejeicao.value }),
        });
        await carregarSolicitacoes();
      } catch (e) {
        erro.textContent = e.message;
        erro.style.display = "block";
      }
    });
  }

  details.appendChild(form);
  return details;
}

function camposRevisaoParaJSON(form) {
  const campos = [
    "nome", "slug", "email", "theme", "navy", "gold", "white", "cream", "navy_dark",
    "google_fonts_url", "ui_heading_font", "ui_body_font", "image_prompt_suffix",
    "ideogram_negative_prompt", "approved_by", "system_prompt", "system_prompt_carousel",
  ];
  const body = {};
  campos.forEach(c => { body[c] = form[c].value; });
  body.use_image_logo = form.use_image_logo.checked ? "true" : "false";
  return body;
}

function wireFormNovoUsuario() {
  const form = document.getElementById("form-novo-usuario");
  const erro = document.getElementById("erro-novo-usuario");
  const roleSelect = document.getElementById("novo-usuario-role");
  const brandLabel = document.getElementById("novo-usuario-brand-label");

  roleSelect.addEventListener("change", () => {
    brandLabel.style.display = roleSelect.value === "admin" ? "none" : "block";
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    erro.style.display = "none";
    document.getElementById("senha-novo-usuario").style.display = "none";
    const body = {
      email: form.email.value,
      role: roleSelect.value,
      brand_slug: form.brand_slug.value,
    };
    try {
      const data = await fetchJSON("/api/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      mostrarSenhaGerada("senha-novo-usuario", data.email, data.senha_temporaria);
      form.reset();
      await carregarStats();
    } catch (err) {
      erro.textContent = err.message;
      erro.style.display = "block";
    }
  });
}
