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
    image_bank,
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
        formato = briefing["formato"]
        veio_do_banco = False

        # Prioridade 1: imagem escolhida no banco reaproveitável (B.5) — pula
        # Ideogram sem custo. Se o id não existir mais, cai pro fluxo normal
        # (mesmo espírito do fallback de upload_filename ausente, abaixo).
        asset_id = (briefing.get("image_asset_id") or "").strip()
        upload_path = image_bank.resolver_path(asset_id) if asset_id else None
        if asset_id and upload_path is None:
            utils.log(cid, f"pipeline: image_asset_id={asset_id!r} não encontrado no banco, caindo pra Ideogram.")
        veio_do_banco = upload_path is not None

        # Prioridade 2: foto enviada pelo operador nesta campanha — vira o
        # fundo das 3 opções (e de todos os slides do carrossel).
        if upload_path is None:
            upload_name = (briefing.get("upload_filename") or "").strip()
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
                copy_options, formato, cid, upload_path=upload_path,
            )
        else:
            image_paths = image_generator.generate(
                copy_options, formato, cid,
            )

        # Registra a arte de fundo no banco reaproveitável (B.5), pra o
        # operador poder reusar em campanhas futuras. Só formatos simples
        # (carrossel gera N imagens por opção — poluiria o banco rápido) e só
        # quando a imagem é "nova" (não veio do próprio banco, e não é
        # placeholder mock — que não tem valor de reaproveitamento real).
        if formato != "carousel" and not veio_do_banco and not settings.USE_MOCK_IMAGES:
            origem = "upload" if upload_path is not None else "ideogram"
            try:
                image_bank.registrar(cid, formato, image_paths, origem)
            except Exception as e:
                # Nunca quebra a campanha por causa do banco de imagens —
                # é uma conveniência, não parte crítica do pipeline.
                utils.log(cid, f"pipeline: falha ao registrar no banco de imagens (não-fatal): {e}")

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
