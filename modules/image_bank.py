"""
modules/image_bank.py — Banco de imagens reaproveitáveis (B.5).

Camada de domínio sobre `store.image_assets` (mesmo papel que campaign_store
tem sobre `store.campaigns`). Guarda artes de fundo já geradas via Ideogram
ou enviadas por upload, pra o operador reaproveitar numa campanha nova sem
pagar de novo pelo Ideogram.

Arquivos físicos vivem em `assets/image_bank/<asset_id>.png` — fora de
`campaigns/`, então não são apagados quando uma campanha é deletada
(`campaign_store.deletar()` faz rmtree só na pasta da campanha).

Escopo desta primeira versão: só formatos simples (square/portrait/story).
Carrossel gera N imagens por opção — registrar todas poluiria o banco
rápido; fica de fora até haver demanda real.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from config import settings
from modules import store


def registrar(
    campaign_id: str, formato: str, image_paths: list[Path], origem: str,
) -> list[dict]:
    """
    Copia as imagens de fundo geradas/enviadas pra assets/image_bank/ e
    registra cada uma no DB.

    Args:
        campaign_id: campanha de origem (só informativo — pode ficar órfão
            se a campanha for deletada depois).
        formato: "square" | "portrait" | "story" (carousel não é chamado
            por quem invoca esta função — ver pipeline.gerar).
        image_paths: paths das imagens já geradas em campaigns/{id}/images/.
        origem: "ideogram" | "upload".

    Returns:
        Lista dos registros criados (dicts do DB).
    """
    settings.IMAGE_BANK_DIR.mkdir(parents=True, exist_ok=True)
    registrados: list[dict] = []
    for image_path in image_paths:
        asset_id = uuid.uuid4().hex
        filename = f"{asset_id}.png"
        destino = settings.IMAGE_BANK_DIR / filename
        shutil.copyfile(image_path, destino)
        registrado = store.insert_image_asset(
            asset_id=asset_id,
            brand_slug=settings.brand.slug,
            origem=origem,
            formato=formato,
            filename=filename,
            origem_campaign_id=campaign_id,
        )
        registrados.append(registrado)
    return registrados


def listar(brand_slug: str | None = None) -> list[dict]:
    """Lista os assets do brand ativo (ou do slug informado), mais recentes primeiro."""
    return store.list_image_assets(brand_slug or settings.brand.slug)


def resolver_path(asset_id: str) -> Path | None:
    """Resolve o path físico de um asset (None se o id não existir mais)."""
    asset = store.get_image_asset(asset_id)
    if asset is None:
        return None
    path = settings.IMAGE_BANK_DIR / asset["filename"]
    return path if path.exists() else None


def deletar(asset_id: str) -> bool:
    """Apaga o registro e o arquivo físico. Retorna True se algo foi apagado."""
    asset = store.get_image_asset(asset_id)
    if asset is None:
        return False
    path = settings.IMAGE_BANK_DIR / asset["filename"]
    if path.exists():
        path.unlink()
    return store.delete_image_asset(asset_id)
