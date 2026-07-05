"""
Testes de autenticação e isolamento entre brands (login multi-tenant).

Cobre: login ok/falha, 401 sem sessão, isolamento cliente A vs B (list omite,
by-id dá 404), admin alterna entre brands.
"""

from __future__ import annotations

import pytest
from werkzeug.security import generate_password_hash

from modules import campaign_store, server, users_store
from tests import _auth_helpers


@pytest.fixture
def app():
    app = server.build_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


def _criar_usuario(email, senha, brand_slug, role="cliente"):
    users_store.criar_usuario(email, generate_password_hash(senha), brand_slug, role)


def _briefing(cid_suffix: str):
    return {
        "campaign_id": f"2099-01-01_teste-auth-{cid_suffix}",
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


# ---------- Login ----------
def test_login_ok(client):
    _criar_usuario("henrique@teste.com", "senha123", "mendes_vaz")
    res = client.post("/login", json={"email": "henrique@teste.com", "senha": "senha123"})
    assert res.status_code == 200


def test_login_senha_errada(client):
    _criar_usuario("henrique2@teste.com", "senha123", "mendes_vaz")
    res = client.post("/login", json={"email": "henrique2@teste.com", "senha": "errada"})
    assert res.status_code == 401


def test_login_email_inexistente(client):
    res = client.post("/login", json={"email": "naoexiste@teste.com", "senha": "x"})
    assert res.status_code == 401


# ---------- Gate de autenticação ----------
def test_api_sem_login_retorna_401(client):
    res = client.get("/api/campaigns")
    assert res.status_code == 401


def test_health_nao_precisa_login(client):
    res = client.get("/health")
    assert res.status_code == 200


# ---------- Isolamento entre brands ----------
def test_cliente_so_ve_campanhas_do_proprio_brand(client):
    _criar_usuario("henrique3@teste.com", "senha123", "mendes_vaz")
    campaign_store.criar(_briefing("mv"), brand_slug="mendes_vaz")
    campaign_store.criar(_briefing("gui"), brand_slug="gui_raw")

    client.post("/login", json={"email": "henrique3@teste.com", "senha": "senha123"})
    data = client.get("/api/campaigns").get_json()
    ids = [c["campaign_id"] for c in data]
    assert "2099-01-01_teste-auth-mv" in ids
    assert "2099-01-01_teste-auth-gui" not in ids


def test_cliente_nao_acessa_campanha_de_outro_brand_por_id(client):
    _criar_usuario("henrique4@teste.com", "senha123", "mendes_vaz")
    campaign_store.criar(_briefing("gui2"), brand_slug="gui_raw")

    client.post("/login", json={"email": "henrique4@teste.com", "senha": "senha123"})
    res = client.get("/api/campaigns/2099-01-01_teste-auth-gui2")
    assert res.status_code == 404


# ---------- Admin ----------
def test_admin_sem_brand_ativo_ve_lista_vazia(client):
    _criar_usuario("admin1@teste.com", "senha123", None, role="admin")
    campaign_store.criar(_briefing("mv2"), brand_slug="mendes_vaz")

    client.post("/login", json={"email": "admin1@teste.com", "senha": "senha123"})
    data = client.get("/api/campaigns").get_json()
    assert data == []


def test_admin_alterna_brand_e_ve_campanhas(client):
    _criar_usuario("admin2@teste.com", "senha123", None, role="admin")
    campaign_store.criar(_briefing("mv3"), brand_slug="mendes_vaz")
    campaign_store.criar(_briefing("gui3"), brand_slug="gui_raw")

    client.post("/login", json={"email": "admin2@teste.com", "senha": "senha123"})

    client.post("/api/admin/brand", json={"slug": "mendes_vaz"})
    ids_mv = [c["campaign_id"] for c in client.get("/api/campaigns").get_json()]
    assert "2099-01-01_teste-auth-mv3" in ids_mv
    assert "2099-01-01_teste-auth-gui3" not in ids_mv

    client.post("/api/admin/brand", json={"slug": "gui_raw"})
    ids_gui = [c["campaign_id"] for c in client.get("/api/campaigns").get_json()]
    assert "2099-01-01_teste-auth-gui3" in ids_gui
    assert "2099-01-01_teste-auth-mv3" not in ids_gui


def test_cliente_nao_pode_trocar_brand(client):
    _criar_usuario("henrique5@teste.com", "senha123", "mendes_vaz")
    client.post("/login", json={"email": "henrique5@teste.com", "senha": "senha123"})
    res = client.post("/api/admin/brand", json={"slug": "gui_raw"})
    assert res.status_code == 403
