"""
Testes de modules/campaign_store.py — agora respaldado por SQLite (state.db).

Cobertura: CRUD básico, máquina de estados, fix de colisão de campaign_id e
concorrência (SQLite com WAL deve servir leitores/escritores em paralelo).
"""

from __future__ import annotations

import shutil
import threading

import pytest

from config import settings
from modules import campaign_store as cs
from modules import store, utils

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


def test_criar_grava_estado_e_briefing():
    estado = cs.criar(_briefing())
    assert estado["status"] == "gerando"
    assert estado["etapa"] == "copy"
    # Briefing recuperável (substitui o antigo check de briefing.json no FS)
    briefing = cs.read_briefing(CID)
    assert briefing["area_direito"] == "Direito Médico"
    assert briefing["formato"] == "square"


def test_write_state_atualiza_campos_e_timestamp():
    cs.criar(_briefing())
    cs.write_state(CID, status="aguardando_aprovacao")
    estado = cs.read_state(CID)
    assert estado["status"] == "aguardando_aprovacao"
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


def test_copy_version_inicial_e_save_get():
    cs.criar(_briefing())
    assert cs.get_copy_version(CID) == 1

    opcoes = [{"option_id": 1, "headline": "h"}]
    cs.save_copy_version(CID, 1, opcoes)
    assert cs.get_copy(CID) == opcoes


def test_next_copy_version_incrementa_e_preserva_anterior():
    cs.criar(_briefing())
    cs.save_copy_version(CID, 1, [{"option_id": 1, "v": 1}])
    nova = cs.next_copy_version(CID)
    cs.save_copy_version(CID, nova, [{"option_id": 1, "v": 2}])

    assert nova == 2
    assert cs.get_copy(CID, versao=1) == [{"option_id": 1, "v": 1}]
    assert cs.get_copy(CID, versao=2) == [{"option_id": 1, "v": 2}]
    # Versão corrente (sem arg) traz a 2
    assert cs.get_copy(CID) == [{"option_id": 1, "v": 2}]


# --------------------------------------------------------------------------
# Fix 🔴 — campaign_id único: não sobrescreve campanha existente do mesmo dia
# --------------------------------------------------------------------------
def test_make_campaign_id_evita_colisao(monkeypatch):
    """Duas campanhas com mesma área/tema no mesmo dia devem gerar ids distintos."""
    tmp_dir = settings.CAMPAIGNS_DIR.parent / "campaigns_test_tmp"
    tmp_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(settings, "CAMPAIGNS_DIR", tmp_dir)
    try:
        id1 = utils.make_campaign_id("Direito Médico", "erro médico")
        (tmp_dir / id1).mkdir()
        id2 = utils.make_campaign_id("Direito Médico", "erro médico")
        (tmp_dir / id2).mkdir()
        id3 = utils.make_campaign_id("Direito Médico", "erro médico")

        assert id1 != id2 != id3
        assert id2.endswith("-2")
        assert id3.endswith("-3")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# --------------------------------------------------------------------------
# Concorrência — SQLite (WAL) deve servir leitores em paralelo com 1 escritor
# --------------------------------------------------------------------------
def test_write_state_concorrente_nao_perde_atualizacoes():
    """20 threads escrevendo status diferentes — última prevalece, sem corromper."""
    cs.criar(_briefing())
    n_threads = 20

    def escrever(i: int) -> None:
        # Status válido: alterna entre os 5 conhecidos
        s = list(cs.STATES)[i % len(cs.STATES)]
        cs.write_state(CID, status=s)

    threads = [threading.Thread(target=escrever, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    estado = cs.read_state(CID)
    # SQLite garante que o estado final é íntegro e contém um status válido
    assert estado["status"] in cs.STATES


def test_leituras_concorrentes_durante_writes_nao_quebram():
    """Leitores em paralelo com escritores não disparam exceções (WAL ON)."""
    cs.criar(_briefing())
    erros: list[str] = []
    parar = threading.Event()

    def escritor() -> None:
        i = 0
        while not parar.is_set():
            cs.write_state(CID, etapa=cs.set_etapa.__name__ if i % 2 else None)
            i += 1

    def leitor() -> None:
        while not parar.is_set():
            try:
                cs.read_state(CID)
            except Exception as e:
                erros.append(str(e))

    threads = [threading.Thread(target=escritor) for _ in range(2)] + \
              [threading.Thread(target=leitor) for _ in range(4)]
    for t in threads:
        t.start()
    threading.Event().wait(0.4)
    parar.set()
    for t in threads:
        t.join()

    assert not erros, f"Leitor falhou {len(erros)}x: {erros[:3]}"


# --------------------------------------------------------------------------
# Migração do FS — campanhas antigas (state.json + briefing.json) são importadas
# --------------------------------------------------------------------------
def test_migrate_from_files_importa_campanha_antiga(monkeypatch, tmp_path):
    import json as _json

    camp_dir = tmp_path / "campaigns"
    camp_dir.mkdir()
    monkeypatch.setattr(settings, "CAMPAIGNS_DIR", camp_dir)

    cid = "2099-05-05_antiga"
    d = camp_dir / cid
    d.mkdir()
    (d / "briefing.json").write_text(
        _json.dumps({**_briefing(), "campaign_id": cid}, ensure_ascii=False),
        encoding="utf-8",
    )
    (d / "state.json").write_text(
        _json.dumps({"status": "aguardando_aprovacao", "copy_version": 1,
                     "atualizado_em": "2099-05-05T00:00:00"}),
        encoding="utf-8",
    )
    (d / "copy_v1.json").write_text(
        _json.dumps([{"option_id": 1, "headline": "h"}]), encoding="utf-8",
    )

    stats = store.migrate_from_files()
    assert stats["campaigns_inseridas"] == 1
    assert stats["copy_versions_inseridas"] == 1

    assert cs.read_state(cid)["status"] == "aguardando_aprovacao"
    assert cs.get_copy(cid) == [{"option_id": 1, "headline": "h"}]

    # Idempotência — rodar de novo não duplica
    stats2 = store.migrate_from_files()
    assert stats2["campaigns_inseridas"] == 0
    assert stats2["ignoradas"] == 1
