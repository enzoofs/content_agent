"""
modules/campaign_store.py — Fonte da verdade do estado das campanhas.

Único módulo que lê/escreve `campaigns/{id}/state.json`. Os demais módulos
(server, pipeline) passam por aqui para mudar estado, evitando escrita
descoordenada do arquivo.

Estados possíveis (status):
    gerando | aguardando_aprovacao | aprovada | ajuste_solicitado | erro

Durante "gerando", o campo `etapa` indica o progresso fino:
    copy | arte | composicao
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from config import settings
from modules import utils

STATES = {"gerando", "aguardando_aprovacao", "aprovada", "ajuste_solicitado", "erro"}
ETAPAS = {"copy", "arte", "composicao"}


def state_path(campaign_id: str) -> Path:
    """Caminho do state.json da campanha."""
    return settings.CAMPAIGNS_DIR / campaign_id / "state.json"


def read_state(campaign_id: str) -> dict | None:
    """Lê o estado da campanha; None se não existir."""
    p = state_path(campaign_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_state(campaign_id: str, **campos) -> dict:
    """
    Faz merge dos campos no state.json (criando se preciso) e atualiza o
    timestamp `atualizado_em`. Retorna o estado resultante.
    """
    p = state_path(campaign_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    estado = read_state(campaign_id) or {"campaign_id": campaign_id}
    estado.update(campos)
    estado["atualizado_em"] = datetime.now().isoformat(timespec="seconds")
    p.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    return estado


def criar(briefing: dict) -> dict:
    """
    Cria a campanha: salva briefing.json e inicia o state como
    (status=gerando, etapa=copy). Retorna o estado.
    """
    cid = briefing["campaign_id"]
    camp = utils.campaign_dir(cid)
    (camp / "briefing.json").write_text(
        json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return write_state(
        cid,
        status="gerando",
        etapa="copy",
        data_agendada=None,
        option_aprovada=None,
        erro=None,
    )


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
    Lista todas as campanhas (varre campaigns/), juntando state + briefing.
    Ordena por id decrescente (mais recentes primeiro). Ignora pastas sem state.
    """
    resultado: list[dict] = []
    if not settings.CAMPAIGNS_DIR.exists():
        return resultado
    for d in sorted(settings.CAMPAIGNS_DIR.iterdir(), key=lambda p: p.name, reverse=True):
        if not d.is_dir():
            continue
        estado = read_state(d.name)
        if estado is None:
            continue
        briefing = {}
        bp = d / "briefing.json"
        if bp.exists():
            briefing = json.loads(bp.read_text(encoding="utf-8"))
        resultado.append({**estado, "briefing": briefing})
    return resultado
