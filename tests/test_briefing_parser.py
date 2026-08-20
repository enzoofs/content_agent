"""Testes de modules/briefing_parser.py — validação e cap de input."""

from __future__ import annotations

import pytest

from modules import briefing_parser as bp


def _briefing_minimo():
    return {
        "area_direito": "Direito Médico",
        "perfil_cliente_ideal": "clínicas em BH",
        "tom": "tecnico",
        "objetivo": "posicionamento",
        "tema_especifico": "prontuário",
        "formato": "square",
        "num_slides": 1,
        "referencias": "",
    }


def test_parse_briefing_valido_retorna_dict_completo():
    out = bp.parse(_briefing_minimo())
    assert out["area_direito"] == "Direito Médico"
    assert out["formato"] == "square"
    assert out["num_slides"] == 1
    assert "campaign_id" in out
    assert "created_at" in out


def test_parse_rejeita_tom_invalido():
    b = _briefing_minimo()
    b["tom"] = "informal"
    with pytest.raises(ValueError, match="tom"):
        bp.parse(b)


def test_parse_rejeita_area_vazia():
    b = _briefing_minimo()
    b["area_direito"] = "   "
    with pytest.raises(ValueError, match="area_direito"):
        bp.parse(b)


def test_parse_carousel_valida_num_slides():
    b = _briefing_minimo()
    b["formato"] = "carousel"
    b["num_slides"] = 10  # fora do intervalo 3-8
    with pytest.raises(ValueError, match="num_slides"):
        bp.parse(b)


# --------------------------------------------------------------------------
# Cap de caracteres (Fix B do roadmap)
# --------------------------------------------------------------------------
def test_cap_area_direito_excedido():
    b = _briefing_minimo()
    b["area_direito"] = "x" * (bp.MAX_CHARS["area_direito"] + 1)
    with pytest.raises(ValueError, match="area_direito.*limite"):
        bp.parse(b)


def test_cap_referencias_excedido():
    b = _briefing_minimo()
    b["referencias"] = "x" * (bp.MAX_CHARS["referencias"] + 1)
    with pytest.raises(ValueError, match="referencias.*limite"):
        bp.parse(b)


def test_cap_perfil_cliente_no_limite_passa():
    """Exatamente no limite deve passar (cap é estrito > limite, não >=)."""
    b = _briefing_minimo()
    b["perfil_cliente_ideal"] = "x" * bp.MAX_CHARS["perfil_cliente_ideal"]
    out = bp.parse(b)
    assert len(out["perfil_cliente_ideal"]) == bp.MAX_CHARS["perfil_cliente_ideal"]


# --------------------------------------------------------------------------
# Fonte (B.4): font_variant / font_size
# --------------------------------------------------------------------------
def test_font_size_default_eh_m_quando_ausente():
    out = bp.parse(_briefing_minimo())
    assert out["font_size"] == "M"


def test_font_size_aceita_p_m_g():
    for tamanho in ("P", "M", "G"):
        b = _briefing_minimo()
        b["font_size"] = tamanho
        out = bp.parse(b)
        assert out["font_size"] == tamanho


def test_font_size_normaliza_minusculo():
    b = _briefing_minimo()
    b["font_size"] = "g"
    out = bp.parse(b)
    assert out["font_size"] == "G"


def test_font_size_rejeita_valor_invalido():
    b = _briefing_minimo()
    b["font_size"] = "XL"
    with pytest.raises(ValueError, match="font_size"):
        bp.parse(b)


def test_font_variant_aceita_string_livre_sem_validar_enum():
    """Parser é brand-agnóstico — não conhece as FontOption do brand ativo,
    então aceita qualquer id; a resolução segura acontece no composer."""
    b = _briefing_minimo()
    b["font_variant"] = "qualquer_coisa"
    out = bp.parse(b)
    assert out["font_variant"] == "qualquer_coisa"


def test_font_variant_default_vazio_quando_ausente():
    out = bp.parse(_briefing_minimo())
    assert out["font_variant"] == ""


# --------------------------------------------------------------------------
# Layout visual
# --------------------------------------------------------------------------
def test_layout_aceita_string_livre_sem_validar_enum():
    """Parser é brand-agnóstico — não conhece as LayoutOption do brand ativo,
    então aceita qualquer id; a resolução segura acontece no composer."""
    b = _briefing_minimo()
    b["layout"] = "cartao"
    out = bp.parse(b)
    assert out["layout"] == "cartao"


def test_layout_default_vazio_quando_ausente():
    out = bp.parse(_briefing_minimo())
    assert out["layout"] == ""


# --------------------------------------------------------------------------
# Upload multi-foto de carrossel
# --------------------------------------------------------------------------
def test_upload_filenames_normaliza_lista_e_ordem():
    b = _briefing_minimo()
    b["upload_filenames"] = ["upload_slide_1.png", " upload_slide_2.png ", ""]
    out = bp.parse(b)
    assert out["upload_filenames"] == ["upload_slide_1.png", "upload_slide_2.png"]


def test_upload_filenames_default_lista_vazia():
    out = bp.parse(_briefing_minimo())
    assert out["upload_filenames"] == []


def test_upload_filenames_ignora_valor_nao_lista():
    b = _briefing_minimo()
    b["upload_filenames"] = "nao_eh_lista.png"
    out = bp.parse(b)
    assert out["upload_filenames"] == []
