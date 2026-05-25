"""
modules/copy_generator.py — Geração de copy via OpenAI.

NOTA DE STACK: a spec original previa Claude API (claude-sonnet-4-6). Nesta fase
trocamos para a OpenAI (sem chave Anthropic disponível). O modelo é configurável
em config.settings.OPENAI_MODEL. O system prompt e o schema de saída permanecem
idênticos aos da spec.

Recebe o briefing validado e retorna NUM_COPY_OPTIONS variações completas de copy.
"""

from __future__ import annotations

import json
import re
import unicodedata

from openai import OpenAI

from config import settings
from modules import campaign_store, utils

# Limite máximo de hashtags por post (spec)
MAX_HASHTAGS = 20


def normalize_hashtags(tags: list) -> list[str]:
    """
    Normaliza hashtags para o padrão de busca: minúsculas, sem acento, sem '#',
    sem espaços/caracteres especiais. Remove vazias e duplicatas (preservando a
    ordem) e limita a MAX_HASHTAGS.

    Ex.: ["#Direito Médico", "clínicasBH"] -> ["direitomedico", "clinicasbh"]
    """
    vistos: set[str] = set()
    limpas: list[str] = []
    for tag in tags:
        if not isinstance(tag, str):
            continue
        # Remove acentos
        sem_acento = (
            unicodedata.normalize("NFKD", tag).encode("ascii", "ignore").decode("ascii")
        )
        # Minúsculas e mantém apenas a-z 0-9 (descarta '#', espaços, pontuação)
        limpa = re.sub(r"[^a-z0-9]", "", sem_acento.lower())
        if limpa and limpa not in vistos:
            vistos.add(limpa)
            limpas.append(limpa)
    return limpas[:MAX_HASHTAGS]

# Schema de uma variação de copy (formatos simples: square / portrait)
COPY_SCHEMA: dict[str, type] = {
    "option_id": int,        # 1, 2 ou 3
    "headline": str,         # máx 60 chars
    "subheadline": str,      # máx 80 chars, pode ser ""
    "body": str,             # máx 150 chars (square/portrait)
    "caption": str,          # máx 2200 chars
    "cta": str,              # máx 40 chars
    "hashtags": list,        # list[str] sem o #, máx 20
    "image_prompt": str,     # inglês, máx 400 chars
    "style_notes": str,      # notas para o compositor
}

# Campos obrigatórios em cada variação retornada pelo modelo
_REQUIRED_FIELDS = set(COPY_SCHEMA) - {"option_id"}

# Schema de uma variação para CARROSSEL: a publicação inteira tem 1 caption/cta/
# hashtags, e os slides[] aninhados carregam o conteúdo visual por página.
CAROUSEL_OPTION_SCHEMA: dict[str, type] = {
    "option_id": int,
    "caption": str,
    "cta": str,
    "hashtags": list,
    "style_notes": str,
    "slides": list,          # list[dict] — cada item segue CAROUSEL_SLIDE_SCHEMA
}
CAROUSEL_SLIDE_SCHEMA: dict[str, type] = {
    "slide_id": int,         # 1..N na ordem do carrossel
    "headline": str,
    "subheadline": str,
    "body": str,
    "image_prompt": str,
}

_CAROUSEL_OPTION_REQUIRED = set(CAROUSEL_OPTION_SCHEMA) - {"option_id"}
_CAROUSEL_SLIDE_REQUIRED = set(CAROUSEL_SLIDE_SCHEMA) - {"slide_id"}

# System prompts foram movidos para config/brands/<slug>.py (Fase B.2).
# Cada cliente define seu próprio tom/identidade — o copy_generator lê do
# brand atual via settings.brand.system_prompt / system_prompt_carousel.


def _build_user_message(briefing: dict, nota_ajuste: str = "") -> str:
    """
    Monta o prompt do usuário a partir do briefing validado.

    Se `nota_ajuste` for fornecida (regeneração após pedido do Henrique), ela é
    anexada como instrução prioritária.
    """
    tema = briefing["tema_especifico"] or "(livre — você escolhe a pauta)"
    referencias = briefing["referencias"] or "(nenhuma)"
    msg = (
        "Gere 3 variações de copy para um post seguindo este briefing:\n\n"
        f"- Área do direito: {briefing['area_direito']}\n"
        f"- Perfil do cliente ideal: {briefing['perfil_cliente_ideal']}\n"
        f"- Tom: {briefing['tom']}\n"
        f"- Objetivo: {briefing['objetivo']}\n"
        f"- Formato do post: {briefing['formato']} ({briefing['num_slides']} slide(s))\n"
        f"- Tema específico: {tema}\n"
        f"- Referências/observações: {referencias}\n\n"
        "Lembre-se dos limites: headline <=60 chars, subheadline <=80, "
        "body <=150, cta <=40, caption <=2200, até 20 hashtags."
    )
    if nota_ajuste.strip():
        msg += (
            "\n\nAJUSTE SOLICITADO PELO CLIENTE (priorize ao máximo este pedido): "
            f"{nota_ajuste.strip()}"
        )
    return msg


