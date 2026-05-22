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
        "headline": escape(copy["headline"]),
        "subheadline_html": subhead_html,
        "body_text": escape(copy["body"]),
        "cta_text": escape(copy["cta"]),
    }
    # safe_substitute: ignora $ órfãos no CSS e não quebra se faltar chave
    return Template(template_text).safe_substitute(mapping)


def render_html_to_png(html: str, output_path: Path, width: int, height: int) -> None:
    """Renderiza HTML -> PNG via Playwright (chromium headless), 1:1 em pixels."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=1,
        )
        page.set_content(html, wait_until="networkidle")
        page.screenshot(path=str(output_path), full_page=False, type="png")
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
    Compõe um único post final.

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


def compose_all(
    copy_options: list[dict],
    image_paths: list[Path],
    briefing: dict,
) -> list[Path]:
    """
    Compõe todas as variações de uma campanha.

    Returns:
        Lista de paths em campaigns/{campaign_id}/composed/option_{n}.png.
    """
    campaign_id = briefing["campaign_id"]
    formato = briefing["formato"]
    width, height = settings.POST_SIZES[formato]
    template_name = settings.TEMPLATE_BY_FORMAT[formato]
    out_dir = utils.campaign_composed_dir(campaign_id)

    composed: list[Path] = []
    for copy, image_path in zip(copy_options, image_paths):
        n = copy["option_id"]
        destino = out_dir / f"option_{n}.png"
        compose(copy, image_path, template_name, destino, width, height)
        utils.log(campaign_id, f"composer: opção {n} composta -> {destino.name}")
        composed.append(destino)

    return composed
