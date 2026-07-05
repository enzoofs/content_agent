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
    atualizado_em         TEXT    NOT NULL,
    tokens_used           INTEGER NOT NULL DEFAULT 0,
    hide_overlay          INTEGER NOT NULL DEFAULT 0,
    upload_filename       TEXT,
    brand_slug            TEXT    NOT NULL DEFAULT 'mendes_vaz'
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
CREATE INDEX IF NOT EXISTS idx_campaigns_brand_slug ON campaigns(brand_slug);
CREATE INDEX IF NOT EXISTS idx_campaigns_brand_status ON campaigns(brand_slug, status);

-- Templates de briefing: preset reutilizável para acelerar criação de campanhas.
-- Guarda apenas os campos do briefing — não vira campanha sozinho.
-- nome é único POR BRAND (dois clientes podem ter um template com o mesmo nome).
CREATE TABLE IF NOT EXISTS briefing_templates (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    nome                  TEXT    NOT NULL,
    brand_slug            TEXT    NOT NULL DEFAULT 'mendes_vaz',
    area_direito          TEXT    NOT NULL DEFAULT '',
    perfil_cliente_ideal  TEXT    NOT NULL DEFAULT '',
    tom                   TEXT    NOT NULL DEFAULT 'tecnico',
    objetivo              TEXT    NOT NULL DEFAULT 'posicionamento',
    formato               TEXT    NOT NULL DEFAULT 'square',
    num_slides            INTEGER NOT NULL DEFAULT 1,
    tema_especifico       TEXT    NOT NULL DEFAULT '',
    referencias           TEXT    NOT NULL DEFAULT '',
    created_at            TEXT    NOT NULL,
    UNIQUE(brand_slug, nome)
);

-- Usuários de login. brand_slug é NULL só pra role='admin' (enxerga todos os brands).
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT    NOT NULL UNIQUE,
    senha_hash  TEXT    NOT NULL,
    brand_slug  TEXT,
    role        TEXT    NOT NULL DEFAULT 'cliente',
    created_at  TEXT    NOT NULL
);
"""

# Colunas editáveis de briefing_templates (id e created_at são geridos pelo DB;
# brand_slug é setado pelo servidor a partir da sessão, nunca vem do cliente).
TEMPLATE_FIELDS = (
    "nome", "area_direito", "perfil_cliente_ideal", "tom", "objetivo",
    "formato", "num_slides", "tema_especifico", "referencias",
)

# Colunas de campaigns na ORDEM EXATA do schema. Usado para INSERT/UPDATE.
CAMPAIGN_COLUMNS = (
    "campaign_id", "area_direito", "perfil_cliente_ideal", "tom", "objetivo",
    "tema_especifico", "formato", "num_slides", "referencias", "created_at",
    "status", "etapa", "copy_version", "option_aprovada", "data_agendada",
    "erro", "atualizado_em", "tokens_used",
    "hide_overlay", "upload_filename", "brand_slug",
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
        # Migration idempotente: adiciona colunas novas em DBs antigos.
        cols = {r["name"] for r in con.execute("PRAGMA table_info(campaigns)").fetchall()}
        if "tokens_used" not in cols:
            con.execute(
                "ALTER TABLE campaigns ADD COLUMN tokens_used INTEGER NOT NULL DEFAULT 0"
            )
        if "hide_overlay" not in cols:
            con.execute(
                "ALTER TABLE campaigns ADD COLUMN hide_overlay INTEGER NOT NULL DEFAULT 0"
            )
        if "upload_filename" not in cols:
            con.execute(
                "ALTER TABLE campaigns ADD COLUMN upload_filename TEXT"
            )
        if "brand_slug" not in cols:
            con.execute(
                "ALTER TABLE campaigns ADD COLUMN brand_slug TEXT NOT NULL DEFAULT 'mendes_vaz'"
            )

        # briefing_templates: DBs antigos ganham a coluna, mas o SQLite não
        # permite ALTER TABLE pra trocar a constraint UNIQUE(nome) existente
        # por UNIQUE(brand_slug, nome) sem recriar a tabela. Como só existe
        # 1 brand em produção hoje, isso é um gap de baixo risco documentado
        # aqui — só viraria problema se dois brands quisessem um template
        # com o MESMO nome num DB que já existia antes desta migration.
        tpl_cols = {r["name"] for r in con.execute("PRAGMA table_info(briefing_templates)").fetchall()}
        if "brand_slug" not in tpl_cols:
            con.execute(
                "ALTER TABLE briefing_templates ADD COLUMN brand_slug TEXT NOT NULL DEFAULT 'mendes_vaz'"
            )


# Alias retrocompat com nomes legados
init_schema = init_db


# --------------------------------------------------------------------------
# Operações de campanha
# --------------------------------------------------------------------------
def _row_to_state(row: sqlite3.Row) -> dict:
    """Converte sqlite3.Row -> dict (igual ao formato antigo do state.json)."""
    return {k: row[k] for k in row.keys()}


def insert_campaign(
    briefing: dict, status: str = "gerando", etapa: str = "copy",
    *, brand_slug: str,
) -> dict:
    """
    Cria registro de campanha a partir do briefing validado.

    Args:
        briefing: saída de briefing_parser.parse.
        status, etapa: estado inicial (padrão: gerando/copy).
        brand_slug: brand dono da campanha. Sempre derivado server-side da
            sessão do usuário logado (nunca do corpo da requisição) — é a
            fronteira de isolamento entre clientes.

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
        "tokens_used": 0,
        "hide_overlay": int(briefing.get("hide_overlay") or 0),
        "upload_filename": briefing.get("upload_filename") or None,
        "brand_slug": brand_slug,
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


