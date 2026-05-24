# Status de postagem & Kanban (engavetado)

> Plano técnico discutido em sessão de redesign visual da Central de Controle.
> Data: 2026-05-23. Autor: Enzo Ferraz + Claude Code.
> Relacionado: [`roadmap-e-melhorias.md`](../roadmap-e-melhorias.md) (Fase 2 — Distribuição).

---

## Resumo da decisão

- **Status de postagem**: implementar. O sistema hoje só sabe se foi *aprovada*,
  não se foi *publicada*. Gap claro de produto.
- **Kanban**: engavetado por enquanto. Complexidade desproporcional ao valor no
  momento; revisitar quando os gatilhos abaixo baterem.
- **APIs IG/LinkedIn**: pré-requisito do "status automático". Documentar a
  costura agora pra não codar o manual sem deixar a integração óbvia depois.

---

## 1. Gap atual (verificado em 2026-05-23)

### O que existe
- `state.json` por campanha em `data/campaigns/<id>/state.json` com campos:
  `status`, `etapa`, `option_aprovada`, `data_agendada`, …
- Tabela SQLite (`modules/store.py`) replica esses campos.
- A aba **Calendário** (`approval_ui/app.js:444`) renderiza chips das campanhas
  com `data_agendada` setada, agrupadas por dia.

### O que NÃO existe
- Nenhum campo do tipo `publicado_em` / `published_at` / `status_publicacao`.
- Calendário não distingue **data passada não publicada** vs **futura** vs
  **publicada**. Todas viram o mesmo chip navy.
- Não há aviso ("⚠ post de 20/05 não foi marcado como publicado") nem em lista,
  nem em calendário, nem em dashboard.
- Audit log (`exports/audit.jsonl`) registra eventos do pipeline (gerou copy,
  aprovou) mas **não** registra publicação real (não tem fonte que dispare).

### Consequência prática
Henrique aprova um post pra "30/05", esquece, e o dia passa. Sistema continua
mostrando "Aprovada · 30/05" como se estivesse tudo bem. O conteúdo gerado fica
órfão na pasta `exports/` sem ninguém saber se foi pro ar.

---

## 2. Plano — Status de postagem

### Estados-alvo (status derivado, a partir dos dados do state.json)

| Estado UI | Condição |
|---|---|
| Gerando | `status == "gerando"` |
| Aguardando aprovação | `status == "aguardando_aprovacao"` |
| Agendada | `status == "aprovada"` && `data_agendada >= hoje` && `!publicado_em` |
| Atrasada ⚠ | `status == "aprovada"` && `data_agendada < hoje` && `!publicado_em` |
| Publicada ✓ | `status == "aprovada"` && `publicado_em != null` |
| Erro | `status == "erro"` |

O backend continua com o vocabulário atual (`status` = workflow do pipeline).
O frontend deriva o **estado de exibição** a partir de `status + data_agendada
+ publicado_em + hoje`. Isso evita migração de status no banco e mantém o
pipeline desacoplado da postagem.

### Fase A — Manual (antes das APIs)

**Backend (uma sessão futura, alinhar com o outro Claude que mexe em
campaign_store):**
- Novo campo opcional `publicado_em: str | None` em `state.json` (ISO 8601).
- Replicar coluna no SQLite (`modules/store.py`).
- Endpoint `POST /api/campaigns/<id>/marcar-publicado` com body
  `{ "publicado_em": "2026-05-30T14:30:00" }`. Default = `now()` se omitido.
- Registrar evento `publicado_manual` em `audit.jsonl`.

**Frontend:**
- Helper `derivarStatusPostagem(campaign)` no `app.js` que retorna um dos
  estados-alvo acima.
- Card aprovado ganha botão **"Marquei como publicado"** com input de data
  opcional (default hoje). Vira badge "Publicada ✓" após confirmar.
- Dashboard usa o estado derivado pra colorir badges (ATRASADA em vermelho
  contido, PUBLICADA em verde-ouro).
- Calendário marca células passadas-não-publicadas com borda vermelha sutil +
  ícone discreto no chip.
- **Filtro "ocultar publicadas"** (toggle persistido em localStorage) — entrega
  o "ocultar aprovadas" pedido no escopo do kanban, sem precisar do kanban.

