"""
main.py — Entry point do sistema Mendes & Vaz Social.

Caminho principal (recomendado) — sobe a Central de Controle web, onde o
Henrique cria campanhas, acompanha a geração, agenda e aprova:

    python main.py --serve

Caminho de terminal (debug) — gera uma campanha pela linha de comando e a
deixa pronta para aprovação na central:

    python main.py --campaign novo
"""

from __future__ import annotations

import argparse
import sys

from modules import briefing_parser, campaign_store, pipeline, server


# --------------------------------------------------------------------------
# Briefing interativo no terminal (caminho de debug)
# --------------------------------------------------------------------------
def _escolha(prompt: str, opcoes: dict[str, tuple[str, str]]) -> str:
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


def run_new_campaign_terminal() -> None:
    """Coleta briefing, valida, cria e gera a campanha (deixa pronta para aprovação)."""
    raw = collect_briefing_interactively()
    briefing = briefing_parser.parse(raw)
    campaign_store.criar(briefing)
    print(f"\n✓ Campanha: {briefing['campaign_id']}")
    print("⟳ Gerando (copy → arte → composição)...")
    pipeline.gerar(briefing)
    print("✓ Geração concluída.")
    print("  Rode 'python main.py --serve' e abra a central para aprovar.")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Mendes & Vaz Social")
    parser.add_argument(
        "--serve", action="store_true",
        help="Sobe a Central de Controle web (recomendado)",
    )
    parser.add_argument(
        "--campaign",
        help='Gera uma campanha pelo terminal: use "novo"',
    )
    args = parser.parse_args()

    if args.serve:
        server.serve()
        return

    if args.campaign == "novo":
        run_new_campaign_terminal()
        return

    parser.print_help()
    sys.exit('\n❌ Use --serve (central web) ou --campaign novo (terminal).')


if __name__ == "__main__":
    main()
