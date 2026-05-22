"""
modules/utils.py — Helpers compartilhados pelo pipeline.

Funções pequenas e sem dependência das APIs externas: slugify, caminhos de
campanha e logging em arquivo. Mantidas aqui para evitar duplicação entre módulos.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

from config import settings


def slugify(texto: str) -> str:
    """
    Converte um texto livre em slug ASCII para nomes de pasta/arquivo.

    Ex.: "Direito Médico" -> "direito-medico".

    Args:
        texto: string de origem.

    Returns:
        Slug em minúsculas, sem acento, com hífens. "campanha" se vazio.
    """
    # Remove acentos (NFKD separa o caractere do diacrítico)
    normalizado = unicodedata.normalize("NFKD", texto)
    ascii_str = normalizado.encode("ascii", "ignore").decode("ascii")
    # Minúsculas, troca não-alfanuméricos por hífen, colapsa hífens
    ascii_str = ascii_str.lower().strip()
    ascii_str = re.sub(r"[^a-z0-9]+", "-", ascii_str)
    ascii_str = ascii_str.strip("-")
    return ascii_str or "campanha"


def make_campaign_id(area_direito: str, tema_especifico: str = "") -> str:
    """
    Gera o campaign_id no formato YYYY-MM-DD_slug.

    Usa o tema específico como base do slug quando houver; senão, a área.
    """
    base = tema_especifico.strip() or area_direito
    data = datetime.now().strftime("%Y-%m-%d")
    return f"{data}_{slugify(base)}"


def campaign_dir(campaign_id: str) -> Path:
    """Retorna (criando se preciso) a pasta da campanha em campaigns/."""
    pasta = settings.CAMPAIGNS_DIR / campaign_id
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def campaign_images_dir(campaign_id: str) -> Path:
    """Pasta das artes de fundo: campaigns/{id}/images/."""
    pasta = campaign_dir(campaign_id) / "images"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def campaign_composed_dir(campaign_id: str) -> Path:
    """Pasta dos posts compostos: campaigns/{id}/composed/."""
    pasta = campaign_dir(campaign_id) / "composed"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def log(campaign_id: str, mensagem: str) -> None:
    """
    Acrescenta uma linha com timestamp ao log da campanha.

    Nunca deixa o pipeline quebrar silenciosamente: tudo de relevante é
    registrado em campaigns/{id}/log.txt além de eventualmente impresso.
    """
    linha = f"[{datetime.now().isoformat(timespec='seconds')}] {mensagem}\n"
    arquivo = campaign_dir(campaign_id) / "log.txt"
    with arquivo.open("a", encoding="utf-8") as f:
        f.write(linha)
