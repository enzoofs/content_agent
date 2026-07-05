"""
modules/brands_store.py — Camada SQLite de brands criados pela tela de admin.

Mesmo padrão de conexão de modules/users_store.py (conexão própria por
função, via store.connect()). Não conhece a dataclass Brand nem importa
config.brands — mantém a direção do import de mão única (config/brands/
__init__.py importa este módulo, nunca o contrário; evita ciclo).
"""

from __future__ import annotations

import json
import sqlite3

from modules import store


def _row_to_brand(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def criar_brand(
    slug: str, nome: str, colors: dict, *,
    logo_filename: str | None = None,
    use_image_logo: bool = True,
    theme: str = "light",
    google_fonts_url: str = "",
    ui_heading_font: str = "",
    ui_body_font: str = "",
    image_prompt_suffix: str = "",
    ideogram_negative_prompt: str = "",
    approved_by: str = "",
    system_prompt: str = "",
    system_prompt_carousel: str = "",
) -> dict:
    """
    Cria um brand novo (usado pelo cadastro de clientes na tela de admin).

    Raises:
        sqlite3.IntegrityError: se o slug já existe (PRIMARY KEY).
    """
    from datetime import datetime
    agora = datetime.now().isoformat(timespec="seconds")
    with store.connect() as con:
        con.execute(
            """
            INSERT INTO brands (
                slug, nome, colors_json, logo_filename, use_image_logo, theme,
                google_fonts_url, ui_heading_font, ui_body_font,
                image_prompt_suffix, ideogram_negative_prompt, approved_by,
                system_prompt, system_prompt_carousel, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                slug, nome, json.dumps(colors, ensure_ascii=False), logo_filename,
                int(use_image_logo), theme, google_fonts_url, ui_heading_font,
                ui_body_font, image_prompt_suffix, ideogram_negative_prompt,
                approved_by, system_prompt, system_prompt_carousel, agora,
            ),
        )
    return get_by_slug(slug)  # type: ignore[return-value]


def get_by_slug(slug: str) -> dict | None:
    """Lê um brand pelo slug (None se não existir)."""
    with store.connect() as con:
        row = con.execute(
            "SELECT * FROM brands WHERE slug = ?", (slug,)
        ).fetchone()
    return _row_to_brand(row) if row else None


def list_brands() -> list[dict]:
    """Lista todos os brands criados via admin, em ordem alfabética por nome."""
    with store.connect() as con:
        rows = con.execute(
            "SELECT * FROM brands ORDER BY nome COLLATE NOCASE"
        ).fetchall()
    return [_row_to_brand(r) for r in rows]


def delete_brand(slug: str) -> bool:
    """
    Apaga um brand por slug. Usado SÓ pelo rollback compensatório de
    POST /api/admin/clients (quando a criação do primeiro usuário falha
    depois do brand já commitado) — não é exposta por nenhuma rota.
    """
    with store.connect() as con:
        cur = con.execute("DELETE FROM brands WHERE slug = ?", (slug,))
    return cur.rowcount > 0
