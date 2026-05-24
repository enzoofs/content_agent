"""
Fixtures globais — isolam cada teste num state.db próprio em tmp.

Sem isso, testes rodando em paralelo (ou em sequência) compartilhariam o DB
real do projeto e poluiriam o estado.
"""

from __future__ import annotations

import pytest

from config import settings
from modules import store


@pytest.fixture(autouse=True)
def _db_isolado(tmp_path, monkeypatch):
    """
    Aponta STATE_DB_PATH pra um arquivo em tmp_path por teste.

    `autouse=True` significa que TODO teste herda esse isolamento — assim
    nenhum teste pode acidentalmente escrever no state.db de produção.
    """
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(settings, "STATE_DB_PATH", db_path)
    store.init_db()
    yield db_path
