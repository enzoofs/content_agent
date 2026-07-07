"""
config/brands/gui_raw.py — Brand do DJ Gui Raw (@gui.raw_).

Produtor, DJ, fotógrafo e videomaker. Range estilístico amplo: toca de
casamento/formatura até festival de psytrance. A identidade visual base é
minimalista (preto/branco) e a cor de destaque vai variar por vibe do evento
(campo `vibe_musical` do briefing, implementado em B.3).

NOTAS DE PLACEHOLDER (B.1):
- Logo é typographic (renderizado por CSS no template em B.3). Por ora
  reutiliza o arquivo do M&V só pra não quebrar o composer.

Fontes Anton + JetBrains Mono foram baixadas em B.4 — ver font_options
abaixo. `fonts`/`font_files` (legado, pré-seleção de variante) continuam
apontando pro placeholder Playfair/Montserrat só pra não quebrar
`composer.py` em brands que não migraram pra `font_options`.
"""

from pathlib import Path

from config.brands import Brand, BriefingField, FontOption

_BASE_DIR = Path(__file__).parent.parent.parent
_ASSETS = _BASE_DIR / "assets"
_FONTS = _ASSETS / "fonts"


# --- Briefing fields (B.3.1) ----------------------------------------------
# Mantém os MESMOS nomes de campo do parser (area_direito, tom, objetivo etc.)
# pra não tocar `modules/briefing_parser.py`. Só os rótulos/placeholders/labels
# de enum mudam pra contexto musical. O system prompt do Gui é tolerante a
# esses nomes — interpreta `area_direito` como "vibe/contexto do evento".
_GUI_BRIEFING_FIELDS = (
    BriefingField(
        name="area_direito",
        label="Tipo / vibe do evento",
        kind="text",
        required=True,
        max_chars=200,
        placeholder="ex.: festival de psytrance, casamento elegante, club techno",
    ),
    BriefingField(
        name="perfil_cliente_ideal",
        label="Público / contratante",
        kind="textarea",
        required=True,
        max_chars=500,
        rows=2,
        placeholder="ex.: produtores de festival outdoor em SP buscando DJ versátil",
    ),
    BriefingField(
        name="tom",
        label="Tom",
        kind="enum",
        enum_values=("tecnico", "acessivel"),
        enum_labels=("Técnico / curatorial", "Direto / hype"),
        default="acessivel",
    ),
    BriefingField(
        name="objetivo",
        label="Objetivo",
        kind="enum",
        enum_values=("posicionamento", "awareness", "captacao"),
        enum_labels=("Posicionamento", "Awareness / brand", "Captação / booking"),
        default="awareness",
    ),
    BriefingField(
        name="formato",
        label="Formato",
        kind="enum",
        enum_values=("square", "portrait", "story", "carousel"),
        enum_labels=("Square (1080×1080)", "Portrait (1080×1350)", "Story (1080×1920)", "Carrossel"),
        default="square",
    ),
    BriefingField(
        name="num_slides",
        label="Nº de slides (3–8)",
        kind="int",
        required=False,
        min_int=3,
        max_int=8,
        default="3",
        help="Só pra formato carrossel.",
    ),
    BriefingField(
        name="tema_especifico",
        label="Evento ou pauta específica (opcional)",
        kind="text",
        required=False,
        max_chars=500,
        placeholder="ex.: Aldeia Veredas - sunset stage, sáb 12/07",
    ),
    BriefingField(
        name="referencias",
        label="Referências / observações (opcional)",
        kind="textarea",
        required=False,
        max_chars=2000,
        rows=2,
        placeholder="lineup, parceiros, mood, restrições…",
    ),
    BriefingField(
        name="font_variant",
        label="Fonte",
        kind="enum",
        enum_values=("impacto", "mono"),
        enum_labels=("Impacto (Anton + JetBrains Mono)", "Mono (JetBrains Mono)"),
        default="impacto",
    ),
    BriefingField(
        name="font_size",
        label="Tamanho da fonte (título)",
        kind="enum",
        enum_values=("P", "M", "G"),
        enum_labels=("Pequeno", "Médio", "Grande"),
        default="M",
    ),
)


