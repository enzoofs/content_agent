# Mendes & Vaz — Social (TimeLabs · Fase 1)

Sistema de automação de conteúdo para Instagram e LinkedIn do escritório
**Mendes & Vaz — Sociedade de Advogados** (Belo Horizonte, MG).

Pipeline Fase 1:

```
Briefing → Copy (OpenAI) → Arte (Ideogram) → Composição (HTML/CSS → PNG) → Aprovação (Flask) → Export PNG
```

Princípios inegociáveis:

- **Texto nunca dentro de imagem de IA** — sempre renderizado por código (zero erro de digitação).
- **Identidade visual fixa** — paleta navy/gold, fontes Playfair Display + Montserrat.
- **Human in the loop** — o Henrique aprova tudo; nada publica automaticamente.

> Nota de stack: a spec original previa a Claude API para a geração de copy.
> Nesta fase usamos a **OpenAI** (sem chave Anthropic disponível). O modelo é
> configurável em `config/settings.py` (`OPENAI_MODEL`). Sem chave Ideogram, a
> geração de arte usa **imagens placeholder** locais (`USE_MOCK_IMAGES`).

## Estrutura

```
config/        Configuração centralizada (settings.py)
assets/        Logo e texturas
templates/     Templates HTML dos posts (square, portrait, carousel)
modules/       Etapas do pipeline (briefing, copy, image, composer, approval, export)
campaigns/     Artefatos por campanha (gerado, ignorado no git)
exports/       Posts aprovados + metadados (gerado, ignorado no git)
approval_ui/   Interface de aprovação (HTML/CSS/JS vanilla)
main.py        Entry point / orquestração
test_pipeline.py  Teste de smoke (mocks, sem APIs reais)
```

## Setup

```bash
# 1. Ambiente virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# 2. Dependências
pip install -r requirements.txt

# 3. Navegador do Playwright
playwright install chromium

# 4. Variáveis de ambiente
copy .env.example .env         # Windows  (cp no Unix)
# editar .env: OPENAI_API_KEY (obrigatória), IDEOGRAM_API_KEY (opcional por ora)

# 5. Logo do cliente já está em assets/logo_mendes_vaz.png
#    (baixa resolução — marcada para substituição)

# 6. Rodar
python main.py --campaign novo
```

## Status

Fase 1 em construção. Esqueleto montado; módulos sendo preenchidos um a um.

---
*TimeLabs · Enzo Ferraz · Maio 2026*
