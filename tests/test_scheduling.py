"""tests/test_scheduling.py — Heurística de sugestão de data/horário."""

from __future__ import annotations

from datetime import date

from modules import scheduling


def test_suggest_datetime_cai_num_dia_bom():
    sugestao = scheduling.suggest_datetime(hoje=date(2026, 9, 3))  # quinta-feira
    resultado = date.fromisoformat(sugestao["data"])
    assert resultado.weekday() in scheduling._DIAS_BONS


def test_suggest_datetime_respeita_antecedencia_minima():
    hoje = date(2026, 9, 3)
    sugestao = scheduling.suggest_datetime(hoje=hoje, antecedencia_minima_dias=5)
    resultado = date.fromisoformat(sugestao["data"])
    assert (resultado - hoje).days >= 5


def test_suggest_datetime_inclui_horario_e_dia_semana():
    sugestao = scheduling.suggest_datetime(hoje=date(2026, 9, 3))
    assert sugestao["horario"] == "11:00"
    assert sugestao["dia_semana"] in scheduling._NOMES_DIA.values()


def test_suggest_datetime_deterministico_pra_mesma_entrada():
    a = scheduling.suggest_datetime(hoje=date(2026, 9, 3))
    b = scheduling.suggest_datetime(hoje=date(2026, 9, 3))
    assert a == b
