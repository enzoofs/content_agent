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
import webbrowser

from flask import Flask, abort, jsonify, request, send_from_directory
from werkzeug.serving import make_server

from config import settings
from modules import (
    briefing_parser,
    campaign_store,
    exporter,
    pipeline,
    utils,
)


# --------------------------------------------------------------------------
# Disparo assíncrono da geração (funções isoladas para facilitar teste/mocks)
# --------------------------------------------------------------------------
def _iniciar_geracao_async(briefing: dict) -> None:
    """Dispara pipeline.gerar numa thread daemon. Erros já viram estado no pipeline."""
    def run():
        try:
            pipeline.gerar(briefing)
        except Exception:
            pass  # pipeline já gravou status=erro
    threading.Thread(target=run, daemon=True).start()


def _iniciar_regeracao_async(campaign_id: str, nota: str) -> None:
    """Dispara pipeline.regerar numa thread daemon."""
    def run():
        try:
            pipeline.regerar(campaign_id, nota)
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()


# --------------------------------------------------------------------------
# Montagem do payload de uma campanha para a UI
# --------------------------------------------------------------------------
def _campaign_payload(campaign_id: str) -> dict:
    """Junta estado + briefing + variações de copy (com URLs das imagens compostas)."""
    estado = campaign_store.read_state(campaign_id)
    if estado is None:
        abort(404, description=f"Campanha {campaign_id} não encontrada.")

    camp = settings.CAMPAIGNS_DIR / campaign_id
    briefing = {}
    bp = camp / "briefing.json"
    if bp.exists():
        briefing = json.loads(bp.read_text(encoding="utf-8"))

    options = []
    cp = camp / "copy_v1.json"
    if cp.exists():
        for c in json.loads(cp.read_text(encoding="utf-8")):
            options.append({
                "option_id": c["option_id"],
                "headline": c["headline"],
                "subheadline": c.get("subheadline", ""),
                "body": c["body"],
                "caption": c["caption"],
                "cta": c["cta"],
                "hashtags": c["hashtags"],
                "composed_image_url": f"/composed/{campaign_id}/option_{c['option_id']}.png",
            })

    return {
        "campaign_id": campaign_id,
        "briefing": briefing,
        "options": options,
        "state": estado,
    }


# --------------------------------------------------------------------------
# App factory
# --------------------------------------------------------------------------
def build_app() -> Flask:
    """Cria a app Flask da central (persistente, multi-campanha)."""
    app = Flask(__name__, static_folder=None)

    # ---- Estáticos / UI ----
    @app.route("/")
    def index():
        return send_from_directory(settings.APPROVAL_UI_DIR, "index.html")

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
        try:
            briefing = briefing_parser.parse(body)
        except ValueError as e:
            return jsonify({"erro": str(e)}), 400

        campaign_store.criar(briefing)
        utils.log(briefing["campaign_id"], "server: campanha criada, iniciando geração.")
        _iniciar_geracao_async(briefing)
        return jsonify({"campaign_id": briefing["campaign_id"], "status": "gerando"}), 201

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

        png_path, meta_path = exporter.export_approved(cid, option_id)
        campaign_store.marcar_aprovada(cid, option_id, data_agendada)
        utils.log(cid, f"server: opção {option_id} aprovada (data={data_agendada}).")
        return jsonify({
            "status": "aprovada",
            "option_id": option_id,
            "data_agendada": data_agendada,
            "export_png": str(png_path),
            "export_metadata": str(meta_path),
        })

    @app.route("/api/campaigns/<cid>/adjust", methods=["POST"])
    def api_adjust(cid: str):
        body = request.get_json(force=True)
        option_id = int(body["option_id"])
        nota = body.get("nota", "")
        campaign_store.write_state(cid, status="ajuste_solicitado", etapa=None)
        utils.log(cid, f"server: ajuste solicitado (opção {option_id}): {nota}")
        _iniciar_regeracao_async(cid, nota)
        return jsonify({"status": "regerando", "nota": nota})

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
    """
    app = build_app()
    # threaded=True: atende requisições em paralelo (html/css/js/api + polling).
    # Sem isso o servidor single-threaded trava com o browser.
    server = make_server(settings.APPROVAL_HOST, settings.APPROVAL_PORT, app, threaded=True)
    url = f"http://{settings.APPROVAL_HOST}:{settings.APPROVAL_PORT}/"

    print(f"✓ Central de controle Mendes & Vaz em {url}")
    print("  (Ctrl+C para encerrar)")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando a central...")
        server.shutdown()
