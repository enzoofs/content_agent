"""
modules/campaign_store.py — API de domínio sobre o estado das campanhas.

Antes: única fonte da verdade era `campaigns/{id}/state.json`. Agora delega o
armazenamento para `modules.store` (SQLite). A API pública é a MESMA — os
demais módulos (pipeline, server, exporter, image_generator) seguem inalterados.

Estados possíveis (status):
    gerando | aguardando_aprovacao | aprovada | ajuste_solicitado | erro

Durante "gerando", o campo `etapa` indica o progresso fino:
    copy | arte | composicao

Histórico de copy: a cada regerar() o pipeline chama next_copy_version(),
preservando as versões anteriores em copy_versions (tabela do DB).
"""

from __future__ import annotations

from datetime import date

from modules import store, utils

STATES = {"gerando", "aguardando_aprovacao", "aprovada", "ajuste_solicitado", "erro"}
ETAPAS = {"copy", "arte", "composicao"}


# --------------------------------------------------------------------------
# Helpers de path (mantidos para compatibilidade com chamadas legadas/tests)
# --------------------------------------------------------------------------
def state_path(campaign_id: str):
    """DEPRECATED — mantido só para testes legados. SQLite não usa arquivo de estado."""
    from config import settings
    return settings.CAMPAIGNS_DIR / campaign_id / "state.json"


def copy_path(campaign_id: str, versao: int):
    """DEPRECATED — copy agora vive em copy_versions (DB). Mantido p/ testes legados."""
    from config import settings
    return settings.CAMPAIGNS_DIR / campaign_id / f"copy_v{versao}.json"


# --------------------------------------------------------------------------
# Leitura/escrita de estado (interface antiga preservada)
# --------------------------------------------------------------------------
def read_state(campaign_id: str) -> dict | None:
    """Lê o estado da campanha; None se não existir."""
    return store.get_campaign(campaign_id)


def write_state(campaign_id: str, **campos) -> dict:
    """
    Faz merge dos campos no estado da campanha. Cria automaticamente o registro
    mínimo se ainda não existir (compat com fluxo legado em que write_state era
    chamado antes do criar() em alguns testes).

    Retorna o estado resultante. Thread-safe via SQLite WAL.
    """
    existente = store.get_campaign(campaign_id)
    if existente is None:
        # Cria registro mínimo (campos obrigatórios com placeholders) — depois faz update
        from datetime import datetime
        from config import settings  # noqa: F401 — só para reforçar dependência ordem-de-import
        agora = datetime.now().isoformat(timespec="seconds")
        store.insert_campaign(
            {
                "campaign_id": campaign_id,
                "area_direito": "(desconhecido)",
                "perfil_cliente_ideal": "(desconhecido)",
                "tom": "tecnico",
                "objetivo": "posicionamento",
                "tema_especifico": "",
                "formato": "square",
                "num_slides": 1,
                "referencias": "",
                "created_at": agora,
            },
            status=campos.get("status", "gerando"),
            etapa=campos.get("etapa", "copy"),
        )
    return store.update_campaign(campaign_id, **campos)


def criar(briefing: dict) -> dict:
    """
    Cria a campanha no DB com (status=gerando, etapa=copy, copy_version=1).
    """
    store.init_schema()  # garante schema na 1ª chamada (testes/fluxos isolados)
    return store.insert_campaign(briefing, status="gerando", etapa="copy")


def set_etapa(campaign_id: str, etapa: str) -> None:
    """Marca o progresso fino durante a geração (status volta a gerando)."""
    write_state(campaign_id, status="gerando", etapa=etapa, erro=None)


def marcar_aguardando(campaign_id: str) -> None:
    """Geração concluída — pronta para aprovação."""
    write_state(campaign_id, status="aguardando_aprovacao", etapa=None)


def set_erro(campaign_id: str, mensagem: str) -> None:
    """Registra falha na geração."""
    write_state(campaign_id, status="erro", erro=mensagem)


def marcar_aprovada(campaign_id: str, option_id: int, data_agendada: str | None = None) -> None:
    """Marca a campanha como aprovada, com a opção escolhida e a data agendada."""
    write_state(
        campaign_id,
        status="aprovada",
        option_aprovada=option_id,
        data_agendada=data_agendada,
    )


def agendar(campaign_id: str, data_str: str) -> None:
    """
    Registra a data de agendamento (formato ISO YYYY-MM-DD).

    Raises:
        ValueError: se a data for inválida ou estiver no passado.
    """
    try:
        d = date.fromisoformat(data_str)
    except ValueError as e:
        raise ValueError(f"Data agendada inválida: {data_str!r} ({e}).") from e
    if d < date.today():
        raise ValueError(f"Data agendada não pode estar no passado: {data_str}.")
    write_state(campaign_id, data_agendada=data_str)


def listar() -> list[dict]:
    """
    Lista todas as campanhas (mais recentes primeiro), com o briefing aninhado.

    O formato {**estado, "briefing": briefing} é mantido para preservar o
    contrato com o dashboard da UI.
    """
    resultado: list[dict] = []
    for campanha in store.list_campaigns():
        briefing = {
            "campaign_id": campanha["campaign_id"],
            "area_direito": campanha["area_direito"],
            "perfil_cliente_ideal": campanha["perfil_cliente_ideal"],
            "tom": campanha["tom"],
            "objetivo": campanha["objetivo"],
            "tema_especifico": campanha["tema_especifico"] or "",
            "formato": campanha["formato"],
            "num_slides": campanha["num_slides"],
            "referencias": campanha["referencias"] or "",
            "created_at": campanha["created_at"],
        }
        resultado.append({**campanha, "briefing": briefing})
    return resultado


def read_briefing(campaign_id: str) -> dict | None:
    """Reconstrói o briefing a partir da row da campanha (compat com pipeline.regerar/server/exporter)."""
    c = store.get_campaign(campaign_id)
    if c is None:
        return None
    return {
        "campaign_id": c["campaign_id"],
        "area_direito": c["area_direito"],
        "perfil_cliente_ideal": c["perfil_cliente_ideal"],
        "tom": c["tom"],
        "objetivo": c["objetivo"],
        "tema_especifico": c["tema_especifico"] or "",
        "formato": c["formato"],
        "num_slides": c["num_slides"],
        "referencias": c["referencias"] or "",
        "created_at": c["created_at"],
    }


# --------------------------------------------------------------------------
# Versionamento de copy
# --------------------------------------------------------------------------
def get_copy_version(campaign_id: str) -> int:
    """Versão atual do copy (default 1)."""
    c = store.get_campaign(campaign_id)
    return int(c["copy_version"]) if c else 1


def next_copy_version(campaign_id: str) -> int:
    """Incrementa a versão e persiste. Usado pelo pipeline ao regerar."""
    nova = get_copy_version(campaign_id) + 1
    write_state(campaign_id, copy_version=nova)
    return nova


def save_copy_version(
    campaign_id: str, versao: int, opcoes: list[dict], nota_ajuste: str = "",
) -> None:
    """Persiste uma versão de copy no DB. Usado pelo copy_generator."""
    store.save_copy_version(campaign_id, versao, opcoes, nota_ajuste)


def get_copy(campaign_id: str, versao: int | None = None) -> list[dict] | None:
    """
    Lê uma versão de copy do DB. Se `versao` for None, usa a versão corrente.

    Usado por server._campaign_payload e exporter.export_approved.
    """
    if versao is None:
        versao = get_copy_version(campaign_id)
    return store.get_copy_version(campaign_id, versao)


# Mantém o import de utils para não quebrar arquivos que dependiam transitive dele
_ = utils  # noqa: F841
