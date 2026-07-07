# Content Agent — TimeLabs

> Pipeline de geração de conteúdo para Instagram e LinkedIn, multi-marca.
> Cliente piloto: **Mendes & Vaz — Sociedade de Advogados** (Belo Horizonte, MG).
> Segundo cliente em preparação: **Gui** (DJ + criador de conteúdo).
>
> _TimeLabs · Enzo Ferraz (+ Marcos, revisão) · atualizado Jul/2026_

```
Briefing → Copy (OpenAI) → Arte (Ideogram ou foto própria) → Composição (HTML/CSS → PNG) → Aprovação → Export
```

Tudo operado por uma **Central de Controle web** onde o operador (Henrique no
caso da M&V) cria campanhas (briefing declarativo por marca), acompanha a
geração, agenda data e aprova. Nada publica sozinho — aprovação humana é
obrigatória.

---

## Sumário

- [Princípios](#princípios)
- [Stack](#stack)
- [Fluxo de trabalho (branches + revisão)](#fluxo-de-trabalho-branches--revisão)
- [Setup](#setup)
- [Como usar](#como-usar)
- [Multi-marca (brand config)](#multi-marca-brand-config)
- [Estrutura do projeto](#estrutura-do-projeto)
- [API HTTP](#api-http)
- [Testes](#testes)
- [Deploy](#deploy)
- [Roadmap](#roadmap)

---

## Princípios

- **Texto nunca dentro de imagem de IA** — sempre renderizado por código (zero erro de digitação).
- **Identidade visual é dado, não código** — paleta, fontes e logo vivem em
  `config/brands/<slug>.py`, um módulo por cliente (ver
  [Multi-marca](#multi-marca-brand-config)). Fontes embarcadas localmente,
  demo funciona offline.
- **Human in the loop** — o operador (Henrique, Gui, etc) aprova tudo; nada
  publica automaticamente.
- **Configuração centralizada** — `config/settings.py` é a única fonte de
  verdade pra dimensões, modelos, chaves e quotas (identidade visual fica no
  brand config, não aqui).

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

## Fluxo de trabalho (branches + revisão)

**A partir de julho/2026, todo merge na `main` passa por revisão do Marcos.**

- Nenhum trabalho vai direto pra `main` — sempre em branch (`feature/`,
  `fix/`, `refactor/`, `chore/`, `docs/`).
- A branch fica aberta (com PR, se fizer sentido) até o Marcos validar.
- Só depois da aprovação dele o merge acontece.

Ver `CLAUDE.md` → "Como trabalhar comigo neste projeto" pra detalhe completo
da regra.

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
- **Nova campanha** — formulário de briefing (campos definidos pela marca ativa)
  → "Gerar campanha". Opcional: subir foto própria (pula a geração via
  Ideogram) e alternar a sombra/overlay decorativo.
- **Progresso** — geração em background (copy → arte → composição); pode sair e voltar.
- **Aprovação** — 3 variações lado a lado, agendamento, aprovar, solicitar ajuste
  (regenera usando a nota) ou editar copy manualmente sem regenerar (custo zero de API).
  Campanha aprovada tem botão de **download .zip** (PNGs + legendas + briefing).
- **Histórico** — lista de campanhas já aprovadas, com acesso rápido ao
  download de cada uma.
- **Calendário** — visão por data agendada das campanhas aprovadas.

### Linha de comando (debug)

```bash
python main.py --campaign novo
```

Coleta o briefing por prompts, gera e deixa pronto pra aprovação na central.

---

## Multi-marca (brand config)

O projeto já roda com identidade visual, prompts e campos de briefing
**por cliente**, definidos em `config/brands/<slug>.py` (paleta, fontes, logo,
system prompts do LLM e schema declarativo dos campos do briefing). O brand
ativo é escolhido pela env var `BRAND` (default: `mendes_vaz`):

```bash
BRAND=gui_raw python main.py --serve
```

Hoje existem dois brands: `mendes_vaz` (cliente piloto) e `gui_raw` (em
preparação). Pra adicionar um novo cliente, criar `config/brands/<slug>.py`
exportando `BRAND = Brand(...)` — ver docstring em `config/brands/__init__.py`.
**Nunca hardcodar identidade visual em `config/settings.py`** — isso é o que
o brand config existe pra evitar.

---

## Estrutura do projeto

```
config/
  settings.py            Configuração centralizada (paths, modelos, quotas)
  brands/                Brand config por cliente (paleta, fontes, prompts, briefing)
    mendes_vaz.py         Cliente piloto
    gui_raw.py             Segundo cliente (em preparação)
assets/
  logo_mendes_vaz.png     Logo institucional M&V
  logo_mendes_vaz_fonte.png  Arquivo-fonte da logo (sem fundo), pra futuras edições
  fonts/                  Playfair + Montserrat (woff2 subset latin, embarcadas)
templates/
  post_square.html        1080×1080
  post_portrait.html      1080×1350
  carousel_slide.html     1080×1080 para slides
  story.html               1080×1920 (formato Stories)
modules/
  briefing_parser.py      Validação dos campos do briefing (schema por brand)
  copy_generator.py       OpenAI + normalização de hashtags + retry
  image_generator.py      Ideogram + upload de foto própria + placeholder fallback
  composer.py             HTML → PNG via Playwright (timeouts explícitos)
  exporter.py             Copia PNG, gera JSON metadata e post.txt
  campaign_store.py       Camada de estado por campanha (read/write SQLite)
  store.py                Inicialização do DB + migração de campanhas antigas
  pipeline.py             Orquestra copy → arte → composição
  server.py               Flask + API JSON + serve o SPA
  backup.py               Utilitário de backup manual (state.db + campaigns + exports)
  utils.py                Slugify, paths de campanha, log
approval_ui/
  index.html, app.js, style.css   SPA vanilla
campaigns/{id}/          Artefatos por campanha (ignored, gerado em runtime)
exports/{id}/            Posts aprovados + metadados (ignored)
state.db                 Banco SQLite (ignored)
scripts/
  migrate_exports_layout.py   Migração de layout antigo (flat → subpasta)
  preview_logo.py             Preview rápido de posicionamento de logo
docs/
  arquitetura.md               Onboarding técnico (~15min), fluxo, modelo de dados
  fase-2-roadmap.md            Plano de evolução pra SaaS multi-tenant
  roadmap-e-melhorias.md       Auditoria técnica + débito identificado
  guia-henrique.md/.html       Guia de operação pro cliente (Henrique)
  manual-reuniao.md            Material de reunião/apresentação
  demo-checklist.md            Roteiro de demo + troubleshooting ao vivo
  video-editing-research.md    Viabilidade de automação de edição de vídeo
  plans/                       Design docs históricos
main.py                  Entry point (--serve | --campaign novo)
Dockerfile, fly.toml      Deploy no fly.io
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
| `GET` | `/api/campaigns/<id>/download` | Baixa .zip (PNGs + legendas + briefing) |
| `POST` | `/api/campaigns/<id>/duplicate` | Duplica campanha existente |
| `DELETE` | `/api/campaigns/<id>` | Remove campanha |
| `GET` | `/api/quotas` | Uso/limite de geração no período |
| `GET` | `/api/brand` | Identidade visual da marca ativa (pra UI) |
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

Cobertura atual: **63 testes** cobrindo briefing, copy generator (mocks),
campaign store (incluindo concorrência), templates, exporter, pipeline,
server API e edição manual de copy.

---

## Deploy

**Já existe deploy configurado pro fly.io** (`Dockerfile` + `fly.toml`).
GitHub Pages não atende (precisa backend Python + Chromium + SQLite).

```bash
fly deploy
```

Detalhes operacionais (variáveis, troubleshooting) em
[`docs/manual-reuniao.md`](docs/manual-reuniao.md) e
[`docs/guia-henrique.md`](docs/guia-henrique.md).

Pra rodar demo local com tunnel (sem depender do deploy):

```bash
python main.py --serve
ngrok http 5000   # opcional, só se o cliente for clicar remotamente
```

Considerar antes de escalar pra produção multi-cliente:
- Mover `state.db` pra Postgres (multi-write seguro)
- Auth básico por marca/operador
- Rotação das chaves OpenAI/Ideogram

---

## Roadmap

Documento técnico completo em [`docs/fase-2-roadmap.md`](docs/fase-2-roadmap.md)
(plano de evolução pra SaaS multi-tenant) e
[`docs/roadmap-e-melhorias.md`](docs/roadmap-e-melhorias.md) (auditoria técnica).

**Próximas frentes:**

1. **Gui (segundo cliente multi-marca)** — brand config já existe
   (`config/brands/gui_raw.py`); falta adaptar briefing/templates pro
   contexto musical e validar em produção.
2. **Publicação automática** via Buffer/Meta API.
3. **Multi-usuário** com permissões (sócios podem aprovar; estagiários só sugerir).
4. **Analytics** — performance dos posts publicados volta como insight pro próximo briefing.
5. **Edição de vídeo automatizada** — demanda do Gui, track técnico separado
   (ver [`docs/video-editing-research.md`](docs/video-editing-research.md)),
   não priorizado antes do Gui rodar com posts estáticos.

---

*TimeLabs · Enzo Ferraz (dev) · Marcos (revisão/manutenção) · atualizado Jul/2026*
