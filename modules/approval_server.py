"""
modules/approval_server.py — Interface de aprovação (Flask local).

Serve a UI estática em approval_ui/ onde o Henrique vê as 3 variações e aprova
uma (ou pede ajuste). Human in the loop: nada é exportado sem clique explícito.

Endpoints:
    GET  /                           -> approval_ui/index.html
    GET  /style.css, /app.js         -> estáticos da UI
    GET  /api/campaign/<campaign_id> -> dados da campanha (copy + imagens compostas)
    POST /api/approve                -> { campaign_id, option_id }
    POST /api/request_adjustment     -> { campaign_id, option_id, notes }
    GET  /composed/<filename>        -> serve imagens compostas para preview

Após a aprovação: chama exporter, encerra o servidor e confirma no terminal.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.serving import make_server

from config import settings
from modules import exporter, utils

# Evento que sinaliza ao servidor para encerrar (setado após a aprovação).
_shutdown_event = threading.Event()
# Guarda o resultado do export para imprimir no terminal após o shutdown.
_resultado: dict = {}


def _carregar_campanha(campaign_id: str) -> dict:
    """Monta o payload de dados da campanha para a UI."""
    camp_dir = settings.CAMPAIGNS_DIR / campaign_id
    briefing = json.loads((camp_dir / "briefing.json").read_text(encoding="utf-8"))
    copy_options = json.loads((camp_dir / "copy_v1.json").read_text(encoding="utf-8"))

    status = "pending"
    approval_file = camp_dir / "approval.json"
    if approval_file.exists():
        status = json.loads(approval_file.read_text(encoding="utf-8")).get("status", "pending")

    options = []
    for c in copy_options:
        options.append({
            "option_id": c["option_id"],
            "headline": c["headline"],
            "subheadline": c.get("subheadline", ""),
            "body": c["body"],
            "caption": c["caption"],
            "cta": c["cta"],
            "hashtags": c["hashtags"],
            "composed_image_url": f"/composed/option_{c['option_id']}.png",
        })

    return {
        "campaign_id": campaign_id,
        "briefing": briefing,
        "options": options,
        "status": status,
    }


def _salvar_status(campaign_id: str, dados: dict) -> None:
    """Grava o estado de aprovação em campaigns/{id}/approval.json."""
    camp_dir = settings.CAMPAIGNS_DIR / campaign_id
    (camp_dir / "approval.json").write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _build_app(campaign_id: str) -> Flask:
    """Cria a app Flask amarrada a uma campanha específica."""
    app = Flask(__name__, static_folder=None)

    @app.route("/")
    def index():
        return send_from_directory(settings.APPROVAL_UI_DIR, "index.html")

    @app.route("/<path:asset>")
    def ui_asset(asset: str):
        # Serve style.css, app.js e quaisquer outros estáticos da UI.
        return send_from_directory(settings.APPROVAL_UI_DIR, asset)

    @app.route("/logo.png")
    def logo():
        return send_from_directory(settings.LOGO_PATH.parent, settings.LOGO_PATH.name)

    @app.route("/composed/<path:filename>")
    def composed(filename: str):
        composed_dir = settings.CAMPAIGNS_DIR / campaign_id / "composed"
        return send_from_directory(composed_dir, filename)

    @app.route("/api/current")
    def api_current():
        # A UI descobre qual campanha carregar (o servidor roda 1 por vez).
        return jsonify({"campaign_id": campaign_id})

    @app.route("/api/campaign/<cid>")
    def api_campaign(cid: str):
        return jsonify(_carregar_campanha(cid))

    @app.route("/api/approve", methods=["POST"])
    def api_approve():
        body = request.get_json(force=True)
        cid = body["campaign_id"]
        option_id = int(body["option_id"])

        png_path, meta_path = exporter.export_approved(cid, option_id)

        _salvar_status(cid, {
            "status": "approved",
            "option_id": option_id,
            "export_png": str(png_path),
            "export_metadata": str(meta_path),
        })
        utils.log(cid, f"approval_server: opção {option_id} APROVADA por {settings.APPROVED_BY}.")

        _resultado.update({
            "option_id": option_id,
            "png": str(png_path),
            "metadata": str(meta_path),
        })
        _shutdown_event.set()  # sinaliza encerramento após responder

        return jsonify({
            "status": "approved",
            "option_id": option_id,
            "export_png": str(png_path),
        })

    @app.route("/api/request_adjustment", methods=["POST"])
    def api_request_adjustment():
        body = request.get_json(force=True)
        cid = body["campaign_id"]
        option_id = int(body["option_id"])
        notes = body.get("notes", "")

        _salvar_status(cid, {
            "status": "adjustment_requested",
            "option_id": option_id,
            "notes": notes,
        })
        utils.log(cid, f"approval_server: ajuste solicitado na opção {option_id}: {notes}")

        return jsonify({"status": "adjustment_requested", "option_id": option_id})

    return app


def serve(campaign_id: str) -> None:
    """
    Sobe o servidor Flask local, abre o navegador e bloqueia até a aprovação.

    Após a aprovação: o handler chama o exporter e seta o evento de shutdown;
    aqui encerramos o servidor e confirmamos no terminal.
    """
    app = _build_app(campaign_id)
    server = make_server(settings.APPROVAL_HOST, settings.APPROVAL_PORT, app)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://{settings.APPROVAL_HOST}:{settings.APPROVAL_PORT}/"
    print(f"✓ Interface de aprovação em {url}")
    print("  (aprove uma variação no navegador para finalizar)")
    try:
        webbrowser.open(url)
    except Exception:
        pass  # se não abrir sozinho, o usuário acessa a URL manualmente

    # Bloqueia até o handler de aprovação sinalizar
    _shutdown_event.wait()
    server.shutdown()
    thread.join(timeout=5)

    if _resultado:
        print("\n✅ Post aprovado e exportado!")
        print(f"   Opção: {_resultado['option_id']}")
        print(f"   PNG:   {_resultado['png']}")
        print(f"   Meta:  {_resultado['metadata']}")
