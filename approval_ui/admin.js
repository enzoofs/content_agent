// approval_ui/admin.js — Página de admin (stats + cadastro de clientes/usuários).
// Standalone: não carrega app.js, não tem topbar, não é brand-themed.

window.addEventListener("DOMContentLoaded", async () => {
  await carregarStats();
  wireFormNovoCliente();
  wireFormNovoUsuario();
});

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

function mostrarSenhaGerada(elId, email, senha) {
  const el = document.getElementById(elId);
  el.style.display = "block";
  el.innerHTML = `
    <p><strong>${escapeHtml(email)}</strong> criado. Senha temporária (mostrada uma única vez):</p>
    <p><code>${escapeHtml(senha)}</code></p>
    <p style="color: var(--ink-3);">Copie e repasse com segurança — não fica salva em lugar nenhum.</p>
  `;
}

function wireFormNovoCliente() {
  const form = document.getElementById("form-novo-cliente");
  const erro = document.getElementById("erro-novo-cliente");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    erro.style.display = "none";
    document.getElementById("senha-novo-cliente").style.display = "none";
    const fd = new FormData(form);
    // Checkbox só manda o value quando marcado — normaliza pra "true"/"false"
    if (!form.use_image_logo.checked) fd.set("use_image_logo", "false");
    try {
      const data = await fetchJSON("/api/admin/clients", { method: "POST", body: fd });
      mostrarSenhaGerada("senha-novo-cliente", data.email, data.senha_temporaria);
      form.reset();
      await carregarStats();
    } catch (err) {
      erro.textContent = err.message;
      erro.style.display = "block";
    }
  });
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
