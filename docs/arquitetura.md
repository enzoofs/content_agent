# Arquitetura — Mendes & Vaz Social

> Documento vivo. Objetivo: alguém novo entender o sistema em 15 min.
> Última atualização: 2026-09-04.
>
> **Contexto atual:** cliente pagante (Mendes & Vaz), em produção no
> Fly.io. Em transição pra multi-marca (Gui DJ entrando como cliente #2,
> ainda não onboardado). A arquitetura abaixo descreve o estado atual; o
> que muda na expansão está em `docs/fase-2-roadmap.md` (especialmente
> item 5.7 — brand config dinâmico).

---

## 1. Visão geral em 30 segundos

Sistema **hospedado (Fly.io), single-tenant hoje** que automatiza criação de posts
pra Instagram/LinkedIn de um escritório de advocacia. **Texto sempre renderizado
por código** (nunca dentro de imagem IA — princípio inegociável). **Henrique aprova
tudo antes de qualquer coisa ir ao ar** — publicação automática (`modules/publisher.py`)
existe como infra opcional, ainda desligada pro M&V, e só publica o que já passou
pela aprovação; não é geração sem humano no loop.

```
[ Henrique ] ── browser → [ Flask + waitress ]
                                ↓ thread daemon
              ┌─────────────────┴─────────────────┐
              ↓                                   ↓
       [ OpenAI gpt-4o ]                  [ Ideogram V_2 ]
          (3 copies)                      (1 imagem/copy)
              ↓                                   ↓
              └────────────┬──────────────────────┘
                           ↓
              [ Playwright → Chromium headless ]
                  templates HTML/CSS → PNG
                           ↓
              [ SQLite (state.db) + FS (campaigns/<id>/) ]
                           ↓
              [ Henrique aprova → exports/<id>/ ]
```

---

## 2. Componentes (de baixo pra cima)

| Camada | Arquivos | Responsabilidade | Quando mexer |
|---|---|---|---|
| **Config** | `config/settings.py` | Única fonte de verdade. Cores, fontes, paths, modelos, quotas, chaves. | Trocar OpenAI por Claude, ajustar limite, nova cor |
| **Storage** | `modules/store.py` | SQL puro. Schema + CRUD. WAL mode. | Nova tabela, novo índice |
| **Domínio (estado)** | `modules/campaign_store.py` | API "ler estado da campanha", "marcar etapa". Encapsula store. | Novo status, nova etapa, regras de transição |
| **Quotas** | `modules/quotas.py` | Política de uso (block/warn/ok). | Mudar regras de plano |
| **Pipeline** | `modules/pipeline.py` | Orquestra: copy → arte → composição. Grava etapa a cada passo. | Adicionar nova etapa (ex: aprovação automática IA) |
| **Geração copy** | `modules/copy_generator.py` | OpenAI + system prompt + retry + validação JSON. | Trocar prompt, novo provedor LLM |
| **Geração imagem** | `modules/image_generator.py` | Ideogram + fallback placeholder. | Trocar provedor, novo tamanho |
| **Composição** | `modules/composer.py` | HTML/CSS → PNG via Playwright. Embute fontes/logo/imagem como data URI. | Novo formato, novo template |
| **Exportação** | `modules/exporter.py` | Copia PNG aprovado + JSON metadata + post.txt. Também registra o audit log (`exports/audit.jsonl`), incluindo publicação manual. | Novo destino de export (S3, etc) |
| **Publicação** | `modules/publisher.py` | Abstração `Publisher` + `BlotatoPublisher` — publica automaticamente no Instagram. **Não testado contra API real** (sem chave neste ambiente) — ver aviso no topo do arquivo sobre URL pública da imagem. | Trocar provedor (Buffer, Meta direto) |
| **Agendador de publicação** | `modules/publish_scheduler.py` | Thread daemon (mesmo padrão de `backup.py`) que publica campanhas aprovadas na data agendada, via `publisher.py`. Sem `BLOTATO_API_KEY`/`blotato_account_id`, não faz nada (não é fatal). | Mudar frequência, lógica de retry |
| **Sugestão de tema** | `modules/theme_suggester.py` | Sugere tema de campanha a partir do histórico recente (OpenAI, com fallback local). Usado pelo fluxo de geração automática via bot de WhatsApp. | Mudar heurística/prompt de sugestão |
| **Sugestão de agenda** | `modules/scheduling.py` | Heurística v1 de melhor dia/horário pra postar. Sem dados reais de engajamento ainda (Fase 4 do roadmap). | Trocar por lógica data-driven quando houver analytics |
| **Briefing** | `modules/briefing_parser.py` | Valida campos + sanitização anti-prompt-injection. | Novo campo de briefing |
| **HTTP/UI** | `modules/server.py` | Flask + waitress + serve SPA. | Novo endpoint |
| **SPA** | `approval_ui/` | Vanilla JS. 4 telas: dashboard, novo, progresso, aprovação. | UI nova |
| **Templates** | `templates/<layout>/<formato>.html` | Layout dos PNGs. Um subdiretório por `LayoutOption` (`gradiente`/`cartao`/`faixa` no M&V), 4 arquivos cada (square/portrait/carousel/story). CSS literal + `$placeholder`. `settings.template_path(formato, layout_id)` resolve o arquivo, com fallback pro `DEFAULT_LAYOUT` se o id não existir. | Novo layout selecionável, ajuste visual |
| **Scripts** | `scripts/` | One-shots: migrations, utilitários. | Apenas operações pontuais |

