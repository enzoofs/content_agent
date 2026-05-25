"""
config/brands/ — Configurações por cliente (brand config).

Cada cliente é um módulo Python aqui dentro que define identidade visual,
prompts de IA e textos específicos. O brand ativo é escolhido pela env var
`BRAND` (default: "mendes_vaz") e injetado em `settings.py`.

Como adicionar um novo brand:
1. Criar `config/brands/<slug>.py` exportando `BRAND = Brand(...)`.
2. Rodar com `BRAND=<slug> python main.py --serve`.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Brand:
    """Configuração visual e textual de um cliente (imutável)."""

    # Identificação
    nome: str                      # "Mendes & Vaz" — exibido na UI
    slug: str                      # "mendes_vaz" — ID interno e nome do módulo

    # Identidade visual
    colors: dict[str, str]         # {"navy": "#272D4D", ...}
    fonts: dict[str, str]          # {"heading": "Playfair Display", ...}
    font_files: dict[str, Path]    # {"montserrat_400": Path(...), ...}
    logo_path: Path

    # Geração de imagem (Ideogram)
    image_prompt_suffix: str       # Sufixo anexado ao image_prompt vindo do LLM
    ideogram_negative_prompt: str  # Negative prompt fixo do Ideogram

    # Exportação
    approved_by: str               # Nome de quem aprova (vai no metadata)

    # Prompts do LLM (copy generator) — Fase B.2
    # System prompt usado em posts simples (square / portrait / story) e em
    # carrossel (variante com slides). Cada brand define seu tom, identidade
    # e regras específicas (advocacia vs DJ vs ...).
    system_prompt: str
    system_prompt_carousel: str


def load(slug: str) -> Brand:
    """
    Carrega o brand pelo slug. Lança ModuleNotFoundError se não existir.

    Args:
        slug: nome do módulo em config/brands/ (ex: "mendes_vaz", "gui_raw").

    Returns:
        Instância de Brand definida no módulo (atributo BRAND).
    """
    modulo = importlib.import_module(f"config.brands.{slug}")
    return modulo.BRAND
