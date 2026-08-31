"""
modules/composer.py — Composição final: arte + texto -> PNG via Playwright.

Recebe uma variação de copy e a imagem de fundo correspondente, preenche o
template HTML e renderiza para PNG. O texto é SEMPRE renderizado por código
(nunca por IA), garantindo tipografia perfeita e zero erro de digitação.

Detalhes de implementação:
- A imagem de fundo e o logo são embutidos como data URIs (base64) no HTML.
  Isso evita problemas de caminho file:// no Windows e torna o HTML autocontido.
- A substituição usa string.Template ($var), seguro contra '{'/'}' no copy.
- As fontes (Playfair Display, Montserrat) vêm do Google Fonts via @import;
  esperamos networkidle para garantir que carregaram antes do screenshot.
"""

from __future__ import annotations

import base64
from html import escape
from pathlib import Path
from string import Template

from playwright.sync_api import sync_playwright

from config import settings
from config.brands import FontOption, LayoutOption
from modules import utils

# Tamanho base do headline (px) por FORMATO — calibrado visualmente. É uma
# propriedade do formato (dimensão do post), não do layout: todos os
# layouts de um mesmo formato compartilham a mesma base, escalada por
# _FONT_SIZE_SCALES conforme o campo font_size do briefing (P/M/G). Só o
# headline é escalado nesta primeira versão — subheadline/body/cta ficam
# fixos pra reduzir risco de overflow de layout.
_HEADLINE_BASE_SIZE = {
    "square": 52,
    "portrait": 62,
    "carousel": 50,
    "story": 84,
}
_FONT_SIZE_SCALES = {"P": 0.85, "M": 1.0, "G": 1.15}

# Cor da sombra (overlay) sobre a imagem de fundo — pedido do Mendes & Vaz
# (2026-08-31): além do azul (navy_dark do brand) original, uma opção preta.
# Os templates usam `$overlay_rgb` dentro do gradiente de `.overlay`; o
# valor aqui é o triplet "r, g, b" já pronto pra virar `rgba($overlay_rgb, a)`.
_OVERLAY_RGB = {
    "azul": "26, 32, 56",   # = navy_dark (#1A2038) do brand M&V — default/legado
    "preto": "0, 0, 0",
}
_OVERLAY_COLOR_DEFAULT = "azul"


def _resolve_overlay_rgb(overlay_color: str) -> str:
    """Resolve a cor da sombra com fallback pro azul (nunca quebra por id inválido)."""
    return _OVERLAY_RGB.get((overlay_color or "").strip(), _OVERLAY_RGB[_OVERLAY_COLOR_DEFAULT])


def _default_layout_option() -> LayoutOption:
    """Fallback quando o brand ativo não define `layout_options` (legado)."""
    return LayoutOption(id=settings.DEFAULT_LAYOUT, label="Default")


def _resolve_layout_option(briefing: dict) -> LayoutOption:
    """
    Resolve o layout escolhido no briefing (`layout`) contra
    `settings.brand.layout_options`. Cai pro primeiro item (default do
    brand) se o id vier ausente/desconhecido, e pro fallback fixo se o
    brand não definir `layout_options` — nunca quebra o pipeline por causa
    de uma variante inválida (mesmo espírito de `_resolve_font_option`).
    """
    options = settings.brand.layout_options
    if not options:
        return _default_layout_option()
    layout_id = (briefing.get("layout") or "").strip()
    for opt in options:
        if opt.id == layout_id:
            return opt
    return options[0]


def _default_font_option() -> FontOption:
    """
    Fallback quando o brand ativo não define `font_options` (legado,
    pré-B.4): monta uma FontOption a partir dos 3 arquivos fixos de
    `settings.FONT_FILES`, preservando o visual original.
    """
    return FontOption(
        id="default",
        label="Default",
        heading_family="Playfair Display",
        heading_weight=700,
        heading_file=settings.FONT_FILES["playfair_700"],
        body_family="Montserrat",
        body_400_file=settings.FONT_FILES["montserrat_400"],
        body_600_file=settings.FONT_FILES["montserrat_600"],
    )


def _resolve_font_option(briefing: dict) -> FontOption:
    """
    Resolve a variante de fonte escolhida no briefing (`font_variant`) contra
    `settings.brand.font_options`. Cai pro primeiro item (default do brand)
    se o id vier ausente/desconhecido, e pro fallback legado se o brand não
    definir `font_options` — nunca quebra o pipeline por causa de uma
    variante inválida (mesmo espírito do fallback em image_generator).
    """
    options = settings.brand.font_options
    if not options:
        return _default_font_option()
    variant_id = (briefing.get("font_variant") or "").strip()
    for opt in options:
        if opt.id == variant_id:
            return opt
    return options[0]