def _build_user_message_carousel(briefing: dict, nota_ajuste: str = "") -> str:
    """
    Variante do user prompt para carrossel — explicita N slides por variação.
    """
    tema = briefing["tema_especifico"] or "(livre — você escolhe a pauta)"
    referencias = briefing["referencias"] or "(nenhuma)"
    n = briefing["num_slides"]
    msg = (
        f"Gere 3 variações de carrossel com EXATAMENTE {n} slides cada, "
        "seguindo este briefing:\n\n"
        f"- Área do direito: {briefing['area_direito']}\n"
        f"- Perfil do cliente ideal: {briefing['perfil_cliente_ideal']}\n"
        f"- Tom: {briefing['tom']}\n"
        f"- Objetivo: {briefing['objetivo']}\n"
        f"- Formato: carrossel ({n} slides)\n"
        f"- Tema específico: {tema}\n"
        f"- Referências/observações: {referencias}\n\n"
        f"Cada variação (option) deve ter 1 caption + 1 cta + 1 lista de hashtags, "
        f"e {n} slides com slide_id 1..{n}.\n"
        "Limites: headline (slide) <=60 chars, subheadline (slide) <=80, "
        "body (slide) <=150, cta <=40, caption <=2200, até 20 hashtags."
    )
    if nota_ajuste.strip():
        msg += (
            "\n\nAJUSTE SOLICITADO PELO CLIENTE (priorize ao máximo este pedido): "
            f"{nota_ajuste.strip()}"
        )
    return msg


def _parse_and_validate(raw_text: str) -> list[dict]:
    """
    Parseia a resposta do modelo como JSON e valida as 3 variações.

    Raises:
        ValueError: se o JSON for inválido ou faltarem campos/opções.
    """
    data = json.loads(raw_text)  # pode lançar json.JSONDecodeError (subclasse de ValueError)

    # Aceita {"options": [...]} ou diretamente [...]
    options = data["options"] if isinstance(data, dict) else data
    if not isinstance(options, list) or len(options) != settings.NUM_COPY_OPTIONS:
        raise ValueError(
            f"Esperado {settings.NUM_COPY_OPTIONS} variações; recebido: "
            f"{len(options) if isinstance(options, list) else type(options).__name__}."
        )

    validadas: list[dict] = []
    for i, op in enumerate(options, start=1):
        faltando = _REQUIRED_FIELDS - set(op)
        if faltando:
            raise ValueError(f"Variação {i} sem os campos: {sorted(faltando)}.")
        op["option_id"] = i  # normaliza o id sequencialmente
        if not isinstance(op["hashtags"], list):
            raise ValueError(f"Variação {i}: 'hashtags' deve ser uma lista.")
        op["hashtags"] = normalize_hashtags(op["hashtags"])  # limpa acento/casing/#
        validadas.append({campo: op[campo] for campo in COPY_SCHEMA})
    return validadas


def _parse_and_validate_carousel(raw_text: str, num_slides: int) -> list[dict]:
    """
    Parseia a resposta do modelo como JSON e valida 3 variações de carrossel.

    Cada variação deve ter num_slides slides com slide_id 1..N.

    Raises:
        ValueError: se o JSON, a contagem ou os campos estiverem inválidos.
    """
    data = json.loads(raw_text)
    options = data["options"] if isinstance(data, dict) else data
    if not isinstance(options, list) or len(options) != settings.NUM_COPY_OPTIONS:
        raise ValueError(
            f"Esperado {settings.NUM_COPY_OPTIONS} variações; recebido: "
            f"{len(options) if isinstance(options, list) else type(options).__name__}."
        )

    validadas: list[dict] = []
    for i, op in enumerate(options, start=1):
        faltando = _CAROUSEL_OPTION_REQUIRED - set(op)
        if faltando:
            raise ValueError(f"Variação {i} sem os campos: {sorted(faltando)}.")
        op["option_id"] = i
        if not isinstance(op["hashtags"], list):
            raise ValueError(f"Variação {i}: 'hashtags' deve ser uma lista.")
        if not isinstance(op["slides"], list) or len(op["slides"]) != num_slides:
            raise ValueError(
                f"Variação {i}: esperado {num_slides} slides; recebido "
                f"{len(op['slides']) if isinstance(op['slides'], list) else type(op['slides']).__name__}."
            )

        slides_validados: list[dict] = []
        for j, slide in enumerate(op["slides"], start=1):
            faltando_s = _CAROUSEL_SLIDE_REQUIRED - set(slide)
            if faltando_s:
                raise ValueError(
                    f"Variação {i}, slide {j} sem os campos: {sorted(faltando_s)}."
                )
            slide["slide_id"] = j  # normaliza ordem sequencial
            slides_validados.append({campo: slide[campo] for campo in CAROUSEL_SLIDE_SCHEMA})

        op["hashtags"] = normalize_hashtags(op["hashtags"])
        op["slides"] = slides_validados
        validadas.append({campo: op[campo] for campo in CAROUSEL_OPTION_SCHEMA})
    return validadas


