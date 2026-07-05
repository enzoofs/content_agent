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
import os
import re
import secrets
import sqlite3
import threading
import traceback
import webbrowser

import io
import zipfile

from flask import Flask, Response, abort, g, jsonify, request, send_file, send_from_directory, session
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from waitress import serve as waitress_serve
from werkzeug.security import check_password_hash, generate_password_hash

from config import settings
from config.brands import BriefingField
from config import brands as brands_module
from modules import (
    briefing_parser,
    brands_store,
    campaign_store,
    composer,
    copy_generator,
    exporter,
    pipeline,
    quotas,
    store,
    users_store,
    utils,
)


# --------------------------------------------------------------------------
# Autenticação (flask-login) — usuário determina qual brand fica ativo
# --------------------------------------------------------------------------
class AuthUser(UserMixin):
    """Wrapper fino sobre uma linha de `users` pro contrato do flask-login."""

    def __init__(self, row: dict):
        self.id = row["id"]
        self.email = row["email"]
        self.brand_slug = row["brand_slug"]
        self.role = row["role"]

    def get_id(self) -> str:
        return str(self.id)


def _active_brand_slug() -> str | None:
    """
    Resolve o slug do brand ativo pra sessão atual.

    - role="cliente": sempre o brand fixo do usuário.
    - role="admin": o brand escolhido na sessão (POST /api/admin/brand),
        ou None se ainda não escolheu nenhum (frontend mostra o seletor).
    """
    if current_user.role == "admin":
        return session.get("active_brand")
    return current_user.brand_slug


# --------------------------------------------------------------------------
# Fallback de briefing_fields — usado quando o brand ativo NÃO declara o seu
# (caso atual de Mendes & Vaz, que é o cliente piloto e ficou intocado durante
# a migração pra schema declarativo). Replica EXATAMENTE o form hardcoded
# original do `approval_ui/index.html` pra que a UI do M&V continue
# byte-idêntica quando renderizada pelo renderer schema-driven.
_DEFAULT_BRIEFING_FIELDS = (
    BriefingField(
        name="area_direito",
        label="Área do direito",
        kind="text",
        required=True,
        max_chars=200,
        placeholder="ex.: Direito Médico",
    ),
    BriefingField(
        name="perfil_cliente_ideal",
        label="Perfil do cliente ideal",
        kind="textarea",
        required=True,
        max_chars=500,
        rows=2,
        placeholder="ex.: Médicos e clínicas de BH preocupados com processos",
    ),
    BriefingField(
        name="tom",
        label="Tom",
        kind="enum",
        enum_values=("tecnico", "acessivel"),
        enum_labels=("Técnico / Autoridade", "Acessível / Educativo"),
        default="tecnico",
    ),
    BriefingField(
        name="objetivo",
        label="Objetivo",
        kind="enum",
        enum_values=("posicionamento", "awareness", "captacao"),
        enum_labels=("Posicionamento", "Awareness", "Captação"),
        default="posicionamento",
    ),
    BriefingField(
        name="formato",
        label="Formato",
        kind="enum",
        enum_values=("square", "portrait", "story", "carousel"),
        enum_labels=("Square (1080×1080)", "Portrait (1080×1350)", "Story (1080×1920)", "Carrossel"),
        default="square",
    ),
    BriefingField(
        name="num_slides",
        label="Nº de slides (3–8)",
        kind="int",
        required=False,
        min_int=3,
        max_int=8,
        default="3",
        help="Só pra formato carrossel.",
    ),
    BriefingField(
        name="tema_especifico",
        label="Tema específico (opcional)",
        kind="text",
        required=False,
        max_chars=500,
        placeholder="deixe em branco para a IA escolher",
    ),
    BriefingField(
        name="referencias",
        label="Referências / observações (opcional)",
        kind="textarea",
        required=False,
        max_chars=2000,
        rows=2,
    ),
)


def _brand_briefing_fields() -> tuple[BriefingField, ...]:
    """Retorna o schema do brand ativo, com fallback pro default M&V-shaped."""
    if g.brand is None:
        return _DEFAULT_BRIEFING_FIELDS
    return g.brand.briefing_fields or _DEFAULT_BRIEFING_FIELDS


def _serialize_briefing_field(f: BriefingField) -> dict:
    """Serializa um BriefingField pra payload JSON da UI."""
    return {
        "name": f.name,
        "label": f.label,
        "kind": f.kind,
        "required": f.required,
        "enum_values": list(f.enum_values),
        "enum_labels": list(f.enum_labels) if f.enum_labels else list(f.enum_values),
        "max_chars": f.max_chars,
        "min_int": f.min_int,
        "max_int": f.max_int,
        "rows": f.rows,
        "default": f.default,
        "placeholder": f.placeholder,
        "help": f.help,
    }


