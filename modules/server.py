"""
modules/server.py — Central de controle (Flask local persistente).

Serve o SPA da central e a API JSON. Diferente da versão antiga (one-shot por
campanha), este servidor é persistente: gerencia todas as campanhas, dispara a
geração em background (thread) e trata aprovação/agendamento/ajuste.

API:
    GET  /api/campaigns               -> lista de campanhas (dashboard)
    POST /api/campaigns               -> cria + dispara geração -> {campaign_id}
    GET  /api/campaigns/<id>          -> briefing + copy + estado (polling)
    POST /api/campaigns/<id>/approve  -> {option_id, data_agendada} -> exporta
    POST /api/campaigns/<id>/adjust   -> {option_id, nota} -> regera

Estáticos:
    GET  /                  -> approval_ui/index.html
    GET  /<asset>           -> arquivos da UI
    GET  /logo.png          -> logo do header
    GET  /composed/<id>/<f> -> imagens compostas para preview
"""

from __future__ import annotations

import json
import threading
import traceback
import webbrowser

from flask import Flask, abort, jsonify, request, send_from_directory
from waitress import serve as waitress_serve

from config import settings
from modules import (
    briefing_parser,
    campaign_store,
    composer,
    copy_generator,
    exporter,
    pipeline,
    quotas,
    store,
    utils,
)


# --------------------------------------------------------------------------
# Disparo assíncrono da geração (funções isoladas para facilitar teste/mocks)
# --------------------------------------------------------------------------
def _iniciar_geracao_async(briefing: dict) -> None:
    """
    Dispara pipeline.gerar numa thread daemon.

    Por que NÃO engolimos exceção: o pipeline já grava status=erro no DB, mas
    sem traceback no log fica impossível depurar erros que acontecem dentro
    da thread (ex.: Playwright travou, OpenAI subiu exceção nova).
    Print + log na campanha = a UI mostra o status_erro_msg E o operador
    consegue ver o traceback no terminal.
    """
    cid = briefing["campaign_id"]
    def run():
        try:
            pipeline.gerar(briefing)
        except Exception as e:
            tb = traceback.format_exc()
            utils.log(cid, f"server: ERRO na thread de geração — {e}\n{tb}")
            print(f"[ERRO geração {cid}] {e}\n{tb}", flush=True)
    threading.Thread(target=run, daemon=True).start()


def _iniciar_regeracao_async(campaign_id: str, nota: str) -> None:
    """Dispara pipeline.regerar numa thread daemon (mesma política de erro de _iniciar_geracao_async)."""
    def run():
        try:
            pipeline.regerar(campaign_id, nota)
        except Exception as e:
            tb = traceback.format_exc()
            utils.log(campaign_id, f"server: ERRO na thread de regeração — {e}\n{tb}")
            print(f"[ERRO regeração {campaign_id}] {e}\n{tb}", flush=True)
    threading.Thread(target=run, daemon=True).start()


