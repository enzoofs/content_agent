// approval_ui/signup.js — Solicitação pública de cadastro (sem login).
// Standalone: não carrega app.js, sem topbar, sem tema de brand.

window.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("signup-form");
  const erro = document.getElementById("signup-erro");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    erro.style.display = "none";

    const fd = new FormData(form);
    // Só manda use_image_logo=true se um arquivo de fato foi escolhido.
    const logoInput = form.querySelector('input[name="logo"]');
    if (logoInput && logoInput.files.length > 0) {
      fd.set("use_image_logo", "true");
    }

    const res = await fetch("/api/signup-requests", { method: "POST", body: fd });
    if (res.ok) {
      document.getElementById("signup-form-wrap").style.display = "none";
      document.getElementById("signup-ok").style.display = "block";
    } else {
      const data = await res.json().catch(() => ({}));
      erro.textContent = data.erro || "Não foi possível enviar sua solicitação.";
      erro.style.display = "block";
    }
  });
});