def _brand_payload() -> dict:
    """
    Metadata do brand ativo pra UI consumir via /api/brand.

    Quando g.brand é None (admin sem brand escolhido ainda), devolve um
    payload neutro — a UI detecta `slug: null` e mostra o seletor de brand.
    """
    if g.brand is None:
        return {
            "nome": None,
            "slug": None,
            "colors": {},
            "fonts": {},
            "logo_url": None,
            "briefing_fields": [_serialize_briefing_field(f) for f in _DEFAULT_BRIEFING_FIELDS],
        }
    b = g.brand
    return {
        "nome": b.nome,
        "slug": b.slug,
        "colors": dict(b.colors),
        "fonts": dict(b.fonts),
        "logo_url": "/brand-logo",
        "briefing_fields": [_serialize_briefing_field(f) for f in _brand_briefing_fields()],
    }


def _brand_css_vars() -> str:
    """
    Render do bloco <style> que sobrescreve tokens visuais do brand ativo
    (paleta, tipografia, hierarquia de tinta no theme dark). Injetado pelo
    route `/` no <head> pra zero flicker no boot.

    - Sempre: mapeia brand.colors (contrato cross-brand: navy/gold/white/
      cream/navy_dark) pras CSS vars do style.css.
    - theme="dark": sobrescreve --ink-1..4 e --line-* pra valores claros
      (rgba branco-translúcido) — sem isso, labels/placeholders ficam
      invisíveis em fundo escuro.
    - ui_heading_font / ui_body_font: força a fonte do brand em .brand-name,
      .page-title e body (sobrepõe Playfair/Montserrat default do M&V).
    """
    if g.brand is None:
        return ""
    b = g.brand
    c = b.colors
    root_overrides = []
    if "navy" in c:
        root_overrides.append(f"--navy: {c['navy']};")
    if "navy_dark" in c:
        root_overrides.append(f"--navy-dark: {c['navy_dark']};")
        root_overrides.append(f"--surface-deep: {c['navy_dark']};")
    if "gold" in c:
        root_overrides.append(f"--gold: {c['gold']};")
    if "white" in c:
        root_overrides.append(f"--white: {c['white']};")
    if "cream" in c:
        root_overrides.append(f"--cream: {c['cream']};")
        root_overrides.append(f"--surface-2: {c['cream']};")

    # Hierarquia de tinta: ink-1 = texto principal, ink-2..4 = secundário/dim.
    # No M&V (light) é navy translúcido. No dark precisa inverter pra branco.
    if b.theme == "dark":
        root_overrides += [
            "--ink-1: #FAFAFA;",
            "--ink-2: rgba(250, 250, 250, 0.78);",
            "--ink-3: rgba(250, 250, 250, 0.55);",
            "--ink-4: rgba(250, 250, 250, 0.35);",
            "--line-soft: rgba(250, 250, 250, 0.08);",
            "--line-medium: rgba(250, 250, 250, 0.18);",
            "--line-strong: rgba(250, 250, 250, 0.28);",
        ]
    elif "navy" in c:
        # Light theme: ink-1 segue navy do brand (mantém comportamento M&V)
        root_overrides.append(f"--ink-1: {c['navy']};")

    blocks = []
    if root_overrides:
        blocks.append(":root {" + " ".join(root_overrides) + "}")

    # No dark theme, os containers com fundo branco/claro (cards do dashboard,
    # células do calendário, modais, etc.) precisam de ink escura no conteúdo
    # — caso contrário herdam --ink-1 branco do :root e ficam ilegíveis.
    # Solução: redefinir --ink-1..4 como tokens escuros DENTRO desses containers
    # (CSS vars cascateiam — todos os filhos herdam automaticamente).
    if b.theme == "dark":
        light_surfaces = (
            ".dash-card, .skel-card, .card, .progress, .erro-box, .done-card, "
            ".schedule-bar, .template-bar, .cal-cell, .cal-nav, .edit-modal-box, "
            ".export-row, .empty, .caption-block, .edit-field-input, .edit-form, "
            ".edit-modal-actions, .dash-card-dup"
        )
        blocks.append(
            light_surfaces + " { "
            "--ink-1: #0A0A0A; "
            "--ink-2: rgba(10, 10, 10, 0.78); "
            "--ink-3: rgba(10, 10, 10, 0.55); "
            "--ink-4: rgba(10, 10, 10, 0.35); "
            "color: var(--ink-1); "
            "}"
        )
        # Inputs do form: idem (já tinham fundo branco). Aqui forçamos a cor
        # do texto/placeholder pra não depender do contexto onde o input vive.
        blocks.append(
            ".form input, .form select, .form textarea, "
            ".edit-field-input { color: #0A0A0A; }"
        )
        blocks.append(
            ".form input::placeholder, .form textarea::placeholder { "
            "color: rgba(10, 10, 10, 0.45); }"
        )
        # Topbar do Gui sem o noise/gold cross-hatch do M&V — pegada minimal,
        # só preto liso com hairline branca embaixo (vibe night/editorial).
        # Substitui o `background` composto do .topbar (várias camadas) por
        # algo limpo pro brand. Mantém o sticky/z-index originais via cascata.
        blocks.append(
            ".topbar { background: " + c.get("navy", "#0A0A0A") + "; "
            "border-bottom: 1px solid rgba(250, 250, 250, 0.12); "
            "background-image: none; }"
        )

    # Tipografia do brand: sobrescreve Playfair/Montserrat default em pontos
    # de impacto visual (brand-name, page-title, body). Outros usos de
    # Playfair em cards/dashboards seguem inalterados — gradual swap.
    if b.ui_heading_font:
        blocks.append(
            ".brand-name, .page-title, .brand-sub { "
            f"font-family: {b.ui_heading_font}; }}"
        )
        # Brand-name typographic vira o "logo": maior, weight forte, tracking
        # apertado pra dar peso de logotipo quando use_image_logo=False.
        if not b.use_image_logo:
            blocks.append(
                ".brand-name { font-size: 26px; font-weight: 800; "
                "letter-spacing: -0.5px; line-height: 1; text-transform: none; }"
            )
            blocks.append(
                ".brand-sub { letter-spacing: 2.4px; font-size: 10px; "
                "font-weight: 500; opacity: 0.7; }"
            )
    if b.ui_body_font:
        blocks.append(f"body {{ font-family: {b.ui_body_font}; }}")

    if not blocks:
        return ""
    return "<style>" + " ".join(blocks) + "</style>"