### Fase B — Automático (após integrar IG/LinkedIn APIs)

Bloqueado pela **virada de arquitetura** descrita em
[`roadmap-e-melhorias.md`](../roadmap-e-melhorias.md) §2 (SQLite + WSGI + auth +
hospedagem + agendador real). Sem isso, não dá pra publicar sozinho às 14:30 de
uma quinta com o navegador fechado.

Quando a infra estiver pronta:
- OAuth real Meta (Instagram Graph API) + LinkedIn API. Tokens em DB, não
  `.env`.
- Endpoint `POST /api/campaigns/<id>/publish` que de fato publica e seta
  `publicado_em = now()` na resposta da API.
- Worker (APScheduler ou RQ) que dispara `publish` automático quando
  `data_agendada <= now()` e há credencial vinculada.
- Ingestão de métricas (likes/views/comments) após publicar → alimenta a Fase 4
  do roadmap (analytics).

**Atalho pragmático:** mesmo na Fase B, manter o botão manual da Fase A como
fallback (para conteúdo postado fora do sistema, story, anúncio, etc.).

---

## 3. Kanban — engavetado

### Por que não agora
1. **Backend persistente.** Mover card entre colunas, comentar, manter
   histórico — tudo isso precisa escrever em `campaign_store.py` /
   `server.py`, onde o outro Claude está editando. Risco alto de colisão.
2. **Complexidade desproporcional.** A Central hoje atende **um único
   aprovador** (Henrique). Kanban resolve coordenação de time; sem time, é
   ergonomia que custa caro pelo que entrega.
3. **Status de postagem entrega 80% do valor pedido.** O pedido original do
   kanban incluía "ocultar aprovadas" e "ver histórico" — ambos cabem dentro da
   Fase A acima (filtro + audit.jsonl exposto).

### Quando reabrir
Qualquer um destes gatilhos:
- Backend estabilizou (outro Claude terminou + SQLite + atomicidade resolvidos).
- Surge **segunda pessoa** aprovando (Henrique + sócio, ou agência + cliente).
- Henrique pedir explicitamente "quero arrastar cards" depois de usar a Fase A
  por um mês e sentir a falta.
- Multi-cliente (SaaS): aí kanban por cliente faz sentido como organização.

### O que reaproveitar quando voltar
- **Comentários**: provavelmente já existirá necessidade na revisão pré-aprovação
  (não só pós). Modelar como `comentarios: [{autor, ts, texto, fase}]` em
  state.json desde o início.
- **Histórico**: `audit.jsonl` já cobre eventos do pipeline. Acrescentar
  `kanban_movido_de_X_para_Y` é só mais um tipo de evento. Já temos a infra.
- **Drag-and-drop**: usar Sortable.js (~20KB, sem deps), evita reinventar.

---

## 4. Sequência recomendada

1. **Sessão dedicada** com o outro Claude alinhado: adicionar `publicado_em` no
   state.json + SQLite + endpoint `marcar-publicado` + log de audit.
2. **No frontend** (sessão separada, sem tocar backend): implementar helper de
   estado derivado, botão manual, filtro "ocultar publicadas", aviso visual de
   atraso no calendário e dashboard.
3. **Validar com Henrique** por 2-4 semanas de uso real. Ver se a UX manual
   incomoda o suficiente pra justificar OAuth.
4. **Depois**: integração IG/LinkedIn na ordem do roadmap geral (Buffer/Later
   primeiro, nativo depois).

---

## 5. Decisões registradas (pra não revisitar)

| Decisão | Razão |
|---|---|
| Status derivado no frontend, não migração de enum no backend | Pipeline e postagem têm ciclos de vida independentes; acoplar é dívida |
| Aviso de atraso em vermelho contido, não brutal | Identidade visual editorial sóbria; alerta sem alarmismo |
| Calendar mostra atraso por borda + ícone, não por trocar cor do chip | Chip navy é parte da assinatura visual; muda o entorno, não o objeto |
| Default do `publicado_em` no botão manual = hoje | Caso de uso comum: "postei agora" |
| `publicado_em` é timestamp, não bool | Preserva data real pra analytics futuros |

---
*TimeLabs · documento de planejamento*
