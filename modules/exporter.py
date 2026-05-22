"""
modules/exporter.py — Export do post aprovado.

Após a aprovação, copia o PNG escolhido para exports/ com nome padronizado e
gera o JSON de metadados (para publicação manual ou, na Fase 2, agendamento).

Saída:
    exports/{campaign_id}_option{n}_approved.png
    exports/{campaign_id}_option{n}_metadata.json
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from config import settings
from modules import utils


def _load_json(path: Path) -> dict | list:
    """Lê e parseia um arquivo JSON da campanha."""
    if not path.exists():
        raise FileNotFoundError(f"Arquivo esperado não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def export_approved(campaign_id: str, option_id: int) -> tuple[Path, Path]:
    """
    Exporta o post aprovado e seus metadados.

    Args:
        campaign_id: id da campanha.
        option_id: variação aprovada (1, 2 ou 3).

    Returns:
        (path_png, path_metadata_json).

    Raises:
        FileNotFoundError: se faltar o briefing, o copy ou o PNG composto.
        ValueError: se a opção aprovada não existir no copy.
    """
    camp_dir = settings.CAMPAIGNS_DIR / campaign_id

    briefing = _load_json(camp_dir / "briefing.json")
    copy_options = _load_json(camp_dir / "copy_v1.json")

    copy = next((c for c in copy_options if c["option_id"] == option_id), None)
    if copy is None:
        raise ValueError(
            f"Opção {option_id} não encontrada no copy da campanha {campaign_id}."
        )

    composed_png = camp_dir / "composed" / f"option_{option_id}.png"
    if not composed_png.exists():
        raise FileNotFoundError(f"PNG composto não encontrado: {composed_png}")

    settings.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # --- Copia o PNG aprovado ---
    png_destino = settings.EXPORTS_DIR / f"{campaign_id}_option{option_id}_approved.png"
    shutil.copyfile(composed_png, png_destino)

    # --- Gera o JSON de metadados ---
    metadata = {
        "campaign_id": campaign_id,
        "approved_at": datetime.now().isoformat(timespec="seconds"),
        "option_id": option_id,
        "formato": briefing["formato"],
        "headline": copy["headline"],
        "caption": copy["caption"],
        "hashtags": copy["hashtags"],
        "approved_by": settings.APPROVED_BY,
        "ready_for_posting": True,
    }
    meta_destino = settings.EXPORTS_DIR / f"{campaign_id}_option{option_id}_metadata.json"
    meta_destino.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    utils.log(
        campaign_id,
        f"exporter: opção {option_id} exportada -> {png_destino.name} (+ metadata).",
    )
    return png_destino, meta_destino
