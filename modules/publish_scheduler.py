"""
modules/publish_scheduler.py — Publica automaticamente campanhas aprovadas
na data agendada, via `modules.publisher` (Blotato).

Mesmo padrão de `modules/backup.py`: thread daemon, sem infra externa (o
container do Fly não tem cron). Roda a cada CHECK_INTERVAL_SECONDS,
verifica campanhas com status="aprovada" + data_agendada <= hoje +
publicado_em ainda vazio, e publica cada uma.

⚠️ Sem BLOTATO_API_KEY ou sem `blotato_account_id` configurado no brand
ativo, isto não publica nada — só loga e segue (não é fatal; o fluxo
manual de export/aprovação continua funcionando normalmente sem isso).
Ver modules/publisher.py pro aviso sobre a URL pública da imagem.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from config import settings
from modules import campaign_store, publisher, utils

CHECK_INTERVAL_SECONDS = 15 * 60  # 15 min — publicação não precisa de precisão de segundo


def _resolver_imagens_e_legenda(campanha: dict) -> tuple[list[Path], str] | None:
    """
    Lê o metadata.json + os PNGs já exportados pra opção aprovada.

    Returns:
        (lista de PNGs em ordem, legenda pronta) ou None se o export ainda
        não existe (não deveria acontecer — approve() já exporta na hora —
        mas é defensivo: nunca assume que o arquivo está lá).
    """
    import json

    cid = campanha["campaign_id"]
    option_id = campanha.get("option_aprovada")
    if not option_id:
        return None

    export_dir = settings.EXPORTS_DIR / cid
    meta_path = export_dir / f"option{option_id}_metadata.json"
    if not meta_path.exists():
        utils.log(cid, f"publish_scheduler: metadata não encontrado ({meta_path}) — pulando.")
        return None

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    caption = (metadata.get("caption") or "").strip()
    tags = metadata.get("hashtags") or []
    if tags:
        caption = f"{caption}\n\n{' '.join(f'#{t}' for t in tags)}"

    imagens = sorted(export_dir.glob(f"option{option_id}*.png"))
    if not imagens:
        utils.log(cid, f"publish_scheduler: nenhum PNG exportado encontrado em {export_dir} — pulando.")
        return None

    return imagens, caption


def publicar_pendentes() -> int:
    """
    Roda 1 ciclo: publica todas as campanhas prontas. Retorna quantas
    publicou com sucesso (usado pelos testes — evita mockar threading).
    """
    account_id = settings.brand.blotato_account_id
    if not account_id:
        return 0  # brand ainda não conectou o Instagram no Blotato — nada a fazer

    publicadas = 0
    for campanha in campaign_store.listar_pendentes_publicacao():
        cid = campanha["campaign_id"]
        resolvido = _resolver_imagens_e_legenda(campanha)
        if resolvido is None:
            continue
        imagens, caption = resolvido

        try:
            publisher.publish_campaign(cid, imagens, caption, account_id)
        except publisher.PublishError as e:
            campaign_store.registrar_erro_publicacao(cid, str(e))
            utils.log(cid, f"publish_scheduler: falha ao publicar — {e}")
            continue

        campaign_store.marcar_publicada(cid)
        utils.log(cid, "publish_scheduler: publicada com sucesso.")
        publicadas += 1

    return publicadas


def start_background_scheduler() -> None:
    """Sobe a thread daemon que verifica e publica a cada CHECK_INTERVAL_SECONDS."""
    def loop():
        time.sleep(90)  # atrasado, mesmo espírito do backup: não briga com o boot
        while True:
            try:
                publicar_pendentes()
            except Exception as e:
                # Nunca derruba a app por causa de publicação — mesma filosofia do backup.
                print(f"⚠ publish_scheduler falhou: {e}")
            time.sleep(CHECK_INTERVAL_SECONDS)

    t = threading.Thread(target=loop, name="publish-scheduler", daemon=True)
    t.start()
