# Manual — deixar tudo pronto pra reunião (Mendes & Vaz, 28/05)

Checklist objetivo. Funciona **sem precisar do Claude rodando** — é só
PowerShell + comandos do projeto.

> Caminho do projeto:
> `C:\Users\Enzo Ferraz\OneDrive - Sintese Biotecnologia\Documentos\content_agent`

---

## 0. Estado atual (verificado em 2026-05-27)

- Repo local **sincronizado** com `origin/main` (último: `fd9635b`).
- `.env` já tem `OPENAI_API_KEY` e `IDEOGRAM_API_KEY`.
- ngrok instalado (WinGet) e authtoken já configurado.
- **Falta**: recriar `venv/` (não existe local hoje) e reinstalar deps.
- Há 5 arquivos modificados não-commitados no brand Gui Raw + approval UI.
  Não afetam M&V em produção, mas se quiser demo 100% limpa:
  ```powershell
  git stash push -m "wip-gui-pre-reuniao" -- approval_ui config/brands modules/server.py
  ```
  Depois da reunião: `git stash pop`.

---

## 1. Preparar o ambiente (~5 min, faz 1 vez)

```powershell
# Entrar na raiz do projeto (ASPAS são obrigatórias — o caminho tem espaços):
cd "C:\Users\Enzo Ferraz\OneDrive - Sintese Biotecnologia\Documentos\content_agent"

python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt   # use `python -m pip`, NÃO só `pip`
playwright install chromium
```

> **Por quê `python -m pip` e não `pip` direto?** Em algumas máquinas
> Windows o `pip` solto resolve pro pip global (Program Files) em vez do
> pip do venv — você verá "Defaulting to user installation because normal
> site-packages is not writeable" e as libs ficam fora do venv. `python -m
> pip` garante que é o pip do venv ativo. Pra confirmar depois:
> `python -m pip show python-dotenv | Select-String Location` — tem que
> apontar pra `...\venv\Lib\site-packages`.

Se `Activate.ps1` falhar por política de execução:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**Smoke test rápido** (confirma que está tudo de pé):
```powershell
python -m pytest -q
```
Esperado: 60 testes passando, sem rede.

---

## 2. Subir a central (terminal #1)

```powershell
.\venv\Scripts\Activate.ps1
python main.py --serve
```

Quando ver `* Running on http://localhost:5000`, abre o navegador em
http://localhost:5000 e confirma que a UI carrega.

> O healthcheck do startup (`_check_credenciais`, `_check_chromium`) já
> reclama se faltar algo — se subiu sem erro, está OK.

---

## 3. Expor pra fora com ngrok (terminal #2, opcional na demo)

Só precisa disto se quiser que **alguém de fora da sua máquina** abra a UI
durante a reunião (ex.: Henrique acessando do escritório dele).

```powershell
ngrok http 5000
```

ngrok mostra uma linha tipo:
```
Forwarding   https://abc123.ngrok-free.app -> http://localhost:5000
```
Esse `https://...ngrok-free.app` é o link pra compartilhar.

**Atalho útil**: painel de inspeção em http://127.0.0.1:4040 (vê
requests passando ao vivo — bom pra debugar se a UI travar).

> Se ngrok pedir authtoken: já está salvo em
> `%LOCALAPPDATA%\ngrok\ngrok.yml`. Caso suma, rodar de novo:
> `ngrok config add-authtoken <seu-token>`.

---

## 4. Gerar 1 campanha-teste antes da reunião (recomendado)

Pelo navegador (http://localhost:5000):
1. Selecionar brand **Mendes & Vaz**.
2. Preencher os 7 campos do briefing com algo realista.
3. Gerar → esperar as 3 variações aparecerem.
4. Aprovar 1 → ver o PNG final em `exports/<campaign_id>/`.

Se algo falhar, conferir os logs no terminal #1. Erros comuns:

| Sintoma | Causa provável | Fix |
|---|---|---|
| "OPENAI_API_KEY missing" | `.env` não foi lido | confirma `.env` na raiz, reinicia |
| Timeout no Playwright | rede lenta | é tolerado pelo composer (`composer.py:107`), screenshot sai mesmo assim |
| Campanha trava em "gerando" | processo morto no meio | reiniciar — `_recover_orphan_campaigns` (`main.py:67`) limpa no startup |
| Imagem sai placeholder navy/gold | `IDEOGRAM_API_KEY` faltou ou `USE_MOCK_IMAGES=true` | conferir `.env` |

---

## 5. Roteiro da reunião (sugestão, 15 min)

1. **Abrir UI** (já com 1 campanha-teste pronta de backup, pra caso a
   geração ao vivo dê ruim).
2. Mostrar o **fluxo de briefing**: 7 campos, validação.
3. Gerar uma campanha **ao vivo** com tema do dia (~2 min de espera, OK
   pra mostrar copy + arte sendo geradas).
4. Mostrar as **3 variações** lado a lado, aprovar 1.
5. Abrir o PNG final no Explorer pra mostrar a saída pronta pra Instagram.
6. Fechar com proxima etapa: integração de publicação, multi-marca, etc.

---

## 6. Se der pau na hora (plano B)

- **Internet caiu** → tem campanha-teste pré-gerada em `exports/`,
  mostrar direto.
- **OpenAI fora do ar** → mesma coisa, usar campanha pré-gerada.
- **Playwright/Chromium quebrou** → `playwright install chromium --force`
  e reinicia.
- **Porta 5000 ocupada** → editar `config/settings.py:131`
  (`APPROVAL_PORT = 5001`) e reiniciar.

---

## 7. Pós-reunião

```powershell
# Se stashou no passo 0:
git stash pop

# Encerrar processos:
# - terminal #1: Ctrl+C no python main.py
# - terminal #2: Ctrl+C no ngrok
```
