"""
test_pipeline.py — Teste de smoke do pipeline.

Roda o pipeline com dados mockados (SEM chamar OpenAI nem Ideogram) e verifica
que os arquivos de saída são criados. Conforme seção 9 da spec.

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
    composer,
    copy_generator,
    exporter,
    image_generator,
)
from modules.approval_server import _build_app


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
    # 1. Briefing válido
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

    try:
        # Salva briefing.json e copy_v1.json (mock, sem OpenAI)
        camp_dir = settings.CAMPAIGNS_DIR / campaign_id
        camp_dir.mkdir(parents=True, exist_ok=True)
        (camp_dir / "briefing.json").write_text(
            json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        copy_options = _mock_copy_options()
        copy_generator._salvar(campaign_id, copy_options)

        # 2. Imagens (mock — USE_MOCK_IMAGES é True sem chave Ideogram)
        assert settings.USE_MOCK_IMAGES, "Teste pressupõe modo mock de imagens"
        image_paths = image_generator.generate(copy_options, "square", campaign_id)
        assert len(image_paths) == 3
        for p in image_paths:
            assert p.exists() and p.stat().st_size > 0

        # 3. Composição
        composed = composer.compose_all(copy_options, image_paths, briefing)
        assert len(composed) == 3
        for p in composed:
            assert p.exists() and p.stat().st_size > 0

        # 4. API de aprovação (sem subir servidor real)
        app = _build_app(campaign_id)
        client = app.test_client()
        resp = client.get(f"/api/campaign/{campaign_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["options"]) == 3
        assert data["status"] == "pending"

        # 5. Export
        png, meta = exporter.export_approved(campaign_id, 2)
        assert png.exists() and meta.exists()
        metadata = json.loads(meta.read_text(encoding="utf-8"))
        assert metadata["option_id"] == 2
        assert metadata["ready_for_posting"] is True

        print("✅ Smoke test OK — 3 imagens, 3 composições, export da opção 2.")

    finally:
        # Limpeza dos artefatos de teste
        shutil.rmtree(settings.CAMPAIGNS_DIR / campaign_id, ignore_errors=True)
        for f in settings.EXPORTS_DIR.glob(f"{campaign_id}_*"):
            f.unlink(missing_ok=True)


if __name__ == "__main__":
    test_smoke_pipeline_mocked()
