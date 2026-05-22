"""
main.py — Entry point do pipeline Mendes & Vaz Social (Fase 1).

Orquestra: briefing -> copy (OpenAI) -> arte (Ideogram/mock) -> composição
(Playwright) -> aprovação (Flask) -> export PNG.

Uso:
    python main.py --campaign novo
    python main.py --campaign 2026-05-22_direito-medico --from image
    python main.py --approve 2026-05-22_direito-medico

Flags --from: briefing | copy | image | compose
"""

from __future__ import annotations

import argparse
import json
import sys

from config import settings
from modules import (
    approval_server,
    briefing_parser,
    composer,
    copy_generator,
    image_generator,
    utils,
)


# --------------------------------------------------------------------------
# Briefing interativo no terminal
# --------------------------------------------------------------------------
def _escolha(prompt: str, opcoes: dict[str, str]) -> str:
    """Pergunta uma opção numerada e devolve o valor mapeado."""
    print(prompt)
    for k, (rotulo, _v) in opcoes.items():
        print(f"   [{k}] {rotulo}")
    while True:
        escolha = input("   > ").strip()
        if escolha in opcoes:
            return opcoes[escolha][1]
        print("   Opção inválida. Tente novamente.")


def collect_briefing_interactively() -> dict:
    """Coleta o briefing via prompts no terminal (formulário da spec)."""
    print("\n=== NOVA CAMPANHA — MENDES & VAZ ===\n")

    area = input("1. Área do direito desta campanha:\n   > ").strip()
    perfil = input("\n2. Perfil do cliente ideal que queremos atrair:\n   > ").strip()

    tom = _escolha(
        "\n3. Tom da comunicação:",
        {"1": ("Técnico / Autoridade", "tecnico"),
         "2": ("Acessível / Educativo", "acessivel")},
    )
    objetivo = _escolha(
        "\n4. Objetivo principal:",
        {"1": ("Awareness (fazer o escritório ser conhecido)", "awareness"),
         "2": ("Captação (gerar leads diretos)", "captacao"),
         "3": ("Posicionamento (reforçar expertise)", "posicionamento")},
    )
    formato = _escolha(
        "\n5. Formato do post:",
        {"1": ("Square (1080×1080) — Feed Instagram e LinkedIn", "square"),
         "2": ("Portrait (1080×1350) — Feed Instagram, maior alcance", "portrait"),
         "3": ("Carrossel (múltiplos slides)", "carousel")},
    )

    num_slides = 1
    if formato == "carousel":
        while True:
            try:
                num_slides = int(input("\n   Quantos slides? (3 a 8):\n   > ").strip())
                if 3 <= num_slides <= 8:
                    break
            except ValueError:
                pass
            print("   Valor inválido. Informe um número de 3 a 8.")

    tema = input("\n6. Tema específico ou pauta (deixe em branco para a IA escolher):\n   > ").strip()
    referencias = input("\n7. Referências ou observações livres (deixe em branco se não houver):\n   > ").strip()

    return {
        "area_direito": area,
        "perfil_cliente_ideal": perfil,
        "tom": tom,
        "objetivo": objetivo,
        "formato": formato,
        "num_slides": num_slides,
        "tema_especifico": tema,
        "referencias": referencias,
    }


# --------------------------------------------------------------------------
# Persistência / carregamento de artefatos da campanha
# --------------------------------------------------------------------------
def _salvar_briefing(briefing: dict) -> None:
    destino = utils.campaign_dir(briefing["campaign_id"]) / "briefing.json"
    destino.write_text(json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8")


def _carregar_briefing(campaign_id: str) -> dict:
    arq = settings.CAMPAIGNS_DIR / campaign_id / "briefing.json"
    if not arq.exists():
        sys.exit(f"❌ briefing.json não encontrado para a campanha {campaign_id}.")
    return json.loads(arq.read_text(encoding="utf-8"))


def _carregar_copy(campaign_id: str) -> list[dict]:
    arq = settings.CAMPAIGNS_DIR / campaign_id / "copy_v1.json"
    if not arq.exists():
        sys.exit(f"❌ copy_v1.json não encontrado para a campanha {campaign_id}.")
    return json.loads(arq.read_text(encoding="utf-8"))


def _image_paths(campaign_id: str, copy_options: list[dict]) -> list:
    img_dir = settings.CAMPAIGNS_DIR / campaign_id / "images"
    return [img_dir / f"option_{c['option_id']}.png" for c in copy_options]


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------
def run_pipeline(briefing: dict, from_step: str = "briefing") -> None:
    """Roda o pipeline a partir da etapa indicada e abre a aprovação."""
    campaign_id = briefing["campaign_id"]
    ordem = ["briefing", "copy", "image", "compose"]
    inicio = ordem.index(from_step)

    # Copy
    if inicio <= ordem.index("copy"):
        print("⟳ Gerando variações de copy com OpenAI...")
        copy_options = copy_generator.generate(briefing)
    else:
        copy_options = _carregar_copy(campaign_id)

    # Imagens
    if inicio <= ordem.index("image"):
        modo = "placeholder" if settings.USE_MOCK_IMAGES else "Ideogram"
        print(f"⟳ Gerando artes ({modo})...")
        image_paths = image_generator.generate(copy_options, briefing["formato"], campaign_id)
    else:
        image_paths = _image_paths(campaign_id, copy_options)

    # Composição
    print("⟳ Compondo posts finais...")
    composer.compose_all(copy_options, image_paths, briefing)

    # Aprovação
    print(f"✓ Abrindo interface de aprovação em http://{settings.APPROVAL_HOST}:{settings.APPROVAL_PORT}")
    approval_server.serve(campaign_id)


def run_new_campaign() -> None:
    """Coleta briefing, valida, salva e roda o pipeline completo."""
    raw = collect_briefing_interactively()
    briefing = briefing_parser.parse(raw)
    _salvar_briefing(briefing)
    print(f"\n✓ Campanha: {briefing['campaign_id']}\n")
    run_pipeline(briefing, from_step="briefing")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline Mendes & Vaz Social")
    parser.add_argument("--campaign", help='"novo" ou um campaign_id existente')
    parser.add_argument(
        "--from",
        dest="from_step",
        choices=["briefing", "copy", "image", "compose"],
        default="briefing",
        help="Etapa a partir da qual retomar",
    )
    parser.add_argument("--approve", help="Abre só a aprovação de um campaign_id")
    args = parser.parse_args()

    if args.approve:
        approval_server.serve(args.approve)
        return

    if not args.campaign:
        parser.print_help()
        sys.exit("\n❌ Informe --campaign novo, --campaign <id> --from <etapa>, ou --approve <id>.")

    if args.campaign == "novo":
        run_new_campaign()
    else:
        briefing = _carregar_briefing(args.campaign)
        run_pipeline(briefing, from_step=args.from_step)


if __name__ == "__main__":
    main()
