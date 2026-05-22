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
