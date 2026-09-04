# Onboarding — content_agent (TimeLabs)

> Documento de entrada pro Marcos. Le isto antes de qualquer outra coisa.
> Tempo estimado de leitura: 25 min. Tempo ate primeiro commit: ~1 hora.
>
> Autor: Enzo Ferraz · Atualizado em 2026-09-04 (revisão geral — a versão
> anterior falava de uma demo de maio que já aconteceu há 4 meses; se você
> está lendo isto, é porque estava desatualizado e alguém corrigiu — bom
> sinal, é assim que este doc deveria funcionar. Ver nota no rodapé.)

---

## 1. Contexto em 2 minutos

**O que o sistema faz:**
Recebe um briefing curto (7 campos sobre o tema do post), chama OpenAI pra
escrever 3 variacoes de copy, chama Ideogram pra gerar 3 artes de fundo,
compoe tudo num PNG final (HTML/CSS renderizado pelo Chromium), e entrega
no painel pra o cliente aprovar. So depois de aprovado e que vira post pronto
pra ir no Instagram/LinkedIn.

**Quem usa hoje:**
Henrique Mendes, do escritorio **Mendes & Vaz** (Belo Horizonte) — **cliente
pagante**, R$247/mes, rodando em producao no Fly.io (nao mais local). Demo
de maio ja aconteceu e fechou o contrato.

**Quem vai usar em breve:**
- **Gui** (DJ + criador de conteudo) — primeiro cliente multi-marca, ainda
  nao onboardado.
- Possivel **agencia de marketing** via rede do Gui — santo graal B2B2C.

**Por que importa pra TimeLabs:**
E o primeiro produto de **conteudo automatizado** da empresa. Se virar SaaS
com 5-10 escritorios/criadores pagantes, vira fluxo de receita recorrente
independente das automacoes N8N sob demanda.

---

## 2. Status agora (2026-09-04)

| Item | Status |
|---|---|
| MVP pra Mendes & Vaz | Em producao (Fly.io), pagante |
| Testes automatizados (unit + smoke) | ~130 passando |
| Brand config dinamico (multi-cliente) | Parcial — layout, cor de sombra e fonte ja sao dado por brand; Gui ainda nao tem brand proprio criado |
| Seletor de layout visual (3 opcoes) | Pronto |
| Upload multi-foto no carrossel | Pronto |
| Publicacao automatica (Instagram, via Blotato) | Infra escrita, **nao testada contra API real**, nao conectada ainda |
| Bot de WhatsApp (lembrete + sugestao de tema) | Nao iniciado — depende de decisao de provedor (Z-API) |
| Edicao de video automatizada | Descartado por enquanto (ver `video-editing-research.md`) |

Nao ha congelamento de codigo agora — isso so existiu na semana da demo de
maio (historico, nao se aplica mais). Trabalhe normal: branch, PR, testes.

---

## 3. Setup local — do zero ao rodando em 10 min

### 3.1 Pre-requisitos
- Python 3.11+
- `git`
- Conexao com internet (pra baixar Chromium do Playwright)
- ~500MB de disco

### 3.2 Passo a passo

```bash
# Clonar e entrar
git clone <repo> content_agent
cd content_agent

# Ambiente virtual
python -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate           # Windows

# Dependencias Python — use `python -m pip`, NAO so `pip`. Em algumas
# maquinas Windows o `pip` solto resolve pro pip global em vez do pip do
# venv ativo (sintoma: "Defaulting to user installation..." e libs fora
# do venv). `python -m pip` garante que e o pip certo.
python -m pip install -r requirements.txt

# Chromium do Playwright (~150MB)
playwright install chromium

# Variaveis de ambiente
cp .env.example .env
# Edita o .env e coloca:
#   OPENAI_API_KEY=sk-...        (obrigatoria — pede pro Enzo)
#   IDEOGRAM_API_KEY=...         (opcional — sem ela, arte sai como placeholder)
```

### 3.3 Validar que funciona

```bash
# Rodar os testes (~30s)
python -m pytest -q
# Esperado: 60 passed

# Subir a central
python main.py --serve
# Abre http://localhost:5000 no browser
# Clica em "Nova campanha", preenche, clica gerar.
# Em ~1 min voce ve 3 variacoes prontas pra aprovar.
```

