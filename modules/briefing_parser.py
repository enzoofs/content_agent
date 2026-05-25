"""
modules/briefing_parser.py — Validação e estruturação do briefing.

Recebe o briefing preenchido pelo Henrique (dicionário Python) e o transforma
em JSON estruturado e validado que os demais módulos consomem.

Comportamento em erro: lança ValueError com mensagem clara (em português)
indicando exatamente qual campo falhou.
"""

from __future__ import annotations

import re
from datetime import datetime

from modules.utils import make_campaign_id

# Padrões de tentativa de prompt injection nos campos livres do briefing.
# Não é defesa absoluta (LLM pode obedecer instrução obfuscada), mas barra
# o ataque trivial copy-paste tipo "Ignore previous instructions and...".
# Bloqueamos textos que pareçam reescrever o system prompt do agente.
_PROMPT_INJECTION_PATTERNS = [
    r"\bignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)\b",
    r"\bdisregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)\b",
    r"\b(you|voc[eê])\s+(are|is|s[ãa]o)\s+(now|agora)\s+a\s+",
    r"\bdesconsidere\s+(todas?\s+as\s+)?(instru[cç][õo]es?|regras?)\s+(anteriores?|acima)\b",
    r"\bignor[ea]\s+(todas?\s+as\s+)?(instru[cç][õo]es?|prompts?|regras?)\s+(anteriores?|acima)\b",
    r"^\s*\[?(system|assistant|user)\s*[:\]]",
    r"<\s*system\s*>",
    r"\bnew\s+(system\s+)?(prompt|instructions?)\s*[:=]",
    r"###\s*(system|new\s+instructions?)",
]
_INJECTION_RE = re.compile("|".join(_PROMPT_INJECTION_PATTERNS), re.IGNORECASE | re.MULTILINE)


def _check_prompt_injection(campo: str, valor: str) -> None:
    """
    Detecta padrões suspeitos de tentativa de override do system prompt.

    Não tenta ser perfeito (LLM é o limite), mas barra o ataque óbvio.
    Em produção real, isto vira input filter com modelo dedicado (Phi-3, Llama Guard, etc).
    """
    if not isinstance(valor, str) or not valor:
        return
    if _INJECTION_RE.search(valor):
        raise ValueError(
            f"Campo '{campo}' contém padrão suspeito de instrução pro modelo. "
            "Reescreva sem tentar dar instruções diretas ao sistema."
        )

# Schema do briefing — TODOS OS CAMPOS SÃO OBRIGATÓRIOS
BRIEFING_SCHEMA: dict[str, type] = {
    "campaign_id": str,            # gerado automaticamente: YYYY-MM-DD_slug
    "created_at": str,             # ISO 8601
    "area_direito": str,           # ex: "direito médico"
    "perfil_cliente_ideal": str,   # cliente que querem atrair
    "tom": str,                    # "tecnico" | "acessivel"
    "objetivo": str,               # "awareness" | "captacao" | "posicionamento"
    "tema_especifico": str,        # pode ser ""
    "formato": str,                # "square" | "portrait" | "carousel" | "story"
    "num_slides": int,             # 1 para simples; 3-8 para carrossel
    "referencias": str,            # pode ser ""
}

TONS_VALIDOS = {"tecnico", "acessivel"}
OBJETIVOS_VALIDOS = {"awareness", "captacao", "posicionamento"}
FORMATOS_VALIDOS = {"square", "portrait", "carousel", "story"}

# Limite de caracteres por campo livre — evita custo/erro com texto gigante no
# prompt da OpenAI e protege a UI de payloads absurdos.
MAX_CHARS = {
    "area_direito": 200,
    "perfil_cliente_ideal": 500,
    "tema_especifico": 500,
    "referencias": 2000,
}


def parse(briefing_raw: dict) -> dict:
    """
    Valida o briefing e retorna o JSON estruturado.

    Args:
        briefing_raw: respostas do formulário de briefing. Campos esperados:
            area_direito, perfil_cliente_ideal, tom, objetivo, tema_especifico,
            formato, num_slides, referencias. (campaign_id e created_at são
            gerados aqui se ausentes.)

    Returns:
        dict validado conforme BRIEFING_SCHEMA.

    Raises:
        ValueError: com mensagem clara indicando qual campo falhou.
    """
    b = dict(briefing_raw)  # cópia rasa — não muta o input

    # --- Normalização de strings (trim) ---
    for campo in ("area_direito", "perfil_cliente_ideal", "tom", "objetivo",
                  "tema_especifico", "formato", "referencias"):
        if campo in b and isinstance(b[campo], str):
            b[campo] = b[campo].strip()

    # --- Campos obrigatórios não-vazios ---
    if not b.get("area_direito"):
        raise ValueError("Campo 'area_direito' é obrigatório e não pode ser vazio.")
    if not b.get("perfil_cliente_ideal"):
        raise ValueError(
            "Campo 'perfil_cliente_ideal' é obrigatório e não pode ser vazio."
        )

    # --- Cap de caracteres por campo livre (custo/erro de prompt gigante) ---
    for campo, limite in MAX_CHARS.items():
        valor = b.get(campo) or ""
        if isinstance(valor, str) and len(valor) > limite:
            raise ValueError(
                f"Campo '{campo}' excede o limite de {limite} caracteres "
                f"(recebido: {len(valor)})."
            )

    # --- Anti prompt injection nos campos livres (vão direto pro prompt do LLM) ---
    for campo in ("area_direito", "perfil_cliente_ideal", "tema_especifico", "referencias"):
        _check_prompt_injection(campo, b.get(campo) or "")

    # --- Enums ---
    if b.get("tom") not in TONS_VALIDOS:
        raise ValueError(
            f"Campo 'tom' deve ser um de {sorted(TONS_VALIDOS)}; recebido: {b.get('tom')!r}."
        )
    if b.get("objetivo") not in OBJETIVOS_VALIDOS:
        raise ValueError(
            f"Campo 'objetivo' deve ser um de {sorted(OBJETIVOS_VALIDOS)}; "
            f"recebido: {b.get('objetivo')!r}."
        )
    if b.get("formato") not in FORMATOS_VALIDOS:
        raise ValueError(
            f"Campo 'formato' deve ser um de {sorted(FORMATOS_VALIDOS)}; "
            f"recebido: {b.get('formato')!r}."
        )

    # --- num_slides ---
    try:
        num_slides = int(b.get("num_slides", 1))
    except (TypeError, ValueError):
        raise ValueError(
            f"Campo 'num_slides' deve ser um inteiro; recebido: {b.get('num_slides')!r}."
        )

    if b["formato"] == "carousel":
        if not (3 <= num_slides <= 8):
            raise ValueError(
                "Para formato 'carousel', 'num_slides' deve estar entre 3 e 8; "
                f"recebido: {num_slides}."
            )
    else:
        # Posts simples são sempre 1 slide
        num_slides = 1
    b["num_slides"] = num_slides

    # --- Campos opcionais garantidos como string ---
    b["tema_especifico"] = b.get("tema_especifico", "") or ""
    b["referencias"] = b.get("referencias", "") or ""

    # --- Campos gerados ---
    b["created_at"] = b.get("created_at") or datetime.now().isoformat(timespec="seconds")
    b["campaign_id"] = b.get("campaign_id") or make_campaign_id(
        b["area_direito"], b["tema_especifico"]
    )

    # --- Retorna apenas os campos do schema, na ordem do schema ---
    return {campo: b[campo] for campo in BRIEFING_SCHEMA}
