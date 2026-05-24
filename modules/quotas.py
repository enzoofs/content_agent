"""
modules/quotas.py — Política de quotas / prevenção de abuse.

Camada fina entre `store.quota_counts()` (SQL puro) e o `server.py` (HTTP).
Concentra a regra de negócio: o que é "soft warning" vs "hard block",
e qual a mensagem amigável devolvida pra UI.

Single-tenant na fase 1 (MVP). Na fase 2, recebe `tenant_id` e consulta
o plano dele em `tenants.plano` → `settings.PLANOS[plano]`.
"""

from __future__ import annotations

from datetime import date
from typing import TypedDict

from config import settings
from modules import store


class QuotaEstado(TypedDict):
    chave: str            # ex: "campanhas_mes"
    rotulo: str           # ex: "Campanhas neste mês"
    atual: int
    limite: int
    pct: float            # 0.0 a 1.0+ (passa de 1.0 quando estourou)
    nivel: str            # "ok" | "warn" | "block"


class QuotaSnapshot(TypedDict):
    itens: list[QuotaEstado]
    bloqueado: bool       # algum item está em "block"?
    proximo_reset: str    # ISO date — quando reseta a quota de mês


# Rótulos amigáveis pra UI (mantém o `settings.QUOTAS` enxuto).
_ROTULOS = {
    "campanhas_mes":          "Campanhas neste mês",
    "agendadas_futuro":       "Campanhas agendadas no futuro",
    "pendentes_aprovacao":    "Campanhas aguardando aprovação",
    "regeracoes_por_campanha": "Regerações por campanha",
}


def _proximo_primeiro_do_mes() -> str:
    """Próximo dia 1 do mês (quando `campanhas_mes` reseta). ISO date."""
    hoje = date.today()
    ano, mes = (hoje.year + 1, 1) if hoje.month == 12 else (hoje.year, hoje.month + 1)
    return date(ano, mes, 1).isoformat()


def _classifica(atual: int, limite: int) -> str:
    """ok | warn | block. Block é `atual >= limite` — bloqueia próxima criação."""
    if limite <= 0:
        return "ok"
    pct = atual / limite
    if pct >= 1.0:
        return "block"
    if pct >= settings.QUOTA_WARN_THRESHOLD:
        return "warn"
    return "ok"


def snapshot() -> QuotaSnapshot:
    """
    Lê as contagens correntes e devolve o estado de todas as quotas pra UI.

    Usado no GET /api/quotas (mostra banner) e no POST /api/campaigns
    (decisão de bloqueio antes de criar).
    """
    counts = store.quota_counts()
    itens: list[QuotaEstado] = []
    bloqueado = False

    # Apenas as quotas que dependem de contagem global (regeracoes_por_campanha
    # é checada na regeração específica, não aqui).
    for chave in ("campanhas_mes", "agendadas_futuro", "pendentes_aprovacao"):
        atual = counts[chave]
        limite = int(settings.QUOTAS[chave])
        nivel = _classifica(atual, limite)
        if nivel == "block":
            bloqueado = True
        itens.append({
            "chave": chave,
            "rotulo": _ROTULOS[chave],
            "atual": atual,
            "limite": limite,
            "pct": round(atual / limite, 3) if limite else 0.0,
            "nivel": nivel,
        })

    return {
        "itens": itens,
        "bloqueado": bloqueado,
        "proximo_reset": _proximo_primeiro_do_mes(),
    }


class QuotaExcedidaError(Exception):
    """Levantada por verificar_pode_criar/regerar quando estoura a quota."""

    def __init__(self, chave: str, atual: int, limite: int, mensagem: str):
        super().__init__(mensagem)
        self.chave = chave
        self.atual = atual
        self.limite = limite
        self.mensagem = mensagem


def verificar_pode_criar() -> None:
    """
    Garante que o usuário pode criar UMA nova campanha agora.

    Raises:
        QuotaExcedidaError: se qualquer quota global estiver em 'block'.
    """
    snap = snapshot()
    if not snap["bloqueado"]:
        return
    # Pega o primeiro item bloqueado pra mensagem clara
    item = next(i for i in snap["itens"] if i["nivel"] == "block")
    rotulo = item["rotulo"]
    mensagens = {
        "campanhas_mes": (
            f"Limite mensal atingido ({item['atual']}/{item['limite']} campanhas). "
            f"A quota reseta em {snap['proximo_reset']}."
        ),
        "agendadas_futuro": (
            f"Você já tem {item['atual']} campanhas agendadas para datas futuras "
            f"(limite: {item['limite']}). Aprove ou ajuste o calendário antes de criar mais."
        ),
        "pendentes_aprovacao": (
            f"Você tem {item['atual']} campanhas aguardando aprovação "
            f"(limite: {item['limite']}). Aprove ou rejeite as pendentes antes de criar novas."
        ),
    }
    raise QuotaExcedidaError(
        chave=item["chave"],
        atual=item["atual"],
        limite=item["limite"],
        mensagem=mensagens.get(item["chave"], f"Quota {rotulo} atingida."),
    )


def verificar_pode_regerar(copy_version_atual: int) -> None:
    """
    Garante que ainda é possível regerar (cada regeração custa $$ em API).

    A regra é por-campanha (não global): copy_version corresponde a quantas
    vezes a campanha foi gerada (1 = primeira, 2 = primeira regeração, etc).

    Raises:
        QuotaExcedidaError: se atingiu o limite.
    """
    limite = int(settings.QUOTAS["regeracoes_por_campanha"])
    # copy_version é a versão *atual* — após regerar, vira atual+1.
    # Bloqueia quando atual >= limite (próxima regeração estouraria).
    if copy_version_atual >= limite:
        raise QuotaExcedidaError(
            chave="regeracoes_por_campanha",
            atual=copy_version_atual,
            limite=limite,
            mensagem=(
                f"Esta campanha já foi regerada {copy_version_atual - 1} vez(es) "
                f"(limite: {limite - 1}). Use a edição manual de copy "
                "ou aprove uma das opções existentes."
            ),
        )
