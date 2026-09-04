"""
modules/theme_suggester.py — Sugestão de tema pro lembrete do bot de WhatsApp.

Parte do fluxo de geração automática de campanha (item 4, spec de
2026-09-03): antes de pedir pro cliente escolher um tema, o bot mostra
opções — e essas opções vêm daqui, olhando o histórico recente de posts
pra sugerir algo relevante e sem repetir o que já foi feito.

Diferente de `copy_generator.py` (crítico — falha o pipeline se a OpenAI
cair), isto é uma conveniência: se a OpenAI falhar ou não houver histórico
suficiente, cai pro fallback local em vez de quebrar o lembrete do bot.
"""

from __future__ import annotations

from openai import OpenAI

from config import settings
from modules import campaign_store

# Quantas campanhas recentes entram no contexto do prompt — nem tudo (custaria
# tokens à toa), nem pouco (perde o "não repita o mesmo ângulo de novo").
HISTORICO_TAMANHO = 12

# Usado quando a OpenAI falha ou não há histórico — genérico o bastante pra
# nunca ficar sem sugestão nenhuma pro bot mandar.
SUGESTOES_FALLBACK = [
    "Direito Empresarial — cláusulas contratuais que evitam litígio",
    "Direito Digital — proteção de dados e LGPD no dia a dia",
    "Direito do Consumidor — direitos em compras online",
]


def _historico_recente(n: int = HISTORICO_TAMANHO) -> list[dict]:
    """Últimas N campanhas (qualquer status) com area_direito/tema_especifico preenchidos."""
    campanhas = campaign_store.listar()[:n]
    return [
        {
            "area_direito": c["briefing"].get("area_direito", ""),
            "tema_especifico": c["briefing"].get("tema_especifico", ""),
        }
        for c in campanhas
        if c["briefing"].get("area_direito")
    ]


def suggest_themes(n: int = 3) -> list[str]:
    """
    Sugere `n` temas de campanha, evitando repetir os últimos já usados.

    Returns:
        Lista de strings curtas (formato "Área — ângulo específico"),
        prontas pra virar botões/lista no WhatsApp. Nunca levanta exceção —
        cai pro fallback em qualquer falha (chave ausente, API fora, etc).
    """
    historico = _historico_recente()

    if not settings.OPENAI_API_KEY:
        return SUGESTOES_FALLBACK[:n]

    linhas_historico = "\n".join(
        f"- {h['area_direito']}" + (f" ({h['tema_especifico']})" if h["tema_especifico"] else "")
        for h in historico
    ) or "(nenhuma campanha anterior ainda)"

    prompt = (
        f"Você sugere pautas de conteúdo jurídico pro Instagram de um escritório "
        f"brasileiro de advocacia. Temas já usados recentemente (não repita o mesmo "
        f"ângulo, pode repetir a área do direito com um ângulo diferente):\n"
        f"{linhas_historico}\n\n"
        f"Sugira exatamente {n} temas NOVOS, cada um numa linha, formato "
        f'"Área do direito — ângulo específico". Curto, sem explicação extra.'
    )

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=200,
            temperature=0.9,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = resp.choices[0].message.content or ""
        linhas = [l.strip("- ").strip() for l in texto.strip().split("\n") if l.strip()]
        sugestoes = [l for l in linhas if l][:n]
        return sugestoes if sugestoes else SUGESTOES_FALLBACK[:n]
    except Exception:
        # Nunca deixa o lembrete do bot travar por causa disto — sugestão
        # ruim (fallback genérico) é sempre melhor que bot mudo.
        return SUGESTOES_FALLBACK[:n]
