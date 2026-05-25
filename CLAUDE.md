# content_agent — Mendes & Vaz Social (TimeLabs)

## O que e este projeto

Pipeline de geracao de conteudo para Instagram/LinkedIn que recebe um briefing
de 7 campos e devolve 3 variacoes de post prontas pra aprovacao. Hoje atende
**Mendes & Vaz** (escritorio de advocacia em BH) como cliente piloto. Em
transicao pra plataforma multi-marca (proximos clientes: DJ Gui, possivel
agencia de marketing).

Stack: Python + Flask + SQLite + Playwright (HTML/CSS -> PNG) + OpenAI (copy)
+ Ideogram (arte de fundo).

## Kit base

`timelabs` (Python + automacao).

## Onde ler primeiro

Toda a documentacao tecnica ja existe. **Nao duplicar aqui, ler la:**

- `README.md` — setup, comandos, arquitetura visual, roadmap resumido.
- `docs/arquitetura.md` — componentes, fluxo de campanha, modelo de dados,
  decisoes arquiteturais, atalhos "como adicionar X". Onboarding em 15 min.
- `docs/fase-2-roadmap.md` — plano completo de evolucao pra SaaS (multi-tenant,
  deploy, quotas, brand config, publicacao automatica).
- `docs/roadmap-e-melhorias.md` — auditoria tecnica + debito identificado.
- `docs/video-editing-research.md` — relatorio sobre automacao de edicao de
  video (gerado em 2026-05-25 pra avaliar entrada nesse mercado).

## Comandos essenciais

```bash
# Setup (1x)
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # depois preencher OPENAI_API_KEY e IDEOGRAM_API_KEY

# Subir a central (modo normal)
python main.py --serve

# Gerar 1 campanha via terminal (debug)
python main.py --campaign novo

# Testes
python -m pytest -q                # unitarios (rapido, sem rede)
python test_pipeline.py            # smoke E2E (Playwright real, API mockada)
```

## Principios inegociaveis

Violar qualquer um destes e bug grave, nao decisao tecnica:

1. **Texto NUNCA dentro de imagem gerada por IA.** Modelos de imagem erram
   tipografia. Toda copy vai pelo template HTML/CSS. Se voce ver alguem
   sugerindo "deixa o Ideogram colocar a headline na arte", recuse.
2. **Identidade visual e dado, nao codigo.** Hoje esta hardcoded em
   `config/settings.py` (COLORS, FONTS, LOGO_PATH) porque so tem 1 cliente.
   **Quando entrar o 2o cliente (Gui DJ), extrair pra brand config por
   cliente** — nao duplicar templates por cliente.
3. **Human in the loop.** Nada publica sozinho. Aprovacao do operador
   (Henrique, Gui, etc) e obrigatoria antes de qualquer export.
4. **`config/settings.py` e a unica fonte de verdade.** Cores, fontes,
   dimensoes, prompts, modelos, chaves, quotas. Nenhum outro modulo deve
   hardcodar valor de config.
5. **Falhar cedo, com mensagem clara.** Healthcheck no startup
   (`_check_credenciais`, `_check_chromium`), validacao de briefing com
   ValueError descritivo, status `erro` com mensagem visivel pro operador.

## Gotchas (coisas que ja morderam)

- **Playwright + `networkidle`**: alguns `@import` remotos travam o evento.
  Por isso o composer pega screenshot mesmo se der timeout em `set_content`
  (`composer.py:107`). As fontes locais ja estao embarcadas como data URI,
  entao o PNG sai correto.
- **Threads daemon morrem com o processo.** Se voce mata `python main.py`
  enquanto uma campanha esta gerando, ela fica "gerando" pra sempre no DB.
  `_recover_orphan_campaigns` marca como erro no proximo startup
  (`main.py:67`).
- **SQLite + threads**: conexoes NAO sao compartilhadas. Cada operacao
  abre/fecha via `connect()` context manager (`store.py:108`). Nao
  reaproveite conexao entre threads — vai dar `ProgrammingError`.
- **Prompt injection nos campos livres do briefing** ja tem filtro regex
  basico (`briefing_parser.py:22`). Nao perfeito, mas barra ataque copy-paste.
- **Cache de assets da SPA**: o servidor injeta `?v=<mtime>` em `app.js` e
  `style.css` (`server.py:259`) pra evitar usuario ver versao antiga apos
  deploy. Mantenha esse comportamento.
- **`image_generator` cai pra placeholder navy/gold** se `IDEOGRAM_API_KEY`
  faltar ou `USE_MOCK_IMAGES=true`. Dev consegue rodar sem chave de imagem.
  Copy sem `OPENAI_API_KEY` falha fatal — sem fallback.

## O que NAO fazer

- **Nao adicionar abstracao "pro caso futuro"** (LangChain, ORM, fila Celery,
  microservicos). Se nao destrava feature concreta da semana, fica fora.
- **Nao mexer em codigo nao-relacionado ao pedido** (regra global do Enzo).
- **Nao commitar com `Co-authored-by` do Claude.** So `@enzoofs` (regra
  global).
- **Nao publicar conteudo automaticamente** — quebra principio 3.
- **Nao trocar vanilla JS por React/Svelte sem pedido explicito.** SPA
  atual aguenta o escopo. Trade-off documentado em `docs/arquitetura.md`.

## Contexto estrategico atual (2026-05-25)

- **MVP entregue dia 22/05** em 3 dias. Demo pra Mendes & Vaz marcada
  pra quinta 28/05.
- **Marcos** entra como socio em breve — codigo precisa ser legivel
  o suficiente pra ele dar manutencao. Documentacao e prioridade.
- **Gui** (DJ + content creator com network forte) sera o primeiro cliente
  multi-marca. Vai exigir:
  - Brand config dinamico (paleta/fontes/logo por cliente) — item 5.7 do
    fase-2-roadmap.
  - Briefing/templates adaptados pra contexto musical (evento, lineup,
    vibe — diferente de "area do direito").
  - Possivelmente novo formato de output (Stories, Reels).
- **Possivel agencia de marketing** via contato do Gui — santo graal B2B2C.
  Exige white-label real + provavelmente API publica. Nao priorizar antes
  de Gui rodar.
- **Edicao de video automatizada** e demanda mencionada pelo Gui. Track
  tecnico completamente diferente (FFmpeg + whisper). Relatorio de
  viabilidade em `docs/video-editing-research.md`. Nao construir antes do
  Gui DJ rodar com posts estaticos.

## Pessoas envolvidas

- **Enzo Ferraz** (`@enzoofs`) — dev solo no momento, dono do produto.
- **Marcos** — socio entrante, vai dar manutencao e/ou comercial.
- **Henrique Mendes** — operador no cliente Mendes & Vaz (aprovador).
- **Gui** — DJ + criador de conteudo, primeiro cliente multi-marca em
  preparacao.

## Como trabalhar comigo neste projeto

- Plano antes de codar pra qualquer mudanca nao-trivial. Confirmar com Enzo.
- Mudancas cirurgicas — diff so com o que foi pedido.
- Comentarios em portugues, codigo legivel pro Marcos.
- Rodar `pytest` antes de qualquer commit. Nao quebrar os 60 testes
  existentes.
- Quando expandir pra multi-marca, **sempre perguntar: isso vale pra
  Mendes & Vaz E pro Gui?** Se so vale pra um, esta no lugar errado
  (provavelmente em brand config, nao em codigo).
