"""
Testes de migração aditiva em modules/store.py — garante que init_db() não
quebra num DB já existente, criado ANTES da coluna brand_slug existir.

Regressão: os índices que dependem de brand_slug rodavam dentro do mesmo
executescript do CREATE TABLE, antes do ALTER TABLE que adiciona a coluna em
bancos antigos — CREATE TABLE IF NOT EXISTS é no-op nesse caso, e o CREATE
INDEX quebrava com "no such column: brand_slug".
"""

from __future__ import annotations

import sqlite3

from config import settings
from modules import store

# Schema pré-login: sem brand_slug em campaigns/briefing_templates, sem users.
_SCHEMA_ANTIGO = """
CREATE TABLE campaigns (
    campaign_id           TEXT    PRIMARY KEY,
    area_direito          TEXT    NOT NULL,
    perfil_cliente_ideal  TEXT    NOT NULL,
    tom                   TEXT    NOT NULL,
    objetivo              TEXT    NOT NULL,
    tema_especifico       TEXT,
    formato               TEXT    NOT NULL,
    num_slides            INTEGER NOT NULL,
    referencias           TEXT,
    created_at            TEXT    NOT NULL,
    status                TEXT    NOT NULL,
    etapa                 TEXT,
    copy_version          INTEGER NOT NULL DEFAULT 1,
    option_aprovada       INTEGER,
    data_agendada         TEXT,
    erro                  TEXT,
    atualizado_em         TEXT    NOT NULL,
    tokens_used           INTEGER NOT NULL DEFAULT 0,
    hide_overlay          INTEGER NOT NULL DEFAULT 0,
    upload_filename       TEXT
);
CREATE TABLE briefing_templates (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                  TEXT    NOT NULL UNIQUE,
    area_direito          TEXT    NOT NULL DEFAULT '',
    perfil_cliente_ideal  TEXT    NOT NULL DEFAULT '',
    tom                   TEXT    NOT NULL DEFAULT 'tecnico',
    objetivo              TEXT    NOT NULL DEFAULT 'posicionamento',
    formato               TEXT    NOT NULL DEFAULT 'square',
    num_slides            INTEGER NOT NULL DEFAULT 1,
    tema_especifico       TEXT    NOT NULL DEFAULT '',
    referencias           TEXT    NOT NULL DEFAULT '',
    created_at            TEXT    NOT NULL
);
"""


def test_init_db_migra_banco_sem_brand_slug(tmp_path, monkeypatch):
    """init_db() não deve quebrar num DB criado antes da coluna brand_slug existir."""
    # O fixture autouse (_db_isolado) já rodou init_db() num DB novo — aqui
    # precisamos de um arquivo à parte, ainda no schema pré-login.
    db_antigo = tmp_path / "state_antigo.db"
    monkeypatch.setattr(settings, "STATE_DB_PATH", db_antigo)

    con = sqlite3.connect(db_antigo)
    con.executescript(_SCHEMA_ANTIGO)
    con.close()

    store.init_db()  # não deve levantar exceção

    with store.connect() as con:
        cols_campaigns = {r["name"] for r in con.execute("PRAGMA table_info(campaigns)").fetchall()}
        cols_templates = {r["name"] for r in con.execute("PRAGMA table_info(briefing_templates)").fetchall()}
        tabelas = {r["name"] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}

    assert "brand_slug" in cols_campaigns
    assert "brand_slug" in cols_templates
    assert "users" in tabelas
    assert "brands" in tabelas
