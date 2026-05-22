"""
Testes da API de modules/server.py via Flask test client.

Mocka a geração assíncrona (sem APIs/threads) e o exporter.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from config import settings
from modules import campaign_store, server

CID = "2099-01-01_teste-server"


@pytest.fixture
def client(monkeypatch):
    # Geração assíncrona vira no-op (não dispara thread/API nos testes)
    monkeypatch.setattr(server, "_iniciar_geracao_async", lambda briefing: None)
    monkeypatch.setattr(server, "_iniciar_regeracao_async", lambda cid, nota: None)
    app = server.build_app()
    app.config.update(TESTING=True)
    yield app.test_client()
    shutil.rmtree(settings.CAMPAIGNS_DIR / CID, ignore_errors=True)
    for f in settings.EXPORTS_DIR.glob(f"{CID}_*"):
        f.unlink(missing_ok=True)


def _briefing_body():
    return {
        "campaign_id": CID,
        "area_direito": "Direito Médico",
        "perfil_cliente_ideal": "clínicas em BH",
        "tom": "tecnico",
        "objetivo": "posicionamento",
        "tema_especifico": "prontuario",
        "formato": "square",
        "num_slides": 1,
        "referencias": "",
    }


def _seed_copy_e_composed():
    """Cria copy_v1.json + 3 PNGs compostos falsos para a campanha CID."""
    camp = settings.CAMPAIGNS_DIR / CID
    (camp / "composed").mkdir(parents=True, exist_ok=True)
    ops = [{
        "option_id": i, "headline": f"h{i}", "subheadline": "s", "body": "b",
        "caption": "c", "cta": "x", "hashtags": ["direito"],
        "image_prompt": "p", "style_notes": "n",
    } for i in (1, 2, 3)]
    (camp / "copy_v1.json").write_text(json.dumps(ops, ensure_ascii=False), encoding="utf-8")
    for i in (1, 2, 3):
        (camp / "composed" / f"option_{i}.png").write_bytes(b"PNG")


def test_criar_campanha(client):
    resp = client.post("/api/campaigns", json=_briefing_body())
    assert resp.status_code == 201
    assert resp.get_json()["campaign_id"] == CID
    assert campaign_store.read_state(CID)["status"] == "gerando"


def test_criar_briefing_invalido_400(client):
    body = _briefing_body()
    body["tom"] = "informal"  # inválido
    resp = client.post("/api/campaigns", json=body)
    assert resp.status_code == 400
    assert "erro" in resp.get_json()


def test_listar_inclui_campanha(client):
    client.post("/api/campaigns", json=_briefing_body())
    ids = [c["campaign_id"] for c in client.get("/api/campaigns").get_json()]
    assert CID in ids


def test_get_campanha_traz_options(client):
    client.post("/api/campaigns", json=_briefing_body())
    _seed_copy_e_composed()
    campaign_store.marcar_aguardando(CID)
    data = client.get(f"/api/campaigns/{CID}").get_json()
    assert data["state"]["status"] == "aguardando_aprovacao"
    assert len(data["options"]) == 3
    assert data["options"][0]["composed_image_url"] == f"/composed/{CID}/option_1.png"


def test_approve_exporta_e_marca(client, monkeypatch):
    client.post("/api/campaigns", json=_briefing_body())
    _seed_copy_e_composed()
    campaign_store.marcar_aguardando(CID)
    monkeypatch.setattr(
        server.exporter, "export_approved",
        lambda cid, oid: (Path("fake.png"), Path("fake.json")),
    )
    resp = client.post(f"/api/campaigns/{CID}/approve",
                       json={"option_id": 2, "data_agendada": "2099-12-31"})
    assert resp.status_code == 200
    estado = campaign_store.read_state(CID)
    assert estado["status"] == "aprovada"
    assert estado["option_aprovada"] == 2
    assert estado["data_agendada"] == "2099-12-31"


def test_approve_data_passada_400(client, monkeypatch):
    client.post("/api/campaigns", json=_briefing_body())
    _seed_copy_e_composed()
    campaign_store.marcar_aguardando(CID)
    monkeypatch.setattr(server.exporter, "export_approved",
                        lambda cid, oid: (Path("fake.png"), Path("fake.json")))
    resp = client.post(f"/api/campaigns/{CID}/approve",
                       json={"option_id": 1, "data_agendada": "2000-01-01"})
    assert resp.status_code == 400


def test_adjust_inicia_regeracao(client):
    client.post("/api/campaigns", json=_briefing_body())
    resp = client.post(f"/api/campaigns/{CID}/adjust",
                       json={"option_id": 1, "nota": "mais técnico"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "regerando"
