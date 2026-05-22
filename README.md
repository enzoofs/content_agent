# Mendes & Vaz — Social (TimeLabs)

Sistema de automação de conteúdo para Instagram e LinkedIn do escritório
**Mendes & Vaz — Sociedade de Advogados** (Belo Horizonte, MG).

Pipeline:

```
Briefing → Copy (OpenAI) → Arte (Ideogram) → Composição (HTML/CSS → PNG) → Aprovação → Export PNG
```

Tudo é operado por uma **Central de Controle** web local, onde o Henrique cria
campanhas (briefing de 7 campos), acompanha a geração, agenda uma data e aprova.

Princípios inegociáveis:

- **Texto nunca dentro de imagem de IA** — sempre renderizado por código (zero erro de digitação).
- **Identidade visual fixa** — paleta navy/gold, fontes Playfair Display + Montserrat.
- **Human in the loop** — o Henrique aprova tudo; nada publica automaticamente.

> Nota de stack: a spec original previa a Claude API para a geração de copy.
> Usamos a **OpenAI** (sem chave Anthropic disponível); modelo configurável em
> `config/settings.py` (`OPENAI_MODEL`). Sem chave Ideogram, a arte usa
> **placeholders** locais (`USE_MOCK_IMAGES`).

## Central de Controle

```bash
python main.py --serve
```

Abre `http://localhost:5000`. Telas:

- **Dashboard** — todas as campanhas com status, formato, tema e data agendada.
- **Nova campanha** — formulário de briefing (7 campos) → "Gerar campanha".
- **Progresso** — geração em background (copy → arte → composição); pode sair e voltar.
- **Aprovação** — 3 variações lado a lado, agendamento de data, aprovar ou
  **solicitar ajuste** (regera usando a nota).

> Agendamento (Fase atual): apenas **registra a data**. Publicação automática
> (Buffer) é uma fase futura.

## Estrutura

```
config/        Configuração centralizada (settings.py)
assets/        Logo e texturas
templates/     Templates HTML dos posts (square, portrait, carousel)
modules/       briefing_parser, copy_generator, image_generator, composer,
               exporter, campaign_store (estado), pipeline (motor), server (central web)
campaigns/     Artefatos + state.json por campanha (gerado, ignorado no git)
exports/       Posts aprovados + metadados (gerado, ignorado no git)
approval_ui/   SPA da central (HTML/CSS/JS vanilla)
docs/plans/    Design e plano de implementação
main.py        Entry point (--serve | --campaign novo)
tests/         Testes unitários (pytest, mocks)
test_pipeline.py  Smoke test de integração
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
# editar .env: OPENAI_API_KEY (obrigatória), IDEOGRAM_API_KEY (opcional)

# 5. Rodar a central
python main.py --serve
```

## Testes

```bash
python -m pytest -q          # unitários (mocks, sem APIs reais)
python test_pipeline.py      # smoke de integração (composição real via Playwright)
```

## Status

Fase 1 completa (geração + aprovação) e Central de Controle implementada.
Próximos passos (fases futuras): publicação automática (Buffer), captação de
leads (Airtable/WhatsApp), hospedagem online.

---
*TimeLabs · Enzo Ferraz · Maio 2026*
