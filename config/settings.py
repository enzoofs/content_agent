"""
config/settings.py — Configurações centralizadas do sistema Mendes & Vaz Social.

Regra de ouro do projeto: NENHUM valor de configuração é hardcoded em outros
módulos. Tudo (dimensões, cores, fontes, caminhos, chaves de API, modelo) vive
aqui. Os demais módulos importam deste arquivo.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega o .env (se existir) para dentro de os.environ
load_dotenv()

# --------------------------------------------------------------------------
# Caminhos base
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent

ASSETS_DIR = BASE_DIR / "assets"
TEMPLATES_DIR = BASE_DIR / "templates"
CAMPAIGNS_DIR = BASE_DIR / "campaigns"
EXPORTS_DIR = BASE_DIR / "exports"
APPROVAL_UI_DIR = BASE_DIR / "approval_ui"

LOGO_PATH = ASSETS_DIR / "logo_mendes_vaz.png"

# --------------------------------------------------------------------------
# Dimensões de posts (px) — Fase 1
# --------------------------------------------------------------------------
POST_SIZES = {
    "square": (1080, 1080),      # Feed Instagram, LinkedIn
    "portrait": (1080, 1350),    # Feed Instagram (maior alcance)
    "carousel": (1080, 1080),    # Slides de carrossel
}

# Mapeia formato -> template HTML usado pelo composer
TEMPLATE_BY_FORMAT = {
    "square": "post_square.html",
    "portrait": "post_portrait.html",
    "carousel": "carousel_slide.html",
}

# --------------------------------------------------------------------------
# Identidade visual — paleta exata Mendes & Vaz (NUNCA desviar)
# --------------------------------------------------------------------------
COLORS = {
    "navy": "#272D4D",       # dominante, fundos principais
    "gold": "#E3B644",       # destaque, títulos, elementos gráficos
    "white": "#FFFFFF",      # texto sobre navy
    "cream": "#F5F0E8",      # fundos claros
    "navy_dark": "#1A2038",  # overlays, gradientes
}

# Tipografia para posts (Google Fonts) — não usar Inter/Roboto/Arial/Helvetica
FONTS = {
    "heading": "Playfair Display",
    "subhead": "Montserrat",
    "body": "Montserrat",
}

# --------------------------------------------------------------------------
# Geração de copy — OpenAI (substitui a Claude API nesta fase)
# --------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o"        # configurável; troca-se aqui sem tocar nos módulos
COPY_MAX_TOKENS = 2000

# Quantas variações de copy geramos por campanha
NUM_COPY_OPTIONS = 3

# --------------------------------------------------------------------------
# Geração de arte — Ideogram
# --------------------------------------------------------------------------
IDEOGRAM_API_KEY = os.getenv("IDEOGRAM_API_KEY")
IDEOGRAM_URL = "https://api.ideogram.ai/generate"

# Mock de imagens: usado quando NÃO há chave Ideogram, ou quando forçado.
# Padrão: usar Ideogram real se houver chave. Defina USE_MOCK_IMAGES=true no
# .env para forçar placeholders mesmo tendo a chave (debug/economia).
USE_MOCK_IMAGES = (
    os.getenv("USE_MOCK_IMAGES", "false").lower() == "true"
    or not IDEOGRAM_API_KEY
)

IDEOGRAM_CONFIG = {
    "model": "V_2",
    "style_type": "REALISTIC",
    "negative_prompt": (
        "text, words, letters, watermark, logo, signature, "
        "scales of justice, gavel, hammer, cartoon, illustration, "
        "vibrant colors, neon, grunge, ugly, deformed, blurry, "
        "low quality, amateur"
    ),
    "color_palette": {
        # A API do Ideogram usa a chave "color_hex" (não "color").
        "members": [
            {"color_hex": "#272D4D", "color_weight": 0.5},
            {"color_hex": "#E3B644", "color_weight": 0.25},
            {"color_hex": "#F5F0E8", "color_weight": 0.25},
        ]
    },
}

# Resolução da Ideogram por formato de post
IDEOGRAM_RESOLUTIONS = {
    "square": "RESOLUTION_1024_1024",
    "portrait": "RESOLUTION_1024_1280",
    "carousel": "RESOLUTION_1024_1024",
}

# Sufixo anexado ao image_prompt para reforçar a estética do cliente
IMAGE_PROMPT_SUFFIX = (
    "elegant law firm atmosphere, navy blue and gold tones, professional, "
    "sophisticated, cinematic lighting, high-end interior, no text"
)

# --------------------------------------------------------------------------
# Servidor de aprovação (Flask local)
# --------------------------------------------------------------------------
APPROVAL_HOST = "localhost"
APPROVAL_PORT = 5000

# Nome de quem aprova (vai para os metadados de export)
APPROVED_BY = "Henrique Mendes"
