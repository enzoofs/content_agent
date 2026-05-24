"""
modules/exporter.py — Export do post aprovado.

Após a aprovação, copia o PNG escolhido para exports/ com nome padronizado,
gera o JSON de metadados (para publicação manual ou, na Fase 2, agendamento)
e anexa uma linha no audit log central — trilha de aprovação append-only
para compliance/auditoria (item da Fase 3 do roadmap).

Saída (organizado em subpasta por campanha — facilita varrer/zipar):
    Post simples (square/portrait):
        exports/{campaign_id}/option{n}.png
        exports/{campaign_id}/option{n}_metadata.json
        exports/{campaign_id}/option{n}_post.txt

    Carrossel:
        exports/{campaign_id}/option{n}_slide{m}.png  (um por slide)
        exports/{campaign_id}/option{n}_metadata.json (slides listados em ordem)
        exports/{campaign_id}/option{n}_post.txt

    Audit log centralizado (todas as aprovações, append-only):
        exports/audit.jsonl
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from config import settings
from modules import campaign_store, utils

# Audit log centralizado: append-only, JSON Lines. Uma linha = uma aprovação.
AUDIT_LOG_PATH = settings.EXPORTS_DIR / "audit.jsonl"


def _load_json(path: Path) -> dict | list:
    """Lê e parseia um arquivo JSON da campanha."""
    if not path.exists():
        raise FileNotFoundError(f"Arquivo esperado não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _format_post_text(copy: dict, formato: str) -> str:
    """
    Monta o texto pronto-pra-postar (Instagram/LinkedIn) de uma opção aprovada.

    Estrutura: headline (ou headlines de cada slide no carrossel) → body →
    separador → caption → linha em branco → hashtags com #.

    O resultado vai para `<cid>_option<n>_post.txt` no diretório de exports —
    o Henrique copia o arquivo todo e cola direto na rede social.
    """
    linhas: list[str] = []

    if formato == "carousel":
        # Cada slide vira um bloco numerado (o copy visual já está no PNG;
        # aqui é só referência para o Henrique conferir antes de postar).
        for s in copy.get("slides", []):
            linhas.append(f"[Slide {s['slide_id']}] {s['headline']}")
            if s.get("subheadline"):
                linhas.append(s["subheadline"])
            if s.get("body"):
                linhas.append(s["body"])
            linhas.append("")
        linhas.append(f"CTA: {copy['cta']}")
    else:
        linhas.append(copy["headline"])
        if copy.get("subheadline"):
            linhas.append(copy["subheadline"])
        linhas.append("")
        linhas.append(copy["body"])
        linhas.append("")
        linhas.append(f"CTA: {copy['cta']}")

    linhas.append("")
    linhas.append("---")
    linhas.append("")
    linhas.append(copy["caption"])

    tags = copy.get("hashtags") or []
    if tags:
        linhas.append("")
        linhas.append(" ".join(f"#{t}" for t in tags))

    return "\n".join(linhas) + "\n"


def _campaign_export_dir(campaign_id: str) -> Path:
    """Subpasta dedicada da campanha em exports/, criada on-demand."""
    d = settings.EXPORTS_DIR / campaign_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_post_txt(campaign_id: str, option_id: int, copy: dict, formato: str) -> Path:
    """Salva o texto pronto-pra-postar em exports/<cid>/option<n>_post.txt."""
    destino = _campaign_export_dir(campaign_id) / f"option{option_id}_post.txt"
    destino.write_text(_format_post_text(copy, formato), encoding="utf-8")
    return destino


def _append_audit(entry: dict) -> None:
    """
    Anexa uma linha JSON ao audit log central (append-only).

    Formato JSON Lines: tolerante a corrupção (uma linha quebrada não invalida
    o resto) e amigável a `grep`/`jq`. Em POSIX, append de < ~4KB é atômico —
    suficiente para a Fase 1 single-user.
    """
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    linha = json.dumps(entry, ensure_ascii=False)
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(linha + "\n")


def export_approved(campaign_id: str, option_id: int) -> dict:
    """
    Exporta o post aprovado e seus metadados.

    Args:
        campaign_id: id da campanha.
        option_id: variação aprovada (1, 2 ou 3).

    Returns:
        dict com:
          - png: Path do PNG aprovado (primeiro slide no carrossel)
          - metadata: Path do JSON de metadados
          - post_txt: Path do texto pronto-pra-postar (post.txt)
          - all_pngs: lista de Paths (1 no simples, N no carrossel)

    Raises:
        FileNotFoundError: se faltar o briefing, o copy ou algum PNG composto.
        ValueError: se a opção aprovada não existir no copy.
    """
    camp_dir = settings.CAMPAIGNS_DIR / campaign_id

    briefing = campaign_store.read_briefing(campaign_id)
    if briefing is None:
        raise FileNotFoundError(f"Briefing não encontrado para {campaign_id}.")

    # Lê o copy da versão corrente (regerar bumpa o contador) direto do DB
    copy_options = campaign_store.get_copy(campaign_id)
    if copy_options is None:
        raise FileNotFoundError(f"Copy não encontrado para {campaign_id}.")

    copy = next((c for c in copy_options if c["option_id"] == option_id), None)
    if copy is None:
        raise ValueError(
            f"Opção {option_id} não encontrada no copy da campanha {campaign_id}."
        )

    _campaign_export_dir(campaign_id)

    if briefing["formato"] == "carousel":
        return _export_carousel(campaign_id, option_id, briefing, copy, camp_dir)
    return _export_simples(campaign_id, option_id, briefing, copy, camp_dir)


def _export_simples(
    campaign_id: str, option_id: int, briefing: dict, copy: dict, camp_dir: Path,
) -> dict:
    """square/portrait: 1 PNG + metadata + post.txt."""
    composed_png = camp_dir / "composed" / f"option_{option_id}.png"
    if not composed_png.exists():
        raise FileNotFoundError(f"PNG composto não encontrado: {composed_png}")

    out_dir = _campaign_export_dir(campaign_id)
    png_destino = out_dir / f"option{option_id}.png"
    shutil.copyfile(composed_png, png_destino)
    post_txt = _save_post_txt(campaign_id, option_id, copy, briefing["formato"])

    approval_id = str(uuid.uuid4())
    approved_at = datetime.now().isoformat(timespec="seconds")
    copy_version = campaign_store.get_copy_version(campaign_id)

    metadata = {
        "approval_id": approval_id,
        "campaign_id": campaign_id,
        "approved_at": approved_at,
        "option_id": option_id,
        "copy_version": copy_version,
        "formato": briefing["formato"],
        "headline": copy["headline"],
        "caption": copy["caption"],
        "hashtags": copy["hashtags"],
        "approved_by": settings.APPROVED_BY,
        "ready_for_posting": True,
    }
    meta_destino = out_dir / f"option{option_id}_metadata.json"
    meta_destino.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _append_audit({
        "approval_id": approval_id,
        "campaign_id": campaign_id,
        "option_id": option_id,
        "copy_version": copy_version,
        "formato": briefing["formato"],
        "approved_at": approved_at,
        "approved_by": settings.APPROVED_BY,
        "headline": copy["headline"],
        "export_png": f"{campaign_id}/{png_destino.name}",
    })

    utils.log(
        campaign_id,
        f"exporter: opção {option_id} exportada -> {png_destino.name} "
        f"(+ metadata + post.txt, audit_id={approval_id[:8]}).",
    )
    return {
        "png": png_destino,
        "metadata": meta_destino,
        "post_txt": post_txt,
        "all_pngs": [png_destino],
    }


def _export_carousel(
    campaign_id: str, option_id: int, briefing: dict, copy: dict, camp_dir: Path,
) -> dict:
    """carrossel: N PNGs + metadata com a lista ordenada de slides + post.txt."""
    slides_meta = []
    all_pngs: list[Path] = []
    out_dir = _campaign_export_dir(campaign_id)

    for slide in copy["slides"]:
        m = slide["slide_id"]
        composed_png = camp_dir / "composed" / f"option_{option_id}_slide_{m}.png"
        if not composed_png.exists():
            raise FileNotFoundError(f"PNG composto não encontrado: {composed_png}")

        destino = out_dir / f"option{option_id}_slide{m}.png"
        shutil.copyfile(composed_png, destino)
        all_pngs.append(destino)

        slides_meta.append({
            "slide_id": m,
            "headline": slide["headline"],
            "body": slide["body"],
            "file": destino.name,
        })

    post_txt = _save_post_txt(campaign_id, option_id, copy, "carousel")

    approval_id = str(uuid.uuid4())
    approved_at = datetime.now().isoformat(timespec="seconds")
    copy_version = campaign_store.get_copy_version(campaign_id)

    metadata = {
        "approval_id": approval_id,
        "campaign_id": campaign_id,
        "approved_at": approved_at,
        "option_id": option_id,
        "copy_version": copy_version,
        "formato": "carousel",
        "num_slides": len(slides_meta),
        "caption": copy["caption"],
        "cta": copy["cta"],
        "hashtags": copy["hashtags"],
        "slides": slides_meta,
        "approved_by": settings.APPROVED_BY,
        "ready_for_posting": True,
    }
    meta_destino = out_dir / f"option{option_id}_metadata.json"
    meta_destino.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _append_audit({
        "approval_id": approval_id,
        "campaign_id": campaign_id,
        "option_id": option_id,
        "copy_version": copy_version,
        "formato": "carousel",
        "num_slides": len(slides_meta),
        "approved_at": approved_at,
        "approved_by": settings.APPROVED_BY,
        "export_metadata": f"{campaign_id}/{meta_destino.name}",
    })

    utils.log(
        campaign_id,
        f"exporter: opção {option_id} (carrossel, {len(slides_meta)} slides) "
        f"exportada + post.txt (audit_id={approval_id[:8]}).",
    )
    return {
        "png": all_pngs[0],
        "metadata": meta_destino,
        "post_txt": post_txt,
        "all_pngs": all_pngs,
    }
