"""
tests/_auth_helpers.py — helpers de login pra testes que batem na API via
Flask test client (não é um arquivo de teste em si, sem test_*).
"""

from __future__ import annotations

from werkzeug.security import generate_password_hash

from modules import users_store

TEST_EMAIL = "teste@mendesvaz.com"
TEST_SENHA = "senha-teste-123"


def seed_usuario_teste(
    brand_slug: str = "mendes_vaz", role: str = "cliente",
    email: str = TEST_EMAIL, senha: str = TEST_SENHA,
) -> tuple[str, str]:
    """Cria (se ainda não existir) um usuário de teste e devolve (email, senha)."""
    if users_store.get_by_email(email) is None:
        users_store.criar_usuario(email, generate_password_hash(senha), brand_slug, role)
    return email, senha


def login(client, brand_slug: str = "mendes_vaz", role: str = "cliente"):
    """
    Semeia um usuário de teste e loga via POST /login no test client.

    A sessão fica no cookie jar do `client` — chamadas seguintes já saem
    autenticadas. Devolve o próprio client, pra encadear.
    """
    email, senha = seed_usuario_teste(brand_slug=brand_slug, role=role)
    res = client.post("/login", json={"email": email, "senha": senha})
    assert res.status_code == 200, f"login de teste falhou: {res.get_json()}"
    return client
