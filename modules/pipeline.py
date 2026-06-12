"""
modules/pipeline.py — Motor de geração compartilhado (terminal e web).

Orquestra copy → arte → composição, atualizando o estado da campanha a cada
etapa via campaign_store. Usado tanto pelo fluxo de terminal (main.py) quanto
pela central web (server.py, que roda `gerar` numa thread).
"""

from __future__ import annotations

from pathlib import Path

from config import settings
from modules import (
    campaign_store,
    composer,
    copy_generator,
    image_generator,
    utils,
)


def gerar(briefing: dict, nota_ajuste: str = "", versao: int = 1) -> list[Path]:
    """
    Roda o pipeline completo de geração para uma campanha já criada no store.

    Atualiza o estado: etapa copy → arte → composicao → status aguardando_aprovacao.
    Em caso de falha, grava status=erro com a mensagem e relança a exceção
    (nunca falha em silêncio).

    Args:
        briefing: briefing validado (saída de briefing_parser.parse).
        nota_ajuste: pedido de ajuste do Henrique (regeneração); vazio na 1ª vez.
        versao: versão do copy (1 na 1ª, 2+ no regerar). Define copy_v{N}.json.

    Returns:
        Lista de paths dos PNGs compostos.
    """
    cid = briefing["campaign_id"]
    try:
        campaign_store.set_etapa(cid, "copy")
        copy_options = copy_generator.generate(briefing, nota_ajuste, versao=versao)

        campaign_store.set_etapa(cid, "arte")
        # Se o operador enviou uma foto, ela vira o fundo das 3 opções
        # (e de todos os slides do carrossel) — Ideogram é pulado.
        upload_name = (briefing.get("upload_filename") or "").strip()
        upload_path = None
        if upload_name:
            candidato = settings.CAMPAIGNS_DIR / cid / upload_name
            if candidato.exists():
                upload_path = candidato
            else:
                utils.log(cid, f"pipeline: upload_filename={upload_name!r} não encontrado, caindo pra Ideogram.")
        # Só passa upload_path como kwarg quando setado, pra não quebrar mocks de
        # testes que monkey-patcham image_generator.generate sem esse parâmetro.
        if upload_path is not None:
            image_paths = image_generator.generate(
                copy_options, briefing["formato"], cid, upload_path=upload_path,
            )
        else:
            image_paths = image_generator.generate(
                copy_options, briefing["formato"], cid,
            )

        campaign_store.set_etapa(cid, "composicao")
        composed = composer.compose_all(copy_options, image_paths, briefing)

        campaign_store.marcar_aguardando(cid)
        utils.log(cid, "pipeline: geração concluída — aguardando aprovação.")
        return composed

    except Exception as e:
        campaign_store.set_erro(cid, str(e))
        utils.log(cid, f"pipeline: ERRO na geração — {e}")
        raise


def regerar(campaign_id: str, nota: str = "") -> list[Path]:
    """
    Regenera uma campanha existente (após pedido de ajuste).

    Bumpa a versão do copy ANTES de gerar, garantindo que a versão anterior
    fique preservada no DB (histórico/auditoria).
    """
    briefing = campaign_store.read_briefing(campaign_id)
    if briefing is None:
        raise FileNotFoundError(f"Briefing não encontrado para {campaign_id}.")
    nova_versao = campaign_store.next_copy_version(campaign_id)
    campaign_store.set_etapa(campaign_id, "copy")
    return gerar(briefing, nota, versao=nova_versao)
