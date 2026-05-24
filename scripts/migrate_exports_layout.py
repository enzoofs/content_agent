"""
scripts/migrate_exports_layout.py — Migra exports/ do layout flat pro layout por campanha.

Antes (flat):
    exports/{cid}_option{N}_approved.png
    exports/{cid}_option{N}_metadata.json
    exports/{cid}_option{N}_post.txt
    exports/{cid}_option{N}_slide{M}_approved.png  (carrossel)

Depois (subpasta):
    exports/{cid}/option{N}.png
    exports/{cid}/option{N}_metadata.json
    exports/{cid}/option{N}_post.txt
    exports/{cid}/option{N}_slide{M}.png

Preserva:
    exports/audit.jsonl  (continua na raiz — log central)

Uso:
    python -m scripts.migrate_exports_layout            # dry-run, mostra plano
    python -m scripts.migrate_exports_layout --apply    # executa
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from config import settings

# Regex pra parsear nomes do layout antigo. _option<N> é o separador chave.
# Formatos esperados:
#   <cid>_option<N>_approved.png             -> option<N>.png
#   <cid>_option<N>_slide<M>_approved.png    -> option<N>_slide<M>.png
#   <cid>_option<N>_metadata.json            -> option<N>_metadata.json
#   <cid>_option<N>_post.txt                 -> option<N>_post.txt
_PATTERNS = [
    (re.compile(r"^(?P<cid>.+?)_option(?P<n>\d+)_slide(?P<m>\d+)_approved\.png$"),
     lambda m: f"option{m['n']}_slide{m['m']}.png"),
    (re.compile(r"^(?P<cid>.+?)_option(?P<n>\d+)_approved\.png$"),
     lambda m: f"option{m['n']}.png"),
    (re.compile(r"^(?P<cid>.+?)_option(?P<n>\d+)_metadata\.json$"),
     lambda m: f"option{m['n']}_metadata.json"),
    (re.compile(r"^(?P<cid>.+?)_option(?P<n>\d+)_post\.txt$"),
     lambda m: f"option{m['n']}_post.txt"),
]


def planejar(exports_dir: Path) -> list[tuple[Path, Path]]:
    """Devolve lista de (origem, destino) pra arquivos no layout antigo."""
    movimentos: list[tuple[Path, Path]] = []
    for arquivo in exports_dir.iterdir():
        if not arquivo.is_file():
            continue  # subpastas (já migradas) e audit.jsonl ficam de fora
        if arquivo.name == "audit.jsonl":
            continue
        for regex, novo_nome in _PATTERNS:
            m = regex.match(arquivo.name)
            if m:
                destino = exports_dir / m["cid"] / novo_nome(m)
                movimentos.append((arquivo, destino))
                break
    return movimentos


def aplicar(movimentos: list[tuple[Path, Path]]) -> None:
    """Move cada arquivo, criando subpasta se necessário."""
    for origem, destino in movimentos:
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            print(f"  PULADO (já existe): {destino.relative_to(settings.EXPORTS_DIR)}")
            continue
        origem.rename(destino)
        print(f"  OK: {origem.name} -> {destino.relative_to(settings.EXPORTS_DIR)}")


def main() -> int:
    apply_mode = "--apply" in sys.argv
    exports_dir = settings.EXPORTS_DIR
    if not exports_dir.exists():
        print(f"exports/ não existe em {exports_dir}.")
        return 0

    movimentos = planejar(exports_dir)
    if not movimentos:
        print("Nada a migrar — exports/ já está no novo layout.")
        return 0

    print(f"{'APLICANDO' if apply_mode else 'DRY-RUN'} — {len(movimentos)} arquivo(s):")
    if not apply_mode:
        for origem, destino in movimentos:
            print(f"  {origem.name} -> {destino.relative_to(exports_dir)}")
        print("\nRode com --apply para executar.")
        return 0

    aplicar(movimentos)
    print(f"\nMigração concluída — {len(movimentos)} arquivo(s) reorganizado(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
