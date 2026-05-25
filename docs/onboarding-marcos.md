# Onboarding — content_agent (TimeLabs)

> Documento de entrada pro Marcos. Le isto antes de qualquer outra coisa.
> Tempo estimado de leitura: 25 min. Tempo ate primeiro commit: ~1 hora.
>
> Autor: Enzo Ferraz · Atualizado em 2026-05-25

---

## 1. Contexto em 2 minutos

**O que o sistema faz:**
Recebe um briefing curto (7 campos sobre o tema do post), chama OpenAI pra
escrever 3 variacoes de copy, chama Ideogram pra gerar 3 artes de fundo,
compoe tudo num PNG final (HTML/CSS renderizado pelo Chromium), e entrega
no painel pra o cliente aprovar. So depois de aprovado e que vira post pronto
pra ir no Instagram/LinkedIn.

**Quem usa hoje:**
Henrique Mendes, do escritorio **Mendes & Vaz** (Belo Horizonte). MVP rodando
local na maquina dele. Demo agendada pra **quinta-feira 28/05/2026**.

**Quem vai usar em breve:**
- **Gui** (DJ + criador de conteudo) — primeiro cliente multi-marca.
- Possivel **agencia de marketing** via rede do Gui — santo graal B2B2C.

**Por que importa pra TimeLabs:**
E o primeiro produto de **conteudo automatizado** da empresa. Se virar SaaS
com 5-10 escritorios/criadores pagantes a R$ 300-500/mes, vira fluxo de
receita recorrente independente das automacoes N8N sob demanda.

---

## 2. Status agora (semana de 25/05/2026)

| Item | Status |
|---|---|
| MVP funcional pra Mendes & Vaz | Pronto |
| Testes automatizados (unit + smoke) | 60 testes passando |
| Demo agendada | Quinta 28/05 |
| Brand config dinamico (multi-cliente) | Planejado pra apos a demo |
| Edicao de video automatizada | Descartado por enquanto (ver `video-editing-research.md`) |
| Deploy em producao | Ainda nao — roda local |

**ATENCAO — congelamento ate quinta-feira:**
Ate a demo do Henrique acontecer (28/05 a noite), o codigo no `main` deve
ficar **estavel e validado**. Nenhuma mudanca em arquivos que afetem
geracao de PNG. Detalhes na secao 8.

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

# Dependencias Python
pip install -r requirements.txt

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

## 8. O que NAO mexer agora (ate apos 28/05)

Demo do Henrique e quinta. Ate la, codigo do `main` esta **congelado** pra
qualquer mudanca em:

| Area | Arquivos | Por que nao mexer |
|---|---|---|
| Pipeline de geracao | `modules/pipeline.py`, `modules/copy_generator.py`, `modules/image_generator.py`, `modules/composer.py` | Qualquer regressao quebra a demo |
| Configuracao visual | `config/settings.py` (COLORS, FONTS, LOGO_PATH, TEMPLATES) | Visual ja validado |
| Templates HTML | `templates/*.html` | Idem |
| Schema de DB | `modules/store.py` (SCHEMA_SQL) | Migration durante demo = desastre |

**O que da pra mexer sem risco:**
- Documentacao (`docs/`, `README.md`, este arquivo)
- Testes novos (sem alterar codigo de producao)
- Scripts em `scripts/`
- Branch propria de exploracao (so nao mergeia)

Apos quinta a noite, congelamento sai e a gente entra na fase 2 (brand
config dinamico, multi-marca pro Gui — ver `docs/fase-2-roadmap.md`).

---

## 9. Roadmap proximas semanas — onde tem trabalho

Pos-demo (a partir de 29/05), na ordem:

| # | Trabalho | Esforco | Quem (provavelmente) |
|---|---|---|---|
| 1 | **Brand config dinamico** (extrair `settings.COLORS/FONTS/LOGO` pra arquivo por cliente) | 2-3 dias | A definir |
| 2 | **Briefing/templates adaptados pra contexto do Gui (DJ)** | 2-3 dias | A definir |
| 3 | **Doc de prompts em `config/prompts.py`** (mover string longa do `copy_generator.py`) | 4h | Bom 1o PR |
| 4 | **Logger estruturado** (substituir `print()` por `logging`) | 4h | Bom 1o PR |
| 5 | **`ruff` + `mypy` configurados** | 2h | Bom 1o PR |
| 6 | **Deploy em VPS/Railway** | 1-2 dias | Enzo provavelmente |

**Sugestoes de primeiro PR pra Marcos** (baixo risco, alto aprendizado):
- Item 3 ou 4 ou 5 da tabela acima. Sao itens da "pre-cirurgia" da fase 2
  (ver `docs/fase-2-roadmap.md` secao "Pre-cirurgia").
- Le o codigo correspondente, abre branch, faz, testa, abre PR.

---

## 10. Referencias

### Docs internas (le antes de mexer no codigo)
- `CLAUDE.md` — principios + contexto estrategico
- `README.md` — visao geral + setup + API HTTP
- `docs/arquitetura.md` — fluxo + modelo de dados + atalhos
- `docs/fase-2-roadmap.md` — plano de evolucao pra SaaS
- `docs/roadmap-e-melhorias.md` — auditoria tecnica do MVP
- `docs/demo-checklist.md` — roteiro da demo de quinta
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
