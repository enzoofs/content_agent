# Central de Controle Mendes & Vaz — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Evoluir o app Flask de aprovação one-shot para uma central web local persistente onde o Henrique gerencia campanhas, dispara a geração (briefing de 7 campos na web) com progresso em background, agenda uma data e aprova.

**Architecture:** Flask persistente serve um SPA vanilla e uma API JSON. Criar campanha dispara `pipeline.gerar` numa thread que grava progresso em `campaigns/{id}/state.json` via `campaign_store`. A UI faz polling. Motor de geração compartilhado entre terminal e web.

**Tech Stack:** Python, Flask, Playwright, OpenAI, Ideogram, HTML/CSS/JS vanilla. Testes com pytest + Flask test client + mocks (zero chamada de API real).

---

## Convenções

- Rodar comandos com `PYTHONUTF8=1` (Windows).
- Testes: `PYTHONUTF8=1 python -m pytest -q`.
- Commits pequenos por tarefa. Mensagem em português, sufixo Co-Authored-By.
- Estados: `gerando | aguardando_aprovacao | aprovada | ajuste_solicitado | erro`.
- Etapas (durante `gerando`): `copy | arte | composicao`.

---

### Task 1: `modules/campaign_store.py` — estado e CRUD

**Files:**
- Create: `modules/campaign_store.py`
- Test: `tests/test_campaign_store.py`

**Funções (assinaturas):**
```python
STATES = {"gerando","aguardando_aprovacao","aprovada","ajuste_solicitado","erro"}

def state_path(campaign_id: str) -> Path                       # campaigns/{id}/state.json
def read_state(campaign_id: str) -> dict | None                # None se não existe
def write_state(campaign_id: str, **campos) -> dict            # merge + atualizado_em
def criar(briefing: dict) -> dict                              # salva briefing.json + state(gerando, etapa=copy)
def set_etapa(campaign_id: str, etapa: str) -> None
def set_erro(campaign_id: str, mensagem: str) -> None          # status=erro
def marcar_aprovada(campaign_id: str, option_id: int, data_agendada: str|None) -> None
def agendar(campaign_id: str, data: str) -> None               # valida data >= hoje
def listar() -> list[dict]                                     # varre campaigns/, junta state+briefing
```

**Testes:** criar() gera state.json com status=gerando; write_state faz merge e atualiza timestamp; set_erro muda status; marcar_aprovada grava option+data; agendar rejeita data passada (ValueError); listar() retorna a campanha criada com seu status. Usar campanha temпорária e limpar no finally.

**Commit:** `feat: campaign_store com estado em state.json`

---

### Task 2: `modules/pipeline.py` — motor de geração compartilhado

**Files:**
- Create: `modules/pipeline.py`
- Modify: `main.py` (passar a usar `pipeline.gerar`)
- Test: `tests/test_pipeline_engine.py`

**Funções:**
```python
def gerar(briefing: dict, nota_ajuste: str = "") -> list[Path]:
    # 1. copy_generator.generate(briefing, nota_ajuste) -> campaign_store.set_etapa("arte")
    # 2. image_generator.generate(...) -> set_etapa("composicao")
    # 3. composer.compose_all(...) -> write_state(status="aguardando_aprovacao", etapa=None)
    # captura exceção -> campaign_store.set_erro(...) e relança

def regerar(campaign_id: str, nota: str = "") -> None:
    # carrega briefing.json, write_state(gerando, etapa=copy), chama gerar(briefing, nota)
```

Extrair de `main.py:run_pipeline` a sequência copy→imagem→composição para `pipeline.gerar`. `main.run_pipeline` passa a chamar `pipeline.gerar` e depois `server.serve`/aprovação.

**Testes (mock):** monkeypatch `copy_generator.generate` (retorna 3 mock copies + salva copy_v1) e usar imagens mock (USE_MOCK_IMAGES já True sem Ideogram em teste — forçar via monkeypatch settings). `gerar()` termina com state=aguardando_aprovacao e 3 PNGs em composed/. Erro numa etapa → state=erro e exceção propagada.

**Commit:** `feat: pipeline.gerar/regerar como motor compartilhado`

---

### Task 3: `copy_generator` aceita nota de ajuste

**Files:**
- Modify: `modules/copy_generator.py` (`generate(briefing, nota_ajuste="")` + `_build_user_message`)
- Test: `tests/test_copy_generator.py` (estende; sem API real)

