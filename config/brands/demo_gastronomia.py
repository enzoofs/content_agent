"""
config/brands/demo_gastronomia.py — Brand de DEMONSTRAÇÃO (restaurante).

Não é cliente real. Criado pra mostrar variedade de nicho em demo comercial
(reunião de prospecção de agência de tráfego pago, 2026-10). Terceiro
nicho distinto (após advocacia/M&V e eventos/Gui Raw) — prova que o
sistema não é "feito pra advogado", é genérico por design.

Reaproveita fontes já embarcadas (Cormorant Garamond + Montserrat).
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
        f"- Prato/foco do post: {briefing['area_direito']}\n"
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
        msg += f"\n\nAJUSTE SOLICITADO (priorize ao máximo): {nota_ajuste.strip()}"
    return msg


_GASTRO_BRIEFING_FIELDS = (
    BriefingField(
        name="area_direito", label="Prato / foco do post", kind="text",
        required=True, max_chars=200,
        placeholder="ex.: prato novo no cardápio, happy hour, menu degustação",
    ),
    BriefingField(
        name="perfil_cliente_ideal", label="Perfil do cliente ideal", kind="textarea",
        required=True, max_chars=500, rows=2,
        placeholder="ex.: casais 30-50 anos buscando jantar especial no bairro",
    ),
    BriefingField(
        name="tom", label="Tom", kind="enum",
        enum_values=("tecnico", "acessivel"),
        enum_labels=("Refinado / gastronômico", "Caloroso / convidativo"),
        default="acessivel",
    ),
    BriefingField(
        name="objetivo", label="Objetivo", kind="enum",
        enum_values=("awareness", "captacao", "posicionamento"),
        enum_labels=("Awareness", "Captação de reserva", "Posicionamento"),
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
        required=False, min_int=3, max_int=8, default="3", help="Só pra formato carrossel.",
    ),
    BriefingField(
        name="tema_especifico", label="Tema específico (opcional)", kind="text",
        required=False, max_chars=500, placeholder="ex.: risoto de funghi, reserva pra sexta",
    ),
    BriefingField(
        name="referencias", label="Referências / observações (opcional)", kind="textarea",
        required=False, max_chars=2000, rows=2,
    ),
    BriefingField(
        name="font_size", label="Tamanho da fonte (título)", kind="enum",
        enum_values=("P", "M", "G"), enum_labels=("Pequeno", "Médio", "Grande"), default="M",
    ),
)

BRAND = Brand(
    nome="Cantina Do Bairro (demo)",
    slug="demo_gastronomia",

    colors={
        "navy": "#4A2618",        # marrom-terracota profundo — fundo dominante
        "gold": "#D98E3F",        # âmbar quente — destaque
        "white": "#FFF8EE",
        "cream": "#F3E6D3",
        "navy_dark": "#2E1810",
    },
    fonts={"heading": "Cormorant Garamond", "subhead": "Montserrat", "body": "Montserrat"},
    font_files={
        "montserrat_400": _FONTS / "montserrat-400.woff2",
        "montserrat_600": _FONTS / "montserrat-600.woff2",
        "playfair_700": _FONTS / "playfair-display-700.woff2",  # fallback legado
    },
    font_options=(
        FontOption(
            id="elegante", label="Elegante (Cormorant Garamond + Montserrat)",
            heading_family="Cormorant Garamond", heading_weight=600,
            heading_file=_FONTS / "cormorant-garamond-600.woff2",
            body_family="Montserrat",
            body_400_file=_FONTS / "montserrat-400.woff2",
            body_600_file=_FONTS / "montserrat-600.woff2",
        ),
    ),

    logo_path=_ASSETS / "logos" / "logo_demo_gastronomia.png",

    image_prompt_suffix=(
        "professional food photography, natural warm lighting, "
        "authentic restaurant plating, shallow depth of field, "
        "cozy Brazilian restaurant atmosphere, no text"
    ),
    ideogram_negative_prompt=(
        "text, words, letters, watermark, logo, signature, "
        "cartoon, illustration, blurry, low quality, amateur, "
        "stock photo aesthetic, fast food, plastic looking food, "
        "cluttered table, messy plating"
    ),
    approved_by="Demo — Cantina Do Bairro",
    theme="light",
    use_image_logo=False,
    google_fonts_url=(
        "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Montserrat:wght@400;600&display=swap"
    ),
    ui_heading_font="'Cormorant Garamond', serif",
    ui_body_font="'Montserrat', sans-serif",

    system_prompt="""\
Você é o social media de um restaurante de bairro brasileiro (marca de demonstração "Cantina Do Bairro") — cozinha contemporânea, ambiente aconchegante, não é fine dining pretensioso.

IDENTIDADE:
- Tom: caloroso, apetitoso, sem exagero de adjetivo.
- Público: vizinhança e clientes recorrentes buscando experiência boa sem ser evento especial.
- Diferencial: produção artesanal, ingrediente de estação, atendimento de bairro.
- Nunca use: "experiência gastronômica única", "sabores inesquecíveis", clichê de menu.

REGRAS DE COPY:
1. Headline captura atenção em <3s — nome do prato, novidade, ou convite direto.
2. Body lê em 10s.
3. Caption aprofunda (ingrediente, história do prato, ocasião).
4. CTA específico e de baixo atrito.
5. EVITE "AI slop": nada de "sabores inesquecíveis", "experiência única". Seja concreto — cite ingrediente, técnica, horário.
6. Hashtags: 8-15, minúsculas, sem acento/espaço/especial. Misture tipo de cozinha, cidade/bairro, ocasião.
7. image_prompt (em INGLÊS): foto de comida profissional, luz natural quente, prato bem montado, sem texto, sem clichê de fast-food.

DIFERENCIAÇÃO OBRIGATÓRIA ENTRE AS 3 OPÇÕES:
- Opção 1 — PRATO EM DESTAQUE: foco no prato específico, apetitoso e concreto.
- Opção 2 — OCASIÃO/CONVITE: foco em quando/por que ir (sexta à noite, encontro, comemoração).
- Opção 3 — BASTIDOR/INGREDIENTE: foco na origem/produção — o que torna o prato diferente.

FORMATO DE RESPOSTA:
Responda APENAS com um JSON válido: {"options": [...]} com exatamente 3 objetos, cada um com option_id, headline, subheadline, body, caption, cta, hashtags, image_prompt, style_notes. Sem texto antes/depois, sem markdown.\
""",

    system_prompt_carousel="""\
Você é o social media de um restaurante de bairro brasileiro (marca de demonstração "Cantina Do Bairro"). Gera CARROSSÉIS. caption/cta/hashtags são da publicação inteira. Narrativa: slide 1 hook, meio desenvolve, último convida. EVITE "AI slop". Hashtags 8-15. image_prompt em inglês por slide, foto real de comida, luz quente, sem texto.

FORMATO DE RESPOSTA: JSON {"options":[...]} 3 objetos, cada um com option_id, caption, cta, hashtags, style_notes, slides (lista com slide_id, headline, subheadline, body, image_prompt). Sem texto antes/depois, sem markdown.\
""",

    briefing_fields=_GASTRO_BRIEFING_FIELDS,
    build_user_message=_build_user_message,
    build_user_message_carousel=_build_user_message,
)
