"""
Testes de modules/brands_store.py — CRUD de brands criados via admin.

Isolamento de DB vem do fixture autouse em conftest.py.
"""

from __future__ import annotations

import sqlite3

import pytest

from modules import brands_store


def _colors():
    return {"navy": "#111111", "gold": "#EEEEEE", "white": "#FFFFFF",
            "cream": "#DDDDDD", "navy_dark": "#000000"}


def test_criar_brand_grava_e_devolve_colors_como_dict():
    b = brands_store.criar_brand("teste_brand", "Teste Brand", _colors())
    assert b["slug"] == "teste_brand"
    assert b["nome"] == "Teste Brand"
    assert b["colors_json"]  # ainda serializado no dict cru do DB
    assert b["use_image_logo"] == 1
    assert b["theme"] == "light"


def test_criar_brand_com_campos_opcionais():
    b = brands_store.criar_brand(
        "teste_completo", "Teste Completo", _colors(),
        logo_filename="logo_teste_completo.png", use_image_logo=True,
        theme="dark", google_fonts_url="https://fonts.example",
        ui_heading_font="'Anton', sans-serif", ui_body_font="'Space Grotesk', sans-serif",
        image_prompt_suffix="suffix", ideogram_negative_prompt="negative",
        approved_by="Fulano", system_prompt="prompt", system_prompt_carousel="prompt carousel",
    )
    assert b["logo_filename"] == "logo_teste_completo.png"
    assert b["theme"] == "dark"
    assert b["approved_by"] == "Fulano"
    assert b["system_prompt_carousel"] == "prompt carousel"


def test_get_by_slug_inexistente():
    assert brands_store.get_by_slug("nao_existe") is None


def test_slug_duplicado_falha():
    brands_store.criar_brand("dup", "Dup", _colors())
    with pytest.raises(sqlite3.IntegrityError):
        brands_store.criar_brand("dup", "Dup 2", _colors())


def test_list_brands_ordem_alfabetica():
    brands_store.criar_brand("zeta_brand", "Zeta", _colors())
    brands_store.criar_brand("alfa_brand", "Alfa", _colors())
    nomes = [b["nome"] for b in brands_store.list_brands()]
    assert nomes == ["Alfa", "Zeta"]


def test_delete_brand():
    brands_store.criar_brand("apagar", "Apagar", _colors())
    assert brands_store.delete_brand("apagar") is True
    assert brands_store.get_by_slug("apagar") is None
    assert brands_store.delete_brand("apagar") is False
