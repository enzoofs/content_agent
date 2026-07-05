"""
Testes de modules/users_store.py — CRUD de usuários de login.

Isolamento de DB vem do fixture autouse em conftest.py.
"""

from __future__ import annotations

import sqlite3

import pytest

from modules import users_store


def test_criar_usuario_cliente():
    u = users_store.criar_usuario("henrique@exemplo.com", "hash123", "mendes_vaz", "cliente")
    assert u["email"] == "henrique@exemplo.com"
    assert u["brand_slug"] == "mendes_vaz"
    assert u["role"] == "cliente"
    assert u["senha_hash"] == "hash123"


def test_criar_usuario_admin_sem_brand():
    u = users_store.criar_usuario("admin@exemplo.com", "hash456", None, "admin")
    assert u["brand_slug"] is None
    assert u["role"] == "admin"


def test_get_by_email_inexistente():
    assert users_store.get_by_email("naoexiste@exemplo.com") is None


def test_get_by_id():
    criado = users_store.criar_usuario("gui@exemplo.com", "hashabc", "gui_raw", "cliente")
    lido = users_store.get_by_id(criado["id"])
    assert lido["email"] == "gui@exemplo.com"


def test_get_by_id_inexistente():
    assert users_store.get_by_id(9999) is None


def test_email_duplicado_falha():
    users_store.criar_usuario("dup@exemplo.com", "hash1", "mendes_vaz", "cliente")
    with pytest.raises(sqlite3.IntegrityError):
        users_store.criar_usuario("dup@exemplo.com", "hash2", "gui_raw", "cliente")


def test_list_usuarios_ordem_alfabetica():
    users_store.criar_usuario("zeta@exemplo.com", "h", "gui_raw", "cliente")
    users_store.criar_usuario("alfa@exemplo.com", "h", "mendes_vaz", "cliente")
    emails = [u["email"] for u in users_store.list_usuarios()]
    assert emails == ["alfa@exemplo.com", "zeta@exemplo.com"]
