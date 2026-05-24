# Fase 2 — Roadmap Técnico (pós-validação Mendes & Vaz)

> **Pré-requisito:** Mendes & Vaz validou o MVP e topou fechar negócio.
> **Objetivo:** transformar MVP local single-user em SaaS multi-cliente
> hospedado, capaz de atender 3-5 escritórios em produção real.
>
> **Estimativa total:** ~10-12 dias úteis de 1 dev sênior.
> **Custo de infra:** $20-50/mês na fase 2.

---

## Sumário

- [Resumo executivo](#resumo-executivo)
- [Pré-cirurgia: o que mudar primeiro](#pré-cirurgia-o-que-mudar-primeiro)
- [Bloco 1 — Multi-usuário](#bloco-1--multi-usuário-23-dias)
- [Bloco 2 — Persistência cloud-ready](#bloco-2--persistência-cloud-ready-2-dias)
- [Bloco 3 — Deploy em produção](#bloco-3--deploy-em-produção-15-dia)
- [Bloco 4 — Observabilidade e segurança](#bloco-4--observabilidade-e-segurança-2-dias)
- [Bloco 5 — Produto: features que destravam venda](#bloco-5--produto-features-que-destravam-venda-23-dias)
- [Ordem de execução sugerida](#ordem-de-execução-sugerida)
- [O que NÃO entra na fase 2](#o-que-não-entra-na-fase-2)
- [Critérios de aceite da fase](#critérios-de-aceite-da-fase)

---

## Resumo executivo

A fase 1 (MVP atual) assumiu:
- 1 escritório (Mendes & Vaz)
- 1 usuário (Henrique)
- 1 máquina (laptop do Enzo / Henrique)
- Estado em filesystem local + SQLite

A fase 2 quebra essas premissas **uma de cada vez**, na ordem certa, sem reescrever nada. Os módulos da fase 1 (`pipeline`, `composer`, `copy_generator`, `image_generator`) **não mudam**. O que muda é:
- `campaign_store` ganha `tenant_id`
- `state.db` (SQLite) vira Postgres
- `campaigns/{id}/` (FS local) vira S3/R2
- `main.py --serve` vira Docker + Gunicorn em servidor
- Acesso passa por auth

---

## Pré-cirurgia: o que mudar primeiro

Coisas pequenas que **destravam tudo o resto** e devem ser feitas antes:

| # | Item | Esforço | Motivo |
|---|---|---|---|
| 0.1 | Doc de arquitetura (1 página + diagrama) | 2h | Reduz bus factor de 1 pra 2; onboarding do próximo dev em horas, não dias |
| 0.2 | Mover prompts do LLM pra `config/prompts.py` | 1h | Permite trocar prompt sem mexer em lógica + versionar com git de forma limpa |
| 0.3 | Trocar `print()` por `logging` estruturado | 2h | Logs ficam grepáveis, com timestamps + níveis (debug/info/warning/error) |
| 0.4 | Adicionar `ruff` + `mypy` ao projeto (config básica) | 1h | Pega bugs de tipo antes de produção; CI vai usar |
| 0.5 | Testes E2E mínimos da API (não só smoke) | 3h | Cobertura de regressão pros refactors da fase 2 |

**Subtotal: ~1.5 dia.**

---

## Bloco 1 — Multi-usuário (2-3 dias)

### 1.1 Schema multi-tenant
- [ ] Adicionar tabela `tenants` (id, nome, plano, criado_em)
- [ ] Adicionar tabela `users` (id, tenant_id, email, senha_hash, role)
- [ ] Adicionar `tenant_id` em `campaigns` + índice composto `(tenant_id, status)`
- [ ] Migration que cria tenant "default" e move campanhas existentes pra ele

### 1.2 Auth básica
- [ ] `flask-login` + bcrypt pra senha
- [ ] Decorator `@login_required` em todas as rotas `/api/*` exceto `/api/login`
- [ ] Sessão HTTP-only cookie, expira em 7 dias
- [ ] Tela de login simples no SPA (1 input email + 1 input senha)

### 1.3 Isolamento de dados
- [ ] Todo `campaign_store.read_*` filtra por `tenant_id` da sessão atual
- [ ] Testes garantindo que tenant A NÃO vê campanhas de tenant B
- [ ] Logs de auditoria pra ações cross-tenant (não deveria acontecer — alerta se acontecer)

### 1.4 Roles
- [ ] `admin` (você): vê todos os tenants, cria/desativa contas
- [ ] `aprovador` (sócio do escritório): pode aprovar, agendar, exportar
- [ ] `criador` (estagiário): pode criar briefing e regerar; aprovação fica bloqueada

**Por que importa:** sem isso, não dá pra ter cliente #2.

---

## Bloco 2 — Persistência cloud-ready (2 dias)

### 2.1 Postgres no lugar de SQLite
- [ ] Subir Postgres gerenciado (Supabase free tier ou Neon)
- [ ] `psycopg[binary]` no `requirements.txt`
- [ ] Adapter em `modules/store.py` — manter API existente
- [ ] Migration de SQLite → Postgres usando `migrate_from_files`-style script
- [ ] Connection pool (`psycopg-pool`) configurado

### 2.2 PNGs em object storage
- [ ] Provider: **Cloudflare R2** (S3-compatible, $0 egress) ou Supabase Storage
- [ ] `boto3` + presigned URLs pra preview
- [ ] `composer.py` salva no R2 em vez de `campaigns/{id}/composed/`
- [ ] `exporter.py` salva no R2 + retorna URL pública assinada
- [ ] Fallback local pra desenvolvimento (`USE_LOCAL_STORAGE=true`)

### 2.3 Backup automatizado
- [ ] Snapshot diário do Postgres (Supabase faz nativo)
- [ ] R2 tem versioning de objetos
- [ ] Retenção: 30 dias

**Por que importa:** desbloqueia deploy multi-host, deploy serverless, e recovery de desastre.

---

## Bloco 3 — Deploy em produção (1.5 dia)

### 3.1 Containerização
- [ ] `Dockerfile` baseado em `python:3.11-slim` + `playwright install --with-deps chromium`
- [ ] `docker-compose.yml` pra dev local com Postgres
- [ ] `.dockerignore` pra não vazar `.env`, `state.db`, `campaigns/`

### 3.2 Hosting
- [ ] **Recomendado:** Railway ($5-10/mês, deploy via git push)
- [ ] Alternativa: Fly.io (volumes persistentes, $5-15/mês)
- [ ] Domínio: `mendesvaz.timelabs.com.br` (ou parecido)
- [ ] HTTPS automático via plataforma
- [ ] Variáveis de ambiente no painel (não no repo)

### 3.3 Servidor de produção
- [ ] Trocar `waitress` por `gunicorn` (Linux-native, melhor concorrência)
- [ ] 2 workers Gunicorn + 4 threads cada
- [ ] Healthcheck endpoint `GET /health` (verifica DB + R2)
- [ ] Graceful shutdown (espera campanhas em geração terminarem)

**Por que importa:** primeiro cliente externo não vai aceitar "abrir no laptop do Enzo".

---

## Bloco 4 — Observabilidade e segurança (2 dias)

### 4.1 Erros
- [ ] **Sentry** (free tier suficiente): captura exceções não tratadas
- [ ] Filtros pra não logar conteúdo de briefing (LGPD)
- [ ] Alertas pra erros novos no Slack/email

### 4.2 Métricas de custo de IA
- [ ] Coluna `tokens_in`, `tokens_out`, `cost_usd` em `copy_versions`
- [ ] Dashboard interno: custo por cliente, por mês
- [ ] Alerta se custo do mês passar de X%/orçamento

### 4.3 Uptime e performance
- [ ] **UptimeRobot** (free): ping no `/health` a cada 5min
- [ ] **Plausible** ou **PostHog** pra analytics da SPA (zero cookies, GDPR-safe)

### 4.4 Segurança mínima de produção
- [ ] Rate limit em `/api/campaigns POST` (3 por minuto por user)
- [ ] CSRF tokens nas mutações
- [ ] Sanitização do `tema_especifico` e `referencias` antes de mandar pro LLM
  (rejeitar inputs com "ignore previous instructions" e similares)
- [ ] Headers de segurança (CSP, X-Frame-Options) via Flask-Talisman
- [ ] Rotação das chaves OpenAI/Ideogram (criar novas, revogar antigas após deploy)

**Por que importa:** o que você não mede você não controla. Custo de IA pode estourar silencioso.

---

## Bloco 5 — Produto: features que destravam venda (2-3 dias)

### 5.1 Templates de briefing (já existe API, falta UI)
- [ ] Tela "Meus templates" na SPA
- [ ] Botão "Salvar como template" na aprovação
- [ ] Botão "Usar template" na criação de campanha

### 5.2 Duplicar campanha
- [ ] Endpoint `POST /api/campaigns/<id>/duplicate`
- [ ] UI: ação no dashboard "Duplicar essa campanha"
- [ ] Permite gerar variação de uma campanha aprovada sem refazer briefing

### 5.3 Calendário editorial real
- [ ] Drag-and-drop de campanhas no calendário
- [ ] Visualização semanal/mensal
- [ ] Ícone visual por status (rascunho/agendada/publicada)

### 5.4 Publicação automática (Buffer / Meta API)
- [ ] Integração com **Buffer** (mais simples) ou **Meta Graph API** (direto)
- [ ] OAuth do Instagram/LinkedIn do cliente
- [ ] Cron job que verifica `data_agendada == hoje` e publica
- [ ] Log de publicações + status (sucesso/erro)

### 5.5 Captação de leads (gancho do Bloco 5.4)
- [ ] Link com UTM gerado automaticamente no post
- [ ] Landing page simples por campanha (`/lp/<campaign_id>`)
- [ ] Form de captação → Airtable/Postgres
- [ ] Notificação no WhatsApp do Henrique quando lead chega

**Por que importa:** publicação automática é o que justifica preço de SaaS (vs uma rodada de Canva).

---

## Ordem de execução sugerida

```
Semana 1 (3-4 dias)
  ├── Pré-cirurgia (0.1 a 0.5)          ▓▓░░░ 1.5d
  └── Bloco 1 — Multi-usuário           ▓▓▓░░ 2.5d

Semana 2 (3-4 dias)
  ├── Bloco 2 — Cloud storage           ▓▓░░░ 2d
  └── Bloco 3 — Deploy                  ▓▓░░░ 1.5d

Semana 3 (3-4 dias)
  ├── Bloco 4 — Observabilidade         ▓▓░░░ 2d
  └── Bloco 5 — Produto (5.1, 5.2, 5.3) ▓▓░░░ 2d

Semana 4 (opcional, condicional)
  └── Bloco 5.4 + 5.5 — Publicação      ▓▓▓▓░ 3-4d
```

**Crítico:** não pular pro Bloco 4/5 sem 1/2/3 prontos — vai retrabalhar.

---

## O que NÃO entra na fase 2

Resistir a essas tentações:

| Item | Por que NÃO agora |
|---|---|
| **Reescrever frontend em React/Svelte** | Vanilla ainda aguenta. Reescrever sem pressão real de UX é vaidade. Fase 3+. |
| **Microservices / event-driven architecture** | Single binary com 2 workers atende 10 clientes. Complexidade prematura. |
| **GraphQL** | REST + JSON é mais simples e legível pro escopo atual. |
| **Kubernetes** | Railway/Fly faz isso por você. K8s só faz sentido > 50 clientes. |
| **LangChain / agentic framework** | Wrapper de OpenAI direto está funcionando. Adicionar camada = adicionar bug surface. |
| **Vector DB / RAG** | Não tem caso de uso — copy é gerado fresh a cada vez. Não tente injetar RAG porque "todo mundo usa". |
| **Mobile app nativo** | PWA da SPA atual atende. Nativo só com 100+ usuários ativos. |
| **A/B testing infrastructure** | Cliente único na fase 2. Sem dados pra A/B testar. Fase 3. |

---

## Bloco 6 — Quotas e prevenção de abuse (1-2 dias)

> **Problema real:** cliente paga R$ 400/mês de SaaS e no primeiro mês cria
> 365 campanhas pra agendar o ano inteiro. Depois não usa mais. Você queima
> $30+ de OpenAI/Ideogram num lead que não vai renovar — margem negativa.

### 6.1 Limites por plano (configurável em `config/settings.py`)

```python
PLANOS = {
    "essencial":  {"campanhas_mes": 12,  "agendadas_futuro": 8,  "pendentes_aprovacao": 5},
    "profissional": {"campanhas_mes": 30, "agendadas_futuro": 20, "pendentes_aprovacao": 10},
    "agencia":    {"campanhas_mes": 100, "agendadas_futuro": 60, "pendentes_aprovacao": 30},
}
```

### 6.2 Regras de quota a implementar
- [ ] **Quota mensal por tenant** — `count(campaigns where created_at >= início do mês)` ≤ limite
- [ ] **Limite de campanhas agendadas no futuro** — `count(where data_agendada > hoje)` ≤ limite
  - Evita o "criar pro ano todo no 1º mês"
- [ ] **Limite de campanhas pendentes não-aprovadas** — força fechar ciclo antes de criar mais
  - Educacional: o operador *precisa* aprovar/rejeitar antes de bombardear o sistema
- [ ] **Cooldown entre criações** (opcional) — min 60s entre POSTs (evita scripts/bots)

### 6.3 Resposta ao estourar quota
- [ ] HTTP `429 Too Many Requests` com body explicativo:
  ```json
  {"erro": "Quota mensal atingida (30/30 campanhas).",
   "tipo": "quota_mes", "limite": 30, "atual": 30,
   "reset_em": "2026-06-01"}
  ```
- [ ] UI mostra banner: "Você usou 30 das 30 campanhas do plano Profissional este mês.
  Renova em 7 dias. Quer fazer upgrade?"
- [ ] Sem bloqueio destrutivo — campanhas já criadas continuam editáveis/aprováveis

### 6.4 Quota de revisão (regeração de copy)
- [ ] **Max N regerações por campanha** — ex: 5. Custo de API soma rápido com revisão sem fim.
- [ ] Atingiu o limite → edição manual continua disponível (custo zero)

### 6.5 Audit log de uso (sem o cliente ver)
- [ ] Tabela `usage_events` (tenant_id, action, cost_usd, timestamp)
- [ ] Internamente você vê: qual escritório está perto de virar prejuízo
- [ ] Trigger pra contato comercial proativo ("notei que você atingiu 80% do plano,
  vale considerar upgrade?")

### 6.6 Soft limits vs Hard limits

| Tipo | Quando aplicar | Comportamento |
|---|---|---|
| **Soft** (warning) | 70% da quota | Banner amarelo "você usou 21/30" |
| **Hard** (bloqueio) | 100% da quota | 429 + UI bloqueia botão "Nova campanha" |

**Por que importa pro negócio:**
- Previsibilidade de custo unitário (CAC vs LTV calculável)
- Educa o cliente a usar dentro do plano
- Cria pressão natural pra upgrade
- Margem garantida no pior caso (cliente bate teto sempre)

**Por que importa pra demo de quinta:**
Versão simplificada (sem multi-tenant, sem plano) dá pra implementar HOJE:
- 1 escritório (Mendes & Vaz) com limites globais
- Mostra durante demo: "tem proteção pra você não estourar"
- Sinal de **maturidade de produto SaaS**, não só engenharia

---

## Critérios de aceite da fase

A fase 2 está pronta quando:

- [ ] **3 escritórios** podem usar simultaneamente sem ver dados um do outro
- [ ] **Login funciona** com email + senha, sessão persistente
- [ ] **Henrique consegue acessar de casa** (não só do laptop dele)
- [ ] **PNG aprovado fica disponível por URL pública** (R2 + presigned)
- [ ] **Sentry recebe** primeiro erro de produção e você é notificado
- [ ] **Custo de IA do mês** está visível num dashboard
- [ ] **Backup do DB** rodou pelo menos 7 vezes consecutivas
- [ ] **Onboarding de um novo cliente** leva < 30 minutos manualmente
- [ ] **Publicação automática** funciona pra Instagram (se Bloco 5.4 entrar)

---

## Estimativa de custo de operação (mensal)

| Item | Custo aprox. |
|---|---|
| Hosting (Railway/Fly) | $5-15 |
| Postgres (Supabase free / Neon) | $0-25 |
| Object storage (R2) | $0-5 |
| Domínio | $1-2 |
| Sentry / UptimeRobot | $0 (free tier) |
| OpenAI (3 clientes × 20 campanhas/mês × $0.05) | $3-5 |
| Ideogram (mesmo cálculo × $0.30) | $18-30 |
| **Total fixo** | **$27-82/mês** |
| **Por cliente extra** | **+$8-10/mês variável** |

**Margem mínima sustentável:** cobrar **R$ 300-500/escritório/mês** dá margem
saudável e cabe no orçamento de marketing de escritório pequeno.

---

## Riscos da fase 2

| Risco | Mitigação |
|---|---|
| Postgres migration corromper dados | Backup do SQLite antes; dry-run em staging |
| R2 ficar caro com muitas variações de PNG | Implementar limpeza de PNGs > 90 dias não-aprovados |
| Auth implementada errado vazar dados | Testes E2E de isolamento multi-tenant antes de subir |
| Meta API change-breaking | Usar Buffer como camada de abstração (eles absorvem mudanças) |
| Bus factor ainda = 1 | Contratar 1 dev part-time OU documentar arquitetura |

---

## Métricas de saúde técnica (acompanhar mensalmente)

- Custo de IA por campanha (deve ficar estável conforme prompts amadurecem)
- Taxa de erros (Sentry) por 1000 campanhas
- p95 de tempo de geração (alvo: < 45s)
- Uptime mensal (alvo: 99%+)
- Churn (escritórios que cancelaram / total)

---

*TimeLabs · Enzo Ferraz · Documento criado em 2026-05-24*
*Revisar antes de iniciar a fase 2.*