def _brand_logo_tag() -> str:
    """
    Render do <img> do logo OU string vazia quando o brand é typographic.
    Usado pra substituir {{BRAND_LOGO_TAG}} no index.html.
    """
    if g.brand is None or not g.brand.use_image_logo:
        return ""
    nome_esc = g.brand.nome.replace('"', "&quot;")
    return f'<img src="/brand-logo" alt="{nome_esc}" class="brand-logo">'


def _brand_google_fonts_link() -> str:
    """Link adicional do Google Fonts do brand (vazio se não definido)."""
    if g.brand is None:
        return ""
    url = g.brand.google_fonts_url
    if not url:
        return ""
    return f'<link href="{url}" rel="stylesheet">'


# --------------------------------------------------------------------------
# Upload de foto própria (alternativa ao Ideogram — M&V)
# --------------------------------------------------------------------------
_UPLOAD_EXT_PERMITIDAS = {".png", ".jpg", ".jpeg", ".webp"}
_UPLOAD_MAX_BYTES = 20 * 1024 * 1024  # 20 MB — foto de celular cabe folgado


def _salvar_upload(campaign_id: str, file_storage) -> str:
    """
    Persiste o arquivo enviado pelo operador em campaigns/<id>/upload.<ext>.

    Returns:
        Nome do arquivo salvo (ex.: "upload.jpg") — vai pro briefing.upload_filename.

    Raises:
        ValueError: extensão não suportada ou arquivo vazio/gigante.
    """
    import os
    nome_orig = file_storage.filename or ""
    ext = os.path.splitext(nome_orig)[1].lower()
    if ext not in _UPLOAD_EXT_PERMITIDAS:
        raise ValueError(
            f"Formato de imagem não suportado: {ext or '(sem extensão)'}. "
            f"Aceitos: {sorted(_UPLOAD_EXT_PERMITIDAS)}."
        )
    destino_dir = settings.CAMPAIGNS_DIR / campaign_id
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / f"upload{ext}"
    file_storage.save(str(destino))
    tamanho = destino.stat().st_size
    if tamanho == 0:
        destino.unlink(missing_ok=True)
        raise ValueError("Arquivo enviado está vazio.")
    if tamanho > _UPLOAD_MAX_BYTES:
        destino.unlink(missing_ok=True)
        raise ValueError(
            f"Arquivo muito grande ({tamanho // 1024 // 1024} MB). "
            f"Limite: {_UPLOAD_MAX_BYTES // 1024 // 1024} MB."
        )
    return destino.name


# --------------------------------------------------------------------------
# Logo de brand novo (cadastro de cliente na tela de admin)
# --------------------------------------------------------------------------
_LOGO_MAX_BYTES = 5 * 1024 * 1024  # 5 MB — logo não precisa do tamanho de foto de campanha