Se travou em algum ponto, **PARE e chama o Enzo.** Nao tente debugar setup —
provavelmente e diferenca de ambiente (chave faltando, Playwright nao instalou).

---

## 4. Tour do codigo — onde mexer pra que

**Antes de codar qualquer coisa, le na ordem:**

1. **`CLAUDE.md`** (raiz) — principios inegociaveis, gotchas conhecidos,
   contexto estrategico atual. **5 min.**
2. **`README.md`** — comandos, estrutura de pastas, API HTTP. **5 min.**
3. **`docs/arquitetura.md`** — diagrama do fluxo, modelo de dados, decisoes
   arquiteturais, atalhos "como adicionar X". **15 min.**

Pra entender o motor:

4. **`config/settings.py`** (179 linhas) — todas as constantes do sistema.
   Unica fonte de verdade pra cores, fontes, modelos, prompts, quotas.
5. **`modules/pipeline.py`** (72 linhas) — orquestra copy → arte → composicao.
   Le inteiro, e curto.
6. **`modules/server.py`** (~500 linhas) — todos os endpoints HTTP.

Pra entender features especificas, consulta a tabela "Como adicionar X" em
`docs/arquitetura.md` secao 7 — ela aponta exatamente quais arquivos mexer
pra cada tipo de mudanca.

---

## 5. Padroes TimeLabs neste projeto

### 5.1 Codigo

- **Comentarios em portugues** (regra do Enzo). Codigo (variaveis, funcoes)
  em ingles segue PEP 8.
- **Type hints** em funcoes publicas (`def fn(x: str) -> int:`).
- **f-strings** pra formatacao (nunca `%` ou `.format`).
- **`pathlib.Path`** ao inves de `os.path`.
- **`logging`** ao inves de `print()` — exceto em scripts de CLI e debug
  do startup (que printam pro operador ver no terminal).
- **Imutabilidade:** nao mutar dicts/listas in-place; criar copia. Ver
  `_aplicar_edicao` em `server.py:195` como exemplo.
- **Funcoes pequenas** (<50 linhas idealmente).
- **Arquivos focados** (<800 linhas).

### 5.2 Testes (obrigatorio)

- **TODO codigo novo precisa de teste.** Cobertura alvo: 80%.
- Estrutura:
  - `tests/test_*.py` — unitarios (rapidos, sem rede)
  - `test_pipeline.py` (raiz) — smoke E2E com Playwright real
- **Roda os testes antes de commitar.** Sem excecao.
  ```bash
  python -m pytest -q
  ```
- **Nunca corrige o teste quando o codigo quebra** — corrige o codigo. So mexe
  no teste se voce mesmo identificou que o teste e que estava errado.

### 5.3 Commits

- Formato: `<tipo>: <descricao em ingles>`
  - Tipos: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`
- **Mensagens em ingles** (padrao mercado).
- **Sem `Co-authored-by` do Claude.** Commits sempre por `@enzoofs` ou
  conta do Marcos quando voce tiver setup.
- **NUNCA commitar direto em `main` sem alinhar com Enzo.**

### 5.4 Seguranca (checklist antes de commitar)

- [ ] Sem secrets hardcoded (API keys, senhas, tokens) — usar `.env`
- [ ] Validacao de input de usuario (briefing passa por `briefing_parser`)
- [ ] Sem queries SQL dinamicas (usar placeholders `?` no sqlite3)
- [ ] Mensagens de erro nao vazam dados sensiveis

### 5.5 Mudancas cirurgicas

Toca **apenas** no que foi pedido. Se notou codigo feio adjacente,
**menciona pra o Enzo — nao refatora junto.** Isso vale ouro pra code review.

---

## 6. Fluxo de branch — como contribuir sem quebrar nada

```bash
# Sempre comeca atualizando main
git checkout main
git pull

# Cria branch a partir de main
git checkout -b feature/nome-curto-em-ingles
# ou: fix/nome  |  refactor/nome  |  docs/nome

# Trabalha, comita pequeno
git add -p           # stage interativo, revisa o que ta indo
git commit -m "feat: descricao curta"

# Roda testes antes de cada commit
python -m pytest -q

# Push da branch
git push -u origin feature/nome-curto-em-ingles

