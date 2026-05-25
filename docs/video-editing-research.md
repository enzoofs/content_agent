# Automacao de Edicao de Video para Criadores — Pesquisa Estrategica TimeLabs

**Data:** 2026-05-25
**Contexto:** TimeLabs ja entrega geracao automatizada de posts estaticos (Instagram/LinkedIn) via OpenAI + Ideogram. Cliente potencial (DJ) sinalizou que o pedido mais comum hoje e edicao de video. Este documento avalia se devemos **construir, integrar ou revender** automacao de video.
**Tom:** direto, acionavel. Time pequeno (1 dev), janela de 4 semanas pra fechar cliente.

---

## 1. O que e tecnicamente possivel HOJE (2026)

A boa noticia: praticamente tudo que ferramentas como Submagic/Opus Clip fazem hoje e implementavel com stack aberta. A ma noticia: a **qualidade percebida** depende de 80% de polimento (fontes, animacao de palavra, timing) que e onde os SaaS prontos brilham.

| Capacidade | Estado da arte open-source | Dificuldade | Comentario |
|---|---|---|---|
| **Corte por fala/silencio** | Whisper (faster-whisper) + ffmpeg silenceremove | Baixa | Maduro. FFmpeg 8.0 ja embute filtro Whisper nativo. |
| **Auto-reframe 16:9 → 9:16** | YOLOv8 + MediaPipe tracking + ffmpeg crop dinamico | Media | Existem projetos como Autocrop-vertical e OpenShorts que funcionam. Quebra em cenas multi-pessoa. |
| **Legendas estilo Submagic** | Whisper word-level + render via ffmpeg/Remotion | Media-alta | Transcrever e facil. Animar palavra-por-palavra com estilo viral (highlight, emoji, bounce) e o trabalho real. |
| **Highlights/best moments** | LLM (GPT) lendo transcript + scoring por engagement signals | Media | Heuristica funciona razoavel. Qualidade Opus Clip vem de modelo proprietario treinado em retencao. |
| **B-roll automatico** | LLM extrai keywords → busca Pexels/Storyblocks API → ffmpeg insert | Media | Resultado generico. Boas implementacoes usam stock pago + matching semantico. |
| **Beat sync (DJ)** | librosa.beat.beat_track ou BeatNet (CRNN) | Baixa-media | Tecnicamente trivial extrair beats. Sincronizar **cortes/transicoes** nos beats e simples; sincronizar **visual reativo** (bouncing, FX) requer template engine. |
| **Transicoes** | ffmpeg xfade + presets | Baixa | Comoditizado. |
| **Color grading** | LUTs via ffmpeg `lut3d` filter | Baixa | Aplicar LUT e trivial. Escolher LUT automaticamente por cena requer modelo de classificacao. |
| **Normalizacao de audio** | ffmpeg loudnorm (EBU R128) | Baixa | Resolvido. Uma linha de comando. |

**Conclusao tecnica:** nenhum item e ciencia foguete isolado. O diferencial dos SaaS lideres esta em (1) UX polida, (2) templates virais atualizados toda semana, (3) modelos proprietarios de highlight scoring e (4) infra pronta pra escalar GPU.

---

## 2. Ferramentas existentes — comparativo (precos 2026)

| Ferramenta | Foco principal | Preco entrada | Plano com API | Custo API | API publica? |
|---|---|---|---|---|---|
| **Opus Clip** | Long-form → shorts virais | $15/mes (150 min) | Business (custom) | Sob consulta | Sim, mas trancado em plano enterprise |
| **Submagic** | Legendas virais + B-roll | $12/mes (15 videos) | Business $41/mes | Incluso + credit metering | Sim, no plano Business |
| **Vizard.ai** | Clipping + reframe | $19.99/mes (50 videos) | Creator+ ($19.99) | Consome minutos do plano | Sim, em todos os planos pagos — **melhor custo-beneficio pra revender** |
| **Klap** | Long → shorts | $29/mes (100 clips) | Business tier | Pay-per-operation | Sim, usage-based |
| **Captions.ai** | AI actors, legendas, dub | $12.99/mes | Business $79.99/mes | $0.25-0.35/min overage | Sim, em Business |
| **Descript** | Edicao baseada em transcript | $16/mes (Hobbyist) | Open beta 2026 | Nao publicado | Sim, beta publico |
| **Veed** | Editor browser all-in-one | $18/mes | Nao tem API publica robusta | N/A | Nao (limitado) |
| **Shotstack** | API pura de renderizacao | $0.40/min PAYG, $49/mes 200cred | Sim (core do produto) | $0.20-0.40/min | Sim, primary product |
| **Creatomate** | API de templates de video | $41/mes 144min ($0.28/min) | Sim (core) | $0.06-0.28/min escalonado | Sim, primary product |

