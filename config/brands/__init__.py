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
    enum_values: tuple[str, ...] = ()         # apenas pra kind="enum" — valores enviados ao backend
    enum_labels: tuple[str, ...] = ()         # rótulos visíveis (mesmo índice de enum_values); vazio = usa values como labels
    max_chars: int | None = None              # cap pra kind in ("text","textarea")
    min_int: int | None = None                # bound pra kind="int"
    max_int: int | None = None                # bound pra kind="int"
    rows: int = 2                             # linhas pra kind="textarea"
    default: str = ""                         # valor inicial (pra enum: deve estar em enum_values)
    placeholder: str = ""                     # placeholder na UI
    help: str = ""                            # tooltip/descrição na UI


@dataclass(frozen=True)
class FontOption:
    """
    Uma variante de tipografia selecionável pelo operador no form de nova
    campanha (B.4 — autonomia de fonte). Cada brand define sua própria lista
    curada em `Brand.font_options` — o operador escolhe entre elas, nunca
    digita uma fonte livre.
    """

    id: str                  # chave enviada no briefing (ex.: "classico")
    label: str                # rótulo visível na UI (ex.: "Clássico")
    heading_family: str       # nome CSS da família do headline
    heading_weight: int       # peso do headline (400/600/700...)
    heading_file: Path        # .woff2 do headline
    body_family: str          # nome CSS da família do corpo/subhead/cta
    body_400_file: Path       # .woff2 peso regular do corpo
    body_600_file: Path       # .woff2 peso semibold do corpo


@dataclass(frozen=True)
class LayoutOption:
    """
    Uma variante de LAYOUT (posição de elementos, não só tipografia)
    selecionável pelo operador no form de nova campanha. Cada id precisa
    ter um template correspondente em `templates/<id>/<formato>.html` pra
    cada formato suportado — ver `settings.template_path`. Primeiro item
    da tupla de `Brand.layout_options` é o default.
    """

    id: str            # chave enviada no briefing (ex.: "cartao")
    label: str         # rótulo visível na UI (ex.: "Cartão central")
    description: str = ""  # frase curta explicando o estilo, exibida no card


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

    # --- A partir daqui, campos com default (Python exige essa ordem) ---

    # Tema visual da UI da central (Fase B.1.2)
    # "light" = paleta clara (cream/navy do M&V), "dark" = paleta escura
    # (preto/branco do Gui). Controla overrides de --ink-X, --line-X etc
    # injetados pelo server pra que labels/placeholders fiquem legíveis.
    theme: str = "light"

    # Logo do header da central:
    # True  → renderiza <img src=brand.logo_path> no header
    # False → omite a imagem e exibe só o nome do brand grande (typographic)
    # Usado quando o brand não tem PNG próprio (Gui Raw, por exemplo).
    use_image_logo: bool = True

    # URL Google Fonts adicional pra carregar no <head> da central. Vazio = só
    # carrega Playfair+Montserrat (fontes do M&V). Quando o brand define fontes
    # display próprias (ex.: Unbounded pro Gui), seta a URL aqui.
    google_fonts_url: str = ""

    # CSS font-family que sobrescreve heading/body da central quando o brand
    # quer trocar a tipografia (vazio = mantém defaults M&V).
    # Ex.: ui_heading_font="'Unbounded', sans-serif".
    ui_heading_font: str = ""
    ui_body_font: str = ""

    # Briefing schema e formatadores de user message — Fase B.3.1
    # `briefing_fields` é a fonte da verdade do schema (parser valida contra
    # ele; UI renderiza form contra ele). `slug_fields` lista os nomes de
    # campos cujos valores (em ordem de prioridade) viram o slug do
    # campaign_id (primeiro não-vazio ganha).
    # `build_user_message` formata o briefing em texto pro LLM (varia por
    # brand porque os campos são diferentes).
    briefing_fields: tuple[BriefingField, ...] = ()
    slug_fields: tuple[str, ...] = ()

    # Variantes de fonte selecionáveis (B.4). Vazio = brand ainda não migrou
    # pra seleção de fonte — composer cai pro font_files fixo (retrocompat).
    # Primeiro item da tupla é o default.
    font_options: tuple[FontOption, ...] = ()

    # Variantes de LAYOUT selecionáveis (posição de headline/logo/CTA, não
    # só tipografia). Vazio = brand ainda não migrou; composer cai pro
    # layout fixo "gradiente" (retrocompat). Primeiro item é o default.
    layout_options: tuple[LayoutOption, ...] = ()
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
