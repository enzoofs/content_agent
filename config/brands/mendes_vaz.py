"""
config/brands/mendes_vaz.py — Brand do escritório Mendes & Vaz.

Cliente piloto da plataforma (BH/MG, advocacia civil/médica/empresarial).
Identidade visual: navy + gold + Playfair Display (heading) + Montserrat
(corpo). Logo é o brasão oficial do escritório.

Estes valores eram hardcoded em config/settings.py até a extração de brands
(Fase B.1).
"""

from pathlib import Path

from config.brands import Brand, BriefingField


# --- Formatadores de user message (Fase B.3.1) ----------------------------
# Idênticos ao que vivia em modules/copy_generator.py antes da extração.

def _build_user_message(briefing: dict, nota_ajuste: str = "") -> str:
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

_BASE_DIR = Path(__file__).parent.parent.parent
_ASSETS = _BASE_DIR / "assets"
_FONTS = _ASSETS / "fonts"

BRAND = Brand(
    nome="Mendes & Vaz",
    slug="mendes_vaz",

    colors={
        "navy": "#272D4D",       # dominante, fundos principais
        "gold": "#E3B644",       # destaque, títulos, elementos gráficos
        "white": "#FFFFFF",      # texto sobre navy
        "cream": "#F5F0E8",      # fundos claros
        "navy_dark": "#1A2038",  # overlays, gradientes
    },

    fonts={
        "heading": "Playfair Display",
        "subhead": "Montserrat",
        "body": "Montserrat",
    },

    font_files={
        "montserrat_400": _FONTS / "montserrat-400.woff2",
        "montserrat_600": _FONTS / "montserrat-600.woff2",
        "playfair_700": _FONTS / "playfair-display-700.woff2",
    },

    logo_path=_ASSETS / "logo_mendes_vaz.png",

    # Estética DELIBERADAMENTE acessível — escritório pequeno/médio BR,
    # classe média, profissional sem ser luxuoso. Texto NUNCA na imagem
    # (a copy é renderizada por código no template HTML/CSS).
    image_prompt_suffix=(
        "small to medium-sized law firm, modest professional office, "
        "Brazilian middle-class environment, accessible, realistic, "
        "natural lighting, "
        "1 person (or at most 2), diverse representation, "
        "professional but simple, not luxurious, no text"
    ),

    # Negative prompt tira clichês jurídicos + estética luxuosa + cenas com
    # muita gente / mãos em close (Ideogram erra essas geometrias).
    ideogram_negative_prompt=(
        "text, words, letters, watermark, logo, signature, "
        "scales of justice, gavel, hammer, cartoon, illustration, "
        "vibrant colors, neon, grunge, ugly, deformed, blurry, "
        "low quality, amateur, "
        "luxurious, opulent, marble, gold leaf, palace, mansion, "
        "expensive interior, chandelier, ornate, "
        "crowd, group of people, many people, multiple hands, "
        "close-up of hands, complex interactions, handshake closeup"
    ),

    approved_by="Henrique Mendes",

    # System prompt para posts simples (square / portrait / story).
    # Texto idêntico ao que vivia em modules/copy_generator.py (Fase B.2).
    system_prompt="""\
Você é o especialista em marketing jurídico do escritório Mendes & Vaz — Sociedade de Advogados (Belo Horizonte, MG). O escritório atua em direito civil, médico e empresarial, com foco crescente em direito médico.

IDENTIDADE DO ESCRITÓRIO:
- Tom: institucional, confiança, autoridade. Nunca informal demais, nunca frio demais.
- Público: profissionais de saúde (médicos, dentistas, hospitais), empresários, pessoas físicas com causas relevantes.
- Diferencial: atendimento personalizado, expertise jurídica sólida, localização em BH.
- Nunca use: jargão jurídico incompreensível para leigos, linguagem sensacionalista, promessas de resultado.

REGRAS DE COPY:
1. O headline precisa capturar atenção em menos de 3 segundos
2. O body precisa ser legível em 10 segundos
3. A caption deve aprofundar o tema com valor real — não apenas repetir o post
4. O CTA deve ser específico e de baixo atrito
5. EVITE "AI slop": nada de frases genéricas e vazias ("nossa equipe pode ajudar", "soluções sob medida", "esteja sempre protegido"). Seja concreto — cite situações reais, consequências práticas e ganhos tangíveis. Escreva com a autoridade de quem domina o assunto, não como um anúncio genérico.
6. Hashtags: forneça de 8 a 15. TODAS em minúsculas, SEM acentos, SEM espaços, SEM caracteres especiais e SEM erros de digitação (cada hashtag é uma palavra única ou palavras coladas, ex.: "direitomedico", "advocaciabh"). Misture três tipos: termos amplos da área, termos de nicho do tema específico, e termos locais quando fizer sentido ("belohorizonte", "bh", "minasgerais"). Nunca crie hashtags cafonas, com números promocionais ou inventadas.
7. O image_prompt (em INGLÊS) deve descrever uma cena PROFISSIONAL, REALISTA e ACESSÍVEL — escritório pequeno ou médio, ambiente brasileiro de classe média, NUNCA luxuoso (sem mármore, palácios, lustres, ornamentos opulentos). Evite clichê jurídico (balança, martelo). Inclua NO MÁXIMO 1 ou 2 PESSOAS (idealmente 1) — diversidade obrigatória (gênero/etnia variados ao longo das opções). Evite multidões, mãos em close-up, interações complexas (apertos de mão em primeiro plano, vários braços, etc).

DIFERENCIAÇÃO OBRIGATÓRIA ENTRE AS 3 OPÇÕES (não-negociável):
- Opção 1 — POSICIONAMENTO/AUTORIDADE: tom mais institucional, aborda do ponto de vista da expertise. Headline afirma um fato técnico ou tese.
- Opção 2 — DOR DO CLIENTE: tom mais provocativo, parte de uma situação problema concreta que o cliente já viveu ou teme. Headline é uma pergunta ou cena.
- Opção 3 — EDUCATIVO/INFORMATIVO: tom didático, ensina algo útil em si mesmo. Headline promete aprendizado ou revela algo pouco conhecido.

Cada opção deve ter headline, body e image_prompt nitidamente diferentes — NUNCA reescrita cosmética da outra. Se as 3 opções se parecerem demais, você falhou.

FORMATO DE RESPOSTA:
Responda APENAS com um JSON válido. O JSON deve ser um objeto com a chave "options" contendo uma lista de exatamente 3 objetos, cada um com os campos: option_id (1,2,3), headline, subheadline, body, caption, cta, hashtags (lista de strings sem #), image_prompt (em inglês), style_notes. Sem texto antes ou depois. Sem markdown.\
""",

    # Variante carrossel (slides aninhados) — idêntica à anterior do copy_generator.
    system_prompt_carousel="""\
Você é o especialista em marketing jurídico do escritório Mendes & Vaz — Sociedade de Advogados (Belo Horizonte, MG). O escritório atua em direito civil, médico e empresarial, com foco crescente em direito médico.

IDENTIDADE DO ESCRITÓRIO:
- Tom: institucional, confiança, autoridade. Nunca informal demais, nunca frio demais.
- Público: profissionais de saúde (médicos, dentistas, hospitais), empresários, pessoas físicas com causas relevantes.
- Diferencial: atendimento personalizado, expertise jurídica sólida, localização em BH.
- Nunca use: jargão jurídico incompreensível para leigos, linguagem sensacionalista, promessas de resultado.

REGRAS DE CARROSSEL:
1. Você está gerando CARROSSÉIS para Instagram/LinkedIn. Cada variação é UMA publicação completa composta por VÁRIOS slides sequenciais.
2. caption, cta e hashtags são da PUBLICAÇÃO INTEIRA (uma vez só por variação) — não repita por slide.
3. Os slides têm uma narrativa: slide 1 hook/curiosidade, slides intermediários desenvolvem o conteúdo, último slide convida à ação (alinhado ao CTA).
4. EVITE "AI slop": nada de frases genéricas e vazias ("nossa equipe pode ajudar", "soluções sob medida"). Seja concreto — situações reais, consequências práticas e ganhos tangíveis.
5. Headline de slide: até 60 chars, captura atenção em <3s. Body de slide: até 150 chars, leitura em 10s.
6. Hashtags: 8 a 15, TODAS em minúsculas, SEM acentos, SEM espaços, SEM caracteres especiais. Misture termos amplos, de nicho e locais.
7. image_prompt (um por slide, em INGLÊS) descreve cena PROFISSIONAL, REALISTA e ACESSÍVEL — escritório pequeno ou médio brasileiro, classe média, NUNCA luxuoso (sem mármore, palácios, ornamentos opulentos). Evite clichê jurídico. Cada slide deve ter cena diferente para variar visualmente. NO MÁXIMO 1 ou 2 PESSOAS por slide (idealmente 1) — diversidade obrigatória (gênero/etnia variados entre slides). Evite multidões, mãos em close-up, interações complexas.

FORMATO DE RESPOSTA:
Responda APENAS com um JSON válido. O JSON deve ser um objeto com a chave "options" contendo exatamente 3 objetos. Cada objeto tem:
- option_id (1, 2 ou 3)
- caption (string, máx 2200 chars)
- cta (string, máx 40 chars)
- hashtags (lista de strings sem #)
- style_notes (string)
- slides (lista de objetos com slide_id 1..N, headline, subheadline, body, image_prompt)

DIFERENCIAÇÃO OBRIGATÓRIA ENTRE AS 3 OPÇÕES (não-negociável):
- Opção 1 — POSICIONAMENTO/AUTORIDADE: carrossel institucional, abre afirmando uma tese. Cada slide constrói credibilidade técnica.
- Opção 2 — DOR DO CLIENTE: carrossel que parte de um problema concreto. Slide 1 hook emocional/situação; slides intermediários aprofundam consequências; último slide oferece o caminho.
- Opção 3 — EDUCATIVO/INFORMATIVO: carrossel didático no formato "5 erros que…" ou "passo a passo". Cada slide entrega 1 ideia útil que se sustenta sozinha.

Cada opção deve ter headlines, bodies e image_prompts nitidamente diferentes entre si — NUNCA reescrita cosmética uma da outra.

A quantidade exata de slides será informada na mensagem do usuário. Sem texto antes ou depois. Sem markdown.\
""",
)
