"""
Testes de config/brands/load() — fallback pro banco quando o slug não tem
arquivo .py (brand criado via tela de admin).
"""

from __future__ import annotations

import pytest

from config import brands
from modules import brands_store


def _colors():
    return {"navy": "#111111", "gold": "#EEEEEE", "white": "#FFFFFF",
            "cream": "#DDDDDD", "navy_dark": "#000000"}


def test_load_arquivo_py_continua_funcionando():
    """Brand hardcoded (mendes_vaz) não deve passar pelo fallback do banco."""
    b = brands.load("mendes_vaz")
    assert b.slug == "mendes_vaz"
    assert b.nome == "Mendes & Vaz"


def test_load_slug_inexistente_levanta_erro():
    with pytest.raises(ModuleNotFoundError):
        brands.load("brand-que-nao-existe-em-lugar-nenhum")


def test_load_cai_pro_banco_quando_nao_ha_arquivo_py():
    brands_store.criar_brand(
        "brand_dinamico", "Brand Dinâmico", _colors(),
        theme="dark", use_image_logo=False,
        image_prompt_suffix="suffix dinamico",
        ideogram_negative_prompt="negative dinamico",
        approved_by="Fulano Dinâmico",
        system_prompt="prompt dinamico", system_prompt_carousel="prompt carousel dinamico",
    )
    b = brands.load("brand_dinamico")
    assert b.slug == "brand_dinamico"
    assert b.nome == "Brand Dinâmico"
    assert b.colors == _colors()
    assert b.theme == "dark"
    assert b.use_image_logo is False
    assert b.approved_by == "Fulano Dinâmico"
    assert b.system_prompt == "prompt dinamico"
    # fonts/font_files compartilhados, briefing_fields cai no fallback do server.py
    assert b.fonts["heading"] == "Playfair Display"
    assert b.font_files["montserrat_400"].name == "montserrat-400.woff2"
    assert b.briefing_fields == ()


def test_load_sem_logo_forca_use_image_logo_false():
    """Mesmo se use_image_logo=True foi setado, sem logo_filename vira False."""
    brands_store.criar_brand(
        "sem_logo", "Sem Logo", _colors(), use_image_logo=True, logo_filename=None,
    )
    b = brands.load("sem_logo")
    assert b.use_image_logo is False


def test_list_available_brands_inclui_hardcoded_e_banco():
    brands_store.criar_brand("brand_extra", "Brand Extra", _colors())
    disponiveis = brands.list_available_brands()
    assert "mendes_vaz" in disponiveis
    assert "gui_raw" in disponiveis
    assert "brand_extra" in disponiveis