### Avaliacao qualitativa

- **Opus Clip:** melhor em highlight detection. Caro pra API. Marca forte com criadores.
- **Submagic:** **estado da arte em legendas viralizaveis.** API existe mas com credit metering opaco.
- **Vizard:** API mais developer-friendly do grupo "clipping". Boa entrada pra white-label.
- **Klap:** competitivo com Opus, API usage-based e mais previsivel.
- **Captions.ai:** unico com AI actors (dub + lipsync). Diferencial pra outro segmento (anuncios UGC).
- **Descript:** otimo pra workflow editorial humano-assistido, nao pra automacao 100%.
- **Shotstack/Creatomate:** **nao sao concorrentes — sao infraestrutura.** Renderizam JSON → video. Usariamos como backend se montassemos templates proprios.

---

## 3. Tres caminhos estrategicos

### Caminho A — Construir do zero (FFmpeg + Whisper + open source)

**Stack realista:**
- `faster-whisper` (transcript word-level)
- `ffmpeg` 8.0 (corte, crop, loudnorm, LUT, xfade)
- `YOLOv8` ou `MediaPipe` (tracking pra reframe)
- `librosa` ou `BeatNet` (beat detection pra DJ)
- `Remotion` ou render programatico (legendas animadas)
- `GPT-4o` (highlight scoring via transcript)

**O que precisa:**
- 1 dev focado **8-12 semanas** ate ter MVP minimamente competitivo
- GPU: necessaria pra Whisper large + YOLOv8 em volume. Pode comecar serverless (Replicate, Modal, RunPod) e migrar pra GPU dedicada quando volume justificar
- Storage: R2/S3 obrigatorio (videos sao pesados)
- Fila de processamento (Celery/Redis ou SQS)

**Custo unitario estimado (por video de 5 min input):**
- Whisper large na Replicate: ~$0.05
- Reframe c/ YOLOv8 (GPU 1 min): ~$0.10
- Render final ffmpeg (CPU 2-3 min): ~$0.02
- LLM scoring: ~$0.01
- Storage egress: ~$0.02
- **Total: ~$0.20/video.** Margem boa se cobrar $30-50/mes por cliente.

**Qualidade alcancavel:**
- **HOJE (MVP em 8 semanas):** 60-70% da qualidade Opus Clip. Legendas funcionais mas sem o "punch" viral. Reframe quebra em cenas complexas.
- **6 meses:** 85-90% se time crescer pra 2 devs + designer pra templates.

**Risco:** voce vai gastar 80% do tempo nos ultimos 20% de polimento (animacao de legenda, edge cases de reframe). Esse e o vale da morte de produtos de video AI.

---

### Caminho B — Integrar API de terceiro

**Melhor candidato:** **Vizard.ai API** (API em qualquer plano pago, sem trava enterprise) ou **Submagic API** ($41/mes Business) pra legendas especificamente.

**Setup:**
- Cliente faz upload no TimeLabs → backend envia pra API do Vizard/Submagic → recebe URL do resultado → entrega no painel TimeLabs com brand kit do cliente
- Esconde a marca do fornecedor (white-label parcial)

**Tempo de dev:** 1-2 semanas pra integracao + UX.

**Custo:**
- Vizard Pro $49.99/mes = videos ilimitados pra um seat. Pra revender via API, precisa Enterprise (custom).
- Submagic Business $41/mes = 100 videos/membro
- Margem: se cobrar $99/mes por cliente entregando 30 videos, margem de ~$50-60 com Vizard

