"""tests/test_publisher.py — Partes puras do publisher.py (sem chamar a Blotato)."""

from __future__ import annotations

from pathlib import Path

import pytest

from config import settings
from modules import publisher


def test_media_urls_monta_url_publica_com_campaign_id_e_arquivo(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "https://exemplo.fly.dev")
    paths = [
        Path("/qualquer/exports/2026-01-01_teste/option1.png"),
        Path("/qualquer/exports/2026-01-01_teste/option1_slide2.png"),
    ]
    urls = publisher._media_urls(paths)
    assert urls == [
        "https://exemplo.fly.dev/exports/2026-01-01_teste/option1.png",
        "https://exemplo.fly.dev/exports/2026-01-01_teste/option1_slide2.png",
    ]


def test_blotato_publisher_sem_chave_falha_cedo(monkeypatch):
    monkeypatch.setattr(settings, "BLOTATO_API_KEY", None)
    with pytest.raises(publisher.PublishError, match="BLOTATO_API_KEY"):
        publisher.BlotatoPublisher()


def test_blotato_publisher_publish_sem_imagens_falha(monkeypatch):
    p = publisher.BlotatoPublisher(api_key="fake-key")
    with pytest.raises(publisher.PublishError, match="sem nenhuma imagem"):
        p.publish(account_id="acc1", caption="oi", image_urls=[])
