# Roadmap & Oportunidades de Melhoria — Mendes & Vaz Social

> Análise técnica de senior (auditoria do MVP + brainstorm de evolução).
> Documento vivo. Data: 2026-05-22. Autor: Enzo Ferraz + Claude Code.

## Veredito geral

O MVP está sólido para o que é: app **local, single-user, com estado em
arquivos** (`state.json` por campanha). Arquitetura limpa e modular
(briefing → copy → imagem → composição → estado → server). Pronto para demo e
uso do Henrique sozinho.

**Porém**, os recursos futuros desejados (post automático, analytics, captura de
leads) **não cabem na arquitetura atual** — exigem uma virada estrutural que vale
planejar desde já para não construir sobre fundação errada.

---

## 1. Auditoria técnica

### 🔴 Importante (corrigir antes de escalar)
- **Colisão de `campaign_id`**: o id é `data_slug`. Duas campanhas no mesmo dia
  com tema parecido geram o mesmo id e **sobrescrevem** uma à outra. Falta sufixo
  único (ex.: contador ou hash curto).
- **Escrita não-atômica do `state.json`**: `campaign_store.write_state` faz
  truncate+write sem lock. Com servidor `threaded` + thread de geração escrevendo
  enquanto o dashboard faz polling, pode-se ler JSON parcial → erro intermitente.
  Solução: escrever em arquivo temporário e `os.replace` (atômico) + lock por campanha.
- **Servidor de desenvolvimento exposto**: `werkzeug make_server` não é para
  produção. Para uso real, usar WSGI de verdade (waitress no Windows / gunicorn no Linux).

### 🟡 Médio
- **Carrossel incompleto**: `num_slides` é coletado e enviado ao prompt, mas o
  pipeline gera 1 imagem + 1 post por opção (não N slides). Hoje "carrossel"
  entrega 3 posts avulsos. Implementar multi-slide de verdade ou remover a opção.
- **Composer abre um Chromium por imagem**: `compose_all` lança o Playwright 3×
  por campanha. Reusar um browser/contexto para os 3 renders economiza tempo/recursos.
- **Sem validação de chaves no startup**: faltando `OPENAI_API_KEY`, só quebra na
  geração. Um health-check no `--serve` avisaria na hora.
- **Sem limite no input do briefing**: campos livres vão direto ao prompt
  (custo/erro com texto gigante). Cap simples resolve.

### 🟢 Nice-to-have
- Dependências com `>=` (não fixas) — pin exato dá builds reproduzíveis.
- Sem histórico de versões de copy (regerar sobrescreve `copy_v1.json`).
- Logs só por campanha (`log.txt`), sem visão central.
- Sem testes de frontend (aceitável no MVP).

---

## 2. A virada de arquitetura (pré-requisito dos recursos futuros)

Os três recursos futuros compartilham um requisito: **rodar sozinhos, 24/7, sem
ninguém no navegador.**

| Recurso futuro | Exige | Por quê |
|---|---|---|
| Post automático IG/LinkedIn | Agendador persistente + servidor hospedado | Postar numa data/hora precisa de um processo rodando; a thread atual morre no restart. |
| Analytics automático | Banco de dados (séries temporais) + jobs agendados | Coletar métricas no tempo não cabe em `state.json`. |
| Captura de leads (WhatsApp/Evolution) | Servidor **público** com webhooks + CRM | A Evolution envia eventos via webhook → exige URL pública estável (não ngrok temporário) + persistência. |

**Caminho de evolução recomendado (em ordem):**
1. **Estado em arquivo → SQLite** (um arquivo, ACID; resolve concorrência e vira
   base de analytics/leads). Migração barata.
2. **Threads → agendador real** (APScheduler embutido ou fila tipo RQ) num serviço.
3. **Local → hospedado** (Render/Fly/VPS) com WSGI de verdade + **autenticação**
   (login do Henrique) — pré-requisito de webhooks e posting agendado.
4. **OAuth real** para tokens de Meta/LinkedIn (não `.env` estático).

⚠️ **Atenção (experiência prática):** publicar nativo no Instagram/LinkedIn exige
conta Business, página e *app review* da Meta/LinkedIn (semanas de burocracia).
Para ir rápido ao mercado, **Buffer ou Later via API** evitam isso — começar por
eles e só depois (se valer) ir nativo.

---

## 3. Brainstorm de features (por fase)

### Fase 2 — Distribuição ("post automático")
- Publicação agendada via **Buffer/Later** (atalho) → depois Meta/LinkedIn nativo.
- **Aprovação pelo celular** (link/WhatsApp) — encaixa na infra Evolution e no
  perfil "sem tempo" do Henrique.
- Notificação "campanha pronta / publicada" (e-mail ou WhatsApp).

### Fase 3 — Captação ("leads")
- Funil WhatsApp (Evolution) → qualificação automática → **Airtable/CRM**.
- Link de captação por campanha → **atribuição (qual post gerou qual lead) → ROI
  por post**. Resolve a dor nº1 do Henrique ("gasto em ads sem saber o retorno").

### Fase 4 — Inteligência ("analytics")
- Ingestão de métricas IG/LinkedIn + **análise automática via LLM**
  ("posts de direito médico com tom técnico performam 2x; sugiro 3 desse tipo").
- **Loop fechado**: analytics → sugestão de pauta no próprio briefing.
  Diferencial que justifica retainer.

### Ideias adicionais (não citadas pelo cliente)
- **Memória de marca**: aprende com o que o Henrique aprova/rejeita e afina os
  prompts sozinho — ativo que melhora com o uso.
- **Multi-cliente (SaaS)**: multi-tenant abriria a TimeLabs para vender o mesmo
  produto a outros escritórios (o relatório fala em modelo SaaS).
- **Trilha de auditoria de aprovação**: o setor de saúde exige aprovação interna
  antes de campanha — registrar quem aprovou o quê/quando vira recurso de
  compliance vendável.
- **Painel de custos** (gasto de API por campanha).
- **Biblioteca + reaproveitamento** de posts aprovados; **séries/cadência**
  (gerar o mês inteiro de uma vez).
- **Editar a copy antes de aprovar** (controle total, custo zero de API).

---

## 4. Sequência recomendada

1. **Agora**: corrigir os 🔴 (id único, escrita atômica) — baratos e evitam falha
   boba na frente do cliente.
2. **Antes de qualquer recurso futuro**: migração **SQLite + WSGI + auth +
   hospedagem**. É a fundação dos três recursos; sem ela, reescreve-se tudo.
3. **Primeiro recurso de impacto comercial**: **captura de leads com atribuição de
   ROI** — dor nº1 do Henrique e o que fecha/renova contrato. Posting automático é
   "legal"; leads é "me dá dinheiro de volta".

---
*TimeLabs · documento de planejamento*
