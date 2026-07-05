"""
scripts/seed_users.py — Cria os usuários iniciais de login (seed idempotente).

Cria 3 contas: Henrique (mendes_vaz/cliente), Gui (gui_raw/cliente) e um
admin (sem brand fixo, alterna entre todos). Os emails abaixo são
PLACEHOLDER — edite antes de rodar. Senhas são geradas aleatoriamente e
impressas no console uma única vez; nunca ficam no código nem em arquivo.

Uso:
    python -m scripts.seed_users
"""

from __future__ import annotations

import secrets
import sys

from werkzeug.security import generate_password_hash

from modules import store, users_store

# EDITE os emails antes de rodar em produção.
SEEDS = [
    {"email": "henrique@exemplo.com", "brand_slug": "mendes_vaz", "role": "cliente"},
    {"email": "gui@exemplo.com", "brand_slug": "gui_raw", "role": "cliente"},
    {"email": "admin@exemplo.com", "brand_slug": None, "role": "admin"},
]


def main() -> int:
    store.init_db()

    for seed in SEEDS:
        existente = users_store.get_by_email(seed["email"])
        if existente is not None:
            print(f"  PULADO (já existe): {seed['email']}")
            continue

        senha = secrets.token_urlsafe(12)
        senha_hash = generate_password_hash(senha)
        users_store.criar_usuario(
            email=seed["email"],
            senha_hash=senha_hash,
            brand_slug=seed["brand_slug"],
            role=seed["role"],
        )
        print(f"  OK: {seed['email']} (role={seed['role']}) — senha: {senha}")

    print("\nGuarde as senhas acima com segurança — não ficam salvas em lugar nenhum.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