**Riscos:**
- **Dependencia total:** se Vizard sobe preco ou muda termos, voce esta refem
- **TOS de revenda:** maioria dessas ferramentas proibe revenda direta. Precisa ler letra miuda. Vizard e Submagic toleram uso via API pra plataformas proprias se voce e o cliente final faturado
- **Margem comprimida** a medida que volume cresce

**Qualidade alcancavel:** 100% da qualidade Vizard/Submagic desde o dia 1.

---

### Caminho C — Orquestrar workflow humano + ferramentas (servico, nao produto)

**Modelo:** TimeLabs vende **"agente de conteudo gerenciado"** pra o DJ. Internamente, voce usa Submagic + Capcut + um editor freelancer (R$ 30-50/h) e entrega 8-12 videos/mes por cliente.

**Stack:**
- Plataforma TimeLabs como **hub de aprovacao** (que ja existe!) — cliente sobe video bruto, ve previews, aprova, recebe
- Backend: trello/notion + freelancer + Submagic licenca tua

**Tempo de dev:** ~1 semana pra adaptar fluxo de aprovacao atual.

**Custo:**
- Licenca Submagic Pro: $23/mes
- Freelancer: ~R$ 800-1500/mes por cliente
- Vende por R$ 2500-4000/mes ⇒ **margem 40-60%**

**Riscos:**
- Nao escala linearmente (precisa contratar mais editores)
- Voce e uma agencia, nao SaaS
- Mas: **valida demanda e gera receita JA**

**Qualidade alcancavel:** maxima desde dia 1 (humano no loop). Diferencial: timing humano pra cortes musicais ainda supera AI em 2026.

---

## 4. Recomendacao final

**Faca C + B em paralelo. Pule A por enquanto.**

### Por que

1. **Janela de 4 semanas e curta demais pra construir.** Caminho A nao entrega nada vendavel nesse prazo.
2. **Voce ja tem o ativo mais dificil:** painel de aprovacao + relacionamento com cliente + pipeline de posts estaticos. Adicionar video como "servico gerenciado" e incremental, nao arquitetural.
3. **Validacao antes de construir.** Caminho C revela se o DJ pagaria R$ 3000/mes por video. Se sim, voce tem dados pra justificar Caminho A daqui 3-6 meses. Se nao, voce nao desperdicou 12 semanas de dev.
4. **Caminho B (Vizard API) e o upgrade natural:** quando 3-5 clientes assinarem o servico C, voce automatiza 60-70% do trabalho do freelancer integrando Vizard. Margem sobe sem nova venda.

### Sequencia recomendada

**Semanas 1-2:** vender pacote "TimeLabs Video" pro DJ. R$ 2500-3500/mes por 10 videos editados (legendas + cortes + 1 reframe vertical). Stack: Submagic Pro ($23) + freelancer.

**Semanas 3-4:** integrar Vizard API no painel de aprovacao (upload → processamento → preview). Comeca a deslocar trabalho do freelancer pra automacao em features simples (legendas, reframe). Freelancer cuida so de beat sync e curadoria.

**Mes 2-3:** se demanda confirmar, comecar Caminho A so pra **beat sync de DJ** (nicho onde nenhuma ferramenta de mercado e boa). librosa + ffmpeg + template Remotion = MVP em 3-4 semanas. Isso vira voce **single-source-of-truth** pra audio-reactive video — diferencial real vs Opus/Submagic.

---

## 5. Teto de qualidade realista

| Caminho | Hoje (4 semanas) | 6 meses |
|---|---|---|
| **A — Construir** | Inviavel no prazo. MVP feio. | 85% Opus Clip, 70% Submagic em legendas. Beat sync superior se for foco. |
| **B — Integrar Vizard/Submagic** | 100% da qualidade Vizard/Submagic. | Mesma qualidade, melhor UX (brand kit, aprovacao integrada). |
| **C — Servico gerenciado** | 100% (humano polindo). Igual agencia top. | Pode escalar pra 20-30 clientes com 2-3 editores. |

**Exemplos publicos de qualidade alcancavel:**
- Caminho B (Submagic): canais @hubermanclips, @lexfridmanclips — legendas geradas por Submagic ou similar
- Caminho A com beat sync: clips de DJs como @fisherofficial, @johnsummit no Instagram — esses sao editados manualmente hoje, oportunidade clara de automacao
- Caminho C: qualquer agencia de social media boa entrega isso

