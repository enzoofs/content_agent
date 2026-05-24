# Mendes & Vaz — Social

> Sistema de geração de conteúdo para Instagram e LinkedIn do escritório
> **Mendes & Vaz — Sociedade de Advogados** (Belo Horizonte, MG).
>
> _TimeLabs · MVP de demo · Maio 2026_

```
Briefing → Copy (OpenAI) → Arte (Ideogram) → Composição (HTML/CSS → PNG) → Aprovação → Export
```

Tudo operado por uma **Central de Controle web local** onde o Henrique cria
campanhas (briefing de 7 campos), acompanha a geração, agenda data e aprova.

---

## Sumário

- [Princípios](#princípios)
- [Stack](#stack)
- [Setup](#setup)
- [Como usar](#como-usar)
- [Estrutura do projeto](#estrutura-do-projeto)
- [API HTTP](#api-http)
- [Testes](#testes)
- [Demo](#demo-quintafeira-280526)
- [Deploy futuro](#deploy-futuro)
- [Roadmap](#roadmap)

---

## Princípios

- **Texto nunca dentro de imagem de IA** — sempre renderizado por código (zero erro de digitação).
- **Identidade visual fixa** — paleta navy/gold, fontes Playfair Display + Montserrat
  (embarcadas localmente, demo funciona offline).
- **Human in the loop** — o Henrique aprova tudo; nada publica automaticamente.
- **Configuração centralizada** — `config/settings.py` é a única fonte de verdade
  pra cores, fontes, dimensões, modelos e chaves.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Copy | OpenAI (`gpt-4o`, configurável em `config/settings.py`) |
| Arte | Ideogram V_2 (com fallback automático pra placeholder navy/gold) |
| Composição | HTML/CSS via Playwright (Chromium headless) |
| Backend | Flask + waitress (WSGI cross-platform) |
| Storage | SQLite com WAL (`state.db`), thread-safe |
| Frontend | SPA vanilla JS — sem framework, sem build step |
| Tipografia | Playfair Display + Montserrat embarcadas como `woff2` (data URI) |

> A spec original previa Claude API para o copy. Usamos OpenAI por enquanto
> (chave Anthropic não disponível); trocar é mexer só em `config/settings.py`.

---

## Setup

```bash
# 1. Ambiente virtual
python -m venv venv
source venv/bin/activate         # Linux/macOS
# venv\Scripts\activate          # Windows

# 2. Dependências Python
pip install -r requirements.txt

# 3. Chromium do Playwright (única dep do SO)
playwright install chromium

# 4. Variáveis de ambiente
cp .env.example .env
# editar .env:
#   OPENAI_API_KEY=...   (obrigatória — copy não roda sem)
#   IDEOGRAM_API_KEY=... (opcional — sem chave, arte sai como placeholder)

# 5. Subir a central
python main.py --serve
```

O `--serve` valida credenciais e o Chromium antes de abrir a porta — se algo
estiver faltando, falha cedo com mensagem clara.

---

## Como usar

### Central de Controle (recomendado)

```bash
python main.py --serve
```

Abre `http://localhost:5000/` no navegador. Telas:

- **Dashboard** — todas as campanhas com status, formato, tema e data agendada.
- **Nova campanha** — formulário de briefing (7 campos) → "Gerar campanha".
- **Progresso** — geração em background (copy → arte → composição); pode sair e voltar.
- **Aprovação** — 3 variações lado a lado, agendamento, aprovar, solicitar ajuste
  (regenera usando a nota) ou editar copy manualmente sem regenerar (custo zero de API).
- **Calendário** — visão por data agendada das campanhas aprovadas.

### Linha de comando (debug)

```bash
python main.py --campaign novo
```

Coleta o briefing por prompts, gera e deixa pronto pra aprovação na central.

---

## Estrutura do projeto

```
config/
  settings.py            Configuração centralizada (paths, cores, fontes, modelos)
assets/
  logo_mendes_vaz.png    Logo institucional
  fonts/                 Playfair + Montserrat (woff2 subset latin, embarcadas)
templates/
  post_square.html       1080×1080
  post_portrait.html     1080×1350
  carousel_slide.html    1080×1080 para slides
modules/
  briefing_parser.py     Validação dos 7 campos do briefing
  copy_generator.py      OpenAI + normalização de hashtags + retry
  image_generator.py     Ideogram + placeholder fallback
  composer.py            HTML → PNG via Playwright (timeouts explícitos)
  exporter.py            Copia PNG, gera JSON metadata e post.txt
  campaign_store.py      Camada de estado por campanha (read/write SQLite)
  store.py               Inicialização do DB + migração de campanhas antigas
  pipeline.py            Orquestra copy → arte → composição
  server.py              Flask + API JSON + serve o SPA
  utils.py               Slugify, paths de campanha, log
approval_ui/
  index.html, app.js, style.css   SPA vanilla
campaigns/{id}/          Artefatos por campanha (ignored, gerado em runtime)
exports/{id}/            Posts aprovados + metadados (ignored)
state.db                 Banco SQLite (ignored)
scripts/
  migrate_exports_layout.py   Migração de layout antigo (flat → subpasta)
docs/
  roadmap-e-melhorias.md      Auditoria técnica + roadmap de evolução
  demo-checklist.md           Roteiro de demo + troubleshooting ao vivo
  plans/                      Design docs históricos
main.py                  Entry point (--serve | --campaign novo)
test_pipeline.py         Smoke de integração (Playwright real)
tests/                   Unitários (pytest, mocks)
```

---

## API HTTP

Toda a UI roda em cima dessa API JSON. Útil pra integrações futuras.

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/campaigns` | Lista campanhas (dashboard) |
| `POST` | `/api/campaigns` | Cria + dispara geração assíncrona |
| `GET` | `/api/campaigns/<id>` | Briefing + copy + estado (polling) |
| `POST` | `/api/campaigns/<id>/approve` | `{option_id, data_agendada}` → exporta |
| `POST` | `/api/campaigns/<id>/adjust` | `{option_id, nota}` → regenera |
| `POST` | `/api/campaigns/<id>/edit-copy` | `{option_id, fields}` → edita sem regenerar |
| `GET` | `/api/templates` | Lista presets de briefing |
| `POST` | `/api/templates` | Salva preset |
| `DELETE` | `/api/templates/<id>` | Apaga preset |

---

## Testes

```bash
# Unitários (rápido, sem rede)
python -m pytest -q

# Smoke de integração (Playwright real, mocks de OpenAI/Ideogram)
python test_pipeline.py
```

Cobertura atual: **60 testes** cobrindo briefing, copy generator (mocks),
campaign store (incluindo concorrência), templates, exporter, pipeline,
server API e edição manual de copy.

---

## Demo (quinta-feira, 28/05/26)

Checklist completo em [`docs/demo-checklist.md`](docs/demo-checklist.md).

TL;DR:

```bash
# Terminal 1 — central local
python main.py --serve

# Terminal 2 (opcional) — tunnel pra cliente clicar
ngrok http 5000
```

Recomendado: **demo local + tela compartilhada**. ngrok só se quiserem clicar.

---

## Deploy futuro

GitHub Pages **não atende** (precisa backend Python + Chromium + SQLite).
Opções viáveis quando fechar negócio:

| Plataforma | Quando faz sentido | Custo aprox. |
|---|---|---|
| **VPS** (Hetzner/DigitalOcean) | Controle total + chaves locais | $5-20/mês |
| **Railway / Render** | Deploy via git push, free tier ok pra POC | $0-15/mês |
| **Fly.io** | Quer SQLite em volume persistente | $5-25/mês |

Em qualquer um, considerar:
- Mover `state.db` pra Postgres (multi-write seguro)
- Auth básico (Henrique + sócios)
- HTTPS obrigatório
- Rotação das chaves OpenAI/Ideogram

---

## Roadmap

Documento técnico completo em [`docs/roadmap-e-melhorias.md`](docs/roadmap-e-melhorias.md).

**Próximas fases (pós-aprovação do cliente):**

1. **Publicação automática** via Buffer/Meta API.
2. **Captação de leads** via Airtable + WhatsApp Business.
3. **Hospedagem dedicada** (ver tabela acima).
4. **Multi-usuário** com permissões (sócios podem aprovar; estagiários só sugerir).
5. **Analytics** — performance dos posts publicados volta como insight pro próximo briefing.

---

*TimeLabs · Enzo Ferraz · Maio 2026*
