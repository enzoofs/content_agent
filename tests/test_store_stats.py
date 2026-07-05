"""Testes de agregações usadas pela página de admin (modules/store.py)."""

from __future__ import annotations

from modules import campaign_store, store


def _briefing(cid: str, brand_slug: str):
    return {
        "campaign_id": cid,
        "created_at": "2099-01-01T00:00:00",
        "area_direito": "x", "perfil_cliente_ideal": "x", "tom": "tecnico",
        "objetivo": "posicionamento", "tema_especifico": "", "formato": "square",
        "num_slides": 1, "referencias": "",
    }


def test_tokens_used_por_brand_agrupa_corretamente():
    campaign_store.criar(_briefing("2099-01-01_stats-mv-1", "mendes_vaz"), brand_slug="mendes_vaz")
    campaign_store.criar(_briefing("2099-01-01_stats-mv-2", "mendes_vaz"), brand_slug="mendes_vaz")
    campaign_store.criar(_briefing("2099-01-01_stats-gui-1", "gui_raw"), brand_slug="gui_raw")

    campaign_store.add_tokens("2099-01-01_stats-mv-1", 1000)
    campaign_store.add_tokens("2099-01-01_stats-mv-2", 2000)
    campaign_store.add_tokens("2099-01-01_stats-gui-1", 500)

    totais = store.tokens_used_por_brand()
    assert totais["mendes_vaz"] == 3000
    assert totais["gui_raw"] == 500


def test_tokens_used_por_brand_vazio_sem_campanhas():
    assert store.tokens_used_por_brand() == {}