---

## 6. Requisitos de infra

### Para Caminho B (integracao Vizard)

- **Storage:** Cloudflare R2 ou S3. ~$0.015/GB/mes + egress gratis (R2) ou $0.09/GB (S3). Estimativa: 50GB/cliente/mes ⇒ R2 $0.75/cliente/mes.
- **Processamento:** zero. Vizard processa.
- **Tempo medio:** Vizard processa 10 min de video em ~3-5 min wall-clock.
- **Custo por video editado:** plano Vizard Pro ilimitado $49.99/mes — se entregar 100 videos/mes ⇒ $0.50/video.

### Para Caminho A (construir)

- **Storage:** R2 obrigatorio (egress = morte com S3). ~$0.015/GB.
- **GPU:** comecar serverless. **Replicate** Whisper-large ~$0.0005/seg de audio. **Modal/RunPod** pra YOLOv8 ~$0.40-0.60/hora GPU L4.
- **Render:** ffmpeg em CPU funciona. Render server-side: Hetzner CPX41 ~$30/mes processa ~200 videos/mes.
- **Fila:** Celery + Redis ou Cloudflare Queues.
- **Tempo medio:** 5 min de video input ⇒ 3-7 min de processamento total (Whisper 30s + reframe 2min + render 2-4min).
- **Custo por video editado:** ~$0.20 (detalhado na secao 3A).

### Para Caminho C (servico)

- **Infra atual TimeLabs ja basta.** Adicionar campo de upload de video bruto + estado "aguardando edicao" no fluxo de aprovacao.
- **Custo variavel = editor freelancer.**

---

## TL;DR pra Enzo

1. **Nao construa do zero agora.** Voce nao tem 12 semanas nem GPU budget.
2. **Venda servico gerenciado pro DJ JA** (Caminho C) — Submagic + freelancer + seu painel. Cobra R$ 2500-3500/mes. Fecha em 4 semanas.
3. **Em paralelo, integra Vizard API** (Caminho B) no painel. Reduz custo variavel ao longo de 1-2 meses.
4. **Beat sync pra DJ e o unico lugar onde vale construir do zero** — nicho, voce e o cliente sabem do que esta falando, ferramentas de mercado nao priorizam isso. Comece SO depois de validar receita.
5. **Stack se construir:** faster-whisper + ffmpeg 8 + librosa + Remotion + Replicate/Modal pra GPU on-demand. R2 pra storage.

Decisao critica: pergunte ao DJ **quanto ele pagaria por 10 videos prontos por mes**. Se for R$ 2k+, Caminho C tem PMF. Se for R$ 500, voce precisa de SaaS escalavel (Caminho B ou A) — e a margem fica apertada.

---

## Fontes

- [Opus Clip Pricing](https://www.opus.pro/pricing) e [OpusClip API](https://www.opus.pro/api)
- [Submagic Pricing](https://www.submagic.co/pricing) e [Submagic API](https://www.submagic.co/api)
- [Vizard Pricing](https://vizard.ai/pricing) e [Vizard API Docs](https://docs.vizard.ai/docs/pricing)
- [Klap Pricing](https://klap.app/pricing) e [Klap API](https://docs.klap.app/pricing)
- [Captions.ai API Pricing](https://captions.ai/help/docs/api/pricing)
- [Descript Pricing](https://www.descript.com/pricing)
- [Shotstack Pricing](https://shotstack.io/pricing/)
- [Creatomate Pricing](https://creatomate.com/blog/the-best-video-generation-apis)
- [FFmpeg 8.0 com filtro Whisper](https://www.phoronix.com/news/FFmpeg-8.0-Released)
- [Autocrop-vertical (YOLOv8 + FFmpeg)](https://github.com/kamilstanuch/Autocrop-vertical)
- [OpenShorts (open source AI video platform)](https://github.com/mutonby/openshorts)
- [BeatNet — beat tracking state-of-the-art](https://github.com/mjhydri/BeatNet)
- [librosa beat tracking](https://librosa.org/doc/main/generated/librosa.beat.beat_track.html)
