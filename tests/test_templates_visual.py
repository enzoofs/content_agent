"""
tests/test_templates_visual.py — Smoke visual dos templates HTML.

Não tenta byte-comparison (anti-aliasing/font hinting variam entre runs).
Verifica invariantes essenciais que pegam regressões reais:

- PNG renderizou com sucesso (existe + tamanho mínimo razoável)
- Dimensões corretas pra cada formato
- Cor dominante é navy (#272D4D) — confirma que o overlay+CSS aplicou
- Imagem tem variação (não é monocromática total = composição quebrou)

Custo: ~5s no total (3 renders Playwright). Rodar via `pytest -q`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from config import settings
from modules import composer


# Cor navy do branding (aceita pequena variação por compressão PNG)
NAVY_RGB = (39, 45, 77)


def _copy_padrao() -> dict:
    """Copy fixo pra reprodutibilidade do render."""
    return {
        "option_id": 1,
        "headline": "Compliance médico: contratos sólidos antes do litígio",
        "subheadline": "Direito Médico · BH",
        "body": "Auditoria preventiva, contratos sólidos e gestão de risco para clínicas e hospitais.",
        "cta": "Fale com um especialista",
        "caption": "x", "hashtags": [], "image_prompt": "x", "style_notes": "x",
    }


def _placeholder_bg(tmp_path: Path, width: int, height: int) -> Path:
    """
    Gera um PNG sólido cinza-claro como imagem de fundo (substitui Ideogram).

    Mantém o teste offline e determinístico.
    """
    p = tmp_path / "bg.png"
    Image.new("RGB", (width, height), (180, 180, 180)).save(p)
    return p


def _cor_dominante(png_path: Path) -> tuple[int, int, int]:
    """Retorna a cor mais frequente do PNG (downsample 1px da imagem reduzida)."""
    img = Image.open(png_path).convert("RGB")
    # Reduz pra 64x64 e pega o pixel mais frequente
    img_small = img.resize((64, 64), Image.Resampling.LANCZOS)
    pixels = img_small.getcolors(maxcolors=64 * 64)
    return max(pixels, key=lambda x: x[0])[1]


def _proximo_de(cor_a: tuple[int, int, int], cor_b: tuple[int, int, int], tol: int = 30) -> bool:
    """Distância L1 por canal."""
    return all(abs(a - b) <= tol for a, b in zip(cor_a, cor_b))


@pytest.mark.parametrize("formato", ["square", "portrait", "carousel"])
def test_template_renderiza_dentro_dos_invariantes(formato, tmp_path):
    """
    Cada formato deve: renderizar, ter dimensões corretas, > 30KB, navy dominante.
    """
    width, height = settings.POST_SIZES[formato]
    template_name = settings.TEMPLATE_BY_FORMAT[formato]
    bg = _placeholder_bg(tmp_path, width, height)
    out = tmp_path / f"{formato}.png"

    composer.compose(
        copy=_copy_padrao(),
        image_path=bg,
        template_name=template_name,
        output_path=out,
        width=width,
        height=height,
    )

    # 1) Arquivo criado e não-vazio
    assert out.exists(), f"PNG não foi gerado pra {formato}"
    tamanho = out.stat().st_size
    assert tamanho >= 30_000, (
        f"PNG do {formato} muito pequeno ({tamanho} bytes) — provavelmente "
        f"o template quebrou e renderizou tela vazia."
    )

    # 2) Dimensões batem com settings.POST_SIZES
    img = Image.open(out)
    assert img.size == (width, height), (
        f"PNG do {formato} tem dimensões {img.size}, esperado {(width, height)}."
    )

    # 3) Cor dominante é navy (overlay/CSS aplicou)
    dom = _cor_dominante(out)
    assert _proximo_de(dom, NAVY_RGB, tol=40), (
        f"Cor dominante do {formato} é {dom}, esperado próximo de navy {NAVY_RGB}. "
        f"O overlay azul-escuro do template provavelmente não aplicou."
    )

    # 4) Imagem tem variação — não é uma cor sólida (composição quebrou)
    img_small = img.convert("RGB").resize((32, 32), Image.Resampling.LANCZOS)
    pixels = img_small.tobytes()
    # tobytes() devolve r,g,b,r,g,b... — agrupa em tuplas de 3
    cores_distintas = len({pixels[i:i+3] for i in range(0, len(pixels), 3)})
    assert cores_distintas >= 30, (
        f"PNG do {formato} tem só {cores_distintas} cores distintas — "
        f"provavelmente é uma chapa sólida (template quebrou)."
    )