---

## 3. Fluxo de uma campanha (do clique ao PNG)

```
1. Henrique POST /api/campaigns com briefing (7 campos)
   ↓
2. server.api_criar:
   - quotas.verificar_pode_criar()          → 429 se estourou
   - briefing_parser.parse()                → 400 se inválido (incl. prompt injection)
   - campaign_store.criar()                 → INSERT campaigns
   - _iniciar_geracao_async()               → thread daemon
   ← 201 {campaign_id, status: "gerando"}
   ↓
3. Thread daemon roda pipeline.gerar():
   - set_etapa("copy")    → copy_generator.generate() → save_copy_version()
   - set_etapa("arte")    → image_generator.generate() → PNG/placeholder em campaigns/<id>/images/
   - set_etapa("composicao") → composer.compose_all() → PNG em campaigns/<id>/composed/
   - marcar_aguardando()  → status = aguardando_aprovacao
   ↓
4. SPA polleia GET /api/campaigns/<id> a cada 2s:
   - Vê etapa mudando → atualiza progress visual (copy ✓ → arte ✓ → composicao ✓)
   - Detecta status=aguardando_aprovacao → muda pra tela de aprovação
   ↓
5. Henrique aprova: POST /api/campaigns/<id>/approve {option_id, data_agendada}
   - exporter.export_approved() → copia PNG, gera JSON metadata, gera post.txt
   - campaign_store.marcar_aprovada()
   ← 200 com paths dos arquivos
   ↓
6. Henrique copia o post.txt e cola no Instagram. Fim.
```

---

## 4. Modelo de dados (state.db, SQLite WAL)

```sql
campaigns
├── campaign_id           PK     -- YYYY-MM-DD_slug (+ sufixo se colide)
├── area_direito          TEXT
├── perfil_cliente_ideal  TEXT
├── tom                   TEXT   -- tecnico | acessivel
├── objetivo              TEXT   -- awareness | captacao | posicionamento
├── tema_especifico       TEXT
├── formato               TEXT   -- square | portrait | carousel | story
├── num_slides            INT
├── referencias           TEXT
├── created_at            TEXT
├── status                TEXT   -- gerando | aguardando_aprovacao | aprovada | ajuste_solicitado | erro
├── etapa                 TEXT   -- copy | arte | composicao (durante gerando)
├── copy_version          INT    -- 1 inicial, bumpa em cada regeração
├── option_aprovada       INT
├── data_agendada         TEXT   -- YYYY-MM-DD (sem horário — ver scheduling.py)
├── erro                  TEXT
├── atualizado_em         TEXT
├── tokens_used           INT
├── hide_overlay          INT    -- 0/1 — esconde a sombra sobre a imagem
├── overlay_color         TEXT   -- azul (default) | preto
├── upload_filename       TEXT   -- foto própria (formatos simples), "" = via IA
├── upload_filenames      TEXT   -- JSON: 1 foto por slide (carrossel), [] = via IA
├── font_variant          TEXT   -- id de FontOption do brand
├── font_size             TEXT   -- P | M | G
├── image_asset_id        TEXT   -- reaproveita imagem do banco (B.5)
├── layout                TEXT   -- id de LayoutOption do brand
├── publicado_em          TEXT   -- setado por publish_scheduler.py OU pelo botão manual
└── publish_erro          TEXT   -- última falha de publicação automática (se houver)

copy_versions               PRIMARY KEY (campaign_id, versao)
├── campaign_id   FK
├── versao        INT
├── payload       TEXT      -- JSON da lista de opções
├── nota_ajuste   TEXT      -- '' na geração inicial; texto na regeração
└── created_at    TEXT

briefing_templates          AUTOINCREMENT id
└── (mesmos campos do briefing) + UNIQUE(nome)

image_assets                PK id (UUID)
├── brand_slug            TEXT
├── origem_campaign_id    TEXT
├── origem                TEXT   -- ideogram | upload
├── formato               TEXT
├── filename              TEXT
└── created_at            TEXT
```