# --------------------------------------------------------------------------
# Montagem do payload de uma campanha para a UI
# --------------------------------------------------------------------------
def _campaign_payload(campaign_id: str) -> dict:
    """Junta estado + briefing + variações de copy (com URLs das imagens compostas).

    Para carrossel, cada opção inclui `slides: [{slide_id, headline, body,
    image_url}]` em vez de um único `composed_image_url`. Caption/cta/hashtags
    ficam no nível da opção (mesmo padrão do Instagram).
    """
    estado = campaign_store.read_state(campaign_id)
    if estado is None:
        abort(404, description=f"Campanha {campaign_id} não encontrada.")

    briefing = campaign_store.read_briefing(campaign_id) or {}

    is_carousel = briefing.get("formato") == "carousel"
    composed_dir = settings.CAMPAIGNS_DIR / campaign_id / "composed"

    def _cache_busted_url(filename: str) -> str:
        """URL do PNG composto + ?v=<mtime> para o browser recarregar quando o arquivo muda."""
        png = composed_dir / filename
        mtime = int(png.stat().st_mtime) if png.exists() else 0
        return f"/composed/{campaign_id}/{filename}?v={mtime}"

    options = []
    # Lê o copy da versão corrente — regerar incrementa esse contador (histórico)
    copy_raw = campaign_store.get_copy(campaign_id)
    if copy_raw:
        for c in copy_raw:
            if is_carousel:
                options.append({
                    "option_id": c["option_id"],
                    "caption": c["caption"],
                    "cta": c["cta"],
                    "hashtags": c["hashtags"],
                    "slides": [
                        {
                            "slide_id": s["slide_id"],
                            "headline": s["headline"],
                            "subheadline": s.get("subheadline", ""),
                            "body": s["body"],
                            "image_url": _cache_busted_url(
                                f"option_{c['option_id']}_slide_{s['slide_id']}.png"
                            ),
                        }
                        for s in c["slides"]
                    ],
                })
            else:
                options.append({
                    "option_id": c["option_id"],
                    "headline": c["headline"],
                    "subheadline": c.get("subheadline", ""),
                    "body": c["body"],
                    "caption": c["caption"],
                    "cta": c["cta"],
                    "hashtags": c["hashtags"],
                    "composed_image_url": _cache_busted_url(f"option_{c['option_id']}.png"),
                })

    payload = {
        "campaign_id": campaign_id,
        "briefing": briefing,
        "options": options,
        "state": estado,
    }

    # Aprovada: anexa os caminhos dos arquivos exportados (UI mostra pra Henrique)
    if estado.get("status") == "aprovada" and estado.get("option_aprovada"):
        oid = int(estado["option_aprovada"])
        payload["exports"] = _compute_export_paths(campaign_id, oid, briefing.get("formato"), copy_raw)

    return payload


def _compute_export_paths(campaign_id: str, option_id: int, formato: str | None, copy_raw) -> dict:
    """
    Devolve os caminhos absolutos dos arquivos em exports/ para a opção aprovada.

    O naming é determinístico (definido em exporter), então não precisamos
    persistir os caminhos no DB — basta reconstruí-los aqui sob demanda.
    """
    base = settings.EXPORTS_DIR / campaign_id
    prefix = f"option{option_id}"
    paths = {
        "metadata": str(base / f"{prefix}_metadata.json"),
        "post_txt": str(base / f"{prefix}_post.txt"),
    }
    if formato == "carousel" and copy_raw:
        opcao = next((o for o in copy_raw if o["option_id"] == option_id), None)
        slides = opcao.get("slides", []) if opcao else []
        pngs = [str(base / f"{prefix}_slide{s['slide_id']}.png") for s in slides]
        paths["png"] = pngs[0] if pngs else ""
        paths["all_pngs"] = pngs
    else:
        png = str(base / f"{prefix}.png")
        paths["png"] = png
        paths["all_pngs"] = [png]
    return paths


# --------------------------------------------------------------------------
# Edição manual de copy (sem regenerar via LLM)
# --------------------------------------------------------------------------
# Campos editáveis no NÍVEL DA OPÇÃO (mesmo conjunto pra simples e carrossel,
# exceto que simples também aceita headline/subheadline/body que no carrossel
# vivem dentro de slides).
_OPTION_FIELDS_COMUNS = {"caption", "cta", "hashtags"}
_OPTION_FIELDS_SIMPLES = _OPTION_FIELDS_COMUNS | {"headline", "subheadline", "body"}
_SLIDE_FIELDS = {"headline", "subheadline", "body"}


