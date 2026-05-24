"""
test_pipeline.py — Teste de smoke (integração) do pipeline.

Roda o pipeline com copy mockado (SEM OpenAI) e imagens mock (SEM Ideogram),
mas com composição REAL (Playwright) e API real do server. Verifica que os
arquivos de saída são criados. Conforme seção 9 da spec.

Rodar:
    pytest test_pipeline.py
    # ou diretamente:
    python test_pipeline.py
"""

from __future__ import annotations

import json
import shutil

from config import settings
from modules import (
    briefing_parser,
    campaign_store,
    composer,
    exporter,
    image_generator,
    server,
    store,
)


def _mock_copy_options() -> list[dict]:
    """3 variações de copy fixas (substituem a chamada à OpenAI)."""
    base = {
        "subheadline": "Direito Médico · BH",
        "body": "Prevenir litígios começa por contratos sólidos e compliance bem estruturado.",
        "caption": "No direito médico, a prevenção vale mais que a melhor defesa. " * 5,
        "cta": "Fale com um especialista",
        "hashtags": ["direitomedico", "advocaciabh", "compliance"],
        "image_prompt": "elegant modern law office, two professionals in serious conversation",
        "style_notes": "tom institucional",
    }
    return [
        {"option_id": i, "headline": f"Variação {i}: seu hospital está protegido?", **base}
        for i in (1, 2, 3)
    ]


def test_smoke_pipeline_mocked():
    """Pipeline completo com mocks deve produzir os 3 PNGs compostos e exportar."""
    briefing = briefing_parser.parse({
        "area_direito": "Direito Médico",
        "perfil_cliente_ideal": "Médicos e clínicas em BH",
        "tom": "tecnico",
        "objetivo": "posicionamento",
        "formato": "square",
        "num_slides": 1,
        "tema_especifico": "smoke test",
        "referencias": "",
    })
    campaign_id = briefing["campaign_id"]

    # Força modo mock de imagens (há chave Ideogram no ambiente; não gastar créditos)
    mock_original = settings.USE_MOCK_IMAGES
    settings.USE_MOCK_IMAGES = True

    # Garante DB inicializado (testes que rodam diretamente, fora da fixture autouse)
    store.init_db()

    try:
        # Cria campanha no DB e salva copy mockado direto no DB
        campaign_store.criar(briefing)
        copy_options = _mock_copy_options()
        campaign_store.save_copy_version(campaign_id, 1, copy_options)

        # Imagens mock
        image_paths = image_generator.generate(copy_options, "square", campaign_id)
        assert len(image_paths) == 3
        for p in image_paths:
            assert p.exists() and p.stat().st_size > 0

        # Composição real (Playwright)
        composed = composer.compose_all(copy_options, image_paths, briefing)
        assert len(composed) == 3
        for p in composed:
            assert p.exists() and p.stat().st_size > 0
        campaign_store.marcar_aguardando(campaign_id)

        # API da central (sem subir servidor real)
        client = server.build_app().test_client()
        resp = client.get(f"/api/campaigns/{campaign_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["options"]) == 3
        assert data["state"]["status"] == "aguardando_aprovacao"

        # Export
        export = exporter.export_approved(campaign_id, 2)
        assert export["png"].exists() and export["metadata"].exists()
        assert export["post_txt"].exists()  # texto pronto-pra-postar
        metadata = json.loads(export["metadata"].read_text(encoding="utf-8"))
        assert metadata["option_id"] == 2
        assert metadata["ready_for_posting"] is True

        print("✅ Smoke test OK — 3 imagens, 3 composições, export da opção 2.")

    finally:
        settings.USE_MOCK_IMAGES = mock_original
        shutil.rmtree(settings.CAMPAIGNS_DIR / campaign_id, ignore_errors=True)
        for f in settings.EXPORTS_DIR.glob(f"{campaign_id}_*"):
            f.unlink(missing_ok=True)


if __name__ == "__main__":
    test_smoke_pipeline_mocked()
