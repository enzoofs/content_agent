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
import json
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
    build_user_message: Callable[[dict, str], str] = field(default=lambda b, n="": "")
    build_user_message_carousel: Callable[[dict, str], str] = field(default=lambda b, n="": "")


# Brands existentes como arquivo .py — tupla explícita (só 2 hoje, não vale
# a abstração de escanear o filesystem). Brands criados pela tela de admin
# vivem no banco (modules/brands_store.py) — ver list_available_brands().
AVAILABLE_BRANDS = ("mendes_vaz", "gui_raw")

# fonts/font_files compartilhados por TODO brand criado via admin — hoje nem
# mendes_vaz nem gui_raw têm infra real de upload de fonte por cliente (os
# dois usam literalmente os mesmos 3 arquivos), então não vale construir essa
# abstração antes de precisar de verdade. Valores idênticos aos hardcoded em
# config/brands/mendes_vaz.py.
_BASE_DIR = Path(__file__).parent.parent.parent
_FONTS_DIR = _BASE_DIR / "assets" / "fonts"
_SHARED_FONTS = {"heading": "Playfair Display", "subhead": "Montserrat", "body": "Montserrat"}
_SHARED_FONT_FILES = {
    "montserrat_400": _FONTS_DIR / "montserrat-400.woff2",
    "montserrat_600": _FONTS_DIR / "montserrat-600.woff2",
    "playfair_700": _FONTS_DIR / "playfair-display-700.woff2",
}


def load(slug: str) -> Brand:
    """
    Carrega o brand pelo slug.

    Primeiro tenta um módulo .py em config/brands/<slug>.py (mendes_vaz,
    gui_raw). Se não existir, cai pro banco (brands criados via tela de
    admin). Lança ModuleNotFoundError se não existir em nenhum dos dois.

    Args:
        slug: "mendes_vaz", "gui_raw", ou slug de um brand criado via admin.

    Returns:
        Instância de Brand.
    """
    try:
        modulo = importlib.import_module(f"config.brands.{slug}")
        return modulo.BRAND
    except ModuleNotFoundError:
        return _load_from_db(slug)


def _load_from_db(slug: str) -> Brand:
    """
    Constrói um Brand a partir de uma row da tabela `brands` (SQLite).

    Import de modules.brands_store/config.settings é TARDIO (dentro da
    função, não no topo do módulo) de propósito: config/settings.py importa
    config.brands ANTES de terminar de definir STATE_DB_PATH. Se um slug
    só-DB fosse resolvido durante o `brands.load(BRAND_NAME)` de bootstrap
    (settings.py, no import), settings.STATE_DB_PATH ainda não existiria no
    módulo parcialmente inicializado -> AttributeError. Isso só aconteceria
    se a env var BRAND apontasse pra um slug só-DB (fluxo terminal/
    --campaign) — o fluxo web real (server.py:_resolve_brand, resolvido por
    request, bem depois do boot completo) nunca bate nesse caso. Limitação
    aceita: brands criados via admin só funcionam pelo login web.
    """
    from modules import brands_store
    from config import settings

    row = brands_store.get_by_slug(slug)
    if row is None:
        raise ModuleNotFoundError(f"Brand {slug!r} não encontrado (nem .py, nem banco).")

    logo_filename = row["logo_filename"]
    use_image_logo = bool(row["use_image_logo"]) and logo_filename is not None
    logo_path = (
        settings.ASSETS_DIR / logo_filename if logo_filename
        else settings.ASSETS_DIR / "logo_mendes_vaz.png"  # nunca renderizada (use_image_logo=False)
    )

    return Brand(
        nome=row["nome"],
        slug=row["slug"],
        colors=json.loads(row["colors_json"]),
        fonts=_SHARED_FONTS,
        font_files=_SHARED_FONT_FILES,
        logo_path=logo_path,
        image_prompt_suffix=row["image_prompt_suffix"],
        ideogram_negative_prompt=row["ideogram_negative_prompt"],
        approved_by=row["approved_by"],
        system_prompt=row["system_prompt"],
        system_prompt_carousel=row["system_prompt_carousel"],
        theme=row["theme"],
        use_image_logo=use_image_logo,
        google_fonts_url=row["google_fonts_url"],
        ui_heading_font=row["ui_heading_font"],
        ui_body_font=row["ui_body_font"],
        # briefing_fields fica () de propósito: cai no fallback
        # _DEFAULT_BRIEFING_FIELDS de server.py, igual o mendes_vaz hoje.
    )


def list_available_brands() -> tuple[str, ...]:
    """AVAILABLE_BRANDS (arquivo .py) + slugs de brands criados via admin (banco)."""
    from modules import brands_store
    return AVAILABLE_BRANDS + tuple(b["slug"] for b in brands_store.list_brands())
