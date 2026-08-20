"""
tests/test_image_generator_carousel_upload.py — Upload multi-foto de
carrossel: cada slide deve usar a foto correspondente da lista, na ordem
recebida (não a mesma foto repetida em todos os slides).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from modules import image_generator


def _foto_solida(path: Path, cor: tuple[int, int, int]) -> Path:
    Image.new("RGB", (200, 200), cor).save(path)
    return path


def _cor_dominante(png_path: Path) -> tuple[int, int, int]:
    img = Image.open(png_path).convert("RGB")
    return img.getpixel((img.width // 2, img.height // 2))


def _copy_options_carousel(n_slides: int) -> list[dict]:
    return [{
        "option_id": 1,
        "slides": [
            {"slide_id": m, "headline": f"h{m}", "body": "b", "image_prompt": "p"}
            for m in range(1, n_slides + 1)
        ],
    }]


def test_generate_carousel_usa_foto_por_slide_na_ordem(tmp_path):
    vermelho = _foto_solida(tmp_path / "slide1.png", (200, 20, 20))
    verde = _foto_solida(tmp_path / "slide2.png", (20, 200, 20))
    azul = _foto_solida(tmp_path / "slide3.png", (20, 20, 200))

    out_dir = tmp_path / "images"
    todas = image_generator._generate_carousel(
        _copy_options_carousel(3), "carousel", (200, 200), out_dir,
        campaign_id="teste", upload_paths=[vermelho, verde, azul],
    )

    slide1, slide2, slide3 = todas[0]
    assert _cor_dominante(slide1)[0] > 150  # dominante vermelho
    assert _cor_dominante(slide2)[1] > 150  # dominante verde
    assert _cor_dominante(slide3)[2] > 150  # dominante azul


def test_generate_carousel_upload_paths_tem_prioridade_sobre_upload_path(tmp_path):
    unica = _foto_solida(tmp_path / "unica.png", (10, 10, 10))
    por_slide = _foto_solida(tmp_path / "por_slide.png", (250, 250, 250))

    out_dir = tmp_path / "images"
    todas = image_generator._generate_carousel(
        _copy_options_carousel(1), "carousel", (200, 200), out_dir,
        campaign_id="teste", upload_path=unica, upload_paths=[por_slide],
    )

    cor = _cor_dominante(todas[0][0])
    assert cor[0] > 200  # usou por_slide (branco), não unica (preto)
