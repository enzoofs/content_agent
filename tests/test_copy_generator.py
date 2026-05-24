"""Testes de modules/copy_generator.py — sem chamar a OpenAI."""

from __future__ import annotations

from modules import copy_generator as cg


def _briefing():
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


def test_user_message_sem_nota_nao_tem_ajuste():
    msg = cg._build_user_message(_briefing())
    assert "AJUSTE" not in msg
    assert "Direito Médico" in msg


def test_user_message_com_nota_inclui_ajuste():
    msg = cg._build_user_message(_briefing(), "deixe o tom mais acessível")
    assert "AJUSTE SOLICITADO" in msg
    assert "deixe o tom mais acessível" in msg


def test_normalize_hashtags():
    out = cg.normalize_hashtags(["#Direito Médico", "clínicasBH", "#Direito Médico", "", 5])
    assert out == ["direitomedico", "clinicasbh"]


def test_parse_valida_contagem():
    bom = '{"options":[' + ",".join(
        '{"option_id":%d,"headline":"h","subheadline":"s","body":"b","caption":"c",'
        '"cta":"x","hashtags":["direito"],"image_prompt":"p","style_notes":"n"}' % i
        for i in (1, 2, 3)
    ) + "]}"
    ops = cg._parse_and_validate(bom)
    assert [o["option_id"] for o in ops] == [1, 2, 3]


# --------------------------------------------------------------------------
# Carrossel — schema aninhado (3 opções × N slides)
# --------------------------------------------------------------------------
def _briefing_carousel(num_slides=4):
    return {
        "area_direito": "Direito Médico",
        "perfil_cliente_ideal": "clínicas em BH",
        "tom": "tecnico",
        "objetivo": "posicionamento",
        "tema_especifico": "prontuário",
        "formato": "carousel",
        "num_slides": num_slides,
        "referencias": "",
    }


def test_user_message_carousel_inclui_num_slides():
    msg = cg._build_user_message_carousel(_briefing_carousel(5))
    assert "5 slides" in msg
    assert "Direito Médico" in msg


def test_parse_carousel_valida_e_normaliza_slides():
    n = 3
    payload = {
        "options": [
            {
                "option_id": i,
                "caption": "legenda completa",
                "cta": "Saiba mais",
                "hashtags": ["#Direito Médico", "clinicasbh"],
                "style_notes": "tom institucional",
                "slides": [
                    {
                        "slide_id": j,
                        "headline": f"h{j}",
                        "subheadline": "",
                        "body": f"b{j}",
                        "image_prompt": "p",
                    }
                    for j in range(1, n + 1)
                ],
            }
            for i in (1, 2, 3)
        ]
    }
    import json as _json
    ops = cg._parse_and_validate_carousel(_json.dumps(payload), num_slides=n)
    assert [o["option_id"] for o in ops] == [1, 2, 3]
    for op in ops:
        assert [s["slide_id"] for s in op["slides"]] == [1, 2, 3]
        # hashtags devem ter sido normalizadas (sem #, sem espaço)
        assert "direitomedico" in op["hashtags"]


def test_parse_carousel_rejeita_quantidade_errada_de_slides():
    payload = {
        "options": [
            {
                "option_id": i,
                "caption": "c", "cta": "x", "hashtags": [], "style_notes": "n",
                "slides": [
                    {"slide_id": 1, "headline": "h", "subheadline": "",
                     "body": "b", "image_prompt": "p"},
                ],  # só 1 slide quando deveria ter 3
            }
            for i in (1, 2, 3)
        ]
    }
    import json as _json
    import pytest
    with pytest.raises(ValueError, match="esperado 3 slides"):
        cg._parse_and_validate_carousel(_json.dumps(payload), num_slides=3)
