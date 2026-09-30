"""
config/brands/demo_fitness.py — Brand de DEMONSTRAÇÃO (academia/fitness).

Não é cliente real. Criado pra mostrar variedade de nicho em demo comercial
(reunião de prospecção de agência de tráfego pago, 2026-10). Segue o mesmo
contrato de Brand que Mendes & Vaz / Gui Raw — prova que o sistema atende
qualquer segmento sem duplicar template, só trocando dado.

Reaproveita fontes já embarcadas (Anton + Montserrat) — zero asset novo.
"""

from pathlib import Path

from config.brands import Brand, BriefingField, FontOption

_BASE_DIR = Path(__file__).parent.parent.parent
_ASSETS = _BASE_DIR / "assets"
_FONTS = _ASSETS / "fonts"


def _build_user_message(briefing: dict, nota_ajuste: str = "") -> str:
    tema = briefing["tema_especifico"] or "(livre — você escolhe a pauta)"
    referencias = briefing["referencias"] or "(nenhuma)"
    msg = (
        "Gere 3 variações de copy para um post seguindo este briefing:\n\n"
        f"- Modalidade/foco: {briefing['area_direito']}\n"
        f"- Perfil do aluno ideal: {briefing['perfil_cliente_ideal']}\n"
        f"- Tom: {briefing['tom']}\n"
        f"- Objetivo: {briefing['objetivo']}\n"
        f"- Formato do post: {briefing['formato']} ({briefing['num_slides']} slide(s))\n"
        f"- Tema específico: {tema}\n"
        f"- Referências/observações: {referencias}\n\n"
        "Lembre-se dos limites: headline <=60 chars, subheadline <=80, "
        "body <=150, cta <=40, caption <=2200, até 20 hashtags."
    )
    if nota_ajuste.strip():
        msg += f"\n\nAJUSTE SOLICITADO (priorize ao máximo): {nota_ajuste.strip()}"
    return msg


_FITNESS_BRIEFING_FIELDS = (
    BriefingField(
        name="area_direito",
        label="Modalidade / foco do post",
        kind="text",
        required=True,
        max_chars=200,
        placeholder="ex.: treino funcional, musculação, aula de spinning",
    ),
    BriefingField(
        name="perfil_cliente_ideal",
        label="Perfil do aluno ideal",
        kind="textarea",
        required=True,
        max_chars=500,
        rows=2,
        placeholder="ex.: iniciantes 25-40 anos buscando rotina, sem tempo pra academia tradicional",
    ),
    BriefingField(
        name="tom", label="Tom", kind="enum",
        enum_values=("tecnico", "acessivel"),
        enum_labels=("Técnico / performance", "Motivacional / acessível"),
        default="acessivel",
    ),
    BriefingField(
        name="objetivo", label="Objetivo", kind="enum",
        enum_values=("awareness", "captacao", "posicionamento"),
        enum_labels=("Awareness", "Captação de matrícula", "Posicionamento"),
        default="captacao",
    ),
    BriefingField(
        name="formato", label="Formato", kind="enum",
        enum_values=("square", "portrait", "story", "carousel"),
        enum_labels=("Square (1080×1080)", "Portrait (1080×1350)", "Story (1080×1920)", "Carrossel"),
        default="square",
    ),
    BriefingField(
        name="num_slides", label="Nº de slides (3–8)", kind="int",
        required=False, min_int=3, max_int=8, default="3",
        help="Só pra formato carrossel.",
    ),
    BriefingField(
        name="tema_especifico", label="Tema específico (opcional)", kind="text",
        required=False, max_chars=500,
        placeholder="ex.: nova turma de manhã, avaliação física grátis",
    ),
    BriefingField(
        name="referencias", label="Referências / observações (opcional)", kind="textarea",
        required=False, max_chars=2000, rows=2,
    ),
    BriefingField(
        name="font_size", label="Tamanho da fonte (título)", kind="enum",
        enum_values=("P", "M", "G"), enum_labels=("Pequeno", "Médio", "Grande"), default="G",
    ),
)

