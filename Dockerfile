# Imagem oficial Playwright com Chromium + deps já instalados.
# Evita 200MB+ de apt-get install e bugs de fonte/libs faltando.
FROM mcr.microsoft.com/playwright/python:v1.60.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APPROVAL_HOST=0.0.0.0 \
    APPROVAL_PORT=8080

WORKDIR /app

# Dependências Python primeiro (cache de layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY . .

# Dados persistentes ficam em /data (volume do Fly).
# Symlinks redirecionam state.db + campaigns/ + exports/ pra lá SEM mudar código.
# Na primeira subida o entrypoint cria os destinos se não existirem.
RUN rm -f state.db && rm -rf campaigns exports backups && \
    ln -s /data/state.db   /app/state.db && \
    ln -s /data/campaigns  /app/campaigns && \
    ln -s /data/exports    /app/exports && \
    ln -s /data/backups    /app/backups

EXPOSE 8080

# Garante que /data tenha a estrutura mínima antes de subir o Flask
CMD mkdir -p /data/campaigns /data/exports /data/backups && \
    touch /data/state.db && \
    python main.py --serve
