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
    """Salva 3 opções de copy no DB + cria 3 PNGs compostos falsos para a campanha CID."""
    camp = settings.CAMPAIGNS_DIR / CID
    (camp / "composed").mkdir(parents=True, exist_ok=True)
    ops = [{
        "option_id": i, "headline": f"h{i}", "subheadline": "s", "body": "b",
        "caption": "c", "cta": "x", "hashtags": ["direito"],
        "image_prompt": "p", "style_notes": "n",
    } for i in (1, 2, 3)]
    campaign_store.save_copy_version(CID, 1, ops)
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
    # URL agora inclui ?v=<mtime> pra cache-busting; checa só o prefixo
    assert data["options"][0]["composed_image_url"].startswith(
        f"/composed/{CID}/option_1.png?v="
    )


def test_approve_exporta_e_marca(client, monkeypatch):
    client.post("/api/campaigns", json=_briefing_body())
    _seed_copy_e_composed()
    campaign_store.marcar_aguardando(CID)
    monkeypatch.setattr(
        server.exporter, "export_approved",
        lambda cid, oid: {
            "png": Path("fake.png"),
            "metadata": Path("fake.json"),
            "post_txt": Path("fake.txt"),
            "all_pngs": [Path("fake.png")],
        },
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
    monkeypatch.setattr(
        server.exporter, "export_approved",
        lambda cid, oid: {
            "png": Path("fake.png"), "metadata": Path("fake.json"),
            "post_txt": Path("fake.txt"), "all_pngs": [Path("fake.png")],
        },
    )
    resp = client.post(f"/api/campaigns/{CID}/approve",
                       json={"option_id": 1, "data_agendada": "2000-01-01"})
    assert resp.status_code == 400


def test_adjust_inicia_regeracao(client):
    client.post("/api/campaigns", json=_briefing_body())
    resp = client.post(f"/api/campaigns/{CID}/adjust",
                       json={"option_id": 1, "nota": "mais técnico"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "regerando"


# --------------------------------------------------------------------------
# Carrossel — payload aninhado com slides[]
# --------------------------------------------------------------------------
def _briefing_body_carousel(n_slides=3):
    body = _briefing_body()
    body["formato"] = "carousel"
    body["num_slides"] = n_slides
    return body


def _seed_carousel_copy_e_composed(n_slides=3):
    """Salva copy carrossel no DB + PNGs por slide (3 opções × N slides)."""
    camp = settings.CAMPAIGNS_DIR / CID
    (camp / "composed").mkdir(parents=True, exist_ok=True)
    ops = []
    for i in (1, 2, 3):
        ops.append({
            "option_id": i,
            "caption": f"caption {i}",
            "cta": "Saiba mais",
            "hashtags": ["direitomedico"],
            "style_notes": "n",
            "slides": [
                {"slide_id": j, "headline": f"h{i}_{j}", "subheadline": "",
                 "body": f"b{i}_{j}", "image_prompt": "p"}
                for j in range(1, n_slides + 1)
            ],
        })
        for j in range(1, n_slides + 1):
            (camp / "composed" / f"option_{i}_slide_{j}.png").write_bytes(b"PNG")
    campaign_store.save_copy_version(CID, 1, ops)


def test_get_campanha_carousel_traz_slides(client):
    client.post("/api/campaigns", json=_briefing_body_carousel(n_slides=4))
    _seed_carousel_copy_e_composed(n_slides=4)
    campaign_store.marcar_aguardando(CID)

    data = client.get(f"/api/campaigns/{CID}").get_json()
    assert data["briefing"]["formato"] == "carousel"
    assert len(data["options"]) == 3

    op1 = data["options"][0]
    # Carrossel: caption/cta/hashtags no nível da opção, sem composed_image_url
    assert "composed_image_url" not in op1
    assert op1["caption"] == "caption 1"
    assert "slides" in op1 and len(op1["slides"]) == 4
    primeiro = op1["slides"][0]
    assert primeiro["slide_id"] == 1
    assert primeiro["image_url"].startswith(f"/composed/{CID}/option_1_slide_1.png?v=")


# --------------------------------------------------------------------------
# Edição manual de copy (sem chamar OpenAI)
# --------------------------------------------------------------------------
def test_edit_copy_simples_atualiza_e_recompoe(client, monkeypatch):
    """Edição num post simples: sobrescreve campos e dispara recompose_option."""
    client.post("/api/campaigns", json=_briefing_body())
    _seed_copy_e_composed()
    campaign_store.marcar_aguardando(CID)

    recomposed: list = []
    monkeypatch.setattr(
        server.composer, "recompose_option",
        lambda briefing, opcao: recomposed.append(opcao) or [Path("fake.png")],
    )

    resp = client.post(
        f"/api/campaigns/{CID}/edit-copy",
        json={
            "option_id": 2,
            "fields": {
                "headline": "Headline NOVO",
                "body": "Corpo NOVO",
                "hashtags": ["#Direito Médico", "advocaciabh"],
            },
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()

    # Payload retornado já reflete a edição
    op2 = next(o for o in data["options"] if o["option_id"] == 2)
    assert op2["headline"] == "Headline NOVO"
    assert op2["body"] == "Corpo NOVO"
    assert op2["hashtags"] == ["direitomedico", "advocaciabh"]  # normalizadas

    # Versão de copy NÃO foi bumpada (edição não é regeração)
    assert campaign_store.get_copy_version(CID) == 1

    # composer.recompose_option foi chamado com a opção 2 atualizada
    assert len(recomposed) == 1
    assert recomposed[0]["option_id"] == 2
    assert recomposed[0]["headline"] == "Headline NOVO"


def test_edit_copy_carrossel_edita_metadado_e_slides(client, monkeypatch):
    """Carrossel: edita caption (opção) + headline de um slide específico."""
    client.post("/api/campaigns", json=_briefing_body_carousel(n_slides=3))
    _seed_carousel_copy_e_composed(n_slides=3)
    campaign_store.marcar_aguardando(CID)

    monkeypatch.setattr(server.composer, "recompose_option",
                        lambda b, o: [Path("fake.png")])

    resp = client.post(
        f"/api/campaigns/{CID}/edit-copy",
        json={
            "option_id": 1,
            "fields": {
                "caption": "Caption editada",
                "slides": [
                    {"slide_id": 2, "headline": "H2 NOVO"},
                ],
            },
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    op1 = next(o for o in data["options"] if o["option_id"] == 1)
    assert op1["caption"] == "Caption editada"
    slide2 = next(s for s in op1["slides"] if s["slide_id"] == 2)
    assert slide2["headline"] == "H2 NOVO"
    # Slides não tocados ficam iguais
    slide1 = next(s for s in op1["slides"] if s["slide_id"] == 1)
    assert slide1["headline"] == "h1_1"


def test_edit_copy_rejeita_campo_desconhecido(client):
    client.post("/api/campaigns", json=_briefing_body())
    _seed_copy_e_composed()
    campaign_store.marcar_aguardando(CID)

    resp = client.post(
        f"/api/campaigns/{CID}/edit-copy",
        json={"option_id": 1, "fields": {"image_prompt": "hack"}},
    )
    assert resp.status_code == 400
    assert "image_prompt" in resp.get_json()["erro"]