# Abre PR pro main, marca Enzo pra review
# Espera approve antes de merge
```

**Regras:**
- 1 branch = 1 feature/fix. Nao mistura.
- PR pequeno = review rapido. Se passou de ~500 linhas mudadas, considera
  quebrar em 2.
- Descricao do PR: **Problema → Solucao → Como testei**.

---

## 7. Comandos do dia a dia

```bash
# Subir a central
python main.py --serve

# Rodar testes unitarios (rapido)
python -m pytest -q

# Rodar 1 teste especifico
python -m pytest tests/test_briefing_parser.py -v

# Smoke de integracao (Playwright real, ~30s)
python test_pipeline.py

# Ver logs de uma campanha especifica
cat campaigns/<campaign_id>/log.txt

# Inspecionar o DB
sqlite3 state.db
> SELECT campaign_id, status, etapa FROM campaigns ORDER BY created_at DESC LIMIT 10;
> .quit

# Limpar tudo pra testar do zero (CUIDADO — apaga estado)
rm -rf campaigns/ exports/ state.db
```

---

## 8. Onde ter cuidado extra (sem congelamento, mas com disciplina)

Nao ha mais janela de congelamento — o M&V ja e cliente pagante em
producao, entao qualquer regressao afeta uso real, nao uma demo:

| Area | Arquivos | Por que ter cuidado |
|---|---|---|
| Pipeline de geracao | `modules/pipeline.py`, `modules/copy_generator.py`, `modules/image_generator.py`, `modules/composer.py` | Regressao quebra geracao de campanha pro cliente pagante |
| Schema de DB | `modules/store.py` (SCHEMA_SQL) | Migracao mal feita corrompe `state.db` em producao (volume Fly.io) |
| Deploy | `fly.toml`, `Dockerfile` | Erro aqui derruba a app do M&V |

**Regra geral do projeto** (ver `CLAUDE.md` na raiz — leia antes de tudo):
mudancas cirurgicas, so o que foi pedido, plano antes de codar mudanca
nao-trivial, rodar `pytest` antes de commitar. E a cada feature nova pra
multi-marca, perguntar: "isso vale pra Mendes & Vaz E pro Gui?" — se so
vale pra um, e brand config, nao codigo.

---

## 9. Onde tem trabalho agora

| # | Trabalho | Status | Depende de |
|---|---|---|---|
| 1 | Conectar Instagram do M&V no Blotato + resolver URL publica da imagem (ver aviso em `modules/publisher.py`) | Bloqueado | Enzo criar a conta Blotato |
| 2 | Bot de WhatsApp (lembrete + sugestao de tema + gatilho de geracao) | Nao iniciado | Decisao Z-API (ja escolhido, falta configurar) |
| 3 | Brand novo pro Gui (`config/brands/gui_*.py`) | Nao iniciado | Gui fechar como cliente |
| 4 | `ruff` + `mypy` configurados | Nao iniciado | Bom 1o PR |
| 5 | Logger estruturado (substituir `print()` por `logging` nos schedulers) | Nao iniciado | Bom 1o PR |

**Sugestao de primeiro PR pra Marcos**: item 4 ou 5 — baixo risco, te
obriga a ler boa parte do código sem mexer em lógica de produto.

---

## 10. Referencias

### Docs internas (le antes de mexer no codigo)
- `CLAUDE.md` — principios + contexto estrategico
- `README.md` — visao geral + setup + API HTTP
- `docs/arquitetura.md` — fluxo + modelo de dados + atalhos
- `docs/fase-2-roadmap.md` — plano de evolucao pra SaaS
- `docs/roadmap-e-melhorias.md` — auditoria tecnica do MVP
- `docs/video-editing-research.md` — relatorio sobre video (descartado por
  enquanto, mas le se a discussao voltar)

### Stack — links uteis
- [Flask docs](https://flask.palletsprojects.com/)
- [Playwright Python](https://playwright.dev/python/)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [Ideogram API](https://developer.ideogram.ai/api-reference/)
- [SQLite WAL mode](https://www.sqlite.org/wal.html)

### Pessoas
- **Enzo Ferraz** — dono do produto, codigo, pricing. Whatsapp/Telegram.
- **Henrique Mendes** — operador no cliente Mendes & Vaz. Contato so via
  Enzo por enquanto.
- **Gui** — proximo cliente (DJ). Contato so via Enzo.

---

*Quando este doc mentir, atualize. Quando inflar, corte.*