def generate(briefing: dict, nota_ajuste: str = "", versao: int = 1) -> list[dict]:
    """
    Gera variações de copy a partir do briefing validado.

    Args:
        briefing: saída de briefing_parser.parse.
        nota_ajuste: pedido de ajuste do Henrique (regeneração). Vazio na 1ª geração.
        versao: número da versão (1 na 1ª geração, 2+ ao regerar). Determina o
            arquivo de saída: campaigns/{cid}/copy_v{versao}.json.

    Returns:
        Lista de dicts:
          - square/portrait: cada item segue COPY_SCHEMA
          - carousel: cada item segue CAROUSEL_OPTION_SCHEMA (com slides[N] aninhados)

    Raises:
        RuntimeError: se a API falhar ou o JSON for inválido após as retentativas.
    """
    campaign_id = briefing["campaign_id"]

    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY não configurada. Defina-a no arquivo .env antes de gerar copy."
        )

    is_carousel = briefing["formato"] == "carousel"
    system_prompt = (
        settings.brand.system_prompt_carousel if is_carousel
        else settings.brand.system_prompt
    )
    user_message = (
        _build_user_message_carousel(briefing, nota_ajuste)
        if is_carousel
        else _build_user_message(briefing, nota_ajuste)
    )

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    ultima_excecao: Exception | None = None
    # 1 tentativa + até 2 retentativas (total 3)
    for tentativa in range(1, 4):
        try:
            utils.log(campaign_id, f"copy_generator: tentativa {tentativa} (modelo {settings.OPENAI_MODEL})")
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                max_tokens=settings.COPY_MAX_TOKENS,
                temperature=settings.OPENAI_COPY_TEMPERATURE,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            raw_text = response.choices[0].message.content
            opcoes = (
                _parse_and_validate_carousel(raw_text, briefing["num_slides"])
                if is_carousel
                else _parse_and_validate(raw_text)
            )
            campaign_store.save_copy_version(
                campaign_id, versao, opcoes, nota_ajuste=nota_ajuste,
            )
            utils.log(
                campaign_id,
                f"copy_generator: 3 variações geradas e salvas (versão {versao}).",
            )
            return opcoes

        except ValueError as e:
            # Erro de parsing/validação — tenta de novo
            ultima_excecao = e
            utils.log(campaign_id, f"copy_generator: JSON inválido na tentativa {tentativa}: {e}")
            print(f"⚠️  Copy: resposta inválida na tentativa {tentativa} — tentando novamente...")

        except Exception as e:
            ultima_excecao = e
            utils.log(campaign_id, f"copy_generator: erro de API na tentativa {tentativa}: {e}")

            # Erros não-retentáveis (cota/auth): falha imediata com orientação.
            mensagem_fatal = _erro_fatal(e)
            if mensagem_fatal:
                utils.log(campaign_id, f"copy_generator: erro fatal — {mensagem_fatal}")
                raise RuntimeError(mensagem_fatal) from e

            print(f"⚠️  Copy: erro na OpenAI API (tentativa {tentativa}): {e}")

    msg = (
        "❌ Falha ao gerar copy após 3 tentativas. "
        f"Último erro: {ultima_excecao}. "
        "Verifique sua OPENAI_API_KEY e a conexão."
    )
    utils.log(campaign_id, msg)
    raise RuntimeError(msg)


def _erro_fatal(e: Exception) -> str | None:
    """
    Retorna uma mensagem de erro clara se a exceção for NÃO-retentável
    (cota esgotada, chave inválida, sem permissão); senão, None (pode retentar).
    """
    code = getattr(e, "code", None)
    status = getattr(e, "status_code", None)

    if code == "insufficient_quota":
        return (
            "❌ OpenAI: cota/créditos esgotados (insufficient_quota). "
            "A geração de copy não vai funcionar até a conta ter saldo. "
            "Adicione créditos em https://platform.openai.com/account/billing "
            "e confirme que o método de pagamento está ativo."
        )
    if code in {"invalid_api_key"} or status in {401}:
        return (
            "❌ OpenAI: chave inválida ou não autorizada (401). "
            "Confira o valor de OPENAI_API_KEY no arquivo .env."
        )
    if status in {403}:
        return (
            "❌ OpenAI: acesso negado (403) — a chave pode não ter permissão "
            f"para o modelo {settings.OPENAI_MODEL}."
        )
    return None


