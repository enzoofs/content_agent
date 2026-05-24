# Arquitetura — Mendes & Vaz Social

> Documento vivo. Objetivo: alguém novo entender o sistema em 15 min.
> Última atualização: 2026-05-24.

---

## 1. Visão geral em 30 segundos

Sistema **local, single-user** que automatiza criação de posts pra Instagram/LinkedIn
de um escritório de advocacia. **Texto sempre renderizado por código** (nunca dentro
de imagem IA — princípio inegociável). **Henrique aprova tudo** — nada publica
automaticamente.

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
| **Exportação** | `modules/exporter.py` | Copia PNG aprovado + JSON metadata + post.txt. | Novo destino de export (S3, etc) |
| **Briefing** | `modules/briefing_parser.py` | Valida campos + sanitização anti-prompt-injection. | Novo campo de briefing |
| **HTTP/UI** | `modules/server.py` | Flask + waitress + serve SPA. | Novo endpoint |
| **SPA** | `approval_ui/` | Vanilla JS. 4 telas: dashboard, novo, progresso, aprovação. | UI nova |
| **Templates** | `templates/*.html` | Layout dos PNGs. CSS literal + `$placeholder`. | Novo layout, ajuste visual |
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
├── formato               TEXT   -- square | portrait | carousel
├── num_slides            INT
├── referencias           TEXT
├── created_at            TEXT
├── status                TEXT   -- gerando | aguardando_aprovacao | aprovada | ajuste_solicitado | erro
├── etapa                 TEXT   -- copy | arte | composicao (durante gerando)
├── copy_version          INT    -- 1 inicial, bumpa em cada regeração
├── option_aprovada       INT
├── data_agendada         TEXT
├── erro                  TEXT
└── atualizado_em         TEXT

copy_versions               PRIMARY KEY (campaign_id, versao)
├── campaign_id   FK
├── versao        INT
├── payload       TEXT      -- JSON da lista de opções
├── nota_ajuste   TEXT      -- '' na geração inicial; texto na regeração
└── created_at    TEXT

briefing_templates          AUTOINCREMENT id
└── (mesmos campos do briefing) + UNIQUE(nome)
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
                  (estado terminal)
```

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
| Novo formato de post (ex: Stories 1080×1920) | `config/settings.py` (POST_SIZES, TEMPLATE_BY_FORMAT) + novo `templates/post_stories.html` + `briefing_parser.FORMATOS_VALIDOS` |
| Novo provedor de LLM | `config/settings.py` (`OPENAI_MODEL` → novo modelo) ou wrapper em `copy_generator.generate` |
| Novo provedor de imagem | `modules/image_generator.py` (adapter — mantém API existente) |
| Nova cor da paleta | `config/settings.py` (COLORS) + referência nos 3 templates |
| Novo limite de quota | `config/settings.py` (QUOTAS) — frontend lê via `/api/quotas` |
| Novo status | `modules/campaign_store.py` (STATES) + UI: `app.js` (statusInfo + route handling) |
| Novo endpoint HTTP | `modules/server.py` (mantém padrão `/api/<recurso>`) |
| Trocar prompt do LLM | `modules/copy_generator.py` (SYSTEM_PROMPT ou SYSTEM_PROMPT_CAROUSEL) |
| Nova validação de briefing | `modules/briefing_parser.py` (`parse` function) |
| Mudar layout do post | `templates/*.html` — CSS literal, placeholders `$variavel` |

---

## 8. O que NÃO há (decisão, não esquecimento)

- ❌ ORM (SQL direto em `store.py` — schema cabe na cabeça)
- ❌ Build step de frontend (vanilla JS direto no browser)
- ❌ Docker (app local, `pip install` resolve)
- ❌ CI/CD (single dev, push direto)
- ❌ Logger estruturado (`print()` + `utils.log()` por campanha — basta pra MVP)
- ❌ Auth (single user assumido — quebra na fase 2)
- ❌ Multi-tenant (single client — quebra na fase 2)
- ❌ Cache (3 opções por campanha são únicas, não compensa)
- ❌ Message broker / fila persistente (threads daemon bastam pra 1 usuário)
- ❌ LangChain / agents framework (LLM como gerador de texto estruturado, só)

**Todas essas ausências têm fix planejado em `docs/fase-2-roadmap.md`.**

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
