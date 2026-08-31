"""
tests/test_composer_overlay_color.py — Cor da sombra (overlay) no composer.

Pedido do Mendes & Vaz (2026-08-31): além do azul (navy_dark) original, uma
opção preta. Testa _resolve_overlay_rgb e a substituição do placeholder
$overlay_rgb em _build_html, sem precisar do Playwright.
"""

from __future__ import annotations

from pathlib import Path

from config import settings
from modules import composer


def _copy_padrao() -> dict:
    return {
        "option_id": 1,
        "headline": "Título de teste",
        "subheadline": "",
        "body": "Corpo de teste",
        "cta": "Saiba mais",
    }


def _bg(tmp_path: Path) -> Path:
    p = tmp_path / "bg.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n")
    return p


def test_resolve_overlay_rgb_default_azul():
    assert composer._resolve_overlay_rgb("") == composer._OVERLAY_RGB["azul"]


def test_resolve_overlay_rgb_preto():
    assert composer._resolve_overlay_rgb("preto") == composer._OVERLAY_RGB["preto"]


def test_resolve_overlay_rgb_fallback_pro_azul_quando_invalido():
    assert composer._resolve_overlay_rgb("verde") == composer._OVERLAY_RGB["azul"]


def test_build_html_substitui_overlay_rgb_preto(tmp_path):
    tpl = settings.template_path("square", settings.DEFAULT_LAYOUT)
    html = composer._build_html(
        _copy_padrao(), _bg(tmp_path), tpl, "square", 1080, 1080,
        overlay_color="preto",
    )
    assert composer._OVERLAY_RGB["preto"] in html
    assert "$overlay_rgb" not in html


def test_build_html_default_overlay_rgb_azul(tmp_path):
    tpl = settings.template_path("square", settings.DEFAULT_LAYOUT)
    html = composer._build_html(
        _copy_padrao(), _bg(tmp_path), tpl, "square", 1080, 1080,
    )
    assert composer._OVERLAY_RGB["azul"] in html
