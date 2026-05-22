# Design — Central de Controle Mendes & Vaz

**Data:** 2026-05-22
**Autor:** Enzo Ferraz (TimeLabs) + Claude Code
**Status:** Aprovado — pronto para implementação

---

## Contexto

A Fase 1 do `content_agent` está completa e validada: o pipeline
briefing → copy (OpenAI) → arte (Ideogram) → composição (Playwright) →
aprovação (Flask) → export funciona ponta a ponta com APIs reais.

Hoje o **briefing é no terminal** (`main.py --campaign novo`) e a **aprovação é uma
página one-shot** (`main.py --approve <id>`) que encerra após uma aprovação.

Este design evolui isso para uma **central de controle única** (app web local) onde
o Henrique faz tudo numa só janela: vê campanhas, dispara a geração a partir de um
briefing, acompanha o progresso, agenda uma data e aprova.

## Escopo (decisões tomadas)

| Tema | Decisão |
|---|---|
| Agendamento | **Só registrar a data** na campanha (calendário/lista). Publicação automática (Buffer) fica para depois do MVP. |
| Briefing | **Formulário completo (7 campos)** na web (mesmos campos do terminal). |
| Espera da geração | **Tela de progresso**, geração em **background**, navegável (pode sair e voltar). |
| Solicitar ajuste | **Regera** a campanha usando a nota do Henrique como instrução extra. |
| Hospedagem | **Local** (`localhost`), Enzo apresenta. Sem deploy/auth no MVP. |
| Background | **Thread + estado em arquivo JSON** (sem Celery/Redis — YAGNI para single-user local). |

Fora de escopo (pós-MVP): publicação automática (Buffer/Later), hospedagem online,
autenticação, multiusuário, CRM/WhatsApp (Fase 3).

## Máquina de estados da campanha

Gravada em `campaigns/{id}/state.json`:

```
rascunho → gerando → aguardando_aprovacao → aprovada
                ↑              ↓
                └── ajuste_solicitado (regera) ──┘
                gerando → erro (falha; permite "tentar novamente")
```

Campos do `state.json`:
```json
{
  "campaign_id": "2026-05-22_slug",
  "status": "gerando|aguardando_aprovacao|aprovada|ajuste_solicitado|erro",
  "etapa": "copy|arte|composicao|null",   // progresso fino durante "gerando"
  "data_agendada": "2026-05-30|null",
  "option_aprovada": 2,
  "erro": "mensagem|null",
  "atualizado_em": "ISO8601"
}
```

## Telas (4, mesma janela)

1. **Dashboard** (`/`) — cards de todas as campanhas com badge de status, formato,
   tema e data agendada. Botão **"+ Nova campanha"**.
2. **Nova campanha** (`/novo`) — formulário de 7 campos. **"Gerar campanha"** dispara
   a geração e leva ao progresso.
3. **Progresso** — etapas copy → arte → composição com indicador; polling a cada ~2s.
4. **Aprovação** — os 3 cards atuais + campo de **data de agendamento** +
   **Aprovar** (exporta) e **Solicitar ajuste** (nota → regera).

## Arquitetura

### Backend (Python)

- **`modules/campaign_store.py`** (novo) — fonte da verdade do estado. CRUD de
  `state.json`, `listar()`, `criar(briefing)`, `agendar(id, data)`, `set_etapa()`,
  `set_erro()`. Único módulo que escreve `state.json`.
- **`modules/pipeline.py`** (novo) — orquestração extraída do `main.py`:
  `gerar(briefing, on_etapa)` roda copy → arte → composição atualizando o estado;
  `regerar(id, nota)` injeta a nota e regenera. Motor compartilhado por terminal e web.
- **`modules/server.py`** (renomeia `approval_server.py`) — Flask **persistente**.
  Serve a UI, expõe a API JSON, e ao criar campanha dispara `pipeline.gerar` numa
  **thread** (a thread grava progresso via `campaign_store`).
- **`main.py`** — ganha `--serve` para subir a central. Fluxo de terminal permanece
  para debug.
- Módulos existentes (`briefing_parser`, `copy_generator`, `image_generator`,
  `composer`, `exporter`, `utils`) seguem como estão; o `copy_generator` ganha um
  parâmetro opcional de "nota de ajuste" para a regeneração.

### API JSON

```
GET  /api/campaigns              → lista (dashboard)
POST /api/campaigns              → cria + dispara geração → { campaign_id }
GET  /api/campaigns/{id}         → dados (briefing, copy, imagens) + estado (polling)
POST /api/campaigns/{id}/approve → { option_id, data_agendada } → exporta, aprovada
POST /api/campaigns/{id}/adjust  → { option_id, nota } → regera (volta a gerando)
GET  /composed/{id}/{arquivo}    → serve imagens compostas para preview
GET  /logo.png                   → logo no header
```

### Frontend

Pequeno **SPA vanilla**: `index.html` (shell) + `app.js` (renderiza as 4 telas no
cliente conforme a rota/hash e consome a API) + `style.css`. Sem frameworks, sem CDN,
desktop-first (paleta navy/gold/creme).

## Geração em background

1. `POST /api/campaigns` valida o briefing (`briefing_parser.parse`), cria a pasta e o
   `state.json` (`status=gerando`, `etapa=copy`), e inicia uma `threading.Thread`.
2. A thread roda `pipeline.gerar`, chamando `campaign_store.set_etapa()` a cada passo
   (copy → arte → composicao) e, ao final, `status=aguardando_aprovacao`.
3. A UI faz polling em `GET /api/campaigns/{id}` e atualiza a barra; quando vê
   `aguardando_aprovacao`, troca para a tela de aprovação.

## Tratamento de erros (nunca falhar em silêncio)

- A thread captura exceções de qualquer etapa, grava `status=erro` + mensagem em
  `state.json` e em `log.txt`. A tela de progresso mostra o erro e oferece
  **"Tentar novamente"**.
- Erros de API (cota OpenAI, Ideogram 4xx) já têm mensagem clara nos módulos; a thread
  apenas os propaga ao estado.
- Agendamento valida data ≥ hoje.
- Botão "Gerar" desabilita ao enviar; criação é idempotente por `campaign_id`.

## Testes (mocks, zero API real)

- `campaign_store`: criar, mudar estado/etapa, listar, agendar (campanha temporária).
- `pipeline.gerar`: copy mockado + imagens mock → termina em `aguardando_aprovacao`
  com 3 PNGs compostos.
- API via Flask test client: criar (→gerando), polling, approve (→aprovada + export +
  data), adjust (→gerando).
- Smoke test atual do motor permanece válido.

## Riscos / notas

- Thread + Flask dev server: ok para single-user local; não usar em produção sem
  repensar (pós-MVP).
- Polling simples (2s) é suficiente para 1 usuário; sem WebSocket (YAGNI).
- A geração custa créditos (OpenAI + Ideogram). A UI deixa claro o que dispara custo
  (gerar, regerar).
