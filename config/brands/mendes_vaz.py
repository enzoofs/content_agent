"""
config/brands/mendes_vaz.py — Brand do escritório Mendes & Vaz.

Cliente piloto da plataforma (BH/MG, advocacia civil/médica/empresarial).
Identidade visual: navy + gold + Playfair Display (heading) + Montserrat
(corpo). Logo é o brasão oficial do escritório.

Estes valores eram hardcoded em config/settings.py até a extração de brands
(Fase B.1).
"""

from pathlib import Path

from config.brands import Brand

_BASE_DIR = Path(__file__).parent.parent.parent
_ASSETS = _BASE_DIR / "assets"
_FONTS = _ASSETS / "fonts"

BRAND = Brand(
    nome="Mendes & Vaz",
    slug="mendes_vaz",

    colors={
        "navy": "#272D4D",       # dominante, fundos principais
        "gold": "#E3B644",       # destaque, títulos, elementos gráficos
        "white": "#FFFFFF",      # texto sobre navy
        "cream": "#F5F0E8",      # fundos claros
        "navy_dark": "#1A2038",  # overlays, gradientes
    },

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

    logo_path=_ASSETS / "logo_mendes_vaz.png",

    # Estética DELIBERADAMENTE acessível — escritório pequeno/médio BR,
    # classe média, profissional sem ser luxuoso. Texto NUNCA na imagem
    # (a copy é renderizada por código no template HTML/CSS).
    image_prompt_suffix=(
        "small to medium-sized law firm, modest professional office, "
        "Brazilian middle-class environment, accessible, realistic, "
        "natural lighting, "
        "1 person (or at most 2), diverse representation, "
        "professional but simple, not luxurious, no text"
    ),

    # Negative prompt tira clichês jurídicos + estética luxuosa + cenas com
    # muita gente / mãos em close (Ideogram erra essas geometrias).
    ideogram_negative_prompt=(
        "text, words, letters, watermark, logo, signature, "
        "scales of justice, gavel, hammer, cartoon, illustration, "
        "vibrant colors, neon, grunge, ugly, deformed, blurry, "
        "low quality, amateur, "
        "luxurious, opulent, marble, gold leaf, palace, mansion, "
        "expensive interior, chandelier, ornate, "
        "crowd, group of people, many people, multiple hands, "
        "close-up of hands, complex interactions, handshake closeup"
    ),

    approved_by="Henrique Mendes",
)
