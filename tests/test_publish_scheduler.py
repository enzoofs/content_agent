"""
tests/test_publish_scheduler.py — Publicação automática de campanhas
aprovadas (mocka `publisher.publish_campaign`, sem chamar Blotato de verdade).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from config import settings
from modules import campaign_store, publish_scheduler, publisher

CID = "2020-01-01_teste-publish-scheduler"


def _briefing():
    return {
        "campaign_id": CID,
        "created_at": "2020-01-01T00:00:00",
        "area_direito": "Direito Médico",
        "perfil_cliente_ideal": "clínicas",
        "tom": "tecnico",
        "objetivo": "posicionamento",
        "tema_especifico": "teste",
        "formato": "square",
        "num_slides": 1,
        "referencias": "",
    }


def _preparar_export(option_id: int = 1):
    """Cria o metadata.json + 1 PNG falso em exports/<cid>/, como o exporter faria."""
    export_dir = settings.EXPORTS_DIR / CID
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / f"option{option_id}.png").write_bytes(b"PNG")
    metadata = {"caption": "Legenda de teste", "hashtags": ["direito", "saude"]}
    (export_dir / f"option{option_id}_metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    return export_dir


def _limpar_export():
    import shutil
    shutil.rmtree(settings.EXPORTS_DIR / CID, ignore_errors=True)


def test_sem_account_id_configurado_nao_publica_nada(monkeypatch):
    monkeypatch.setattr(settings, "brand", SimpleNamespace(blotato_account_id=""))
    assert publish_scheduler.publicar_pendentes() == 0


def test_publica_campanha_pendente_com_sucesso(monkeypatch):
    monkeypatch.setattr(settings, "brand", SimpleNamespace(blotato_account_id="acc123"))
    campaign_store.criar(_briefing())
    campaign_store.marcar_aprovada(CID, option_id=1, data_agendada="2020-01-01")
    _preparar_export(option_id=1)

    chamadas = []

    def _fake_publish(cid, imagens, caption, account_id):
        chamadas.append((cid, [p.name for p in imagens], caption, account_id))
        return publisher.PublishResult(provider="blotato", external_id="ext1", raw={})

    monkeypatch.setattr(publisher, "publish_campaign", _fake_publish)
    try:
        assert publish_scheduler.publicar_pendentes() == 1
        assert chamadas == [(CID, ["option1.png"], "Legenda de teste\n\n#direito #saude", "acc123")]
        estado = campaign_store.read_state(CID)
        assert estado["publicado_em"] is not None
        assert estado["publish_erro"] is None
    finally:
        _limpar_export()


def test_falha_ao_publicar_registra_erro_sem_marcar_publicada(monkeypatch):
    monkeypatch.setattr(settings, "brand", SimpleNamespace(blotato_account_id="acc123"))
    campaign_store.criar(_briefing())
    campaign_store.marcar_aprovada(CID, option_id=1, data_agendada="2020-01-01")
    _preparar_export(option_id=1)

    def _fake_publish_quebrado(cid, imagens, caption, account_id):
        raise publisher.PublishError("Blotato: 500 Internal Server Error")

    monkeypatch.setattr(publisher, "publish_campaign", _fake_publish_quebrado)
    try:
        assert publish_scheduler.publicar_pendentes() == 0
        estado = campaign_store.read_state(CID)
        assert estado["publicado_em"] is None
        assert "500" in estado["publish_erro"]
    finally:
        _limpar_export()


def test_campanha_ja_publicada_nao_e_republicada(monkeypatch):
    monkeypatch.setattr(settings, "brand", SimpleNamespace(blotato_account_id="acc123"))
    campaign_store.criar(_briefing())
    campaign_store.marcar_aprovada(CID, option_id=1, data_agendada="2020-01-01")
    campaign_store.marcar_publicada(CID)
    _preparar_export(option_id=1)

    def _fake_publish(cid, imagens, caption, account_id):
        raise AssertionError("não deveria ser chamado — campanha já publicada")

    monkeypatch.setattr(publisher, "publish_campaign", _fake_publish)
    try:
        assert publish_scheduler.publicar_pendentes() == 0
    finally:
        _limpar_export()
