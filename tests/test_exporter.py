"""
Testes de modules/exporter.py — foco na trilha de aprovação (audit log).

Cobre:
- Geração de approval_id único por aprovação
- Append correto no exports/audit.jsonl (JSON Lines)
- Persistência de copy_version no metadata e no audit
- Cada linha do audit é JSON válido e independente
"""

from __future__ import annotations

import json
import shutil

import pytest

from config import settings
from modules import campaign_store, exporter

CID = "2099-01-01_teste-exporter"


def _briefing() -> dict:
    return {
        "campaign_id": CID,
        "created_at": "2099-01-01T00:00:00",
        "area_direito": "Direito Médico",
        "perfil_cliente_ideal": "clínicas",
        "tom": "tecnico",
        "objetivo": "posicionamento",
        "tema_especifico": "prontuario",
        "formato": "square",
        "num_slides": 1,
        "referencias": "",
    }


def _copy_options() -> list[dict]:
    """3 variações mínimas válidas para o exporter consumir."""
    return [
        {
            "option_id": i,
            "headline": f"Headline {i}",
            "subheadline": "",
            "body": f"Body {i}",
            "caption": f"Caption {i}",
            "cta": "Saiba mais",
            "hashtags": ["direitomedico", "bh"],
            "image_prompt": "elegant office",
            "style_notes": "",
        }
        for i in (1, 2, 3)
    ]


@pytest.fixture
def campanha_pronta(monkeypatch, tmp_path):
    """
    Sandbox: redireciona CAMPAIGNS_DIR e EXPORTS_DIR pra tmp, monta a campanha
    (briefing + copy v1) no DB e cria 3 PNGs compostos fake. Limpa no teardown.
    """
    campaigns_tmp = tmp_path / "campaigns"
    exports_tmp = tmp_path / "exports"
    campaigns_tmp.mkdir()
    exports_tmp.mkdir()

    monkeypatch.setattr(settings, "CAMPAIGNS_DIR", campaigns_tmp)
    monkeypatch.setattr(settings, "EXPORTS_DIR", exports_tmp)
    # AUDIT_LOG_PATH foi resolvido na importação do módulo — repointa em runtime
    monkeypatch.setattr(exporter, "AUDIT_LOG_PATH", exports_tmp / "audit.jsonl")

    # Cria a campanha no DB e os PNGs compostos no FS
    camp_dir = campaigns_tmp / CID
    composed_dir = camp_dir / "composed"
    composed_dir.mkdir(parents=True)

    campaign_store.criar(_briefing())
    campaign_store.save_copy_version(CID, 1, _copy_options())
    campaign_store.marcar_aguardando(CID)

    # PNGs fake (conteúdo qualquer — o exporter só faz copyfile)
    for i in (1, 2, 3):
        (composed_dir / f"option_{i}.png").write_bytes(b"\x89PNG fake")

    yield camp_dir

    shutil.rmtree(camp_dir, ignore_errors=True)


def _ler_audit() -> list[dict]:
    """Lê o audit.jsonl como lista de dicts (uma linha = um evento)."""
    linhas = exporter.AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(l) for l in linhas if l.strip()]


# --------------------------------------------------------------------------
# Trilha de aprovação — audit.jsonl
# --------------------------------------------------------------------------
def test_aprovacao_gera_linha_no_audit(campanha_pronta):
    """Uma aprovação deve gerar uma linha no audit com os campos esperados."""
    exporter.export_approved(CID, option_id=2)

    eventos = _ler_audit()
    assert len(eventos) == 1
    e = eventos[0]
    # Campos obrigatórios
    for campo in ("approval_id", "campaign_id", "option_id", "copy_version",
                  "approved_at", "approved_by", "formato"):
        assert campo in e, f"campo {campo!r} ausente no audit"
    assert e["campaign_id"] == CID
    assert e["option_id"] == 2
    assert e["copy_version"] == 1
    assert e["approved_by"] == settings.APPROVED_BY
    assert e["formato"] == "square"


def test_duas_aprovacoes_geram_dois_uuids_distintos(campanha_pronta):
    """Cada aprovação tem approval_id único, mesmo que opção/campanha repita."""
    exporter.export_approved(CID, option_id=1)
    exporter.export_approved(CID, option_id=1)  # mesma opção, segunda aprovação

    eventos = _ler_audit()
    assert len(eventos) == 2
    ids = {e["approval_id"] for e in eventos}
    assert len(ids) == 2, "approval_id deveria ser único por aprovação"


def test_audit_log_e_jsonl_valido(campanha_pronta):
    """Cada linha é JSON independente; uma linha quebrada não corromperia o resto."""
    for opt in (1, 2, 3):
        exporter.export_approved(CID, option_id=opt)

    texto = exporter.AUDIT_LOG_PATH.read_text(encoding="utf-8")
    linhas = [l for l in texto.splitlines() if l.strip()]
    assert len(linhas) == 3
    # Cada linha parseia isoladamente
    for l in linhas:
        json.loads(l)  # não levanta


def test_metadata_da_campanha_inclui_approval_id_e_copy_version(campanha_pronta):
    """O JSON de metadados por campanha também recebe approval_id e copy_version."""
    export = exporter.export_approved(CID, option_id=3)
    meta_path = export["metadata"]

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert "approval_id" in meta
    assert meta["copy_version"] == 1
    assert meta["option_id"] == 3

    # E o approval_id no metadata bate com o do audit
    eventos = _ler_audit()
    assert eventos[0]["approval_id"] == meta["approval_id"]


def test_export_gera_post_txt_copiavel(campanha_pronta):
    """post.txt deve conter headline, body, caption e hashtags com # — pronto pra colar."""
    export = exporter.export_approved(CID, option_id=2)
    txt = export["post_txt"].read_text(encoding="utf-8")
    assert "Headline 2" in txt
    assert "Body 2" in txt
    assert "Caption 2" in txt
    assert "#direitomedico" in txt
    assert "CTA: Saiba mais" in txt
