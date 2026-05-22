"""
modules/image_generator.py — Geração de arte de fundo via Ideogram.

Gera uma imagem de fundo (SEM texto, SEM logo) para cada variação de copy.
O texto e o logo são adicionados depois pelo composer.

Enquanto não houver IDEOGRAM_API_KEY (ou USE_MOCK_IMAGES=true), gera imagens
placeholder navy/gold localmente via Pillow, para o pipeline rodar fim a fim.

REGRA CRÍTICA: nunca quebra o pipeline por causa de uma imagem. Após 3 falhas
numa opção, registra no log e cai para o placeholder.
"""

from __future__ import annotations

import math
from pathlib import Path

import requests
from PIL import Image, ImageDraw

from config import settings
from modules import utils


def generate(copy_options: list[dict], formato: str, campaign_id: str) -> list[Path]:
    """
    Gera as imagens de fundo das variações de copy.

    Args:
        copy_options: saída de copy_generator.generate.
        formato: "square" | "portrait" | "carousel".
        campaign_id: id da campanha (define a pasta de saída).

    Returns:
        Lista de paths PNG em campaigns/{campaign_id}/images/option_{n}.png.
    """
    out_dir = utils.campaign_images_dir(campaign_id)
    size = settings.POST_SIZES[formato]
    paths: list[Path] = []

    for copy in copy_options:
        n = copy["option_id"]
        destino = out_dir / f"option_{n}.png"
        prompt = _build_prompt(copy["image_prompt"])

        if settings.USE_MOCK_IMAGES:
            utils.log(campaign_id, f"image_generator: opção {n} usando placeholder (mock).")
            _generate_mock_image(prompt, destino, size, seed=n)
        else:
            _generate_with_fallback(prompt, destino, size, formato, campaign_id, n)

        paths.append(destino)

    return paths


def _build_prompt(image_prompt: str) -> str:
    """Enriquece o prompt do copy com o sufixo de estética do cliente."""
    return f"{image_prompt}, {settings.IMAGE_PROMPT_SUFFIX}"


def _generate_with_fallback(
    prompt: str, destino: Path, size: tuple[int, int],
    formato: str, campaign_id: str, n: int,
) -> None:
    """Tenta a Ideogram até 3x; se falhar, cai para o placeholder local."""
    for tentativa in range(1, 4):
        try:
            _generate_with_ideogram(prompt, destino, formato)
            utils.log(campaign_id, f"image_generator: opção {n} gerada via Ideogram.")
            return
        except Exception as e:
            utils.log(
                campaign_id,
                f"image_generator: Ideogram falhou opção {n} tentativa {tentativa}: {e}",
            )
            print(f"⚠️  Ideogram falhou (opção {n}, tentativa {tentativa}): {e}")

    utils.log(campaign_id, f"image_generator: opção {n} caiu para placeholder após 3 falhas.")
    print(f"   → Usando placeholder local para a opção {n}.")
    _generate_mock_image(prompt, destino, size, seed=n)


def _generate_with_ideogram(prompt: str, destino: Path, formato: str) -> None:
    """
    Chama a Ideogram API, baixa o PNG resultante e salva em `destino`.

    Raises:
        Exception: em qualquer falha de rede, auth ou resposta inesperada.
    """
    payload = {
        "image_request": {
            "prompt": prompt,
            "model": settings.IDEOGRAM_CONFIG["model"],
            "resolution": settings.IDEOGRAM_RESOLUTIONS[formato],
            "style_type": settings.IDEOGRAM_CONFIG["style_type"],
            "negative_prompt": settings.IDEOGRAM_CONFIG["negative_prompt"],
            "color_palette": settings.IDEOGRAM_CONFIG["color_palette"],
        }
    }
    headers = {
        "Api-Key": settings.IDEOGRAM_API_KEY,
        "Content-Type": "application/json",
    }

    resp = requests.post(settings.IDEOGRAM_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    image_url = resp.json()["data"][0]["url"]

    img_resp = requests.get(image_url, timeout=120)
    img_resp.raise_for_status()
    destino.write_bytes(img_resp.content)

    # Normaliza para o tamanho exato do post (Ideogram entrega 1024-base)
    _resize_to_post(destino, settings.POST_SIZES[formato])


def _resize_to_post(path: Path, size: tuple[int, int]) -> None:
    """Reamostra a imagem para o tamanho exato do post, recortando o excesso (cover)."""
    with Image.open(path) as img:
        img = img.convert("RGB")
        alvo_w, alvo_h = size
        escala = max(alvo_w / img.width, alvo_h / img.height)
        novo = img.resize((round(img.width * escala), round(img.height * escala)))
        esq = (novo.width - alvo_w) // 2
        topo = (novo.height - alvo_h) // 2
        novo.crop((esq, topo, esq + alvo_w, topo + alvo_h)).save(path)


def _generate_mock_image(
    prompt: str, output_path: Path, size: tuple[int, int], seed: int = 1
) -> Path:
    """
    Gera um placeholder elegante navy com um brilho dourado sutil.

    Mantém a estética do cliente para que a composição já fique apresentável
    enquanto a chave Ideogram não está disponível. Sem texto na imagem.
    """
    w, h = size
    navy = _hex_rgb(settings.COLORS["navy_dark"])
    navy_top = _hex_rgb(settings.COLORS["navy"])
    gold = _hex_rgb(settings.COLORS["gold"])

    img = Image.new("RGB", (w, h), navy)
    px = img.load()

    # Gradiente vertical navy -> navy_dark
    for y in range(h):
        t = y / max(h - 1, 1)
        r = round(navy_top[0] + (navy[0] - navy_top[0]) * t)
        g = round(navy_top[1] + (navy[1] - navy_top[1]) * t)
        b = round(navy_top[2] + (navy[2] - navy_top[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)

    # Brilho dourado radial sutil, posição variando com a seed (para 3 opções distintas)
    cx = w * (0.3 + 0.2 * ((seed - 1) % 3))
    cy = h * 0.32
    raio = max(w, h) * 0.55
    draw_glow(img, cx, cy, raio, gold, intensidade=0.18)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    return output_path


def draw_glow(img: Image.Image, cx: float, cy: float, raio: float,
              cor: tuple[int, int, int], intensidade: float) -> None:
    """Aplica um halo radial suave da cor dada sobre a imagem (in-place)."""
    px = img.load()
    w, h = img.size
    raio2 = raio * raio
    for y in range(h):
        for x in range(w):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if d2 < raio2:
                fator = (1 - math.sqrt(d2) / raio) * intensidade
                r, g, b = px[x, y]
                px[x, y] = (
                    min(255, round(r + (cor[0] - r) * fator)),
                    min(255, round(g + (cor[1] - g) * fator)),
                    min(255, round(b + (cor[2] - b) * fator)),
                )


def _hex_rgb(hex_color: str) -> tuple[int, int, int]:
    """'#272D4D' -> (39, 45, 77)."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
