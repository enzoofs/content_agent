"""
modules/store.py — Camada SQLite do sistema (low-level).

Substitui o estado em arquivos (state.json, briefing.json, copy_v*.json) por um
único banco SQLite, mantendo as imagens/composed/exports em arquivo (binários
não cabem bem em SQLite).

Único módulo que conhece SQL. campaign_store importa daqui e expõe API de
domínio. Os demais módulos NUNCA tocam direto no DB.

Pragmas usados:
- journal_mode=WAL  -> múltiplos leitores + 1 escritor concorrente (essencial
                       com o servidor Flask threaded).
- foreign_keys=ON   -> integridade referencial (não é default no SQLite).
- synchronous=NORMAL -> bom equilíbrio durabilidade/perf em WAL.

Conexões NÃO são compartilhadas entre threads (regra do sqlite3); cada operação
abre/fecha sua própria conexão via context manager.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from config import settings

def db_path() -> Path:
    """Resolve o caminho do DB no momento da chamada (permite override em testes via monkeypatch em settings.STATE_DB_PATH)."""
    return Path(settings.STATE_DB_PATH)


# --------------------------------------------------------------------------
# Schema (idempotente: CREATE IF NOT EXISTS)
# --------------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS campaigns (
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
    atualizado_em         TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS copy_versions (
    campaign_id   TEXT    NOT NULL,
    versao        INTEGER NOT NULL,
    payload       TEXT    NOT NULL,                    -- JSON da lista de opções
    nota_ajuste   TEXT    NOT NULL DEFAULT '',         -- '' = geração inicial; texto = ajuste solicitado
    created_at    TEXT    NOT NULL,
    PRIMARY KEY (campaign_id, versao),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);
CREATE INDEX IF NOT EXISTS idx_campaigns_data_agendada ON campaigns(data_agendada);

-- Templates de briefing: preset reutilizável para acelerar criação de campanhas.
-- Guarda apenas os campos do briefing — não vira campanha sozinho.
CREATE TABLE IF NOT EXISTS briefing_templates (
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

# Colunas editáveis de briefing_templates (id e created_at são geridos pelo DB).
TEMPLATE_FIELDS = (
    "nome", "area_direito", "perfil_cliente_ideal", "tom", "objetivo",
    "formato", "num_slides", "tema_especifico", "referencias",
)

# Colunas de campaigns na ORDEM EXATA do schema. Usado para INSERT/UPDATE.
CAMPAIGN_COLUMNS = (
    "campaign_id", "area_direito", "perfil_cliente_ideal", "tom", "objetivo",
    "tema_especifico", "formato", "num_slides", "referencias", "created_at",
    "status", "etapa", "copy_version", "option_aprovada", "data_agendada",
    "erro", "atualizado_em",
)


# --------------------------------------------------------------------------
# Conexão e bootstrap
# --------------------------------------------------------------------------
@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """
    Abre conexão SQLite com pragmas corretos e devolve via context manager.

    Faz commit no exit normal e rollback se houver exceção. Conexão NÃO é
    reaproveitada entre threads (regra do sqlite3 padrão).
    """
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p, isolation_level=None, timeout=10.0)
    # WAL: leitores não bloqueiam escritor; essencial com Flask threaded
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous = NORMAL")
    con.execute("PRAGMA foreign_keys = ON")
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def init_db() -> None:
    """Cria tabelas e índices se não existirem. Idempotente."""
    with connect() as con:
        con.executescript(SCHEMA_SQL)


# Alias retrocompat com nomes legados
init_schema = init_db


# --------------------------------------------------------------------------
# Operações de campanha
# --------------------------------------------------------------------------
def _row_to_state(row: sqlite3.Row) -> dict:
    """Converte sqlite3.Row -> dict (igual ao formato antigo do state.json)."""
    return {k: row[k] for k in row.keys()}


def insert_campaign(briefing: dict, status: str = "gerando", etapa: str = "copy") -> dict:
    """
    Cria registro de campanha a partir do briefing validado.

    Args:
        briefing: saída de briefing_parser.parse.
        status, etapa: estado inicial (padrão: gerando/copy).

    Returns:
        Estado completo da campanha.

    Raises:
        sqlite3.IntegrityError: se campaign_id já existe (PRIMARY KEY).
    """
    from datetime import datetime
    agora = datetime.now().isoformat(timespec="seconds")
    valores = {
        "campaign_id": briefing["campaign_id"],
        "area_direito": briefing["area_direito"],
        "perfil_cliente_ideal": briefing["perfil_cliente_ideal"],
        "tom": briefing["tom"],
        "objetivo": briefing["objetivo"],
        "tema_especifico": briefing.get("tema_especifico", "") or "",
        "formato": briefing["formato"],
        "num_slides": briefing["num_slides"],
        "referencias": briefing.get("referencias", "") or "",
        "created_at": briefing.get("created_at", agora),
        "status": status,
        "etapa": etapa,
        "copy_version": 1,
        "option_aprovada": None,
        "data_agendada": None,
        "erro": None,
        "atualizado_em": agora,
    }
    cols = ", ".join(CAMPAIGN_COLUMNS)
    placeholders = ", ".join(f":{c}" for c in CAMPAIGN_COLUMNS)
    with connect() as con:
        con.execute(f"INSERT INTO campaigns ({cols}) VALUES ({placeholders})", valores)
    return get_campaign(briefing["campaign_id"])  # type: ignore[return-value]


def get_campaign(campaign_id: str) -> dict | None:
    """Lê uma campanha completa (None se não existir)."""
    with connect() as con:
        row = con.execute(
            "SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,)
        ).fetchone()
    return _row_to_state(row) if row else None


def update_campaign(campaign_id: str, **campos) -> dict:
    """
    Atualiza colunas específicas + atualizado_em. Faz merge com o estado atual.

    Args:
        campaign_id: id da campanha.
        campos: pares coluna=valor para atualizar.

    Returns:
        Estado completo após o UPDATE.

    Raises:
        ValueError: se a campanha não existir ou uma coluna desconhecida for passada.
    """
    from datetime import datetime
    if not campos:
        existente = get_campaign(campaign_id)
        if existente is None:
            raise ValueError(f"Campanha {campaign_id!r} não encontrada.")
        return existente

    # Valida colunas — evita injeção via chave (placeholder não cobre nomes)
    desconhecidas = set(campos) - set(CAMPAIGN_COLUMNS)
    if desconhecidas:
        raise ValueError(f"Colunas desconhecidas em campaigns: {sorted(desconhecidas)}")

    campos["atualizado_em"] = datetime.now().isoformat(timespec="seconds")
    set_clause = ", ".join(f"{k} = :{k}" for k in campos)
    params = {**campos, "campaign_id": campaign_id}
    with connect() as con:
        cur = con.execute(
            f"UPDATE campaigns SET {set_clause} WHERE campaign_id = :campaign_id",
            params,
        )
        if cur.rowcount == 0:
            raise ValueError(f"Campanha {campaign_id!r} não encontrada.")
    return get_campaign(campaign_id)  # type: ignore[return-value]


def list_campaigns() -> list[dict]:
    """Lista todas as campanhas, mais recentes primeiro (por created_at desc)."""
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM campaigns ORDER BY created_at DESC, campaign_id DESC"
        ).fetchall()
    return [_row_to_state(r) for r in rows]


def campaign_id_exists(campaign_id: str) -> bool:
    """True se a campaign_id já está em uso (usado por make_campaign_id para evitar colisão)."""
    with connect() as con:
        row = con.execute(
            "SELECT 1 FROM campaigns WHERE campaign_id = ? LIMIT 1", (campaign_id,)
        ).fetchone()
    return row is not None


# --------------------------------------------------------------------------
# Operações de copy (versionamento)
# --------------------------------------------------------------------------
def save_copy_version(
    campaign_id: str, versao: int, opcoes: list[dict], nota_ajuste: str = "",
) -> None:
    """
    Persiste uma versão do copy. UPSERT: se já existir (cid, versao), substitui.

    O payload é o JSON serializado da lista de opções — mesmo formato do antigo
    copy_v{N}.json. Mantém compatibilidade direta.
    """
    from datetime import datetime
    payload = json.dumps(opcoes, ensure_ascii=False)
    agora = datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        con.execute(
            """
            INSERT INTO copy_versions (campaign_id, versao, payload, nota_ajuste, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(campaign_id, versao) DO UPDATE SET
                payload = excluded.payload,
                nota_ajuste = excluded.nota_ajuste,
                created_at = excluded.created_at
            """,
            (campaign_id, versao, payload, nota_ajuste or "", agora),
        )


def get_copy_version(campaign_id: str, versao: int) -> list[dict] | None:
    """Lê uma versão específica de copy. Retorna a lista de opções ou None."""
    with connect() as con:
        row = con.execute(
            "SELECT payload FROM copy_versions WHERE campaign_id = ? AND versao = ?",
            (campaign_id, versao),
        ).fetchone()
    return json.loads(row["payload"]) if row else None


def list_copy_versions(campaign_id: str) -> list[int]:
    """Lista os números de versão de copy disponíveis (ordem crescente)."""
    with connect() as con:
        rows = con.execute(
            "SELECT versao FROM copy_versions WHERE campaign_id = ? ORDER BY versao",
            (campaign_id,),
        ).fetchall()
    return [r["versao"] for r in rows]


# --------------------------------------------------------------------------
# Migration: arquivos antigos -> DB
# --------------------------------------------------------------------------
def migrate_from_files() -> dict:
    """
    Varre campaigns/*/state.json + briefing.json + copy_v*.json e popula o DB.

    Idempotente: campanhas já existentes no DB são ignoradas. Arquivos NÃO são
    apagados — ficam como backup natural até o Enzo decidir limpar.

    Returns:
        {"campaigns_inseridas": int, "copy_versions_inseridas": int, "ignoradas": int}.
    """
    init_db()
    stats = {"campaigns_inseridas": 0, "copy_versions_inseridas": 0, "ignoradas": 0}

    if not settings.CAMPAIGNS_DIR.exists():
        return stats

    for camp_dir in sorted(settings.CAMPAIGNS_DIR.iterdir()):
        if not camp_dir.is_dir():
            continue
        state_p = camp_dir / "state.json"
        briefing_p = camp_dir / "briefing.json"
        if not state_p.exists() or not briefing_p.exists():
            continue

        cid = camp_dir.name
        if campaign_id_exists(cid):
            stats["ignoradas"] += 1
            continue

        try:
            briefing = json.loads(briefing_p.read_text(encoding="utf-8"))
            state = json.loads(state_p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue  # arquivo corrompido — pula em silêncio (não trava migration)

        # INSERT direto com TODAS as colunas (combina briefing + state)
        from datetime import datetime
        agora = datetime.now().isoformat(timespec="seconds")
        valores = {
            "campaign_id": cid,
            "area_direito": briefing.get("area_direito", ""),
            "perfil_cliente_ideal": briefing.get("perfil_cliente_ideal", ""),
            "tom": briefing.get("tom", "tecnico"),
            "objetivo": briefing.get("objetivo", "posicionamento"),
            "tema_especifico": briefing.get("tema_especifico", "") or "",
            "formato": briefing.get("formato", "square"),
            "num_slides": int(briefing.get("num_slides", 1)),
            "referencias": briefing.get("referencias", "") or "",
            "created_at": briefing.get("created_at", agora),
            "status": state.get("status", "aguardando_aprovacao"),
            "etapa": state.get("etapa"),
            "copy_version": int(state.get("copy_version", 1)),
            "option_aprovada": state.get("option_aprovada"),
            "data_agendada": state.get("data_agendada"),
            "erro": state.get("erro"),
            "atualizado_em": state.get("atualizado_em", agora),
        }
        cols = ", ".join(CAMPAIGN_COLUMNS)
        placeholders = ", ".join(f":{c}" for c in CAMPAIGN_COLUMNS)
        with connect() as con:
            con.execute(
                f"INSERT INTO campaigns ({cols}) VALUES ({placeholders})", valores
            )
        stats["campaigns_inseridas"] += 1

        # Migra todas as copy_v*.json desta campanha
        for cp in sorted(camp_dir.glob("copy_v*.json")):
            try:
                versao = int(cp.stem.removeprefix("copy_v"))
                opcoes = json.loads(cp.read_text(encoding="utf-8"))
            except (ValueError, json.JSONDecodeError, OSError):
                continue
            save_copy_version(cid, versao, opcoes)
            stats["copy_versions_inseridas"] += 1

    return stats


# --------------------------------------------------------------------------
# Templates de briefing (presets reutilizáveis)
# --------------------------------------------------------------------------
def _row_to_template(row: sqlite3.Row) -> dict:
    """Converte sqlite3.Row -> dict (formato de template)."""
    return {k: row[k] for k in row.keys()}


def list_templates() -> list[dict]:
    """Lista todos os templates em ordem alfabética por nome."""
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM briefing_templates ORDER BY nome COLLATE NOCASE"
        ).fetchall()
    return [_row_to_template(r) for r in rows]


def get_template(template_id: int) -> dict | None:
    """Lê um template por id (None se não existir)."""
    with connect() as con:
        row = con.execute(
            "SELECT * FROM briefing_templates WHERE id = ?", (template_id,)
        ).fetchone()
    return _row_to_template(row) if row else None


def save_template(nome: str, dados: dict) -> dict:
    """
    Cria ou atualiza um template (UPSERT por nome — case-sensitive).

    Args:
        nome: nome único do template.
        dados: dicionário com chaves de TEMPLATE_FIELDS (exceto 'nome').

    Returns:
        Template recém-salvo (com id e created_at).

    Raises:
        ValueError: se um campo desconhecido for passado.
    """
    from datetime import datetime
    desconhecidos = set(dados) - set(TEMPLATE_FIELDS) - {"nome"}
    if desconhecidos:
        raise ValueError(f"Campos desconhecidos em template: {sorted(desconhecidos)}")

    valores = {
        "nome": nome,
        "area_direito": dados.get("area_direito", "") or "",
        "perfil_cliente_ideal": dados.get("perfil_cliente_ideal", "") or "",
        "tom": dados.get("tom", "tecnico") or "tecnico",
        "objetivo": dados.get("objetivo", "posicionamento") or "posicionamento",
        "formato": dados.get("formato", "square") or "square",
        "num_slides": int(dados.get("num_slides", 1) or 1),
        "tema_especifico": dados.get("tema_especifico", "") or "",
        "referencias": dados.get("referencias", "") or "",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    cols = ", ".join(valores.keys())
    placeholders = ", ".join(f":{c}" for c in valores)
    update_set = ", ".join(
        f"{c} = excluded.{c}" for c in valores if c not in ("nome", "created_at")
    )
    with connect() as con:
        con.execute(
            f"""
            INSERT INTO briefing_templates ({cols}) VALUES ({placeholders})
            ON CONFLICT(nome) DO UPDATE SET {update_set}
            """,
            valores,
        )
        row = con.execute(
            "SELECT * FROM briefing_templates WHERE nome = ?", (nome,)
        ).fetchone()
    return _row_to_template(row)


def delete_template(template_id: int) -> bool:
    """Apaga um template por id. Retorna True se algo foi apagado."""
    with connect() as con:
        cur = con.execute(
            "DELETE FROM briefing_templates WHERE id = ?", (template_id,)
        )
    return cur.rowcount > 0
