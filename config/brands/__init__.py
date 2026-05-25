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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class BriefingField:
    """
    Descritor declarativo de um campo do briefing — usado tanto pelo parser
    (validação) quanto pela UI (renderização do form dinâmico em B.3.3).

    `kind` define o tipo de input. Valores aceitos:
        - "text":     input de uma linha
        - "textarea": input multilinha
        - "enum":     select com opções em `enum_values`
        - "int":      input numérico (validado contra min_int/max_int)
        - "date":     input de data ISO (YYYY-MM-DD)
    """

    name: str                                 # chave no dict do briefing (ex: "area_direito")
    label: str                                # rótulo visível na UI ("Área do direito")
    kind: str                                 # "text" | "textarea" | "enum" | "int" | "date"
    required: bool = True
    enum_values: tuple[str, ...] = ()         # apenas pra kind="enum"
    max_chars: int | None = None              # cap pra kind in ("text","textarea")
    min_int: int | None = None                # bound pra kind="int"
    max_int: int | None = None                # bound pra kind="int"
    placeholder: str = ""                     # placeholder na UI
    help: str = ""                            # tooltip/descrição na UI


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

    # Briefing schema e formatadores de user message — Fase B.3.1
    # `briefing_fields` é a fonte da verdade do schema (parser valida contra
    # ele; UI renderiza form contra ele). `slug_fields` lista os nomes de
    # campos cujos valores (em ordem de prioridade) viram o slug do
    # campaign_id (primeiro não-vazio ganha).
    # `build_user_message` formata o briefing em texto pro LLM (varia por
    # brand porque os campos são diferentes).
    briefing_fields: tuple[BriefingField, ...] = ()
    slug_fields: tuple[str, ...] = ()
    build_user_message: Callable[[dict, str], str] = field(default=lambda b, n="": "")
    build_user_message_carousel: Callable[[dict, str], str] = field(default=lambda b, n="": "")


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
