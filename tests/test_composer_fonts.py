"""
tests/test_composer_fonts.py — Resolução de fonte/tamanho no composer (B.4).

Testa a lógica de _resolve_font_option/_resolve_headline_size e a
substituição de placeholders em _build_html, sem precisar do Playwright
(_build_html só monta a string HTML — o render fica pro
test_templates_visual.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

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
    # _build_html só lê bytes do arquivo (_data_uri) — não precisa ser um PNG válido.
    p = tmp_path / "bg.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n")
    return p


# --------------------------------------------------------------------------
# _resolve_font_option
# --------------------------------------------------------------------------
def test_resolve_font_option_default_quando_variant_ausente():
    opt = composer._resolve_font_option({})
    assert opt == settings.brand.font_options[0]


def test_resolve_font_option_encontra_por_id():
    esperado = settings.brand.font_options[1]  # "elegante" no M&V
    opt = composer._resolve_font_option({"font_variant": esperado.id})
    assert opt.id == esperado.id


def test_resolve_font_option_fallback_pro_default_quando_id_invalido():
    opt = composer._resolve_font_option({"font_variant": "id_que_nao_existe"})
    assert opt == settings.brand.font_options[0]


# --------------------------------------------------------------------------
# _resolve_headline_size
# --------------------------------------------------------------------------
def test_resolve_headline_size_escala_por_p_m_g():
    base = composer._HEADLINE_BASE_SIZE["square"]
    assert composer._resolve_headline_size("square", "M") == base
    assert composer._resolve_headline_size("square", "P") < base
    assert composer._resolve_headline_size("square", "G") > base


def test_resolve_headline_size_cai_pro_m_quando_invalido():
    assert composer._resolve_headline_size("square", "XL") == (
        composer._resolve_headline_size("square", "M")
    )


# --------------------------------------------------------------------------
# _build_html — substituição de placeholders
# --------------------------------------------------------------------------
def test_build_html_substitui_placeholders_de_fonte(tmp_path):
    opt = settings.brand.font_options[1]  # "elegante"
    tpl = settings.template_path("square", settings.DEFAULT_LAYOUT)
    html = composer._build_html(
        _copy_padrao(), _bg(tmp_path), tpl, "square", 1080, 1080,
        font_option=opt, font_size="G",
    )
    assert opt.heading_family in html
    assert opt.body_family in html
    assert "$font_heading_family" not in html
    assert "$font_body_family" not in html
    assert "$headline_size" not in html


def test_build_html_usa_default_quando_font_option_none(tmp_path):
    tpl = settings.template_path("square", settings.DEFAULT_LAYOUT)
    html = composer._build_html(
        _copy_padrao(), _bg(tmp_path), tpl, "square", 1080, 1080,
    )
    default = composer._default_font_option()
    assert default.heading_family in html
