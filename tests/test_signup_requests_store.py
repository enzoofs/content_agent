"""
Testes de modules/signup_requests_store.py — CRUD de solicitações públicas.

Isolamento de DB vem do fixture autouse em conftest.py.
"""

from __future__ import annotations

from modules import signup_requests_store as sreq


def _colors():
    return {"navy": "#111111", "gold": "#EEEEEE", "white": "#FFFFFF",
            "cream": "#DDDDDD", "navy_dark": "#000000"}


def test_criar_solicitacao_status_pendente_por_padrao():
    s = sreq.criar_solicitacao("Acme Ltda", "acme@teste.com", _colors())
    assert s["status"] == "pendente"
    assert s["nome"] == "Acme Ltda"
    assert s["email"] == "acme@teste.com"
    assert s["reviewed_at"] is None
    assert s["reviewed_by"] is None


def test_criar_solicitacao_com_campos_opcionais():
    s = sreq.criar_solicitacao(
        "Beta", "beta@teste.com", _colors(),
        slug_sugerido="beta", logo_filename_pendente="pending_abc.png",
        sobre_negocio="Vendemos widgets.",
    )
    assert s["slug_sugerido"] == "beta"
    assert s["logo_filename_pendente"] == "pending_abc.png"
    assert s["sobre_negocio"] == "Vendemos widgets."


def test_get_by_id_inexistente():
    assert sreq.get_by_id(9999) is None


def test_list_solicitacoes_ordem_mais_recente_primeiro():
    s1 = sreq.criar_solicitacao("Primeira", "p@teste.com", _colors())
    s2 = sreq.criar_solicitacao("Segunda", "s@teste.com", _colors())
    lista = sreq.list_solicitacoes()
    assert lista[0]["id"] == s2["id"]
    assert lista[1]["id"] == s1["id"]


def test_list_solicitacoes_filtra_por_status():
    s1 = sreq.criar_solicitacao("Pendente", "pend@teste.com", _colors())
    s2 = sreq.criar_solicitacao("Vai aprovar", "aprov@teste.com", _colors())
    sreq.marcar_revisada(s2["id"], "aprovado", "admin@teste.com")

    pendentes = sreq.list_solicitacoes("pendente")
    aprovadas = sreq.list_solicitacoes("aprovado")
    assert [s["id"] for s in pendentes] == [s1["id"]]
    assert [s["id"] for s in aprovadas] == [s2["id"]]


def test_marcar_revisada_aprovado():
    s = sreq.criar_solicitacao("X", "x@teste.com", _colors())
    atualizado = sreq.marcar_revisada(s["id"], "aprovado", "admin@teste.com")
    assert atualizado["status"] == "aprovado"
    assert atualizado["reviewed_by"] == "admin@teste.com"
    assert atualizado["reviewed_at"] is not None


def test_marcar_revisada_rejeitado_com_motivo():
    s = sreq.criar_solicitacao("Y", "y@teste.com", _colors())
    atualizado = sreq.marcar_revisada(
        s["id"], "rejeitado", "admin@teste.com", motivo_rejeicao="fora do escopo"
    )
    assert atualizado["status"] == "rejeitado"
    assert atualizado["motivo_rejeicao"] == "fora do escopo"
