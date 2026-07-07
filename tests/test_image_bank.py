"""
tests/test_image_bank.py — Banco de imagens reaproveitáveis (B.5).

Cobre: CRUD em store.image_assets, modules/image_bank.py (copiar/listar/
resolver/deletar arquivo físico), e a integração com pipeline.gerar
(registro automático após geração + reaproveitamento via image_asset_id
pulando Ideogram).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from config import settings
from modules import briefing_parser, campaign_store, image_bank, pipeline, store

CID = "2099-01-02_teste-banco-imagens"


def _briefing(**overrides):
    base = {
        "campaign_id": CID,
        "area_direito": "Direito Médico",
        "perfil_cliente_ideal": "clínicas",
        "tom": "tecnico",
        "objetivo": "posicionamento",
        "tema_especifico": "prontuario",
        "formato": "square",
        "num_slides": 1,
        "referencias": "",
    }
    base.update(overrides)
    return briefing_parser.parse(base)


def _png(path: Path, size=(10, 10)) -> Path:
    Image.new("RGB", size, (10, 20, 30)).save(path)
    return path


def teardown_function():
    shutil.rmtree(settings.CAMPAIGNS_DIR / CID, ignore_errors=True)
    for asset in store.list_image_assets(settings.brand.slug):
        image_bank.deletar(asset["id"])


# --------------------------------------------------------------------------
# store.py — CRUD cru
# --------------------------------------------------------------------------
def test_insert_e_get_image_asset():
    row = store.insert_image_asset(
        asset_id="abc123", brand_slug="mendes_vaz", origem="ideogram",
        formato="square", filename="abc123.png", origem_campaign_id=CID,
    )
    assert row["id"] == "abc123"
    assert store.get_image_asset("abc123")["filename"] == "abc123.png"


def test_list_image_assets_filtra_por_brand():
    store.insert_image_asset("a1", "mendes_vaz", "ideogram", "square", "a1.png")
    store.insert_image_asset("a2", "gui_raw", "upload", "square", "a2.png")
    assert [a["id"] for a in store.list_image_assets("mendes_vaz")] == ["a1"]
    assert [a["id"] for a in store.list_image_assets("gui_raw")] == ["a2"]


def test_delete_image_asset_remove_registro():
    store.insert_image_asset("del1", "mendes_vaz", "upload", "square", "del1.png")
    assert store.delete_image_asset("del1") is True
    assert store.get_image_asset("del1") is None
    assert store.delete_image_asset("del1") is False  # já apagado


# --------------------------------------------------------------------------
# modules/image_bank.py — arquivo físico + DB juntos
# --------------------------------------------------------------------------
def test_registrar_copia_arquivo_e_cria_registro(tmp_path):
    origem = _png(tmp_path / "fundo.png")
    registrados = image_bank.registrar(CID, "square", [origem], "ideogram")

    assert len(registrados) == 1
    asset = registrados[0]
    assert asset["brand_slug"] == settings.brand.slug
    assert asset["origem"] == "ideogram"
    destino = settings.IMAGE_BANK_DIR / asset["filename"]
    assert destino.exists()
    assert destino.read_bytes() == origem.read_bytes()


def test_listar_retorna_assets_do_brand_ativo(tmp_path):
    image_bank.registrar(CID, "square", [_png(tmp_path / "a.png")], "upload")
    assets = image_bank.listar()
    assert len(assets) == 1
    assert assets[0]["formato"] == "square"


def test_resolver_path_encontra_arquivo_existente(tmp_path):
    registrados = image_bank.registrar(CID, "square", [_png(tmp_path / "b.png")], "ideogram")
    asset_id = registrados[0]["id"]
    resolved = image_bank.resolver_path(asset_id)
    assert resolved is not None
    assert resolved.exists()


def test_resolver_path_none_quando_id_nao_existe():
    assert image_bank.resolver_path("id-que-nao-existe") is None


def test_deletar_remove_arquivo_e_registro(tmp_path):
    registrados = image_bank.registrar(CID, "square", [_png(tmp_path / "c.png")], "ideogram")
    asset_id = registrados[0]["id"]
    path = settings.IMAGE_BANK_DIR / registrados[0]["filename"]
    assert path.exists()

    assert image_bank.deletar(asset_id) is True
    assert not path.exists()
    assert store.get_image_asset(asset_id) is None


# --------------------------------------------------------------------------
# Integração com pipeline.gerar
# --------------------------------------------------------------------------
def test_pipeline_registra_imagem_apos_geracao_real(monkeypatch, tmp_path):
    """Formato simples + USE_MOCK_IMAGES=False deve registrar no banco."""
    monkeypatch.setattr(settings, "USE_MOCK_IMAGES", False)
    monkeypatch.setattr(pipeline.copy_generator, "generate", lambda b, nota="", versao=1: [{"option_id": 1}])

    gerado = _png(tmp_path / "gerada.png")
    monkeypatch.setattr(pipeline.image_generator, "generate", lambda ops, fmt, cid: [gerado])
    monkeypatch.setattr(pipeline.composer, "compose_all", lambda ops, imgs, b: [])

    briefing = _briefing()
    campaign_store.criar(briefing)
    pipeline.gerar(briefing)

    assets = image_bank.listar()
    assert len(assets) == 1
    assert assets[0]["origem"] == "ideogram"
    assert assets[0]["origem_campaign_id"] == CID


def test_pipeline_nao_registra_placeholder_mock(monkeypatch, tmp_path):
    """USE_MOCK_IMAGES=True (sem chave Ideogram) não tem valor de reaproveitar."""
    monkeypatch.setattr(settings, "USE_MOCK_IMAGES", True)
    monkeypatch.setattr(pipeline.copy_generator, "generate", lambda b, nota="", versao=1: [{"option_id": 1}])
    monkeypatch.setattr(pipeline.image_generator, "generate", lambda ops, fmt, cid: [_png(tmp_path / "mock.png")])
    monkeypatch.setattr(pipeline.composer, "compose_all", lambda ops, imgs, b: [])

    briefing = _briefing()
    campaign_store.criar(briefing)
    pipeline.gerar(briefing)

    assert image_bank.listar() == []


def test_pipeline_nao_registra_carrossel(monkeypatch, tmp_path):
    """Carrossel gera N imagens por opção — fora de escopo nesta primeira versão."""
    monkeypatch.setattr(settings, "USE_MOCK_IMAGES", False)
    monkeypatch.setattr(
        pipeline.copy_generator, "generate",
        lambda b, nota="", versao=1: [{"option_id": 1, "cta": "x", "slides": [
            {"slide_id": 1, "headline": "h", "body": "b"},
        ]}],
    )
    gerado = _png(tmp_path / "slide.png")
    monkeypatch.setattr(pipeline.image_generator, "generate", lambda ops, fmt, cid: [[gerado]])
    monkeypatch.setattr(pipeline.composer, "compose_all", lambda ops, imgs, b: [])

    briefing = _briefing(formato="carousel", num_slides=3)
    campaign_store.criar(briefing)
    pipeline.gerar(briefing)

    assert image_bank.listar() == []


def test_pipeline_reaproveita_asset_do_banco_pula_ideogram(monkeypatch, tmp_path):
    """image_asset_id setado -> vira upload_path, Ideogram não é chamado."""
    fonte = _png(tmp_path / "fundo_banco.png")
    registrados = image_bank.registrar("outra-campanha", "square", [fonte], "ideogram")
    asset_id = registrados[0]["id"]

    monkeypatch.setattr(pipeline.copy_generator, "generate", lambda b, nota="", versao=1: [{"option_id": 1}])

    chamadas = {}

    def fake_image_generate(ops, fmt, cid, upload_path=None):
        chamadas["upload_path"] = upload_path
        return [upload_path]

    monkeypatch.setattr(pipeline.image_generator, "generate", fake_image_generate)
    monkeypatch.setattr(pipeline.composer, "compose_all", lambda ops, imgs, b: [])
    monkeypatch.setattr(settings, "USE_MOCK_IMAGES", False)

    briefing = _briefing(image_asset_id=asset_id)
    campaign_store.criar(briefing)
    pipeline.gerar(briefing)

    assert chamadas["upload_path"] == settings.IMAGE_BANK_DIR / registrados[0]["filename"]
    # Reaproveitar não deve criar um SEGUNDO registro no banco (só o original).
    assert len(image_bank.listar()) == 1


def test_pipeline_asset_id_invalido_cai_pro_fluxo_normal(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline.copy_generator, "generate", lambda b, nota="", versao=1: [{"option_id": 1}])
    gerado = _png(tmp_path / "fallback.png")
    monkeypatch.setattr(pipeline.image_generator, "generate", lambda ops, fmt, cid, **kw: [gerado])
    monkeypatch.setattr(pipeline.composer, "compose_all", lambda ops, imgs, b: [])
    monkeypatch.setattr(settings, "USE_MOCK_IMAGES", True)

    briefing = _briefing(image_asset_id="id-que-nao-existe-mais")
    campaign_store.criar(briefing)
    # Não deve lançar exceção — cai pro fluxo normal (Ideogram/mock).
    pipeline.gerar(briefing)
    assert campaign_store.read_state(CID)["status"] == "aguardando_aprovacao"
