"""
modules/users_store.py — Camada SQLite de usuários de login.

Segue a mesma convenção de conexão do modules/store.py (conexão própria por
função, via `store.connect()`). Não guarda senha em texto puro — só o hash
(gerado com werkzeug.security em modules/server.py e scripts/seed_users.py).
"""

from __future__ import annotations

import sqlite3

from modules import store


def _row_to_user(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def criar_usuario(
    email: str, senha_hash: str, brand_slug: str | None, role: str = "cliente",
) -> dict:
    """
    Cria um usuário. `brand_slug` só pode ser None quando role="admin".

    Raises:
        sqlite3.IntegrityError: se o email já existe (UNIQUE).
    """
    from datetime import datetime
    agora = datetime.now().isoformat(timespec="seconds")
    with store.connect() as con:
        con.execute(
            "INSERT INTO users (email, senha_hash, brand_slug, role, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (email, senha_hash, brand_slug, role, agora),
        )
    return get_by_email(email)  # type: ignore[return-value]


def get_by_email(email: str) -> dict | None:
    """Lê um usuário pelo email (None se não existir)."""
    with store.connect() as con:
        row = con.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    return _row_to_user(row) if row else None


def get_by_id(user_id: int) -> dict | None:
    """Lê um usuário pelo id (None se não existir). Usado pelo user_loader do flask-login."""
    with store.connect() as con:
        row = con.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return _row_to_user(row) if row else None


def list_usuarios() -> list[dict]:
    """Lista todos os usuários (suporte administrativo)."""
    with store.connect() as con:
        rows = con.execute(
            "SELECT * FROM users ORDER BY email COLLATE NOCASE"
        ).fetchall()
    return [_row_to_user(r) for r in rows]
