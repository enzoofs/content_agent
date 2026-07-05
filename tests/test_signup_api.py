"""
Testes do fluxo de solicitação pública de cadastro + aprovação de admin.

Cobre: submissão pública (com/sem logo), validação, listagem admin-only,
aprovar (com/sem edição de campos pelo admin, colisão de slug re-checada,
rollback de email duplicado), rejeitar (com/sem motivo, logo pendente
apagado), e que POST /api/admin/clients não existe mais.
"""

from __future__ import annotations

import io

import pytest
from werkzeug.security import generate_password_hash

from modules import brands_store, server, signup_requests_store, users_store


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


# ---------- submissão pública ----------
def test_signup_publico_nao_precisa_login(client):
    res = client.post("/api/signup-requests", json={"nome": "Acme", "email": "acme@teste.com"})
    assert res.status_code == 201
    assert res.get_json() == {"status": "recebido"}


def test_signup_cria_solicitacao_pendente_com_campos_tecnicos_vazios(client):
    client.post("/api/signup-requests", json={
        "nome": "Beta Negocios", "email": "beta@teste.com",
        "sobre_negocio": "Vendemos widgets.",
    })
    s = signup_requests_store.list_solicitacoes()[0]
    assert s["status"] == "pendente"
    assert s["nome"] == "Beta Negocios"
    assert s["sobre_negocio"] == "Vendemos widgets."
    assert s["system_prompt"] == ""
    assert s["ideogram_negative_prompt"] == ""


def test_signup_com_logo(client, tmp_path, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "ASSETS_DIR", tmp_path)
    data = {
        "nome": "Com Logo", "email": "comlogo@teste.com",
        "logo": (io.BytesIO(b"fake png bytes"), "logo.png"),
    }
    res = client.post("/api/signup-requests", content_type="multipart/form-data", data=data)
    assert res.status_code == 201
    s = signup_requests_store.list_solicitacoes()[0]
    pendente = s["logo_filename_pendente"]
    assert pendente.endswith(".png")
    assert (tmp_path / "pending_logos" / pendente).exists()


def test_signup_sem_nome_400(client):
    res = client.post("/api/signup-requests", json={"email": "x@x.com"})
    assert res.status_code == 400


def test_signup_email_invalido_400(client):
    res = client.post("/api/signup-requests", json={"nome": "X", "email": "sem-arroba"})
    assert res.status_code == 400


# ---------- listagem (admin only) ----------
def test_listar_solicitacoes_403_pra_cliente(client):
    _login_cliente(client)
    assert client.get("/api/admin/signup-requests").status_code == 403


def test_listar_solicitacoes_admin(client):
    client.post("/api/signup-requests", json={"nome": "Gama", "email": "gama@teste.com"})
    _login_admin(client)
    data = client.get("/api/admin/signup-requests").get_json()
    assert len(data) == 1
    assert data[0]["nome"] == "Gama"


def test_listar_solicitacoes_filtra_por_status(client):
    client.post("/api/signup-requests", json={"nome": "Delta", "email": "delta@teste.com"})
    _login_admin(client)
    data = client.get("/api/admin/signup-requests?status=aprovado").get_json()
    assert data == []


# ---------- aprovar ----------
def test_aprovar_403_pra_cliente(client):
    client.post("/api/signup-requests", json={"nome": "X", "email": "x2@teste.com"})
    _login_cliente(client)
    s = signup_requests_store.list_solicitacoes()[0]
    res = client.post(f"/api/admin/signup-requests/{s['id']}/approve", json={})
    assert res.status_code == 403


def test_aprovar_sem_edicao_usa_dados_da_solicitacao(client):
    client.post("/api/signup-requests", json={
        "nome": "Aprovar Simples", "email": "simples@teste.com",
    })
    _login_admin(client)
    s = signup_requests_store.list_solicitacoes()[0]
    res = client.post(f"/api/admin/signup-requests/{s['id']}/approve", json={})
    assert res.status_code == 201
    data = res.get_json()
    assert data["slug"] == "aprovar_simples"
    assert data["email"] == "simples@teste.com"
    assert data["senha_temporaria"]

    brand = brands_store.get_by_slug("aprovar_simples")
    assert brand["nome"] == "Aprovar Simples"
    usuario = users_store.get_by_email("simples@teste.com")
    assert usuario["brand_slug"] == "aprovar_simples"

    atualizado = signup_requests_store.get_by_id(s["id"])
    assert atualizado["status"] == "aprovado"
    assert atualizado["reviewed_by"] == "admin@teste.com"


def test_aprovar_admin_completa_prompts_tecnicos(client):
    client.post("/api/signup-requests", json={"nome": "Completar", "email": "completar@teste.com"})
    _login_admin(client)
    s = signup_requests_store.list_solicitacoes()[0]
    res = client.post(f"/api/admin/signup-requests/{s['id']}/approve", json={
        "system_prompt": "prompt completo pelo admin",
        "ideogram_negative_prompt": "negative completo",
        "approved_by": "Fulano Admin",
    })
    assert res.status_code == 201
    slug = res.get_json()["slug"]
    brand = brands_store.get_by_slug(slug)
    assert brand["system_prompt"] == "prompt completo pelo admin"
    assert brand["ideogram_negative_prompt"] == "negative completo"
    assert brand["approved_by"] == "Fulano Admin"


