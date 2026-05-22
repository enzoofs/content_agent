"""Testes de modules/campaign_store.py — estado em state.json (sem APIs)."""

from __future__ import annotations

import shutil

import pytest

from config import settings
from modules import campaign_store as cs

CID = "2099-01-01_teste-store"


def _briefing():
    return {
        "campaign_id": CID,
        "created_at": "2099-01-01T00:00:00",
        "area_direito": "Direito Médico",
        "perfil_cliente_ideal": "clínicas",
        "tom": "tecnico",
        "objetivo": "posicionamento",
        "tema_especifico": "teste",
        "formato": "square",
        "num_slides": 1,
        "referencias": "",
    }


def _cleanup():
    shutil.rmtree(settings.CAMPAIGNS_DIR / CID, ignore_errors=True)


def teardown_function():
    _cleanup()


def test_criar_grava_state_e_briefing():
    estado = cs.criar(_briefing())
    assert estado["status"] == "gerando"
    assert estado["etapa"] == "copy"
    assert cs.state_path(CID).exists()
    assert (settings.CAMPAIGNS_DIR / CID / "briefing.json").exists()


def test_write_state_faz_merge():
    cs.criar(_briefing())
    cs.write_state(CID, foo="bar")
    estado = cs.read_state(CID)
    assert estado["foo"] == "bar"
    assert estado["status"] == "gerando"  # campo anterior preservado
    assert "atualizado_em" in estado


def test_set_etapa_e_erro():
    cs.criar(_briefing())
    cs.set_etapa(CID, "arte")
    assert cs.read_state(CID)["etapa"] == "arte"
    cs.set_erro(CID, "falhou x")
    estado = cs.read_state(CID)
    assert estado["status"] == "erro"
    assert estado["erro"] == "falhou x"


def test_marcar_aprovada():
    cs.criar(_briefing())
    cs.marcar_aprovada(CID, 2, "2099-02-01")
    estado = cs.read_state(CID)
    assert estado["status"] == "aprovada"
    assert estado["option_aprovada"] == 2
    assert estado["data_agendada"] == "2099-02-01"


def test_agendar_rejeita_data_passada():
    cs.criar(_briefing())
    with pytest.raises(ValueError):
        cs.agendar(CID, "2000-01-01")


def test_agendar_aceita_data_futura():
    cs.criar(_briefing())
    cs.agendar(CID, "2099-12-31")
    assert cs.read_state(CID)["data_agendada"] == "2099-12-31"


def test_listar_inclui_campanha_criada():
    cs.criar(_briefing())
    ids = [c["campaign_id"] for c in cs.listar()]
    assert CID in ids


def test_read_state_inexistente_retorna_none():
    assert cs.read_state("nao-existe-xyz") is None