def _aplicar_edicao(opcao: dict, fields: dict, formato: str) -> dict:
    """
    Aplica campos editáveis numa opção de copy, em cima de uma cópia (imutável).

    Raises:
        ValueError: se um campo desconhecido for enviado ou tipos inválidos.
    """
    nova = dict(opcao)  # cópia rasa — imutabilidade

    permitidos = _OPTION_FIELDS_COMUNS if formato == "carousel" else _OPTION_FIELDS_SIMPLES
    desconhecidos = set(fields) - permitidos - {"slides"}
    if desconhecidos:
        raise ValueError(
            f"Campos não editáveis: {sorted(desconhecidos)}. "
            f"Permitidos: {sorted(permitidos | ({'slides'} if formato == 'carousel' else set()))}."
        )

    for k in permitidos:
        if k in fields:
            if k == "hashtags":
                if not isinstance(fields[k], list):
                    raise ValueError("hashtags deve ser uma lista.")
                nova[k] = copy_generator.normalize_hashtags(fields[k])
            else:
                nova[k] = str(fields[k])

    if formato == "carousel" and "slides" in fields:
        slides_edit = fields["slides"]
        if not isinstance(slides_edit, list):
            raise ValueError("slides deve ser uma lista.")
        slides_novos = [dict(s) for s in nova.get("slides", [])]
        for slide_edit in slides_edit:
            sid = slide_edit.get("slide_id")
            idx = next((i for i, s in enumerate(slides_novos) if s["slide_id"] == sid), None)
            if idx is None:
                raise ValueError(f"slide_id {sid} não existe nesta opção.")
            for k in _SLIDE_FIELDS:
                if k in slide_edit:
                    slides_novos[idx][k] = str(slide_edit[k])
        nova["slides"] = slides_novos

    return nova