def delete_campaign(campaign_id: str) -> bool:
    """
    Apaga a campanha e suas copy_versions (cascade via FK).

    Returns:
        True se algo foi apagado, False se a campanha não existia.
    """
    with connect() as con:
        cur = con.execute(
            "DELETE FROM campaigns WHERE campaign_id = ?", (campaign_id,)
        )
    return cur.rowcount > 0


def list_campaigns(brand_slug: str | None = None) -> list[dict]:
    """
    Lista campanhas, mais recentes primeiro (por created_at desc).

    Args:
        brand_slug: filtra por brand. None = sem filtro (visão "todos os
            brands" do admin) — mantido opcional pra não quebrar chamadas
            existentes antes do wiring de auth (PR2).
    """
    with connect() as con:
        if brand_slug is None:
            rows = con.execute(
                "SELECT * FROM campaigns ORDER BY created_at DESC, campaign_id DESC"
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM campaigns WHERE brand_slug = ? "
                "ORDER BY created_at DESC, campaign_id DESC",
                (brand_slug,),
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
            "tokens_used": int(state.get("tokens_used", 0) or 0),
            "hide_overlay": int(state.get("hide_overlay", 0) or 0),
            "upload_filename": state.get("upload_filename") or None,
            # Importador legado: só existia 1 brand (M&V) na época desses arquivos.
            "brand_slug": "mendes_vaz",
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


def list_templates(brand_slug: str | None = None) -> list[dict]:
    """
    Lista templates em ordem alfabética por nome.

    Args:
        brand_slug: filtra por brand. None = sem filtro — opcional pra não
            quebrar chamadas existentes antes do wiring de auth (PR2).
    """
    with connect() as con:
        if brand_slug is None:
            rows = con.execute(
                "SELECT * FROM briefing_templates ORDER BY nome COLLATE NOCASE"
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM briefing_templates WHERE brand_slug = ? "
                "ORDER BY nome COLLATE NOCASE",
                (brand_slug,),
            ).fetchall()
    return [_row_to_template(r) for r in rows]


def get_template(template_id: int) -> dict | None:
    """Lê um template por id (None se não existir)."""
    with connect() as con:
        row = con.execute(
            "SELECT * FROM briefing_templates WHERE id = ?", (template_id,)
        ).fetchone()
    return _row_to_template(row) if row else None


def save_template(nome: str, dados: dict, brand_slug: str = "mendes_vaz") -> dict:
    """
    Cria ou atualiza um template (UPSERT por (brand_slug, nome) — case-sensitive).

    Args:
        nome: nome do template (único dentro do brand).
        dados: dicionário com chaves de TEMPLATE_FIELDS (exceto 'nome').
        brand_slug: brand dono do template — sempre derivado server-side da
            sessão, nunca de `dados` (mantém default pra não quebrar
            chamadas existentes antes do wiring de auth em PR2).

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
        "brand_slug": brand_slug,
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
        f"{c} = excluded.{c}" for c in valores
        if c not in ("nome", "brand_slug", "created_at")
    )
    with connect() as con:
        con.execute(
            f"""
            INSERT INTO briefing_templates ({cols}) VALUES ({placeholders})
            ON CONFLICT(brand_slug, nome) DO UPDATE SET {update_set}
            """,
            valores,
        )
        row = con.execute(
            "SELECT * FROM briefing_templates WHERE brand_slug = ? AND nome = ?",
            (brand_slug, nome),
        ).fetchone()
    return _row_to_template(row)


def delete_template(template_id: int, brand_slug: str | None = None) -> bool:
    """
    Apaga um template por id. Retorna True se algo foi apagado.

    Args:
        brand_slug: se informado, só apaga se o template pertencer a esse
            brand (evita um cliente apagar template de outro por id direto).
            None = sem checagem de posse (compat pré-PR2).
    """
    with connect() as con:
        if brand_slug is None:
            cur = con.execute(
                "DELETE FROM briefing_templates WHERE id = ?", (template_id,)
            )
        else:
            cur = con.execute(
                "DELETE FROM briefing_templates WHERE id = ? AND brand_slug = ?",
                (template_id, brand_slug),
            )
    return cur.rowcount > 0


# --------------------------------------------------------------------------
# Quotas / uso (single-tenant — vira por-tenant na fase 2)
# --------------------------------------------------------------------------
def quota_counts(brand_slug: str | None = None) -> dict[str, int]:
    """
    Calcula as contagens correntes de uso pra confronto com as quotas.

    Args:
        brand_slug: filtra por brand. None = global sem filtro — mantido
            opcional pra não quebrar chamadas existentes antes do wiring de
            auth (PR2), onde cada brand passa a ter sua própria contagem.

    Retorna dict com:
      - campanhas_mes: criadas no mês corrente (UTC simples — ISO date prefix)
      - agendadas_futuro: campanhas com data_agendada > hoje
      - pendentes_aprovacao: status ∈ {gerando, ajuste_solicitado, aguardando_aprovacao}
    """
    from datetime import date
    hoje = date.today().isoformat()
    mes_prefix = hoje[:7]  # YYYY-MM
    brand_filtro = "AND brand_slug = ?" if brand_slug is not None else ""
    brand_args = (brand_slug,) if brand_slug is not None else ()

    with connect() as con:
        row_mes = con.execute(
            f"SELECT COUNT(*) AS n FROM campaigns WHERE substr(created_at,1,7) = ? {brand_filtro}",
            (mes_prefix, *brand_args),
        ).fetchone()
        row_futuro = con.execute(
            "SELECT COUNT(*) AS n FROM campaigns WHERE data_agendada IS NOT NULL "
            f"AND data_agendada > ? {brand_filtro}",
            (hoje, *brand_args),
        ).fetchone()
        row_pendentes = con.execute(
            "SELECT COUNT(*) AS n FROM campaigns "
            f"WHERE status IN ('gerando','ajuste_solicitado','aguardando_aprovacao') {brand_filtro}",
            brand_args,
        ).fetchone()

    return {
        "campanhas_mes": int(row_mes["n"]),
        "agendadas_futuro": int(row_futuro["n"]),
        "pendentes_aprovacao": int(row_pendentes["n"]),
    }


def find_orphan_campaigns(threshold_seconds: int = 300) -> list[str]:
    """
    Lista campanhas com status='gerando' cujo atualizado_em é mais antigo que
    threshold_seconds. Indicador de thread daemon que morreu (kill do processo,
    OOM, crash de Playwright) — devem ser marcadas como erro no startup.
    """
    from datetime import datetime, timedelta
    limite = (datetime.now() - timedelta(seconds=threshold_seconds)).isoformat(timespec="seconds")
    with connect() as con:
        rows = con.execute(
            "SELECT campaign_id FROM campaigns "
            "WHERE status = 'gerando' AND atualizado_em < ?",
            (limite,),
        ).fetchall()
    return [r["campaign_id"] for r in rows]