def _resolve_headline_size(formato: str, font_size: str) -> int:
    """Tamanho do headline (px) pro formato, escalado por P/M/G."""
    base = _HEADLINE_BASE_SIZE.get(formato, 52)
    escala = _FONT_SIZE_SCALES.get((font_size or "M").strip().upper(), 1.0)
    return round(base * escala)


def _data_uri(path: Path, mime: str = "image/png") -> str:
    """Lê um arquivo e devolve um data URI base64 (para embutir no HTML)."""
    b64 = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _font_data_uri(path: Path) -> str:
    """Data URI woff2 — pra @font-face local (zero dependência de Google Fonts)."""
    return _data_uri(path, mime="font/woff2")


def _build_html(
    copy: dict, image_path: Path, template_file: Path, formato: str, width: int, height: int,
    hide_overlay: bool = False,
    font_option: FontOption | None = None,
    font_size: str = "M",
    overlay_color: str = _OVERLAY_COLOR_DEFAULT,
) -> str:
    """Carrega o template e substitui as variáveis com os dados do copy.

    `template_file` é o caminho já resolvido (ver `settings.template_path`),
    e `formato` só é usado pra calibrar o tamanho do headline
    (`_HEADLINE_BASE_SIZE` é por formato, não por layout).

    `hide_overlay=True` remove a sombra (gradiente sobre o fundo) inteira —
    usado quando o operador envia uma foto própria e quer ela visível sem
    filtro. `overlay_color` ("azul" | "preto") escolhe a cor da sombra
    quando ela está visível — ver `_OVERLAY_RGB`.

    `font_option`/`font_size` controlam a tipografia (B.4) — `font_option=None`
    cai pro fallback legado (`_default_font_option`).
    """
    template_text = Path(template_file).read_text(encoding="utf-8")

    subhead = (copy.get("subheadline") or "").strip()
    subhead_html = (
        f'<p class="subheadline">{escape(subhead)}</p>' if subhead else ""
    )

    overlay_html = "" if hide_overlay else '<div class="overlay"></div>'
    font_option = font_option or _default_font_option()

    mapping = {
        "width": width,
        "height": height,
        "gold": settings.COLORS["gold"],
        "navy": settings.COLORS["navy"],
        "navy_dark": settings.COLORS["navy_dark"],
        "background_image": _data_uri(image_path),
        "logo": _data_uri(settings.LOGO_PATH),
        "font_heading_family": font_option.heading_family,
        "font_heading_weight": font_option.heading_weight,
        "font_heading_file": _font_data_uri(font_option.heading_file),
        "font_body_family": font_option.body_family,
        "font_body_400_file": _font_data_uri(font_option.body_400_file),
        "font_body_600_file": _font_data_uri(font_option.body_600_file),
        "headline_size": _resolve_headline_size(formato, font_size),
        "overlay_html": overlay_html,
        "overlay_rgb": _resolve_overlay_rgb(overlay_color),
        "headline": escape(copy["headline"]),
        "subheadline_html": subhead_html,
        "body_text": escape(copy["body"]),
        "cta_text": escape(copy["cta"]),
    }
    # safe_substitute: ignora $ órfãos no CSS e não quebra se faltar chave
    return Template(template_text).safe_substitute(mapping)


_RENDER_TIMEOUT_MS = 15000  # 15s: tempo limite para a página + fontes carregarem.

# Flags pra acelerar o boot do Chromium em ambiente headless de servidor.
# - disable-dev-shm-usage: evita falhar por /dev/shm pequeno em containers
# - disable-gpu: sem GPU em headless, evita inicializar pipeline gráfico
# - disable-background-timer-throttling: contagem de timers consistente
# - no-first-run: não tenta UI de primeira execução
# Pre-warm "real" (manter browser entre chamadas) exige refactor pra worker
# dedicado — fora do escopo do MVP. Ver docs/fase-2-roadmap.md.
_CHROMIUM_ARGS = [
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--no-first-run",
]


