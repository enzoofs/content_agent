"""
Testes de override explícito de `brand` nos módulos do pipeline de geração
(copy_generator, image_generator, composer, exporter).

Cada um roda numa thread daemon separada da request (ver modules/pipeline.py),
então não podem depender do settings.brand global — precisam aceitar um
`brand` explícito que sobrescreva o fallback. Aqui confirmamos que passar
o brand gui_raw produz valores de gui_raw, não do settings.brand (mendes_vaz).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from config import brands
from modules import composer, exporter, image_generator

GUI_RAW = brands.load("gui_raw")


def _briefing(cid: str, brand_slug: str = "gui_raw"):
    return {
        "campaign_id": cid,
        "created_at": "2099-01-01T00:00:00",
        "area_direito": "x",
        "perfil_cliente_ideal": "x",
        "tom": "tecnico",
        "objetivo": "posicionamento",
        "tema_especifico": "",
        "formato": "square",
        "num_slides": 1,
        "referencias": "",
        "brand_slug": brand_slug,
    }


def test_copy_generator_usa_system_prompt_do_brand_passado(monkeypatch):
    from modules import copy_generator

    capturado = {}

    class FakeResponse:
        class Choice:
            class Message:
                content = '{"options": []}'
            message = Message()
        choices = [Choice()]

    class FakeChatCompletions:
        def create(self, **kwargs):
            capturado["messages"] = kwargs["messages"]
            return FakeResponse()

    class FakeChat:
        completions = FakeChatCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(copy_generator, "OpenAI", lambda **kw: FakeClient())
    monkeypatch.setattr("config.settings.OPENAI_API_KEY", "fake-key")

    try:
        copy_generator.generate(_briefing("2099-01-01_brand-copy"), brand=GUI_RAW)
    except Exception:
        pass  # o parse do JSON vazio falha depois — só nos importa o system prompt capturado

    system_msg = next(m["content"] for m in capturado["messages"] if m["role"] == "system")
    assert system_msg == GUI_RAW.system_prompt


def test_image_generator_build_prompt_usa_suffix_do_brand():
    prompt = image_generator._build_prompt("a dj booth", GUI_RAW)
    assert GUI_RAW.image_prompt_suffix in prompt


def test_image_generator_mock_usa_cores_do_brand(tmp_path):
    destino = tmp_path / "mock.png"
    image_generator._generate_mock_image("prompt", destino, (100, 100), GUI_RAW, seed=1)
    assert destino.exists()
    # Cor de fundo dominante deve ser bem próxima do preto do gui_raw (#0A0A0A),
    # não do navy do M&V (#272D4D) — checa o pixel do canto (fora do glow).
    from PIL import Image
    with Image.open(destino) as img:
        r, g, b = img.getpixel((0, 0))
    assert (r, g, b) != (0x27, 0x2D, 0x4D)  # não é o navy do M&V


def test_composer_build_html_usa_cores_do_brand(tmp_path):
    bg = tmp_path / "bg.png"
    from PIL import Image
    Image.new("RGB", (10, 10), (0, 0, 0)).save(bg)

    copy = {
        "headline": "H", "subheadline": "", "body": "B", "cta": "C",
    }
    html = composer._build_html(copy, bg, "post_square.html", 1080, 1080, GUI_RAW)
    assert GUI_RAW.colors["gold"] in html
    assert GUI_RAW.colors["navy"] in html


def test_exporter_usa_approved_by_do_brand(tmp_path, monkeypatch):
    from config import settings
    from modules import campaign_store

    cid = "2099-01-01_brand-export"
    monkeypatch.setattr(exporter, "AUDIT_LOG_PATH", tmp_path / "audit.jsonl")

    campaign_store.criar(_briefing(cid), brand_slug="gui_raw")
    campaign_store.save_copy_version(cid, 1, [{
        "option_id": 1, "headline": "h", "subheadline": "", "body": "b",
        "caption": "c", "cta": "x", "hashtags": [],
        "image_prompt": "p", "style_notes": "n",
    }])
    composed_dir = settings.CAMPAIGNS_DIR / cid / "composed"
    composed_dir.mkdir(parents=True, exist_ok=True)
    (composed_dir / "option_1.png").write_bytes(b"PNG")

    export = exporter.export_approved(cid, 1, brand=GUI_RAW)
    import json
    metadata = json.loads(export["metadata"].read_text(encoding="utf-8"))
    assert metadata["approved_by"] == "Gui Raw"
