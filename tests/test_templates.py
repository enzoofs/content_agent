"""
Testes de templates de briefing — modules/store.py + endpoints REST em server.

Cobre:
- CRUD básico (criar, ler, atualizar via UPSERT, apagar)
- UNIQUE por nome (segundo save com mesmo nome substitui)
- Validação de campos desconhecidos
- Endpoints GET/POST/DELETE /api/templates
"""

from __future__ import annotations

import pytest

from modules import server, store


# ---------- Helpers ----------
def _payload() -> dict:
    return {
        "area_direito": "Direito Médico",
        "perfil_cliente_ideal": "clínicas e hospitais",
        "tom": "tecnico",
        "objetivo": "posicionamento",
        "formato": "carousel",
        "num_slides": 5,
        "tema_especifico": "prontuário eletrônico",
        "referencias": "casos recentes",
    }


# ---------- store.py: funções de baixo nível ----------
def test_save_template_cria_com_id_e_timestamp():
    t = store.save_template("Médico Padrão", _payload())
    assert t["id"] > 0
    assert t["nome"] == "Médico Padrão"
    assert t["area_direito"] == "Direito Médico"
    assert t["num_slides"] == 5
    assert t["created_at"]  # ISO timestamp


def test_save_template_upsert_substitui_por_nome():
    """Segundo save com mesmo nome atualiza, mantém id."""
    primeiro = store.save_template("Reuso", _payload())
    atualizado = store.save_template("Reuso", {**_payload(), "area_direito": "Trabalhista"})
    assert atualizado["id"] == primeiro["id"]
    assert atualizado["area_direito"] == "Trabalhista"


def test_list_templates_ordem_alfabetica():
    store.save_template("Zebra", _payload())
    store.save_template("Alfa", _payload())
    nomes = [t["nome"] for t in store.list_templates()]
    assert nomes == sorted(nomes, key=str.lower)


def test_get_template_inexistente_retorna_none():
    assert store.get_template(99999) is None


def test_delete_template_remove():
    t = store.save_template("Pra apagar", _payload())
    assert store.delete_template(t["id"]) is True
    assert store.get_template(t["id"]) is None
    # Segundo delete vira no-op (retorna False)
    assert store.delete_template(t["id"]) is False


def test_save_template_rejeita_campo_desconhecido():
    with pytest.raises(ValueError, match="desconhecid"):
        store.save_template("X", {**_payload(), "foo_invalido": "bar"})


def test_save_template_aplica_defaults_em_campos_omitidos():
    """Salvar payload mínimo deve usar defaults do schema."""
    t = store.save_template("Mínimo", {"area_direito": "Civil"})
    assert t["tom"] == "tecnico"
    assert t["objetivo"] == "posicionamento"
    assert t["formato"] == "square"
    assert t["num_slides"] == 1


# ---------- server.py: endpoints REST ----------
@pytest.fixture
def client():
    app = server.build_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_endpoint_post_cria_template(client):
    res = client.post("/api/templates", json={"nome": "Via API", **_payload()})
    assert res.status_code == 201
    data = res.get_json()
    assert data["nome"] == "Via API"
    assert data["formato"] == "carousel"


def test_endpoint_post_sem_nome_retorna_400(client):
    res = client.post("/api/templates", json=_payload())  # sem 'nome'
    assert res.status_code == 400
    assert "obrigatório" in res.get_json()["erro"]


def test_endpoint_post_nome_em_branco_retorna_400(client):
    res = client.post("/api/templates", json={"nome": "   ", **_payload()})
    assert res.status_code == 400


def test_endpoint_get_lista_templates(client):
    client.post("/api/templates", json={"nome": "T1", **_payload()})
    client.post("/api/templates", json={"nome": "T2", **_payload()})
    res = client.get("/api/templates")
    assert res.status_code == 200
    nomes = [t["nome"] for t in res.get_json()]
    assert "T1" in nomes and "T2" in nomes


def test_endpoint_delete_apaga_template(client):
    res = client.post("/api/templates", json={"nome": "Tchau", **_payload()})
    tid = res.get_json()["id"]

    res = client.delete(f"/api/templates/{tid}")
    assert res.status_code == 200
    assert res.get_json()["status"] == "apagado"

    # Segundo delete vira 404
    res = client.delete(f"/api/templates/{tid}")
    assert res.status_code == 404