def _salvar_logo_brand(slug: str, file_storage) -> str:
    """
    Persiste o logo enviado no cadastro de cliente em assets/logo_<slug>.<ext>
    (mesma convenção dos brands hardcoded — ver config/brands/mendes_vaz.py).

    Returns:
        Nome do arquivo salvo (ex.: "logo_acme.png") — vai pro brands.logo_filename.

    Raises:
        ValueError: extensão não suportada ou arquivo vazio/gigante demais.
    """
    nome_orig = file_storage.filename or ""
    ext = os.path.splitext(nome_orig)[1].lower()
    if ext not in _UPLOAD_EXT_PERMITIDAS:
        raise ValueError(
            f"Formato de imagem não suportado: {ext or '(sem extensão)'}. "
            f"Aceitos: {sorted(_UPLOAD_EXT_PERMITIDAS)}."
        )
    destino = settings.ASSETS_DIR / f"logo_{slug}{ext}"
    file_storage.save(str(destino))
    tamanho = destino.stat().st_size
    if tamanho == 0:
        destino.unlink(missing_ok=True)
        raise ValueError("Logo enviado está vazio.")
    if tamanho > _LOGO_MAX_BYTES:
        destino.unlink(missing_ok=True)
        raise ValueError(
            f"Logo muito grande ({tamanho // 1024 // 1024} MB). "
            f"Limite: {_LOGO_MAX_BYTES // 1024 // 1024} MB."
        )
    return destino.name


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
# Guarda de posse (isolamento entre brands)
# --------------------------------------------------------------------------
def _checar_posse(campaign_id: str) -> dict:
    """
    Carrega a campanha e garante que pertence ao brand ativo (ou que o
    usuário é admin, que enxerga tudo).

    404 (não 403) em caso de acesso cruzado — evita confirmar pra um cliente
    que existe uma campanha de outro brand com aquele id.

    Raises:
        werkzeug.exceptions.NotFound: campanha inexistente OU de outro brand.
    """
    campanha = campaign_store.read_state(campaign_id)
    if campanha is None:
        abort(404, description=f"Campanha {campaign_id} não encontrada.")
    if current_user.role != "admin" and campanha.get("brand_slug") != (g.brand.slug if g.brand else None):
        abort(404, description=f"Campanha {campaign_id} não encontrada.")
    return campanha


# --------------------------------------------------------------------------
# Montagem do payload de uma campanha para a UI
# --------------------------------------------------------------------------
def _campaign_payload(campaign_id: str) -> dict:
    """Junta estado + briefing + variações de copy (com URLs das imagens compostas).

    Para carrossel, cada opção inclui `slides: [{slide_id, headline, body,
    image_url}]` em vez de um único `composed_image_url`. Caption/cta/hashtags
    ficam no nível da opção (mesmo padrão do Instagram).
    """
    estado = _checar_posse(campaign_id)

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


