"""
Render rápido de preview do template M&V com a nova logo no topo central.
Não toca no DB nem na central — só gera um PNG num caminho temp e imprime.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import settings  # noqa: E402
from modules import composer  # noqa: E402


BG = ROOT / "campaigns" / "2026-05-28_direito-medico-3" / "images" / "option_1.png"
OUT_DIR = ROOT / "exports" / "_preview_logo"
OUT_DIR.mkdir(parents=True, exist_ok=True)

COPY = {
    "headline": "Garantindo seu direito a medicamentos essenciais",
    "subheadline": "Direito à saúde",
    "body": (
        "Sua saúde não pode esperar. Conheça a segurança jurídica do respaldo "
        "legal — atendimento humano e técnico."
    ),
    "cta": "Fale conosco",
}

for formato in ("square", "portrait"):
    w, h = settings.POST_SIZES[formato]
    tpl = settings.TEMPLATE_BY_FORMAT[formato]
    out = OUT_DIR / f"preview_{formato}.png"
    composer.compose(COPY, BG, tpl, out, w, h)
    print(f"OK  {formato}: {out}")
