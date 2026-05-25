"""
config/brands/gui_raw.py — Brand do DJ Gui Raw (@gui.raw_).

Produtor, DJ, fotógrafo e videomaker. Range estilístico amplo: toca de
casamento/formatura até festival de psytrance. A identidade visual base é
minimalista (preto/branco) e a cor de destaque vai variar por vibe do evento
(campo `vibe_musical` do briefing, implementado em B.3).

NOTAS DE PLACEHOLDER (B.1):
- Fontes Anton + JetBrains Mono ainda não foram baixadas. Usando
  Playfair/Montserrat do M&V como placeholder. Trocar em B.2.
- Logo é typographic (renderizado por CSS no template em B.3). Por ora
  reutiliza o arquivo do M&V só pra não quebrar o composer.
"""

from pathlib import Path

from config.brands import Brand

_BASE_DIR = Path(__file__).parent.parent.parent
_ASSETS = _BASE_DIR / "assets"
_FONTS = _ASSETS / "fonts"

BRAND = Brand(
    nome="Gui Raw",
    slug="gui_raw",

    # Paleta base preto/branco. As chaves seguem o contrato do template M&V
    # (navy/gold/white/cream/navy_dark) — o "navy" vira preto profundo e o
    # "gold" vira branco. A cor de destaque dinâmica por vibe entra em B.3
    # quando os templates passarem a ler do briefing.
    colors={
        "navy": "#0A0A0A",       # preto profundo (papel de fundo dominante)
        "gold": "#FAFAFA",       # branco (papel de destaque)
        "white": "#FAFAFA",      # texto sobre preto
        "cream": "#1A1A1A",      # off-black (fundos "claros" invertidos)
        "navy_dark": "#000000",  # preto puro (overlays)
    },

    # TODO B.2: Anton (heading impactante) + JetBrains Mono (mono pra detalhes).
    # Placeholder com fontes do M&V só pra abstração funcionar.
    fonts={
        "heading": "Playfair Display",
        "subhead": "Montserrat",
        "body": "Montserrat",
    },
    font_files={
        "montserrat_400": _FONTS / "montserrat-400.woff2",
        "montserrat_600": _FONTS / "montserrat-600.woff2",
        "playfair_700": _FONTS / "playfair-display-700.woff2",
    },

    # TODO B.3: substituir por logo typographic via CSS (sem PNG).
    logo_path=_ASSETS / "logo_mendes_vaz.png",

    # Fotografia de evento (DJ booth, iluminação cinematográfica, contexto
    # de nightlife BR). Sem palácios, sem clichê de "festa de luxo".
    image_prompt_suffix=(
        "professional event photography, cinematic lighting, "
        "Brazilian nightlife or celebration context, authentic atmosphere, "
        "DJ booth or lighting equipment when relevant, "
        "crowd silhouettes when appropriate, "
        "no text, no readable signage"
    ),

    ideogram_negative_prompt=(
        "text, words, letters, watermark, logo, signature, "
        "cartoon, illustration, blurry, low quality, amateur, "
        "deformed faces, distorted hands, "
        "stock photo aesthetic, clipart, generic event photo, "
        "scales of justice, gavel"
    ),

    approved_by="Gui Raw",
)