**Mudança:** `generate` ganha param `nota_ajuste`. Se não-vazio, anexar ao user message: `"\n\nAJUSTE SOLICITADO PELO CLIENTE (priorize): {nota_ajuste}"`. `_build_user_message(briefing, nota_ajuste)`.

**Teste:** `_build_user_message(b, "deixe mais técnico")` contém a string do ajuste; sem nota, não contém "AJUSTE".

**Commit:** `feat: copy_generator aceita nota de ajuste para regeneração`

---

### Task 4: `modules/server.py` — Flask persistente + API

**Files:**
- Rename: `modules/approval_server.py` → `modules/server.py` (git mv)
- Modify: `main.py` (import server; `--serve`)
- Test: `tests/test_server_api.py` (Flask test client, mocks)

**App (factory `build_app()`):** rotas estáticas (`/`, `/<asset>`, `/logo.png`, `/composed/<id>/<arq>`) e API:
```
GET  /api/campaigns               -> campaign_store.listar()
POST /api/campaigns               -> valida briefing_parser.parse, campaign_store.criar,
                                      Thread(pipeline.gerar) , retorna {campaign_id}
GET  /api/campaigns/<id>          -> briefing + copy (se houver) + state + urls compostas
POST /api/campaigns/<id>/approve  -> {option_id, data_agendada} -> exporter.export_approved,
                                      campaign_store.marcar_aprovada
POST /api/campaigns/<id>/adjust   -> {option_id, nota} -> Thread(pipeline.regerar(id, nota))
```
`serve()` agora sobe o app persistente (não encerra após aprovar). `_iniciar_geracao_async(briefing)` encapsula o Thread com try/except → set_erro.

**Testes (mock pipeline.gerar para não chamar API):** POST cria e retorna id + state=gerando; GET lista inclui a campanha; após simular geração (escrever composed + copy + state=aguardando), GET /<id> traz 3 options; approve exporta (mock exporter) e marca aprovada com data; adjust dispara regerar (mock) e volta a gerando.

**Commit:** `feat: server.py persistente com API de campanhas`

---

### Task 5: `main.py --serve` e limpeza

**Files:** Modify `main.py`

**Mudança:** adicionar `--serve` que chama `server.serve()` (sobe a central). Manter `--campaign novo`/`--from`/`--approve` para debug, agora usando `pipeline`. Atualizar docstring.

**Teste:** `python main.py --serve` sobe e responde em `/` (verificação manual / smoke leve com test_client já coberto na Task 4).

**Commit:** `feat: main --serve sobe a central de controle`

---

### Task 6: Frontend SPA vanilla (4 telas)

**Files:**
- Modify: `approval_ui/index.html` (shell + containers das views)
- Rewrite: `approval_ui/app.js` (router por hash + render das 4 telas + polling)
- Modify: `approval_ui/style.css` (estilos do dashboard, form, progresso)

**Telas/rotas (hash):**
- `#/` Dashboard: `GET /api/campaigns`, cards com badge de status, formato, tema, data; botão "+ Nova campanha".
- `#/novo` Form 7 campos → `POST /api/campaigns` → redireciona para `#/campanha/{id}`.
- `#/campanha/{id}`:
  - state=gerando/ajuste → tela de progresso (etapas copy→arte→composição), polling 2s.
  - state=erro → mensagem + "Tentar novamente" (re-`POST adjust` sem nota, ou re-gerar).
  - state=aguardando_aprovacao → 3 cards (reaproveita UI atual) + input date (data agendada) + Aprovar / Solicitar ajuste (nota → adjust).
  - state=aprovada → tela de confirmação + data agendada.

Sem frameworks/CDN. Reaproveitar componentes de card já existentes.

**Verificação:** manual no browser (descrita na Task 7). Sem teste automatizado de JS (YAGNI no MVP).

**Commit:** `feat: SPA da central (dashboard, novo, progresso, aprovação)`

---

### Task 7: Verificação ponta a ponta

**Files:** Modify `test_pipeline.py` se necessário; `README.md` (instruções `--serve`).

**Passos:**
1. `PYTHONUTF8=1 python -m pytest -q` — todos verdes.
2. `python main.py --serve`, abrir `localhost:5000`:
   - criar campanha (mock ou real conforme créditos), ver progresso, aprovar com data, ver no dashboard como aprovada.
3. Atualizar README (seção "Central de Controle" + `python main.py --serve`).

**Commit:** `docs: README da central + verificação`

---

## Ordem e dependências

1 → 2 → 3 (paralelo a 2) → 4 → 5 → 6 → 7. Cada tarefa com testes verdes antes de commitar.