def test_aprovar_com_logo_pendente_promove_pro_nome_final(client, tmp_path, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "ASSETS_DIR", tmp_path)
    data = {
        "nome": "Com Logo Aprovar", "email": "logoaprovar@teste.com",
        "logo": (io.BytesIO(b"fake png bytes"), "logo.png"),
    }
    client.post("/api/signup-requests", content_type="multipart/form-data", data=data)
    _login_admin(client)
    s = signup_requests_store.list_solicitacoes()[0]
    res = client.post(f"/api/admin/signup-requests/{s['id']}/approve", json={"use_image_logo": "true"})
    assert res.status_code == 201
    slug = res.get_json()["slug"]
    assert (tmp_path / f"logo_{slug}.png").exists()
    assert not (tmp_path / "pending_logos" / s["logo_filename_pendente"]).exists()
    brand = brands_store.get_by_slug(slug)
    assert brand["logo_filename"] == f"logo_{slug}.png"


def test_aprovar_slug_colide_re_checado(client):
    client.post("/api/signup-requests", json={"nome": "Mendes Vaz", "email": "colide@teste.com"})
    _login_admin(client)
    s = signup_requests_store.list_solicitacoes()[0]
    res = client.post(
        f"/api/admin/signup-requests/{s['id']}/approve",
        json={"slug": "mendes_vaz"},
    )
    assert res.status_code == 400


def test_aprovar_rollback_email_duplicado(client):
    _criar_usuario("jaexiste2@teste.com", "senha123", "mendes_vaz")
    client.post("/api/signup-requests", json={"nome": "Rollback Signup", "email": "jaexiste2@teste.com"})
    _login_admin(client)
    s = signup_requests_store.list_solicitacoes()[0]
    res = client.post(f"/api/admin/signup-requests/{s['id']}/approve", json={})
    assert res.status_code == 400
    assert brands_store.get_by_slug("rollback_signup") is None


def test_aprovar_solicitacao_ja_revisada_400(client):
    client.post("/api/signup-requests", json={"nome": "Duas Vezes", "email": "duasvezes@teste.com"})
    _login_admin(client)
    s = signup_requests_store.list_solicitacoes()[0]
    client.post(f"/api/admin/signup-requests/{s['id']}/approve", json={})
    res = client.post(f"/api/admin/signup-requests/{s['id']}/approve", json={})
    assert res.status_code == 400


# ---------- rejeitar ----------
def test_rejeitar_com_motivo(client):
    client.post("/api/signup-requests", json={"nome": "Rejeitar", "email": "rejeitar@teste.com"})
    _login_admin(client)
    s = signup_requests_store.list_solicitacoes()[0]
    res = client.post(f"/api/admin/signup-requests/{s['id']}/reject", json={"motivo": "fora do escopo"})
    assert res.status_code == 200
    atualizado = signup_requests_store.get_by_id(s["id"])
    assert atualizado["status"] == "rejeitado"
    assert atualizado["motivo_rejeicao"] == "fora do escopo"


def test_rejeitar_apaga_logo_pendente(client, tmp_path, monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "ASSETS_DIR", tmp_path)
    data = {
        "nome": "Rejeitar Logo", "email": "rejeitarlogo@teste.com",
        "logo": (io.BytesIO(b"fake png bytes"), "logo.png"),
    }
    client.post("/api/signup-requests", content_type="multipart/form-data", data=data)
    _login_admin(client)
    s = signup_requests_store.list_solicitacoes()[0]
    pendente = s["logo_filename_pendente"]
    assert (tmp_path / "pending_logos" / pendente).exists()

    client.post(f"/api/admin/signup-requests/{s['id']}/reject", json={})
    assert not (tmp_path / "pending_logos" / pendente).exists()


def test_rejeitar_403_pra_cliente(client):
    client.post("/api/signup-requests", json={"nome": "X", "email": "x3@teste.com"})
    _login_cliente(client)
    s = signup_requests_store.list_solicitacoes()[0]
    res = client.post(f"/api/admin/signup-requests/{s['id']}/reject", json={})
    assert res.status_code == 403


# ---------- página /signup ----------
def test_signup_page_publica_sem_login(client):
    res = client.get("/signup")
    assert res.status_code == 200
    assert b"Solicitar acesso" in res.data


# ---------- endpoint antigo removido ----------
def test_endpoint_antigo_criar_cliente_nao_existe_mais(client):
    _login_admin(client)
    res = client.post("/api/admin/clients", json={"nome": "X", "email": "x4@teste.com"})
    assert res.status_code in (404, 405)