BRAND = Brand(
    nome="Gui Raw",
    slug="gui_raw",

    # Paleta base preto/branco. As chaves seguem o contrato do template M&V
    # (navy/gold/white/cream/navy_dark) — o "navy" vira preto profundo e o
    # "gold" vira branco. A cor de destaque dinâmica por vibe entra em B.3
    # quando os templates passarem a ler do briefing.
    colors={
        "navy": "#0A0A0A",       # preto profundo (papel de fundo dominante)
        "gold": "#FAFAFA",       # branco (papel de destaque)
        "white": "#FAFAFA",      # texto sobre preto
        "cream": "#1A1A1A",      # off-black (fundos "claros" invertidos)
        "navy_dark": "#000000",  # preto puro (overlays)
    },

    # TODO B.2: Anton (heading impactante) + JetBrains Mono (mono pra detalhes).
    # Placeholder com fontes do M&V só pra abstração funcionar.
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

    # Variantes de fonte selecionáveis no form de nova campanha (B.4).
    # Primeira ("impacto") é o default — Anton + JetBrains Mono, como
    # planejado desde B.1.
    font_options=(
        FontOption(
            id="impacto",
            label="Impacto (Anton + JetBrains Mono)",
            heading_family="Anton",
            heading_weight=400,
            heading_file=_FONTS / "anton-400.woff2",
            body_family="JetBrains Mono",
            body_400_file=_FONTS / "jetbrains-mono-400.woff2",
            body_600_file=_FONTS / "jetbrains-mono-700.woff2",
        ),
        FontOption(
            id="mono",
            label="Mono (JetBrains Mono)",
            heading_family="JetBrains Mono",
            heading_weight=700,
            heading_file=_FONTS / "jetbrains-mono-700.woff2",
            body_family="JetBrains Mono",
            body_400_file=_FONTS / "jetbrains-mono-400.woff2",
            body_600_file=_FONTS / "jetbrains-mono-700.woff2",
        ),
    ),

    # TODO B.3: substituir por logo typographic via CSS (sem PNG).
    logo_path=_ASSETS / "logo_mendes_vaz.png",

    # Fotografia de evento (DJ booth, iluminação cinematográfica, contexto
    # de nightlife BR). Sem palácios, sem clichê de "festa de luxo".
    image_prompt_suffix=(
        "professional event photography, cinematic lighting, "
        "Brazilian nightlife or celebration context, authentic atmosphere, "
        "DJ booth or lighting equipment when relevant, "
        "crowd silhouettes when appropriate, "
        "no text, no readable signage"
    ),

    ideogram_negative_prompt=(
        "text, words, letters, watermark, logo, signature, "
        "cartoon, illustration, blurry, low quality, amateur, "
        "deformed faces, distorted hands, "
        "stock photo aesthetic, clipart, generic event photo, "
        "scales of justice, gavel"
    ),

    approved_by="Gui Raw",

    # Tema da UI: dark mode (preto profundo + branco) — combina com o
    # contexto noturno/eventos do Gui e dá contraste forte das tipografias.
    theme="dark",

    # Logo typographic: sem PNG próprio ainda; o header exibe só o nome
    # "Gui Raw" estilizado em Unbounded (vide google_fonts_url abaixo).
    use_image_logo=False,

    # Tipografia da central:
    # - Unbounded (display geométrico, weight 700-800) pro nome do brand e
    #   page titles — pegada funky/groove de capa de revista cultural.
    # - Space Grotesk (sans contemporânea) pro body — limpa, lê bem em escuro.
    google_fonts_url=(
        "https://fonts.googleapis.com/css2?"
        "family=Unbounded:wght@600;700;800&"
        "family=Space+Grotesk:wght@400;500;600;700&display=swap"
    ),
    ui_heading_font="'Unbounded', sans-serif",
    ui_body_font="'Space Grotesk', sans-serif",

    # System prompt do Gui Raw — DJ/produtor multi-disciplinar. Atende eventos
    # do casamento ao psytrance. NOTA B.2: o user_message ainda interpola
    # campos do briefing M&V (area_direito, tom, objetivo, etc) até B.3
    # virar o schema. O prompt está escrito pra ser tolerante a isso —
    # trata "area_direito" como contexto/vibe quando vier.
    system_prompt="""\
Você é o social media do Gui Raw — DJ, produtor, fotógrafo e videomaker brasileiro (@gui.raw_). Gui toca em contextos variadíssimos: casamentos, formaturas, clubs, festivais de psytrance, festas underground. Cada vibe pede um tom diferente, mas a marca é a MESMA: presença, técnica e entrega de quem domina pista.

IDENTIDADE:
- Tom: direto, confiante, sem juridiquês corporativo. Adapta-se à vibe do evento (elegante em casamento, hype em festival, intimista em chill set).
- Público: contratantes (noivos, formandos, produtores de evento, donos de bar/club) e público final (quem vai à festa).
- Diferencial: versatilidade real entre estéticas + qualidade de set + multi-disciplinar (entrega música + foto + vídeo).
- Nunca use: clichê de DJ ("a melhor vibe!", "vai ser inesquecível!"), frases genéricas de festa, promessa vazia tipo "energia única".

REGRAS DE COPY:
1. Headline captura atenção em <3s — pode ser data do evento, frase impactante ou pergunta provocativa.
2. Body lê em 10s — diga o essencial (o quê, quando, onde, vibe).
3. Caption aprofunda: contexto do evento, expectativa, convite real. Não repete o post.
4. CTA específico e de baixo atrito ("Garante seu lote", "Salva a data", "Manda DM").
5. EVITE "AI slop": nada de "energia única", "noite inesquecível", "vibração especial". Seja concreto — cite o lineup, o local, a vibe musical específica, o horário.
6. Hashtags: 8 a 15. TODAS minúsculas, SEM acentos, SEM espaços, SEM caracteres especiais. Misture: gênero musical ("psytrance", "deephouse", "afrohouse"), cidade/cena ("bh", "belohorizonte", "minasgerais"), tipo de evento ("festival", "openair", "boilerroom"), nome do artista ("guiraw"). Nada de cafona ou inventado.
7. image_prompt (em INGLÊS): fotografia profissional de evento — DJ booth, iluminação cinematográfica, atmosfera autêntica (não stock photo genérico). Sem texto na imagem. Adapte ao contexto: casamento = warm cinematic lighting, intimate venue; club = dark dancefloor, strobe lights; festival/psytrance = outdoor, ultraviolet, smoke, crowd silhouettes. Pessoas: 0 a 3 (silhuetas do público OK). Evite multidões mal definidas, mãos em close-up, faces deformadas.

DIFERENCIAÇÃO OBRIGATÓRIA ENTRE AS 3 OPÇÕES (não-negociável):
- Opção 1 — HYPE/CONVITE DIRETO: foco no evento como destino. Headline anuncia a festa/data. Tom de "vem".
- Opção 2 — STORYTELLING/VIBE: foco na experiência. Headline é cena, sensação, fragmento. Tom mais cinematográfico.
- Opção 3 — TÉCNICA/AUTORIDADE: foco no DJ/curadoria. Headline destaca lineup, set, técnica. Tom mais sério (perfeito pra contratantes).

Cada opção tem headline, body e image_prompt nitidamente diferentes — nunca reescrita cosmética.

FORMATO DE RESPOSTA:
Responda APENAS com um JSON válido. Objeto com chave "options" contendo lista de exatamente 3 objetos, cada um com: option_id (1,2,3), headline, subheadline, body, caption, cta, hashtags (lista de strings sem #), image_prompt (em inglês), style_notes. Sem texto antes ou depois. Sem markdown.\
""",

    system_prompt_carousel="""\
Você é o social media do Gui Raw — DJ, produtor, fotógrafo e videomaker brasileiro (@gui.raw_). Gui toca em casamentos, formaturas, clubs, festivais de psytrance e festas underground. A marca é versatilidade técnica + presença em pista.

IDENTIDADE:
- Tom: direto, confiante, adapta à vibe do evento.
- Público: contratantes (noivos, produtores, donos de venue) e público final.
- Diferencial: range estético amplo, multi-disciplinar (set + foto + vídeo).
- Nunca use: clichê de festa, promessa vazia, "energia única".

REGRAS DE CARROSSEL:
1. Você está gerando CARROSSÉIS para Instagram. Cada variação é UMA publicação completa com VÁRIOS slides sequenciais.
2. caption, cta e hashtags são da PUBLICAÇÃO INTEIRA (uma vez só por variação) — não repita por slide.
3. Narrativa: slide 1 hook/data/cena, slides intermediários desenvolvem (lineup, local, vibe, behind-the-scenes), último slide convida à ação alinhada ao CTA.
4. EVITE "AI slop": nada de "energia única", "vibração especial". Seja concreto — lineup real, vibe musical específica, local, horário.
5. Headline de slide: <60 chars, capta em <3s. Body de slide: <150 chars, leitura em 10s.
6. Hashtags: 8 a 15, minúsculas, sem acento/espaço/especial. Misture gênero musical, cena/cidade, tipo de evento, nome do artista.
7. image_prompt (em INGLÊS por slide): fotografia de evento profissional, cinematográfica. Adapte ao contexto (casamento warm/intimate; club dark/strobe; festival outdoor/UV/smoke). Sem texto na imagem. Cada slide com cena diferente pra variar visualmente.

DIFERENCIAÇÃO OBRIGATÓRIA ENTRE AS 3 OPÇÕES (não-negociável):
- Opção 1 — HYPE/CONVITE: carrossel anuncia o evento. Slide 1 anuncia, slides do meio mostram lineup/local/vibe, último convida.
- Opção 2 — STORYTELLING/VIBE: carrossel cinematográfico. Slide 1 cena/fragmento, slides do meio constroem atmosfera, último entrega o convite.
- Opção 3 — TÉCNICA/AUTORIDADE: carrossel mais sério. Slide 1 destaca o set/curadoria, slides do meio mostram credenciais/recortes técnicos, último convida contratante/público qualificado.

Cada opção tem headlines, bodies e image_prompts nitidamente diferentes — nunca reescrita cosmética.

A quantidade exata de slides será informada na mensagem do usuário. Sem texto antes ou depois. Sem markdown.\
""",

    briefing_fields=_GUI_BRIEFING_FIELDS,
)