**Por que SQLite?** Single-user, single-host MVP. WAL permite ler enquanto a
thread daemon escreve. Pra fase 2 (multi-tenant), vira Postgres — interface de
`modules/store.py` continua igual.

**Por que PNGs no FS, não no DB?** Binários pesados em SQLite incham o DB e
matam performance de queries.

---

## 5. Estados possíveis de uma campanha

```
                ┌─────────────┐
   POST ──────► │   gerando   │
                └─────┬───────┘
                      │
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
   ┌─────────┐  ┌──────────────┐ ┌──────┐
   │   erro  │  │ aguardando_  │ │      │
   │         │  │  aprovacao   │ │      │
   └────┬────┘  └─────┬────────┘ │      │
        │             │          │      │
   ajuste            approve     │      │
   solicitado         │          │      │
        │             ↓          │      │
        │       ┌──────────┐     │      │
        └──────►│ ajuste_  │     │      │
                │solicitado│     │      │
                └────┬─────┘     │      │
                     │           │      │
                     ↓           │      │
                  (regera) ──────┘      │
                                        │
                  ┌────────────┐        │
                  │  aprovada  │ ◄──────┘
                  └────────────┘
                  (estado terminal do workflow de geração)
```

`status="aprovada"` é terminal no backend, mas tem um ciclo de vida
**derivado** de publicação por cima (não migra o enum — ver
`docs/plans/2026-05-23-status-postagem-e-kanban.md`): a UI computa
Agendada / Atrasada ⚠ / Publicada ✓ a partir de `data_agendada` +
`publicado_em` + hoje (`statusInfo()` em `approval_ui/app.js`). Publicação
em si acontece via `modules/publish_scheduler.py` (automático, Blotato)
ou pelo botão manual "Marquei como publicado" — nenhum dos dois muda
`status`, só grava `publicado_em`.

---

## 6. Decisões arquiteturais (e por que)

| Decisão | Por que | Trade-off |
|---|---|---|
| **Texto fora da imagem IA** | Modelos de imagem erram tipografia. Texto via HTML/CSS = zero erro. | Mais código (templates HTML), menos magia |
| **Mock fallback pro Ideogram** | Dev sem chave roda normal; demo continua se a API cair | Imagens placeholder são feias mas o sistema sobrevive |
| **Threads daemon, sem fila** | 1 usuário, 1 geração por vez. Celery seria overkill. | Se processo morre, perde trabalho — mitigado por recovery no startup |
| **SQLite + WAL** | Zero infra. Migration trivial pra Postgres na fase 2. | Não escala multi-host |
| **Vanilla JS sem build** | Zero ferramenta. Edita e recarrega. | Vai virar saco grande conforme cresce |
| **Fontes embarcadas (woff2 base64)** | Demo funciona offline. Sem dependência de Google Fonts. | +20KB nos templates |
| **Health-check no startup** | Falha cedo com mensagem clara > erro mudo dentro de thread | Adiciona ~3s ao boot |
| **Renderização por campanha (sem cache)** | 3 opções costumam ser distintas o suficiente | Custo de API por geração |
| **`option_id` sempre 1/2/3** | Schema simples, payload previsível | Não suporta N variações |

---

## 7. Como adicionar X (atalhos)

