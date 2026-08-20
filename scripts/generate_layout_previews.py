"""
scripts/generate_layout_previews.py — Gera as miniaturas estáticas do
seletor de layout na Nova Campanha.

Roda offline (sem OpenAI/Ideogram): usa um copy de exemplo + o mesmo
placeholder navy/gold que o pipeline usa quando não há IDEOGRAM_API_KEY
(`image_generator._generate_mock_image`), renderiza o template `square`
de cada `LayoutOption` do brand ativo via Playwright e salva um PNG
reduzido em `assets/layout_previews/<layout_id>.png`.

Rodar 1x sempre que um layout for adicionado/alterado:
    python scripts/generate_layout_previews.py
Os PNGs resultantes são commitados como asset estático (mesmo tratamento
do logo) — o form de nova campanha carrega essas miniaturas via
GET /layout-previews/<id>.png, sem custo de API por visualização.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from config import settings  # noqa: E402
from modules import composer, image_generator  # noqa: E402

THUMB_SIZE = 480  # px — miniatura final (quadrada), carregamento instantâneo no form

COPY_EXEMPLO = {
    "headline": "Seu contrato protege seu negócio?",
    "subheadline": "Direito Empresarial",
    "body": "Cláusulas mal redigidas custam caro. Veja como uma revisão preventiva evita litígios.",
    "cta": "Fale com um especialista",
}


def main() -> None:
    out_dir = settings.ASSETS_DIR / "layout_previews"
    out_dir.mkdir(parents=True, exist_ok=True)

    layout_options = settings.brand.layout_options
    if not layout_options:
        print("Brand ativo não define layout_options — nada a gerar.")
        return

    width, height = settings.POST_SIZES["square"]
    bg_path = out_dir / "_bg_mock.png"
    image_generator._generate_mock_image("layout preview background", bg_path, (width, height), seed=1)

    for opt in layout_options:
        template_file = settings.template_path("square", opt.id)
        html = composer._build_html(COPY_EXEMPLO, bg_path, template_file, "square", width, height)
        full_png = out_dir / f"_full_{opt.id}.png"
        composer.render_html_to_png(html, full_png, width, height)

        img = Image.open(full_png).convert("RGB")
        img = img.resize((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
        thumb_path = out_dir / f"{opt.id}.png"
        img.save(thumb_path, optimize=True)
        full_png.unlink()
        print(f"OK  {opt.id} -> {thumb_path}")

    bg_path.unlink()


if __name__ == "__main__":
    main()
