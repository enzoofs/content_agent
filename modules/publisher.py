"""
modules/publisher.py — Publicação automática do post aprovado no Instagram.

Camada de abstração sobre o provedor de publicação (Blotato hoje), no mesmo
espírito de `image_generator.py` (troca de Ideogram por outro provedor sem
mexer no resto do pipeline). Se um dia migrarmos pra integração direta com
o Meta Graph API, só `BlotatoPublisher` muda — `publish_scheduler.py` e o
resto do sistema continuam iguais.

⚠️ NÃO TESTADO CONTRA A API REAL — escrito a partir da documentação pública
do Blotato (blotato.com + help.blotato.com), sem conta/chave disponível
neste ambiente. Antes de rodar em produção:
  1. Confirmar os nomes exatos dos campos com uma chamada real
     (`list_accounts()` primeiro é o teste mais barato).
  2. Resolver o problema do "ponto 3" abaixo (URL pública da imagem).

Ponto 3 — imagem precisa ser alcançável pela Blotato:
    A API do Blotato aceita ou uma URL pública em `mediaUrls`, ou upload via
    endpoint de "presigned upload" (não documentado em detalhe aqui). Como a
    central roda com Basic Auth em produção (`server.py:_require_basic_auth`),
    uma URL tipo `/composed/<cid>/<file>` NÃO é alcançável pela Blotato sem
    autenticação. Duas saídas, a escolher antes de ativar isto de verdade:
      (a) Isentar `/composed/`/`/exports/` do Basic Auth (mais simples, mas
          expõe os PNGs sem autenticação — aceitável? nome de arquivo já é
          um UUID/campaign_id, não é adivinhável).
      (b) Usar o endpoint de upload direto do Blotato (mais seguro, precisa
          de teste com a chave real pra confirmar o formato).
    `_media_urls()` abaixo implementa (a) por ser o caminho mais simples;
    trocar pra (b) é local e não afeta o resto do módulo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import requests

from config import settings


class PublishError(Exception):
    """Falha ao publicar — mensagem já pronta pra log/retry, nunca crua da lib HTTP."""


@dataclass(frozen=True)
class PublishResult:
    """Resultado de uma publicação bem-sucedida — guardado só pra log/auditoria."""

    provider: str
    external_id: str | None  # id do post no provedor, se ele devolver um
    raw: dict


class Publisher(Protocol):
    """Interface que qualquer provedor de publicação deve implementar."""

    def list_accounts(self) -> list[dict]:
        """Contas conectadas no provedor — usado pra descobrir o accountId do cliente."""
        ...

    def publish(self, account_id: str, caption: str, image_urls: list[str]) -> PublishResult:
        """Publica um post (1 imagem = simples, N imagens = carrossel)."""
        ...


class BlotatoPublisher:
    """
    Publisher via Blotato (blotato.com) — hoje o provedor escolhido pra
    publicação automática no Instagram sem passar pelo app review do Meta
    (o app do Blotato já é aprovado; a gente só usa a API deles).

    Requer BLOTATO_API_KEY no .env. Sem a chave, `publish()` levanta
    PublishError cedo (mesma filosofia de falhar cedo do resto do projeto).
    """

    BASE_URL = "https://backend.blotato.com/v2"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.BLOTATO_API_KEY
        if not self.api_key:
            raise PublishError(
                "BLOTATO_API_KEY não configurada — publicação automática desligada."
            )

    def _headers(self) -> dict:
        return {"blotato-api-key": self.api_key, "Content-Type": "application/json"}

    def list_accounts(self) -> list[dict]:
        try:
            resp = requests.get(
                f"{self.BASE_URL}/users/me/accounts", headers=self._headers(), timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise PublishError(f"Blotato: falha ao listar contas conectadas — {e}") from e
        return resp.json()

    def publish(self, account_id: str, caption: str, image_urls: list[str]) -> PublishResult:
        if not image_urls:
            raise PublishError("Blotato: publish() chamado sem nenhuma imagem.")
        payload = {
            "post": {
                "accountId": account_id,
                "content": {
                    "text": caption,
                    "mediaUrls": image_urls,
                    "platform": "instagram",
                },
                "target": {"targetType": "instagram"},
            }
        }
        try:
            resp = requests.post(
                f"{self.BASE_URL}/posts", headers=self._headers(), json=payload, timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            corpo = getattr(e.response, "text", "") if e.response is not None else ""
            raise PublishError(f"Blotato: falha ao publicar — {e} {corpo}".strip()) from e
        data = resp.json() if resp.content else {}
        return PublishResult(provider="blotato", external_id=data.get("id"), raw=data)


def _media_urls(image_paths: list[Path]) -> list[str]:
    """
    Converte paths locais dos PNGs exportados em URLs públicas que a Blotato
    consegue buscar. Ver aviso do "ponto 3" no docstring do módulo — hoje
    assume que `/exports/<cid>/<arquivo>` está fora do Basic Auth.
    """
    urls = []
    for p in image_paths:
        cid = p.parent.name
        urls.append(f"{settings.PUBLIC_BASE_URL}/exports/{cid}/{p.name}")
    return urls


def publish_campaign(campaign_id: str, image_paths: list[Path], caption: str, account_id: str) -> PublishResult:
    """
    Ponto de entrada usado por `publish_scheduler.py` — resolve o publisher
    ativo, monta as URLs públicas e publica. Isolado em função própria pra
    o scheduler não precisar saber qual provedor está por trás.
    """
    publisher = BlotatoPublisher()
    urls = _media_urls(image_paths)
    return publisher.publish(account_id=account_id, caption=caption, image_urls=urls)