def _briefing_to_text(briefing: dict | None) -> str:
    """Briefing humano-legível pro pacote .zip que o cliente baixa."""
    if not briefing:
        return "Briefing indisponível.\n"
    linhas = [
        f"Campanha: {briefing.get('campaign_id', '')}",
        f"Criada em: {briefing.get('created_at', '')}",
        "",
        f"Área do direito: {briefing.get('area_direito', '')}",
        f"Perfil do cliente ideal: {briefing.get('perfil_cliente_ideal', '')}",
        f"Tom: {briefing.get('tom', '')}",
        f"Objetivo: {briefing.get('objetivo', '')}",
        f"Formato: {briefing.get('formato', '')}",
    ]
    if briefing.get("formato") == "carousel":
        linhas.append(f"Nº de slides: {briefing.get('num_slides', '')}")
    linhas += [
        f"Tema específico: {briefing.get('tema_especifico') or '(livre)'}",
        f"Referências: {briefing.get('referencias') or '(nenhuma)'}",
    ]
    return "\n".join(linhas) + "\n"


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

    # ---- Sessão / login (flask-login) ----
    # FLASK_SECRET_KEY ausente = chave efêmera por processo (dev local "só
    # funciona", igual o Basic Auth antigo) — sessões não sobrevivem a
    # restart do servidor nesse caso.
    secret = os.getenv("FLASK_SECRET_KEY")
    if not secret:
        secret = secrets.token_hex(32)
        print("⚠️  FLASK_SECRET_KEY não configurada — usando chave efêmera "
              "(sessões não sobrevivem a um restart do servidor).")
    app.secret_key = secret

    login_manager = LoginManager()
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        row = users_store.get_by_id(int(user_id))
        return AuthUser(row) if row else None

    # Endpoint público p/ healthcheck do Fly.io — precisa ficar livre de auth
    @app.route("/health")
    def _health():
        return "ok", 200

    # /style.css é público pra login.html conseguir carregar o CSS sem sessão.
    _ROTAS_PUBLICAS = {"/health", "/login", "/logout", "/style.css"}

    @app.before_request
    def _require_login():
        if request.path in _ROTAS_PUBLICAS:
            return None
        if current_user.is_authenticated:
            return None
        if request.path.startswith("/api/"):
            return jsonify({"erro": "Autenticação necessária."}), 401
        return Response(status=302, headers={"Location": "/login"})

    @app.before_request
    def _resolve_brand():
        """Popula g.brand pra sessão atual (None se não-autenticado ou admin sem brand escolhido)."""
        if not current_user.is_authenticated:
            g.brand = None
            return
        slug = _active_brand_slug()
        g.brand = brands_module.load(slug) if slug else None

    @app.route("/login", methods=["GET"])
    def login_form():
        html = (settings.APPROVAL_UI_DIR / "login.html").read_text(encoding="utf-8")
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/login", methods=["POST"])
    def login_submit():
        if request.is_json:
            body = request.get_json(force=True)
            email, senha = body.get("email", ""), body.get("senha", "")
        else:
            email, senha = request.form.get("email", ""), request.form.get("senha", "")
        row = users_store.get_by_email(email)
        if row is None or not check_password_hash(row["senha_hash"], senha):
            if request.is_json:
                return jsonify({"erro": "Email ou senha inválidos."}), 401
            return "Email ou senha inválidos.", 401
        login_user(AuthUser(row))
        if request.is_json:
            return jsonify({"status": "ok"})
        return Response(status=302, headers={"Location": "/"})

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout_submit():
        logout_user()
        session.pop("active_brand", None)
        return Response(status=302, headers={"Location": "/login"})

    @app.route("/api/me", methods=["GET"])
    @login_required
    def api_me():
        return jsonify({
            "email": current_user.email,
            "role": current_user.role,
            "brand_slug": _active_brand_slug(),
            "available_brands": list(brands_module.list_available_brands()) if current_user.role == "admin" else [],
        })

    @app.route("/api/admin/brand", methods=["POST"])
    @login_required
    def api_admin_brand():
        if current_user.role != "admin":
            return jsonify({"erro": "Só admin pode trocar de brand."}), 403
        body = request.get_json(force=True) or {}
        slug = body.get("slug")
        if slug not in brands_module.list_available_brands():
            return jsonify({"erro": f"Brand desconhecido: {slug!r}."}), 400
        session["active_brand"] = slug
        return jsonify({"status": "ok", "brand_slug": slug})

    @app.route("/api/admin/stats", methods=["GET"])
    @login_required
    def api_admin_stats():
        """Stats pra tela de admin: quota + tokens por brand, usuários cadastrados."""
        if current_user.role != "admin":
            return jsonify({"erro": "Só admin pode ver estatísticas."}), 403

        tokens_por_brand = store.tokens_used_por_brand()
        brands_info = []
        for slug in brands_module.list_available_brands():
            brands_info.append({
                "slug": slug,
                "quota": quotas.snapshot(slug),
                "tokens_used": tokens_por_brand.get(slug, 0),
            })
        # NUNCA devolve senha_hash — é o hash da senha, mas ainda assim não
        # deve trafegar pro cliente.
        usuarios = [
            {k: v for k, v in u.items() if k != "senha_hash"}
            for u in users_store.list_usuarios()
        ]
        return jsonify({"brands": brands_info, "usuarios": usuarios})

    @app.route("/api/admin/clients", methods=["POST"])
    @login_required
    def api_admin_criar_cliente():
        """
        Cadastra um cliente novo: cria o brand (multipart, logo opcional) +
        o primeiro usuário desse brand, numa única chamada.
        """
        if current_user.role != "admin":
            return jsonify({"erro": "Só admin pode cadastrar clientes."}), 403

        if request.content_type and request.content_type.startswith("multipart/form-data"):
            body = {k: v for k, v in request.form.items()}
            logo_file = request.files.get("logo")
            if logo_file and not logo_file.filename:
                logo_file = None
        else:
            body = request.get_json(force=True) or {}
            logo_file = None

        nome = (body.get("nome") or "").strip()
        email = (body.get("email") or "").strip()
        if not nome:
            return jsonify({"erro": "Campo 'nome' é obrigatório."}), 400
        if not email:
            return jsonify({"erro": "Campo 'email' é obrigatório."}), 400

        slug = (body.get("slug") or "").strip() or utils.slugify_brand(nome)
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,49}", slug):
            return jsonify({"erro": f"Slug inválido: {slug!r}. Use letras minúsculas, números e '_'."}), 400
        if slug in brands_module.list_available_brands():
            return jsonify({"erro": f"Já existe um brand com o slug {slug!r}."}), 400

        colors = {
            "navy": body.get("navy") or "#272D4D",
            "gold": body.get("gold") or "#E3B644",
            "white": body.get("white") or "#FFFFFF",
            "cream": body.get("cream") or "#F5F0E8",
            "navy_dark": body.get("navy_dark") or "#1A2038",
        }

        logo_filename = None
        if logo_file is not None:
            try:
                logo_filename = _salvar_logo_brand(slug, logo_file)
            except ValueError as e:
                return jsonify({"erro": str(e)}), 400

        use_image_logo = (body.get("use_image_logo") in ("true", "1", "on", True)) and logo_filename is not None

        brands_store.criar_brand(
            slug, nome, colors,
            logo_filename=logo_filename,
            use_image_logo=use_image_logo,
            theme=body.get("theme") or "light",
            google_fonts_url=body.get("google_fonts_url") or "",
            ui_heading_font=body.get("ui_heading_font") or "",
            ui_body_font=body.get("ui_body_font") or "",
            image_prompt_suffix=body.get("image_prompt_suffix") or "",
            ideogram_negative_prompt=body.get("ideogram_negative_prompt") or "",
            approved_by=body.get("approved_by") or "",
            system_prompt=body.get("system_prompt") or "",
            system_prompt_carousel=body.get("system_prompt_carousel") or "",
        )

        senha = secrets.token_urlsafe(12)
        try:
            users_store.criar_usuario(email, generate_password_hash(senha), slug, role="cliente")
        except sqlite3.IntegrityError:
            # Email já existe — desfaz o brand recém-criado (evita brand
            # órfão sem ninguém pra logar nele).
            brands_store.delete_brand(slug)
            return jsonify({"erro": f"Email {email!r} já está cadastrado."}), 400

        return jsonify({"slug": slug, "email": email, "senha_temporaria": senha}), 201

    @app.route("/api/admin/users", methods=["POST"])
    @login_required
    def api_admin_criar_usuario():
        """Cria um usuário adicional pra um brand já existente (ou outro admin)."""
        if current_user.role != "admin":
            return jsonify({"erro": "Só admin pode criar usuários."}), 403

        body = request.get_json(force=True) or {}
        email = (body.get("email") or "").strip()
        role = body.get("role", "cliente")
        brand_slug = body.get("brand_slug")

        if not email:
            return jsonify({"erro": "Campo 'email' é obrigatório."}), 400
        if role not in ("cliente", "admin"):
            return jsonify({"erro": f"Role inválida: {role!r}."}), 400
        if role == "cliente":
            if brand_slug not in brands_module.list_available_brands():
                return jsonify({"erro": f"Brand desconhecido: {brand_slug!r}."}), 400
        else:
            brand_slug = None

        senha = secrets.token_urlsafe(12)
        try:
            users_store.criar_usuario(email, generate_password_hash(senha), brand_slug, role)
        except sqlite3.IntegrityError:
            return jsonify({"erro": f"Email {email!r} já está cadastrado."}), 400

        return jsonify({"email": email, "senha_temporaria": senha}), 201

    # ---- Estáticos / UI ----
    @app.route("/")
    def index():
        """
        Serve o index.html injetando: ?v=<mtime> nos refs de app.js/style.css,
        o nome/logo do brand ativo e um bloco <style> com CSS vars do brand
        (zero flicker M&V → Gui no boot).

        Sem cache-bust: o browser cacheia versões antigas dos assets — bug
        clássico quando a gente atualiza JS/CSS e o usuário continua vendo o
        comportamento velho (ex.: botão "Salvando…" travado após edição).
        """
        html = (settings.APPROVAL_UI_DIR / "index.html").read_text(encoding="utf-8")
        js_mtime = int((settings.APPROVAL_UI_DIR / "app.js").stat().st_mtime)
        css_mtime = int((settings.APPROVAL_UI_DIR / "style.css").stat().st_mtime)
        html = html.replace('src="app.js"', f'src="app.js?v={js_mtime}"')
        html = html.replace('href="style.css"', f'href="style.css?v={css_mtime}"')

        # Injeção de brand (server-side, zero flicker):
        # - {{BRAND_NAME}}: nome humano do brand (escapado p/ HTML)
        # - {{BRAND_LOGO_TAG}}: <img> do logo OU vazio (brands typographic)
        # - {{BRAND_GOOGLE_FONTS}}: <link> extra de Google Fonts do brand
        # - {{BRAND_CSS_VARS}}: <style> com paleta/fontes/dark-theme overrides
        from html import escape as _esc
        nome = g.brand.nome if g.brand else "Central de Conteúdo"
        html = html.replace("{{BRAND_NAME}}", _esc(nome))
        html = html.replace("{{BRAND_LOGO_TAG}}", _brand_logo_tag())
        html = html.replace("{{BRAND_GOOGLE_FONTS}}", _brand_google_fonts_link())
        html = html.replace("{{BRAND_CSS_VARS}}", _brand_css_vars())
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/admin")
    @login_required
    def admin_page():
        """Página de admin (stats + cadastro de clientes) — sem topbar de campanhas."""
        if current_user.role != "admin":
            abort(403)
        html = (settings.APPROVAL_UI_DIR / "admin.html").read_text(encoding="utf-8")
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/logo.png")
    def logo():
        # Legacy: mantida pra compat caso algum link antigo aponte pra /logo.png
        logo_path = g.brand.logo_path if g.brand else settings.LOGO_PATH
        return send_from_directory(logo_path.parent, logo_path.name)

    @app.route("/brand-logo")
    def brand_logo():
        """Serve o logo do brand ativo (config/brands/<slug>.py:logo_path)."""
        logo_path = g.brand.logo_path if g.brand else settings.LOGO_PATH
        return send_from_directory(logo_path.parent, logo_path.name)

    @app.route("/api/brand", methods=["GET"])
    def api_brand():
        """Metadata do brand ativo (nome, paleta, fontes, briefing_fields)."""
        return jsonify(_brand_payload())

    @app.route("/composed/<cid>/<path:filename>")
    def composed(cid: str, filename: str):
        _checar_posse(cid)
        return send_from_directory(settings.CAMPAIGNS_DIR / cid / "composed", filename)

    # ---- API ----
    @app.route("/api/campaigns", methods=["GET"])
    def api_listar():
        # Admin sem brand escolhido ainda: lista vazia (frontend mostra o seletor).
        if g.brand is None:
            return jsonify([])
        return jsonify(campaign_store.listar(brand_slug=g.brand.slug))

    @app.route("/api/campaigns", methods=["POST"])
    def api_criar():
        if g.brand is None:
            return jsonify({"erro": "Escolha um brand antes de criar uma campanha."}), 400

        # Aceita JSON (fluxo padrão) ou multipart/form-data (quando o operador
        # envia uma foto pra usar como fundo em vez do Ideogram).
        upload_file = None
        if request.content_type and request.content_type.startswith("multipart/form-data"):
            body = {k: v for k, v in request.form.items()}
            upload_file = request.files.get("upload")
            if upload_file and not upload_file.filename:
                upload_file = None
        else:
            body = request.get_json(force=True)

        # 1) Quota antes de qualquer parse — falha cedo, sem custo
        try:
            quotas.verificar_pode_criar(g.brand.slug)
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

        # 3) Salva o upload (se houver) DEPOIS do parse — agora temos o
        #    campaign_id pra rotear o arquivo. Patcha o briefing antes do INSERT
        #    pra que upload_filename seja persistido junto.
        if upload_file:
            try:
                upload_name = _salvar_upload(briefing["campaign_id"], upload_file)
            except ValueError as e:
                return jsonify({"erro": str(e)}), 400
            briefing["upload_filename"] = upload_name

        campaign_store.criar(briefing, brand_slug=g.brand.slug)
        utils.log(briefing["campaign_id"], "server: campanha criada, iniciando geração.")
        _iniciar_geracao_async(briefing)
        return jsonify({"campaign_id": briefing["campaign_id"], "status": "gerando"}), 201

    @app.route("/api/quotas", methods=["GET"])
    def api_quotas():
        """Snapshot atual das quotas — UI mostra banner amarelo/vermelho conforme."""
        if g.brand is None:
            return jsonify({"itens": [], "bloqueado": False, "proximo_reset": ""})
        return jsonify(quotas.snapshot(g.brand.slug))

    @app.route("/api/campaigns/<cid>", methods=["GET"])
    def api_campanha(cid: str):
        return jsonify(_campaign_payload(cid))

    @app.route("/api/campaigns/<cid>/approve", methods=["POST"])
    def api_approve(cid: str):
        _checar_posse(cid)
        body = request.get_json(force=True)
        option_id = int(body["option_id"])
        data_agendada = body.get("data_agendada") or None

        # Valida a data antes de exportar (lança ValueError -> 400)
        if data_agendada:
            try:
                campaign_store.agendar(cid, data_agendada)
            except ValueError as e:
                return jsonify({"erro": str(e)}), 400

        export = exporter.export_approved(cid, option_id, brand=g.brand)
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

    @app.route("/api/campaigns/<cid>/download", methods=["GET"])
    def api_download(cid: str):
        """
        Empacota a campanha aprovada num .zip e devolve via navegador.

        Conteúdo: PNGs compostos + legendas.txt (pronto pra postar) + briefing.txt
        (referência humana). O cliente escolhe onde salvar no diálogo do browser
        — não precisa saber a estrutura de pastas do servidor.
        """
        estado = _checar_posse(cid)
        if estado.get("status") != "aprovada" or not estado.get("option_aprovada"):
            return jsonify({"erro": "Só dá pra baixar campanha aprovada."}), 409

        briefing = campaign_store.read_briefing(cid)
        oid = int(estado["option_aprovada"])
        export_dir = settings.EXPORTS_DIR / cid

        if not export_dir.exists():
            return jsonify({"erro": "Pasta de exports ausente — re-aprove a campanha."}), 410

        pngs = sorted(export_dir.glob(f"option{oid}*.png"))
        post_txt = export_dir / f"option{oid}_post.txt"
        if not pngs or not post_txt.exists():
            return jsonify({"erro": "Arquivos da opção aprovada ausentes."}), 410

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in pngs:
                zf.write(p, arcname=p.name)
            zf.writestr("legendas.txt", post_txt.read_text(encoding="utf-8"))
            zf.writestr("briefing.txt", _briefing_to_text(briefing))
        buf.seek(0)

        nome = f"{cid}_opcao{oid}.zip"
        return send_file(
            buf, mimetype="application/zip",
            as_attachment=True, download_name=nome,
        )

    @app.route("/api/campaigns/<cid>", methods=["DELETE"])
    def api_deletar(cid: str):
        """
        Apaga a campanha (DB + arquivos em disco). Operação destrutiva — a UI
        já confirma com o usuário antes de chamar.

        Recusa apagar enquanto status='gerando' (thread ativa pode reescrever
        o registro logo depois e deixar tudo inconsistente). Operador pode
        esperar a geração terminar ou cair em 'erro' antes de tentar de novo.
        """
        estado = _checar_posse(cid)
        if estado["status"] == "gerando":
            return jsonify({
                "erro": "Não dá pra apagar campanha em geração. Espere terminar ou cair em erro.",
            }), 409
        campaign_store.deletar(cid)
        utils.log(cid, "server: campanha apagada.")
        return jsonify({"status": "apagada", "campaign_id": cid})

    @app.route("/api/campaigns/<cid>/duplicate", methods=["POST"])
    def api_duplicate(cid: str):
        """
        Cria uma nova campanha reusando o briefing de uma existente.

        Gera novo campaign_id (data atual + sufixo se colidir), dispara geração.
        Não copia copy/imagens — a regeração via IA produz variações novas.
        Útil pra "quero outra rodada do mesmo tema" ou pivot de pequena escala.
        """
        _checar_posse(cid)
        if g.brand is None:
            return jsonify({"erro": "Escolha um brand antes de duplicar uma campanha."}), 400
        original = campaign_store.read_briefing(cid)
        try:
            quotas.verificar_pode_criar(g.brand.slug)
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

        campaign_store.criar(briefing, brand_slug=g.brand.slug)
        utils.log(briefing["campaign_id"], f"server: duplicado de {cid}, iniciando geração.")
        _iniciar_geracao_async(briefing)
        return jsonify({
            "campaign_id": briefing["campaign_id"],
            "duplicada_de": cid,
            "status": "gerando",
        }), 201

    @app.route("/api/campaigns/<cid>/adjust", methods=["POST"])
    def api_adjust(cid: str):
        _checar_posse(cid)
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
        _checar_posse(cid)
        body = request.get_json(force=True)
        option_id = int(body["option_id"])
        fields = body.get("fields", {})

        briefing = campaign_store.read_briefing(cid)
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
        composer.recompose_option(briefing, opcoes[idx], brand=g.brand)

        utils.log(cid, f"server: opção {option_id} editada manualmente e recomposta.")
        return jsonify(_campaign_payload(cid))

    # ---- Templates de briefing (presets reutilizáveis) ----
    @app.route("/api/templates", methods=["GET"])
    def api_templates_listar():
        if g.brand is None:
            return jsonify([])
        return jsonify(store.list_templates(brand_slug=g.brand.slug))

    @app.route("/api/templates", methods=["POST"])
    def api_templates_salvar():
        if g.brand is None:
            return jsonify({"erro": "Escolha um brand antes de salvar um template."}), 400
        body = request.get_json(force=True) or {}
        nome = (body.get("nome") or "").strip()
        if not nome:
            return jsonify({"erro": "Campo 'nome' é obrigatório."}), 400
        try:
            tpl = store.save_template(nome, body, brand_slug=g.brand.slug)
        except ValueError as e:
            return jsonify({"erro": str(e)}), 400
        return jsonify(tpl), 201

    @app.route("/api/templates/<int:template_id>", methods=["DELETE"])
    def api_templates_apagar(template_id: int):
        brand_slug = None if current_user.role == "admin" else (g.brand.slug if g.brand else None)
        if not store.delete_template(template_id, brand_slug=brand_slug):
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

    print(f"✓ Central de controle (login multi-brand) em {url}")
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