| Quero... | Mexo em... |
|---|---|
| Novo formato de post (ex: Stories 1080×1920) | `config/settings.py` (POST_SIZES) + novo `templates/<layout>/<formato>.html` pra CADA layout existente + `briefing_parser.FORMATOS_VALIDOS` |
| Novo layout selecionável (posição de elementos) | `config/brands/<slug>.py` (`layout_options`, novo `LayoutOption`) + `templates/<novo_id>/*.html` (4 arquivos, um por formato) + rodar `scripts/generate_layout_previews.py` pra gerar a miniatura |
| Novo provedor de LLM | `config/settings.py` (`OPENAI_MODEL` → novo modelo) ou wrapper em `copy_generator.generate` |
| Novo provedor de imagem | `modules/image_generator.py` (adapter — mantém API existente) |
| Nova cor da paleta | `config/settings.py` (COLORS) + referência em todos os `templates/<layout>/*.html` |
| Novo limite de quota | `config/settings.py` (QUOTAS) — frontend lê via `/api/quotas` |
| Novo status | `modules/campaign_store.py` (STATES) + UI: `app.js` (statusInfo + route handling) |
| Novo endpoint HTTP | `modules/server.py` (mantém padrão `/api/<recurso>`) |
| Trocar prompt do LLM | `modules/copy_generator.py` (SYSTEM_PROMPT ou SYSTEM_PROMPT_CAROUSEL) |
| Nova validação de briefing | `modules/briefing_parser.py` (`parse` function) |
| Nova cor de sombra sobre a imagem | `modules/composer.py` (`_OVERLAY_RGB`) + `briefing_parser.OVERLAY_COLORS_VALIDAS` — cor é fixa do sistema, não por brand |
| Publicar automaticamente num provedor novo | `modules/publisher.py` (implementa `Publisher`, troca `BlotatoPublisher`) — `publish_scheduler.py` não muda |
| Novo status de publicação/UI | `approval_ui/app.js` (`statusInfo`) — deriva de `status`+`data_agendada`+`publicado_em`, não migra enum no backend |

---

## 8. O que NÃO há (decisão, não esquecimento)

- ❌ ORM (SQL direto em `store.py` — schema cabe na cabeça)
- ❌ Build step de frontend (vanilla JS direto no browser)
- ❌ CI/CD (single dev, push direto — inclusive deploy é manual, `fly deploy`)
- ❌ Logger estruturado (`print()` + `utils.log()` por campanha — basta pro tamanho atual)
- ❌ Multi-tenant de verdade (DB/config isolado por cliente — hoje é 1 DB compartilhado + brand config por client_slug; quebra quando o 2º cliente pagante entrar de vez)
- ❌ Cache (3 opções por campanha são únicas, não compensa)
- ❌ Message broker / fila persistente (threads daemon bastam pro volume atual)
- ❌ LangChain / agents framework (LLM como gerador de texto estruturado, só)

**Já existe, ao contrário do que versões antigas deste doc diziam:**
- ✅ **Docker** — `Dockerfile` na raiz, usado pelo deploy no Fly.io (não é mais "só local").
- ✅ **Auth básica** — `BASIC_AUTH_USER`/`BASIC_AUTH_PASS` (env vars) protegem a SPA em produção via `server.py:_require_basic_auth`. Não é auth por usuário/permissão (isso sim ainda não existe), mas não é mais "zero auth".

**As ausências reais acima têm fix planejado em `docs/fase-2-roadmap.md`.**

---

## 9. Onde ler primeiro pra entender o sistema

1. `README.md` — visão geral + setup
2. `config/settings.py` — constantes do sistema todo
3. `modules/pipeline.py` — orquestração (curto, 72 linhas)
4. `modules/server.py` — todos os endpoints
5. `modules/store.py` — modelo de dados
6. `approval_ui/app.js` — fluxo da SPA
7. `docs/fase-2-roadmap.md` — o que muda quando virar SaaS

---

## 10. Onde achar logs e estado

| O quê | Onde |
|---|---|
| Logs por campanha | `campaigns/<id>/log.txt` |
| Audit de exports | `exports/audit.jsonl` (append-only) |
| Estado completo | `state.db` (SQLite — abrir com `sqlite3` ou DB Browser) |
| Erros de thread daemon | terminal do `python main.py --serve` (printam traceback) |

---

*Quando esse doc mentir, atualize. Quando inflar, corte.*