def _render_with_browser(browser, html: str, output_path: Path, width: int, height: int) -> None:
    """
    Renderiza HTML -> PNG num browser já aberto (reusado entre slides/opções).

    Timeouts explícitos evitam que set_content fique aguardando networkidle
    infinitamente quando uma fonte/recurso externo demora a responder.
    Em caso de timeout, tomamos o screenshot mesmo assim — fontes locais
    embarcadas como data URI já estão prontas; um @import remoto pendurado
    não deve bloquear o post.
    """
    page = browser.new_page(
        viewport={"width": width, "height": height},
        device_scale_factor=1,
    )
    try:
        try:
            page.set_content(html, wait_until="networkidle", timeout=_RENDER_TIMEOUT_MS)
        except Exception as e:
            # networkidle pode estourar se algum @import remoto travar.
            # Como as fontes principais são embarcadas como data URI, seguimos
            # com o screenshot do que já foi pintado.
            print(f"[composer] networkidle timeout, prosseguindo: {e}", flush=True)
        page.screenshot(path=str(output_path), full_page=False, type="png", timeout=_RENDER_TIMEOUT_MS)
    finally:
        page.close()


def render_html_to_png(html: str, output_path: Path, width: int, height: int) -> None:
    """Renderiza HTML -> PNG via Playwright (abre e fecha um browser dedicado)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(args=_CHROMIUM_ARGS)
        try:
            _render_with_browser(browser, html, output_path, width, height)
        finally:
            browser.close()


def compose(
    copy: dict,
    image_path: Path,
    template_file: Path,
    formato: str,
    output_path: Path,
    width: int,
    height: int,
) -> Path:
    """
    Compõe um único post final (abre um Chromium dedicado).

    Args:
        copy: uma variação de copy.
        image_path: imagem de fundo correspondente.
        template_file: caminho resolvido do template (ver `settings.template_path`).
        formato: "square" | "portrait" | "carousel" | "story" — calibra o headline.
        output_path: onde salvar o PNG final.
        width, height: dimensões do post.

    Returns:
        Path do PNG gerado.
    """
    html = _build_html(copy, image_path, template_file, formato, width, height)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    render_html_to_png(html, output_path, width, height)
    return output_path


def recompose_option(briefing: dict, copy_option: dict) -> list[Path]:
    """
    Recompõe os PNGs de UMA opção reusando as imagens de fundo existentes.

    Usado pela edição manual de copy (não regera arte, só renderiza o template
    com texto novo). Devolve a lista de PNGs gerados (1 para simples, N para
    carrossel).

    Args:
        briefing: briefing da campanha (precisa de formato + campaign_id).
        copy_option: a variação a recompor (com option_id e os campos editados).

    Raises:
        FileNotFoundError: se faltar alguma imagem de fundo (caso recompose
            seja chamado antes da arte ter sido gerada).
    """
    campaign_id = briefing["campaign_id"]
    formato = briefing["formato"]
    hide_overlay = bool(briefing.get("hide_overlay") or 0)
    overlay_color = briefing.get("overlay_color") or _OVERLAY_COLOR_DEFAULT
    font_option = _resolve_font_option(briefing)
    font_size = briefing.get("font_size") or "M"
    layout_option = _resolve_layout_option(briefing)
    width, height = settings.POST_SIZES[formato]
    template_file = settings.template_path(formato, layout_option.id)
    out_dir = utils.campaign_composed_dir(campaign_id)
    images_dir = utils.campaign_images_dir(campaign_id)
    n = copy_option["option_id"]

    paths: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=_CHROMIUM_ARGS)
        try:
            if formato == "carousel":
                cta = copy_option["cta"]
                for slide in copy_option["slides"]:
                    m = slide["slide_id"]
                    img = images_dir / f"option_{n}_slide_{m}.png"
                    if not img.exists():
                        raise FileNotFoundError(f"Imagem de fundo ausente: {img}")
                    destino = out_dir / f"option_{n}_slide_{m}.png"
                    copy_slide = {
                        "headline": slide["headline"],
                        "subheadline": slide.get("subheadline", ""),
                        "body": slide["body"],
                        "cta": cta,
                    }
                    html = _build_html(copy_slide, img, template_file, formato, width, height, hide_overlay=hide_overlay, font_option=font_option, font_size=font_size, overlay_color=overlay_color)  # noqa: E501
                    _render_with_browser(browser, html, destino, width, height)
                    paths.append(destino)
            else:
                img = images_dir / f"option_{n}.png"
                if not img.exists():
                    raise FileNotFoundError(f"Imagem de fundo ausente: {img}")
                destino = out_dir / f"option_{n}.png"
                html = _build_html(copy_option, img, template_file, formato, width, height, hide_overlay=hide_overlay, font_option=font_option, font_size=font_size, overlay_color=overlay_color)  # noqa: E501
                _render_with_browser(browser, html, destino, width, height)
                paths.append(destino)
        finally:
            browser.close()

    utils.log(campaign_id, f"composer: opção {n} recomposta (edição manual) -> {len(paths)} PNG(s)")
    return paths


def compose_all(
    copy_options: list[dict],
    image_paths,  # list[Path] (simples) | list[list[Path]] (carrossel)
    briefing: dict,
):
    """
    Compõe todas as variações de uma campanha — reusa um único Chromium para
    todos os renders (vários slides/opções), economizando ~3x o custo de boot.

    Args:
        copy_options: saída de copy_generator.generate.
        image_paths: saída de image_generator.generate (formato bate com briefing).
        briefing: briefing da campanha.

    Returns:
        - simples: list[Path] (option_{n}.png)
        - carrossel: list[list[Path]] (cada opção com seus N slides em ordem)
    """
    campaign_id = briefing["campaign_id"]
    formato = briefing["formato"]
    hide_overlay = bool(briefing.get("hide_overlay") or 0)
    overlay_color = briefing.get("overlay_color") or _OVERLAY_COLOR_DEFAULT
    font_option = _resolve_font_option(briefing)
    font_size = briefing.get("font_size") or "M"
    layout_option = _resolve_layout_option(briefing)
    width, height = settings.POST_SIZES[formato]
    template_file = settings.template_path(formato, layout_option.id)
    out_dir = utils.campaign_composed_dir(campaign_id)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=_CHROMIUM_ARGS)
        try:
            if formato == "carousel":
                return _compose_carousel(
                    copy_options, image_paths, briefing,
                    browser, template_file, formato, width, height, out_dir, campaign_id,
                    hide_overlay=hide_overlay, font_option=font_option, font_size=font_size, overlay_color=overlay_color,
                )
            return _compose_simples(
                copy_options, image_paths, briefing,
                browser, template_file, formato, width, height, out_dir, campaign_id,
                hide_overlay=hide_overlay, font_option=font_option, font_size=font_size, overlay_color=overlay_color,
            )
        finally:
            browser.close()


def _compose_simples(
    copy_options, image_paths, briefing,
    browser, template_file, formato, width, height, out_dir, campaign_id,
    hide_overlay: bool = False,
    font_option: FontOption | None = None,
    font_size: str = "M",
    overlay_color: str = _OVERLAY_COLOR_DEFAULT,
) -> list[Path]:
    """square/portrait: 1 PNG por opção."""
    composed: list[Path] = []
    for copy, image_path in zip(copy_options, image_paths):
        n = copy["option_id"]
        destino = out_dir / f"option_{n}.png"
        html = _build_html(copy, image_path, template_file, formato, width, height, hide_overlay=hide_overlay, font_option=font_option, font_size=font_size, overlay_color=overlay_color)  # noqa: E501
        destino.parent.mkdir(parents=True, exist_ok=True)
        _render_with_browser(browser, html, destino, width, height)
        utils.log(campaign_id, f"composer: opção {n} composta -> {destino.name}")
        composed.append(destino)
    return composed


def _compose_carousel(
    copy_options, image_paths, briefing,
    browser, template_file, formato, width, height, out_dir, campaign_id,
    hide_overlay: bool = False,
    font_option: FontOption | None = None,
    font_size: str = "M",
    overlay_color: str = _OVERLAY_COLOR_DEFAULT,
) -> list[list[Path]]:
    """carrossel: N PNGs por opção. Cada slide vira um post com headline/body
    próprios; caption/cta/hashtags (no nível da opção) ficam no metadado."""
    todas: list[list[Path]] = []
    for copy, slides_imgs in zip(copy_options, image_paths):
        n = copy["option_id"]
        cta = copy["cta"]
        slides_paths: list[Path] = []
        for slide, image_path in zip(copy["slides"], slides_imgs):
            m = slide["slide_id"]
            destino = out_dir / f"option_{n}_slide_{m}.png"
            # Compose recebe o "copy" no formato do template — adapta slide -> copy plano
            copy_slide = {
                "headline": slide["headline"],
                "subheadline": slide.get("subheadline", ""),
                "body": slide["body"],
                "cta": cta,
            }
            html = _build_html(copy_slide, image_path, template_file, formato, width, height, hide_overlay=hide_overlay, font_option=font_option, font_size=font_size, overlay_color=overlay_color)  # noqa: E501
            destino.parent.mkdir(parents=True, exist_ok=True)
            _render_with_browser(browser, html, destino, width, height)
            utils.log(campaign_id, f"composer: opção {n} slide {m} -> {destino.name}")
            slides_paths.append(destino)
        todas.append(slides_paths)
    return todas
