"""
modules/signup_requests_store.py — Camada SQLite de solicitações públicas
de cadastro (tela /signup, sem autenticação).

Mesmo padrão de conexão de modules/brands_store.py (conexão própria por
função, via store.connect()).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from modules import store


def _row_to_solicitacao(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def criar_solicitacao(
    nome: str, email: str, colors: dict, *,
    slug_sugerido: str | None = None,
    logo_filename_pendente: str | None = None,
    use_image_logo: bool = True,
    theme: str = "light",
    google_fonts_url: str = "",
    ui_heading_font: str = "",
    ui_body_font: str = "",
    sobre_negocio: str = "",
    image_prompt_suffix: str = "",
    ideogram_negative_prompt: str = "",
    approved_by: str = "",
    system_prompt: str = "",
    system_prompt_carousel: str = "",
) -> dict:
    """Cria uma solicitação pendente (status='pendente' por padrão)."""

    agora = datetime.now().isoformat(timespec="seconds")
    with store.connect() as con:
        cur = con.execute(
            """
            INSERT INTO signup_requests (
                nome, email, slug_sugerido, colors_json, logo_filename_pendente,
                use_image_logo, theme, google_fonts_url, ui_heading_font,
                ui_body_font, sobre_negocio, image_prompt_suffix,
                ideogram_negative_prompt, approved_by, system_prompt,
                system_prompt_carousel, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente', ?)
            """,
            (
                nome, email, slug_sugerido, json.dumps(colors, ensure_ascii=False),
                logo_filename_pendente, int(use_image_logo), theme, google_fonts_url,
                ui_heading_font, ui_body_font, sobre_negocio, image_prompt_suffix,
                ideogram_negative_prompt, approved_by, system_prompt,
                system_prompt_carousel, agora,
            ),
        )
        novo_id = cur.lastrowid
    return get_by_id(novo_id)  # type: ignore[return-value]


def get_by_id(id_: int) -> dict | None:
    """Lê uma solicitação pelo id (None se não existir)."""
    with store.connect() as con:
        row = con.execute(
            "SELECT * FROM signup_requests WHERE id = ?", (id_,)
        ).fetchone()
    return _row_to_solicitacao(row) if row else None


def list_solicitacoes(status: str | None = None) -> list[dict]:
    """Lista solicitações, mais recentes primeiro. status=None lista todas."""
    with store.connect() as con:
        if status is None:
            rows = con.execute(
                "SELECT * FROM signup_requests ORDER BY created_at DESC, id DESC"
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM signup_requests WHERE status = ? ORDER BY created_at DESC, id DESC",
                (status,),
            ).fetchall()
    return [_row_to_solicitacao(r) for r in rows]


def marcar_revisada(
    id_: int, status: str, reviewed_by: str, motivo_rejeicao: str = "",
) -> dict:
    """
    Marca a solicitação como aprovada ou rejeitada.

    Args:
        status: "aprovado" ou "rejeitado".
        reviewed_by: email do admin que revisou.
        motivo_rejeicao: nota interna opcional (não é enviada a ninguém —
            notificação está fora de escopo por ora).
    """

    agora = datetime.now().isoformat(timespec="seconds")
    with store.connect() as con:
        con.execute(
            "UPDATE signup_requests SET status = ?, reviewed_at = ?, "
            "reviewed_by = ?, motivo_rejeicao = ? WHERE id = ?",
            (status, agora, reviewed_by, motivo_rejeicao, id_),
        )
    return get_by_id(id_)  # type: ignore[return-value]
