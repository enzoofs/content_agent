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
from modules import utils


def _data_uri(path: Path, mime: str = "image/png") -> str:
    """Lê um arquivo e devolve um data URI base64 (para embutir no HTML)."""
    b64 = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _font_data_uri(path: Path) -> str:
    """Data URI woff2 — pra @font-face local (zero dependência de Google Fonts)."""
    return _data_uri(path, mime="font/woff2")


def _build_html(
    copy: dict, image_path: Path, template_name: str, width: int, height: int
) -> str:
    """Carrega o template e substitui as variáveis com os dados do copy."""
    template_text = (settings.TEMPLATES_DIR / template_name).read_text(encoding="utf-8")

    subhead = (copy.get("subheadline") or "").strip()
    subhead_html = (
        f'<p class="subheadline">{escape(subhead)}</p>' if subhead else ""
    )

    mapping = {
        "width": width,
        "height": height,
        "gold": settings.COLORS["gold"],
        "navy": settings.COLORS["navy"],
        "navy_dark": settings.COLORS["navy_dark"],
        "background_image": _data_uri(image_path),
        "logo": _data_uri(settings.LOGO_PATH),
        "font_montserrat_400": _font_data_uri(settings.FONT_FILES["montserrat_400"]),
        "font_montserrat_600": _font_data_uri(settings.FONT_FILES["montserrat_600"]),
        "font_playfair_700": _font_data_uri(settings.FONT_FILES["playfair_700"]),
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
    template_name: str,
    output_path: Path,
    width: int,
    height: int,
) -> Path:
    """
    Compõe um único post final (abre um Chromium dedicado).

    Args:
        copy: uma variação de copy.
        image_path: imagem de fundo correspondente.
        template_name: arquivo em templates/ (ex: "post_square.html").
        output_path: onde salvar o PNG final.
        width, height: dimensões do post.

    Returns:
        Path do PNG gerado.
    """
    html = _build_html(copy, image_path, template_name, width, height)
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
    width, height = settings.POST_SIZES[formato]
    template_name = settings.TEMPLATE_BY_FORMAT[formato]
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
                    html = _build_html(copy_slide, img, template_name, width, height)
                    _render_with_browser(browser, html, destino, width, height)
                    paths.append(destino)
            else:
                img = images_dir / f"option_{n}.png"
                if not img.exists():
                    raise FileNotFoundError(f"Imagem de fundo ausente: {img}")
                destino = out_dir / f"option_{n}.png"
                html = _build_html(copy_option, img, template_name, width, height)
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
    width, height = settings.POST_SIZES[formato]
    template_name = settings.TEMPLATE_BY_FORMAT[formato]
    out_dir = utils.campaign_composed_dir(campaign_id)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=_CHROMIUM_ARGS)
        try:
            if formato == "carousel":
                return _compose_carousel(
                    copy_options, image_paths, briefing,
                    browser, template_name, width, height, out_dir, campaign_id,
                )
            return _compose_simples(
                copy_options, image_paths, briefing,
                browser, template_name, width, height, out_dir, campaign_id,
            )
        finally:
            browser.close()


def _compose_simples(
    copy_options, image_paths, briefing,
    browser, template_name, width, height, out_dir, campaign_id,
) -> list[Path]:
    """square/portrait: 1 PNG por opção."""
    composed: list[Path] = []
    for copy, image_path in zip(copy_options, image_paths):
        n = copy["option_id"]
        destino = out_dir / f"option_{n}.png"
        html = _build_html(copy, image_path, template_name, width, height)
        destino.parent.mkdir(parents=True, exist_ok=True)
        _render_with_browser(browser, html, destino, width, height)
        utils.log(campaign_id, f"composer: opção {n} composta -> {destino.name}")
        composed.append(destino)
    return composed


def _compose_carousel(
    copy_options, image_paths, briefing,
    browser, template_name, width, height, out_dir, campaign_id,
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
            html = _build_html(copy_slide, image_path, template_name, width, height)
            destino.parent.mkdir(parents=True, exist_ok=True)
            _render_with_browser(browser, html, destino, width, height)
            utils.log(campaign_id, f"composer: opção {n} slide {m} -> {destino.name}")
            slides_paths.append(destino)
        todas.append(slides_paths)
    return todas
