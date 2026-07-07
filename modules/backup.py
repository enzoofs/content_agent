"""
modules/backup.py — Snapshot diário do state.db dentro do volume persistente.

Por que existe:
    O state.db guarda TODAS as campanhas aprovadas. Em produção (Fly.io) vive
    no volume `/data`. Se o arquivo corromper (crash no meio de uma escrita,
    bug de migração, dedo gordo do operador), perde tudo. Snapshot diário cria
    cópias datadas em /data/backups/ e mantém só as N mais recentes.

Por que não usa cron / GitHub Actions:
    Container do Fly não tem cron. Subir GHA cron exige flyctl SSH + auth token
    fora do projeto. Thread daemon Python resolve dentro da própria app, zero
    infra extra.

Limitações honestas:
    - É backup LOCAL (mesmo volume do banco). Protege contra corrupção de
      arquivo, NÃO contra perda do volume inteiro. Pra off-site, o Enzo
      precisa puxar periodicamente via `flyctl ssh sftp` (instruções no doc).
    - Usa a API .backup() do sqlite3 — segura mesmo com escritas concorrentes
      (não é cópia bruta de arquivo).
"""
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from config import settings

# Onde os snapshots vivem. Em prod = /data/backups (volume Fly).
# Em dev local = ./backups (relativo ao BASE_DIR).
BACKUP_DIR = settings.BASE_DIR / "backups"

# Quantos snapshots manter. 14 dias cobre "operador notou ontem que algo tava
# errado anteontem" sem encher o volume de 1GB.
KEEP_LAST = 14

# Intervalo entre snapshots. 24h é suficiente — campanhas não somem do nada,
# e o operador notaria perda em horas, não minutos.
INTERVAL_SECONDS = 24 * 60 * 60


def snapshot_now() -> Path | None:
    """Cria 1 snapshot do state.db imediatamente. Retorna o caminho ou None."""
    src = settings.STATE_DB_PATH
    if not src.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    dst = BACKUP_DIR / f"state-{stamp}.db"

    # sqlite3.Connection.backup() é seguro durante escritas (vs. shutil.copy
    # que pode pegar arquivo no meio de uma transação)
    src_con = sqlite3.connect(src, timeout=10.0)
    dst_con = sqlite3.connect(dst)
    try:
        src_con.backup(dst_con)
    finally:
        dst_con.close()
        src_con.close()

    _cleanup_old_snapshots()
    return dst


def _cleanup_old_snapshots() -> None:
    """Mantém só os KEEP_LAST snapshots mais recentes."""
    if not BACKUP_DIR.exists():
        return
    snaps = sorted(
        BACKUP_DIR.glob("state-*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in snaps[KEEP_LAST:]:
        try:
            old.unlink()
        except OSError:
            pass


def start_background_scheduler() -> None:
    """
    Sobe uma thread daemon que tira snapshot a cada INTERVAL_SECONDS.

    Daemon=True: morre junto com o processo (não trava shutdown).
    Faz um snapshot logo no boot pra garantir pelo menos 1 cópia recente
    mesmo se o container reiniciar antes de completar 24h.
    """
    def loop():
        # Snapshot inicial no boot — atrasado 60s pra não brigar com migração
        # de banco que roda no startup.
        time.sleep(60)
        while True:
            try:
                snapshot_now()
            except Exception as e:
                # Backup não pode derrubar a app. Loga e segue.
                print(f"⚠ backup falhou: {e}")
            time.sleep(INTERVAL_SECONDS)

    t = threading.Thread(target=loop, name="backup-scheduler", daemon=True)
    t.start()
