"""
tests/test_composer_layouts.py — Resolução de layout no composer (seletor
de layout visual). Espelha tests/test_composer_fonts.py.
"""

from __future__ import annotations

from config import settings
from modules import composer


def test_resolve_layout_option_default_quando_ausente():
    opt = composer._resolve_layout_option({})
    assert opt == settings.brand.layout_options[0]


def test_resolve_layout_option_encontra_por_id():
    esperado = settings.brand.layout_options[1]  # "cartao" no M&V
    opt = composer._resolve_layout_option({"layout": esperado.id})
    assert opt.id == esperado.id


def test_resolve_layout_option_fallback_pro_default_quando_id_invalido():
    opt = composer._resolve_layout_option({"layout": "id_que_nao_existe"})
    assert opt == settings.brand.layout_options[0]


def test_template_path_existe_pra_cada_layout_e_formato():
    for layout in settings.brand.layout_options:
        for formato in ("square", "portrait", "carousel", "story"):
            tpl = settings.template_path(formato, layout.id)
            assert tpl.exists(), f"Template ausente: {layout.id}/{formato}.html"


def test_template_path_cai_pro_default_quando_layout_desconhecido():
    esperado = settings.template_path("square", settings.DEFAULT_LAYOUT)
    obtido = settings.template_path("square", "layout_que_nao_existe")
    assert obtido == esperado
