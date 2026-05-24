"""
Testes de modules/pipeline.py — orquestração e estado.

Mocka copy_generator, image_generator e composer (sem APIs nem Playwright);
foca na máquina de estados e no encadeamento das etapas.
"""

from __future__ import annotations

import shutil

import pytest

from config import settings
from modules import briefing_parser, campaign_store, pipeline

CID = "2099-01-01_teste-pipeline"


def _briefing():
    return briefing_parser.parse({
        "campaign_id": CID,
        "area_direito": "Direito Médico",
        "perfil_cliente_ideal": "clínicas",
        "tom": "tecnico",
        "objetivo": "posicionamento",
        "tema_especifico": "prontuario",
        "formato": "square",
        "num_slides": 1,
        "referencias": "",
    })


def teardown_function():
    shutil.rmtree(settings.CAMPAIGNS_DIR / CID, ignore_errors=True)


def test_gerar_passa_pelas_etapas_e_termina_aguardando(monkeypatch):
    etapas_vistas = []
    monkeypatch.setattr(
        campaign_store, "set_etapa",
        lambda cid, etapa: etapas_vistas.append(etapa),
    )
    monkeypatch.setattr(pipeline.copy_generator, "generate", lambda b, nota="", versao=1: [{"option_id": 1}])
    monkeypatch.setattr(pipeline.image_generator, "generate", lambda ops, fmt, cid: ["img"])
    monkeypatch.setattr(
        pipeline.composer, "compose_all",
        lambda ops, imgs, b: [settings.CAMPAIGNS_DIR / CID / "composed" / "option_1.png"],
    )

    briefing = _briefing()
    campaign_store.criar(briefing)
    composed = pipeline.gerar(briefing)

    assert etapas_vistas == ["copy", "arte", "composicao"]
    assert len(composed) == 1
    assert campaign_store.read_state(CID)["status"] == "aguardando_aprovacao"


def test_gerar_falha_marca_erro_e_relanca(monkeypatch):
    def boom(b, nota="", versao=1):
        raise RuntimeError("falha na copy")
    monkeypatch.setattr(pipeline.copy_generator, "generate", boom)

    briefing = _briefing()
    campaign_store.criar(briefing)
    with pytest.raises(RuntimeError, match="falha na copy"):
        pipeline.gerar(briefing)

    estado = campaign_store.read_state(CID)
    assert estado["status"] == "erro"
    assert "falha na copy" in estado["erro"]


# --------------------------------------------------------------------------
# Versionamento de copy (Fix C do roadmap) — regerar não sobrescreve
# --------------------------------------------------------------------------
def test_regerar_bumpa_versao_e_preserva_copy_anterior(monkeypatch):
    """regerar() incrementa copy_version e a versão antiga continua no disco."""
    versoes_recebidas: list[int] = []

    def fake_generate(briefing, nota="", versao=1):
        versoes_recebidas.append(versao)
        return [{"option_id": 1, "nota": nota, "versao": versao}]

    monkeypatch.setattr(pipeline.copy_generator, "generate", fake_generate)
    monkeypatch.setattr(pipeline.image_generator, "generate", lambda ops, fmt, cid: ["img"])
    monkeypatch.setattr(pipeline.composer, "compose_all", lambda ops, imgs, b: [])

    briefing = _briefing()
    campaign_store.criar(briefing)

    # 1ª geração — versão 1
    pipeline.gerar(briefing)
    assert campaign_store.get_copy_version(CID) == 1
    assert versoes_recebidas == [1]

    # Regerar — deve ir pra versão 2
    pipeline.regerar(CID, nota="mais técnico")
    assert campaign_store.get_copy_version(CID) == 2
    assert versoes_recebidas == [1, 2]