BRAND = Brand(
    nome="Vitta Fit (demo)",
    slug="demo_fitness",

    colors={
        "navy": "#161616",        # preto quase puro — fundo dominante
        "gold": "#FF5A2E",        # laranja vibrante — energia/ação
        "white": "#FAFAFA",
        "cream": "#1F1F1F",
        "navy_dark": "#0A0A0A",
    },
    fonts={"heading": "Anton", "subhead": "Montserrat", "body": "Montserrat"},
    font_files={
        "montserrat_400": _FONTS / "montserrat-400.woff2",
        "montserrat_600": _FONTS / "montserrat-600.woff2",
        "playfair_700": _FONTS / "playfair-display-700.woff2",  # fallback legado
    },
    font_options=(
        FontOption(
            id="impacto", label="Impacto (Anton + Montserrat)",
            heading_family="Anton", heading_weight=400,
            heading_file=_FONTS / "anton-400.woff2",
            body_family="Montserrat",
            body_400_file=_FONTS / "montserrat-400.woff2",
            body_600_file=_FONTS / "montserrat-600.woff2",
        ),
    ),

    logo_path=_ASSETS / "logos" / "logo_demo_fitness.png",

    image_prompt_suffix=(
        "professional fitness studio photography, dynamic action shot, "
        "natural gym lighting, authentic Brazilian gym environment, "
        "1 person training, diverse representation, "
        "energetic but not overproduced, no text"
    ),
    ideogram_negative_prompt=(
        "text, words, letters, watermark, logo, signature, "
        "cartoon, illustration, blurry, low quality, amateur, "
        "deformed faces, distorted hands, "
        "stock photo aesthetic, generic gym clipart, "
        "crowd, multiple people, steroid physique, unrealistic body"
    ),
    approved_by="Demo — Vitta Fit",
    theme="dark",
    use_image_logo=False,
    google_fonts_url=(
        "https://fonts.googleapis.com/css2?family=Anton&family=Montserrat:wght@400;600;800&display=swap"
    ),
    ui_heading_font="'Anton', sans-serif",
    ui_body_font="'Montserrat', sans-serif",

    system_prompt="""\
Você é o social media de uma academia de treino funcional/musculação brasileira (marca de demonstração "Vitta Fit").

IDENTIDADE:
- Tom: motivacional mas concreto — nunca "no pain no gain" genérico.
- Público: gente comum tentando criar rotina de treino, não atleta de elite.
- Diferencial: horários flexíveis, acompanhamento real, ambiente sem intimidação.
- Nunca use: "transforme seu corpo em 30 dias", promessa vazia, comparação corporal.

REGRAS DE COPY:
1. Headline captura atenção em <3s — horário, resultado concreto, ou provocação real.
2. Body lê em 10s.
3. Caption aprofunda com valor real (dica, contexto, prova social concreta).
4. CTA específico e de baixo atrito.
5. EVITE "AI slop": nada de "sua melhor versão", "supere seus limites". Seja concreto.
6. Hashtags: 8-15, minúsculas, sem acento/espaço/especial. Misture modalidade, cidade, tipo de objetivo.
7. image_prompt (em INGLÊS): foto de academia real, iluminação natural, 1 pessoa treinando, sem texto, sem clichê de suplemento/anabolizante.

DIFERENCIAÇÃO OBRIGATÓRIA ENTRE AS 3 OPÇÕES:
- Opção 1 — RESULTADO CONCRETO: foco no que muda na rotina/corpo, de forma realista.
- Opção 2 — DOR DO ALUNO: parte de uma barreira real (falta de tempo, vergonha, cansaço).
- Opção 3 — COMUNIDADE/AMBIENTE: foco em como é treinar ali, não sozinho.

FORMATO DE RESPOSTA:
Responda APENAS com um JSON válido: {"options": [...]} com exatamente 3 objetos, cada um com option_id, headline, subheadline, body, caption, cta, hashtags, image_prompt, style_notes. Sem texto antes/depois, sem markdown.\
""",

    system_prompt_carousel="""\
Você é o social media de uma academia de treino funcional/musculação brasileira (marca de demonstração "Vitta Fit"). Gera CARROSSÉIS. caption/cta/hashtags são da publicação inteira. Narrativa: slide 1 hook, meio desenvolve, último convida. EVITE "AI slop". Hashtags 8-15. image_prompt em inglês por slide, foto real de academia, 1 pessoa, sem texto.

FORMATO DE RESPOSTA: JSON {"options":[...]} 3 objetos, cada um com option_id, caption, cta, hashtags, style_notes, slides (lista com slide_id, headline, subheadline, body, image_prompt). Sem texto antes/depois, sem markdown.\
""",

    briefing_fields=_FITNESS_BRIEFING_FIELDS,
    build_user_message=_build_user_message,
    build_user_message_carousel=_build_user_message,
)
