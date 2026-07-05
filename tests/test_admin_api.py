"""
Testes das rotas de admin (stats, cadastro de usuário, página /admin).

Cadastro de cliente (brand novo) saiu daqui — ver tests/test_signup_api.py:
agora é um fluxo de solicitação pública + aprovação de admin, não mais um
form direto em /admin.
"""

from __future__ import annotations

import pytest
from werkzeug.security import generate_password_hash

from modules import campaign_store, server, users_store


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


def _login_cliente(client):
    _criar_usuario("cliente@teste.com", "senha123", "mendes_vaz")
    client.post("/login", json={"email": "cliente@teste.com", "senha": "senha123"})


def _login_admin(client):
    _criar_usuario("admin@teste.com", "senha123", None, role="admin")
    client.post("/login", json={"email": "admin@teste.com", "senha": "senha123"})


def _colors():
    return {"navy": "#111", "gold": "#222", "white": "#fff", "cream": "#ccc", "navy_dark": "#000"}


# ---------- 403 pra cliente ----------
def test_stats_403_pra_cliente(client):
    _login_cliente(client)
    assert client.get("/api/admin/stats").status_code == 403


def test_criar_usuario_403_pra_cliente(client):
    _login_cliente(client)
    res = client.post("/api/admin/users", json={"email": "x@x.com", "brand_slug": "mendes_vaz"})
    assert res.status_code == 403


# ---------- stats ----------
def test_stats_nunca_devolve_senha_hash(client):
    _login_admin(client)
    _criar_usuario("outro@teste.com", "senha123", "mendes_vaz")
    data = client.get("/api/admin/stats").get_json()
    assert "senha_hash" not in str(data)
    emails = [u["email"] for u in data["usuarios"]]
    assert "outro@teste.com" in emails


def test_stats_inclui_tokens_por_brand(client):
    _login_admin(client)
    campaign_store.criar(
        {"campaign_id": "2099-01-01_admin-stats", "created_at": "2099-01-01T00:00:00",
         "area_direito": "x", "perfil_cliente_ideal": "x", "tom": "tecnico",
         "objetivo": "posicionamento", "tema_especifico": "", "formato": "square",
         "num_slides": 1, "referencias": ""},
        brand_slug="mendes_vaz",
    )
    campaign_store.add_tokens("2099-01-01_admin-stats", 1234)
    data = client.get("/api/admin/stats").get_json()
    mv = next(b for b in data["brands"] if b["slug"] == "mendes_vaz")
    assert mv["tokens_used"] == 1234


# ---------- criar usuário adicional ----------
def test_criar_usuario_feliz(client):
    _login_admin(client)
    res = client.post("/api/admin/users", json={
        "email": "novo@teste.com", "brand_slug": "gui_raw", "role": "cliente",
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["email"] == "novo@teste.com"
    assert data["senha_temporaria"]
    usuario = users_store.get_by_email("novo@teste.com")
    assert usuario["brand_slug"] == "gui_raw"


def test_criar_usuario_brand_desconhecido_400(client):
    _login_admin(client)
    res = client.post("/api/admin/users", json={
        "email": "novo2@teste.com", "brand_slug": "nao_existe", "role": "cliente",
    })
    assert res.status_code == 400


def test_criar_usuario_email_duplicado_400(client):
    _login_admin(client)
    _criar_usuario("dup2@teste.com", "senha123", "mendes_vaz")
    res = client.post("/api/admin/users", json={
        "email": "dup2@teste.com", "brand_slug": "mendes_vaz", "role": "cliente",
    })
    assert res.status_code == 400


def test_criar_usuario_admin_sem_brand(client):
    _login_admin(client)
    res = client.post("/api/admin/users", json={
        "email": "novoadmin@teste.com", "role": "admin",
    })
    assert res.status_code == 201
    usuario = users_store.get_by_email("novoadmin@teste.com")
    assert usuario["brand_slug"] is None
    assert usuario["role"] == "admin"


# ---------- página /admin ----------
def test_admin_page_403_pra_cliente(client):
    _login_cliente(client)
    assert client.get("/admin").status_code == 403


def test_admin_page_200_pra_admin(client):
    _login_admin(client)
    res = client.get("/admin")
    assert res.status_code == 200
    assert b"Administra" in res.data


def test_admin_page_redireciona_deslogado(client):
    res = client.get("/admin")
    assert res.status_code == 302
    assert res.headers["Location"] == "/login"
