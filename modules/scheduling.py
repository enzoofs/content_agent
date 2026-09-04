"""
modules/scheduling.py — Sugestão de data/horário ideal pra publicar um post.

Item novo do spec de 2026-09-03 (mapa mental do Enzo): "sistema sugere
datas e horário ideais pra post". V1 heurística, sem dados reais de
engajamento ainda (isso é Fase 4 — analytics — no roadmap do projeto,
ver docs/roadmap-e-melhorias.md). Trocar por sugestão data-driven quando
`analytics` de posts publicados existir.

Nota de schema: `campaign_store.agendar()` valida `data_agendada` como
DATA (YYYY-MM-DD), sem componente de horário — o campo `horario` sugerido
aqui é só pra exibir/comunicar (ex: no lembrete do bot), ainda não é
persistido em lugar nenhum. Se quiserem guardar o horário escolhido de
verdade, precisa de uma coluna nova em `campaigns` (fora do escopo deste
módulo, que só sugere).
"""

from __future__ import annotations

from datetime import date, timedelta

# Dias da semana com engajamento historicamente melhor pra conteúdo B2B
# jurídico (heurística de mercado — terça a quinta, fora segunda "de ressaca"
# e sexta/fim de semana "modo desligado"). 0=segunda ... 6=domingo.
_DIAS_BONS = {1, 2, 3}  # terça, quarta, quinta

# Horário sugerido — meio da manhã tardia, quando o público profissional já
# resolveu o email do dia mas ainda não entrou no "modo almoço".
_HORARIO_SUGERIDO = "11:00"

_NOMES_DIA = {
    0: "segunda-feira", 1: "terça-feira", 2: "quarta-feira", 3: "quinta-feira",
    4: "sexta-feira", 5: "sábado", 6: "domingo",
}


def suggest_datetime(hoje: date | None = None, antecedencia_minima_dias: int = 2) -> dict:
    """
    Sugere a próxima data "boa" pra publicar, com pelo menos
    `antecedencia_minima_dias` de folga (tempo pra aprovar antes).

    Args:
        hoje: data de referência (default: hoje de verdade — parametrizável
            pra testes determinísticos).
        antecedencia_minima_dias: quantos dias de folga mínima antes da
            data sugerida (default 2 — dá tempo do cliente aprovar).

    Returns:
        dict com `data` (ISO YYYY-MM-DD), `dia_semana` (nome por extenso) e
        `horario` (string "HH:MM", só sugestão — ver nota de schema no
        docstring do módulo).
    """
    hoje = hoje or date.today()
    candidata = hoje + timedelta(days=antecedencia_minima_dias)

    # Anda pra frente até cair num dos dias bons (no máximo 6 passos —
    # sempre encontra um dentro de uma semana).
    for _ in range(7):
        if candidata.weekday() in _DIAS_BONS:
            break
        candidata += timedelta(days=1)

    return {
        "data": candidata.isoformat(),
        "dia_semana": _NOMES_DIA[candidata.weekday()],
        "horario": _HORARIO_SUGERIDO,
    }
