# Checklist de Demo — Mendes & Vaz Social

> Apresentação: **quinta-feira, 28/05/2026**.
> Setup recomendado: **demo local + tela compartilhada**, com ngrok pronto
> como plano B caso peçam pra clicar.

---

## 1. Antes da reunião (idealmente quarta à noite)

### Smoke ponta-a-ponta
```bash
cd ~/projetos/timelabs/content_agent
source venv/bin/activate
python -m pytest -q            # deve fechar 60 passed
python test_pipeline.py        # deve fechar com "✅ Smoke test OK"
```

Se algum dos dois quebrar, **não vá pra demo sem entender o porquê**.

### Estado limpo
A pasta já está zerada (state.db, campaigns/, exports/ vazios).
Backup dos dados antigos em `.backup_demo_2026-05-24/` — não apagar até depois
da reunião, caso precise mostrar histórico.

### Variáveis de ambiente
- `OPENAI_API_KEY` — **obrigatória**, copy não roda sem.
- `IDEOGRAM_API_KEY` — opcional; sem ela, arte sai como placeholder navy/gold.
  Para a demo, **defina** se quiser arte real (impressiona mais).
- `USE_MOCK_IMAGES=true` no `.env` força placeholder mesmo com chave.

### Browser do Playwright
Já deve estar instalado. Se trocar de máquina:
```bash
playwright install chromium
```

---

## 2. Subir a central

```bash
cd ~/projetos/timelabs/content_agent
source venv/bin/activate
python main.py --serve
```

Espera por:
- `✓ Credenciais OK (OpenAI conectada).`
- `✓ Chromium (Playwright) pronto.`
- `✓ Banco de estado em state.db pronto.`
- `✓ Central de controle Mendes & Vaz em http://localhost:5000/`

Abre o browser automaticamente. **Não fecha o terminal** — os logs de erro
agora aparecem ali (foi um dos fixes pré-demo: threads daemon não engolem
mais exceção).

---

## 3. Backup com ngrok (caso queiram clicar)

Em outro terminal:
```bash
ngrok http 5000
```

Vai mostrar algo como:
```
Forwarding   https://abc-123-xyz.ngrok-free.app -> http://localhost:5000
```

Manda a URL `https://...ngrok-free.app` no chat. Eles abrem e veem
exatamente o mesmo que você no laptop.

**Atenção:**
- O free tier mostra um warning na primeira visita ("Visit Site"). Avisa.
- Latência: cada clique passa pelo tunnel. Use só se eles **quiserem** clicar.
- O cleanup do ngrok é só fechar o terminal (Ctrl+C).

---

## 4. Roteiro sugerido da demo (15-20 min)

1. **Abrir o dashboard** vazio — explica que cada linha é uma campanha.
2. **Nova campanha** — preenche o briefing de 7 campos ao vivo
   (escolhe uma área concreta: "Direito de Família" ou "Direito Empresarial",
   tema "Reforma Tributária 2026").
3. **Acompanha geração** — copy → arte → composição, ~30s a 1min.
4. **Tela de aprovação** — mostra 3 variações lado a lado.
5. **Pede ajuste** numa opção ("mais técnico", "tom mais direto") — regera.
6. **Aprova** uma, agenda data, exporta.
7. **Mostra os arquivos exportados** — `exports/<id>/` tem PNG + JSON + post.txt
   pronto pra copiar/colar no Instagram.

---

## 5. Se algo der errado AO VIVO

| Sintoma | Causa provável | Ação rápida |
|---|---|---|
| UI fica "Gerando..." > 1 min | OpenAI lenta ou caiu | Olha o terminal — agora tem traceback. Se for timeout, refresh + nova tentativa. |
| Imagem não aparece | Ideogram caiu | Cai automático pra placeholder (não bloqueia). |
| Fonte do post errada | (não deveria — fontes embarcadas) | Confirma `assets/fonts/*.woff2` existe. |
| Chromium não abre | Playwright sem browser | `playwright install chromium`. |
| Porta 5000 ocupada | Outra app rodando | Mata processo ou altera `APPROVAL_PORT` em `config/settings.py`. |

---

## 6. Discurso pra fechar negócio

Se eles topam:
- **Próximas fases já mapeadas** (ver `docs/roadmap-e-melhorias.md`):
  publicação automática via Buffer, captação de leads (Airtable/WhatsApp),
  hospedagem online dedicada.
- **MVP foi entregue em ~2 semanas**, próxima fase é incremental, não rewrite.
- **Tudo o que rodar online** depende de servidor próprio (não GH Pages):
  Railway, Render ou VPS — custo ~$5-20/mês.

---

*Última atualização: 2026-05-24 — Enzo Ferraz*
