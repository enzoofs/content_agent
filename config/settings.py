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
FONTS_DIR = ASSETS_DIR / "fonts"

# --------------------------------------------------------------------------
# Brand atual (extraído por cliente em config/brands/ — Fase B.1)
# --------------------------------------------------------------------------
# Cada cliente vira um módulo em config/brands/ exportando `BRAND = Brand(...)`.
# A env var `BRAND` escolhe qual carregar; default = mendes_vaz (cliente piloto).
# Pra rodar como Gui Raw: `BRAND=gui_raw python main.py --serve`.
from config import brands  # noqa: E402 — depende de BASE_DIR/load_dotenv acima

BRAND_NAME = os.getenv("BRAND", "mendes_vaz")
brand = brands.load(BRAND_NAME)

# Atributos do brand re-exportados como constantes módulo-level pra manter
# compatibilidade com todos os módulos que já leem settings.COLORS, etc.
LOGO_PATH = brand.logo_path
FONT_FILES = brand.font_files

# Banco de estado (SQLite). Tudo que era state.json/briefing.json/copy_v*.json
# agora vive aqui; PNGs continuam em campaigns/{id}/ no FS.
STATE_DB_PATH = BASE_DIR / "state.db"

# --------------------------------------------------------------------------
# Dimensões de posts (px) — Fase 1
# --------------------------------------------------------------------------
POST_SIZES = {
    "square": (1080, 1080),      # Feed Instagram, LinkedIn
    "portrait": (1080, 1350),    # Feed Instagram (maior alcance)
    "carousel": (1080, 1080),    # Slides de carrossel
    "story": (1080, 1920),       # Stories Instagram (9:16, full-screen)
}

# Mapeia formato -> template HTML usado pelo composer
TEMPLATE_BY_FORMAT = {
    "square": "post_square.html",
    "portrait": "post_portrait.html",
    "carousel": "carousel_slide.html",
    "story": "story.html",
}

# --------------------------------------------------------------------------
# Identidade visual — vem do brand atual (config/brands/<slug>.py)
# --------------------------------------------------------------------------
COLORS = brand.colors
FONTS = brand.fonts

# --------------------------------------------------------------------------
# Geração de copy — OpenAI (substitui a Claude API nesta fase)
# --------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o"        # configurável; troca-se aqui sem tocar nos módulos
COPY_MAX_TOKENS = 2000

# Quantas variações de copy geramos por campanha
NUM_COPY_OPTIONS = 3

# Temperature da chamada de geração de copy. Default OpenAI é 1.0; subimos
# pra 0.95 + instrução explícita no prompt pra cada opção ter ÂNGULO distinto
# (vs. as 3 saídas serem variações cosméticas do mesmo texto).
OPENAI_COPY_TEMPERATURE = 0.95

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
    # Negative prompt vem do brand (varia por cliente — Mendes & Vaz tira
    # clichês jurídicos / luxo; Gui Raw tira clichê de stock photo, etc).
    "negative_prompt": brand.ideogram_negative_prompt,
    # color_palette REMOVIDO de propósito: forçava paleta do brand em toda
    # imagem, deixando o feed monocromático (efeito Wes Anderson). A identidade
    # visual já é garantida pelo overlay/filete/logo do template — aqui
    # deixamos a arte respirar com cores naturais.
}

# Resolução da Ideogram por formato de post
IDEOGRAM_RESOLUTIONS = {
    "square": "RESOLUTION_1024_1024",
    "portrait": "RESOLUTION_1024_1280",
    "carousel": "RESOLUTION_1024_1024",
    "story": "RESOLUTION_720_1280",   # 9:16 nativo na V_2; composer faz upscale pra 1080x1920
}

# Sufixo anexado ao image_prompt — vem do brand atual. Texto NUNCA na imagem
# (vem renderizado por código no template). Não direcionamos paleta aqui — o
# branding vem do template overlay, então a arte pode ter cores naturais.
IMAGE_PROMPT_SUFFIX = brand.image_prompt_suffix

# --------------------------------------------------------------------------
# Servidor de aprovação (Flask local)
# --------------------------------------------------------------------------
APPROVAL_HOST = "localhost"
APPROVAL_PORT = 5000

# Nome de quem aprova (vai para os metadados de export) — vem do brand atual
APPROVED_BY = brand.approved_by

# --------------------------------------------------------------------------
# Quotas / prevenção de abuse
# --------------------------------------------------------------------------
# Limites globais aplicados antes da fase 2 (multi-tenant). Na fase 2 isso
# vira `PLANOS = {essencial: {...}, profissional: {...}}` indexado por tenant.
#
# Filosofia:
# - "mes": evita cliente queimar API/budget em janela curta
# - "agendadas_futuro": evita criar pro ano todo no 1º mês e abandonar
# - "pendentes_aprovacao": força fechar ciclo antes de abrir novo
# - "regeracoes_por_campanha": cap em revisão infinita (cada regera custa $)
QUOTAS = {
    "campanhas_mes":            30,   # criações no mês corrente
    "agendadas_futuro":         20,   # com data_agendada > hoje
    "pendentes_aprovacao":      10,   # status em (gerando, ajuste_solicitado, aguardando_aprovacao)
    "regeracoes_por_campanha":   5,   # copy_version máxima permitida
}

# Soft warning quando atingir esse % da quota (UI fica amarela)
QUOTA_WARN_THRESHOLD = 0.7