# --------------------------------------------------------------------------
# App factory
# --------------------------------------------------------------------------
def build_app() -> Flask:
    """Cria a app Flask da central (persistente, multi-campanha)."""
    app = Flask(__name__, static_folder=None)

    # ---- Estáticos / UI ----
    @app.route("/")
    def index():
        """
        Serve o index.html injetando ?v=<mtime> nos refs de app.js e style.css.

        Sem isso, o browser cacheia versões antigas dos assets — bug clássico
        quando a gente atualiza JS/CSS e o usuário continua vendo o comportamento
        velho (ex.: botão "Salvando…" travado após edição).
        """
        html = (settings.APPROVAL_UI_DIR / "index.html").read_text(encoding="utf-8")
        js_mtime = int((settings.APPROVAL_UI_DIR / "app.js").stat().st_mtime)
        css_mtime = int((settings.APPROVAL_UI_DIR / "style.css").stat().st_mtime)
        html = html.replace('src="app.js"', f'src="app.js?v={js_mtime}"')
        html = html.replace('href="style.css"', f'href="style.css?v={css_mtime}"')
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/logo.png")
    def logo():
        return send_from_directory(settings.LOGO_PATH.parent, settings.LOGO_PATH.name)

    @app.route("/composed/<cid>/<path:filename>")
    def composed(cid: str, filename: str):
        return send_from_directory(settings.CAMPAIGNS_DIR / cid / "composed", filename)

    # ---- API ----
    @app.route("/api/campaigns", methods=["GET"])
    def api_listar():
        return jsonify(campaign_store.listar())

    @app.route("/api/campaigns", methods=["POST"])
    def api_criar():
        body = request.get_json(force=True)
        # 1) Quota antes de qualquer parse — falha cedo, sem custo
        try:
            quotas.verificar_pode_criar()
        except quotas.QuotaExcedidaError as e:
            return jsonify({
                "erro": e.mensagem,
                "tipo": "quota_excedida",
                "quota": e.chave,
                "atual": e.atual,
                "limite": e.limite,
            }), 429
        # 2) Validação do briefing
        try:
            briefing = briefing_parser.parse(body)
        except ValueError as e:
            return jsonify({"erro": str(e)}), 400

        campaign_store.criar(briefing)
        utils.log(briefing["campaign_id"], "server: campanha criada, iniciando geração.")
        _iniciar_geracao_async(briefing)
        return jsonify({"campaign_id": briefing["campaign_id"], "status": "gerando"}), 201

    @app.route("/api/quotas", methods=["GET"])
    def api_quotas():
        """Snapshot atual das quotas — UI mostra banner amarelo/vermelho conforme."""
        return jsonify(quotas.snapshot())

    @app.route("/api/campaigns/<cid>", methods=["GET"])
    def api_campanha(cid: str):
        return jsonify(_campaign_payload(cid))

    @app.route("/api/campaigns/<cid>/approve", methods=["POST"])
    def api_approve(cid: str):
        body = request.get_json(force=True)
        option_id = int(body["option_id"])
        data_agendada = body.get("data_agendada") or None

        # Valida a data antes de exportar (lança ValueError -> 400)
        if data_agendada:
            try:
                campaign_store.agendar(cid, data_agendada)
            except ValueError as e:
                return jsonify({"erro": str(e)}), 400

        export = exporter.export_approved(cid, option_id)
        campaign_store.marcar_aprovada(cid, option_id, data_agendada)
        utils.log(cid, f"server: opção {option_id} aprovada (data={data_agendada}).")
        return jsonify({
            "status": "aprovada",
            "option_id": option_id,
            "data_agendada": data_agendada,
            "export_png": str(export["png"]),
            "export_metadata": str(export["metadata"]),
            "export_post_txt": str(export["post_txt"]),
            "export_all_pngs": [str(p) for p in export["all_pngs"]],
        })

    @app.route("/api/campaigns/<cid>/duplicate", methods=["POST"])
    def api_duplicate(cid: str):
        """
        Cria uma nova campanha reusando o briefing de uma existente.

        Gera novo campaign_id (data atual + sufixo se colidir), dispara geração.
        Não copia copy/imagens — a regeração via IA produz variações novas.
        Útil pra "quero outra rodada do mesmo tema" ou pivot de pequena escala.
        """
        original = campaign_store.read_briefing(cid)
        if original is None:
            return jsonify({"erro": f"Campanha {cid} não encontrada."}), 404
        try:
            quotas.verificar_pode_criar()
        except quotas.QuotaExcedidaError as e:
            return jsonify({
                "erro": e.mensagem, "tipo": "quota_excedida",
                "quota": e.chave, "atual": e.atual, "limite": e.limite,
            }), 429

        # Briefing novo = mesmo conteúdo, sem campaign_id/created_at
        # (briefing_parser.parse regenera ambos).
        novo_raw = {
            "area_direito": original["area_direito"],
            "perfil_cliente_ideal": original["perfil_cliente_ideal"],
            "tom": original["tom"],
            "objetivo": original["objetivo"],
            "tema_especifico": original["tema_especifico"],
            "formato": original["formato"],
            "num_slides": original["num_slides"],
            "referencias": original["referencias"],
        }
        try:
            briefing = briefing_parser.parse(novo_raw)
        except ValueError as e:
            return jsonify({"erro": f"Briefing original inválido: {e}"}), 400

        campaign_store.criar(briefing)
        utils.log(briefing["campaign_id"], f"server: duplicado de {cid}, iniciando geração.")
        _iniciar_geracao_async(briefing)
        return jsonify({
            "campaign_id": briefing["campaign_id"],
            "duplicada_de": cid,
            "status": "gerando",
        }), 201

    @app.route("/api/campaigns/<cid>/adjust", methods=["POST"])
    def api_adjust(cid: str):
        body = request.get_json(force=True)
        option_id = int(body["option_id"])
        nota = body.get("nota", "")
        # Quota de regeração — cada chamada custa $$ em API
        versao_atual = campaign_store.get_copy_version(cid)
        try:
            quotas.verificar_pode_regerar(versao_atual)
        except quotas.QuotaExcedidaError as e:
            return jsonify({
                "erro": e.mensagem,
                "tipo": "quota_excedida",
                "quota": e.chave,
                "atual": e.atual,
                "limite": e.limite,
            }), 429
        campaign_store.write_state(cid, status="ajuste_solicitado", etapa=None)
        utils.log(cid, f"server: ajuste solicitado (opção {option_id}): {nota}")
        _iniciar_regeracao_async(cid, nota)
        return jsonify({"status": "regerando", "nota": nota})

    @app.route("/api/campaigns/<cid>/edit-copy", methods=["POST"])
    def api_edit_copy(cid: str):
        """
        Edita manualmente o copy de uma opção e recompoõe o PNG.

        Body: { option_id: int, fields: dict }
            fields aceita: headline, subheadline, body, caption, cta, hashtags,
            e (carrossel) slides: [{slide_id, headline?, subheadline?, body?}, ...]

        Sobrescreve a versão atual do copy (não bumpa copy_version — bump é só
        pra regeração via LLM). Custo zero de API.
        """
        body = request.get_json(force=True)
        option_id = int(body["option_id"])
        fields = body.get("fields", {})

        briefing = campaign_store.read_briefing(cid)
        if briefing is None:
            return jsonify({"erro": f"Campanha {cid} não encontrada."}), 404
        opcoes = campaign_store.get_copy(cid)
        if opcoes is None:
            return jsonify({"erro": "Copy não encontrado para esta campanha."}), 404

        # Localiza a opção a ser editada
        idx = next((i for i, o in enumerate(opcoes) if o["option_id"] == option_id), None)
        if idx is None:
            return jsonify({"erro": f"Opção {option_id} não encontrada."}), 404

        try:
            opcoes[idx] = _aplicar_edicao(opcoes[idx], fields, briefing["formato"])
        except ValueError as e:
            return jsonify({"erro": str(e)}), 400

        # Persiste e recompoõe
        versao = campaign_store.get_copy_version(cid)
        campaign_store.save_copy_version(cid, versao, opcoes)
        composer.recompose_option(briefing, opcoes[idx])

        utils.log(cid, f"server: opção {option_id} editada manualmente e recomposta.")
        return jsonify(_campaign_payload(cid))

    # ---- Templates de briefing (presets reutilizáveis) ----
    @app.route("/api/templates", methods=["GET"])
    def api_templates_listar():
        return jsonify(store.list_templates())

    @app.route("/api/templates", methods=["POST"])
    def api_templates_salvar():
        body = request.get_json(force=True) or {}
        nome = (body.get("nome") or "").strip()
        if not nome:
            return jsonify({"erro": "Campo 'nome' é obrigatório."}), 400
        try:
            tpl = store.save_template(nome, body)
        except ValueError as e:
            return jsonify({"erro": str(e)}), 400
        return jsonify(tpl), 201

    @app.route("/api/templates/<int:template_id>", methods=["DELETE"])
    def api_templates_apagar(template_id: int):
        if not store.delete_template(template_id):
            return jsonify({"erro": f"Template {template_id} não encontrado."}), 404
        return jsonify({"status": "apagado", "id": template_id})

    # ---- Estáticos genéricos da UI (por último, menos específico) ----
    @app.route("/<path:asset>")
    def ui_asset(asset: str):
        return send_from_directory(settings.APPROVAL_UI_DIR, asset)

    return app


def serve() -> None:
    """
    Sobe a central de controle (persistente) e abre o navegador.

    Bloqueia até Ctrl+C. Diferente da versão antiga, NÃO encerra após aprovar —
    o Henrique pode gerenciar várias campanhas na mesma sessão.

    Usa waitress (WSGI cross-platform: Windows + Linux) em vez do werkzeug
    make_server, que é apenas para desenvolvimento.
    """
    app = build_app()
    url = f"http://{settings.APPROVAL_HOST}:{settings.APPROVAL_PORT}/"

    print(f"✓ Central de controle Mendes & Vaz em {url}")
    print("  (Ctrl+C para encerrar)")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        # threads=8: atende requisições em paralelo (html/css/js/api + polling
        # do dashboard) sem travar enquanto uma thread de geração roda.
        waitress_serve(
            app,
            host=settings.APPROVAL_HOST,
            port=settings.APPROVAL_PORT,
            threads=8,
        )
    except KeyboardInterrupt:
        print("\nEncerrando a central...")
