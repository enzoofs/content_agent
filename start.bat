@echo off
REM ==========================================================================
REM start.bat - Sobe tudo que precisa pra demo numa tacada so.
REM   1) Servidor Flask em http://localhost:5000  (janela "content_agent")
REM   2) Tunel ngrok publico                       (janela "ngrok")
REM   3) Abre o navegador na UI local
REM
REM Pre-requisito (1x): venv criado e deps instaladas. Se nao, ver
REM docs\manual-reuniao.md secao 1.
REM ==========================================================================

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERRO] venv nao encontrado em "%~dp0venv".
    echo Rode primeiro:
    echo     python -m venv venv
    echo     venv\Scripts\activate.bat
    echo     python -m pip install -r requirements.txt
    echo     playwright install chromium
    pause
    exit /b 1
)

echo [1/3] Subindo servidor Flask em nova janela...
start "content_agent server" cmd /k "call venv\Scripts\activate.bat && set PYTHONIOENCODING=utf-8 && python main.py --serve"

echo [2/3] Subindo tunel ngrok em nova janela...
start "ngrok tunnel" cmd /k "ngrok http 5000"

echo [3/3] Esperando 5s e abrindo o navegador...
timeout /t 5 /nobreak >nul
start "" "http://localhost:5000"

echo.
echo Pronto. Para parar tudo: feche as 2 janelas que abriram.
echo Link publico (ngrok): olhe a janela "ngrok tunnel" — linha "Forwarding".
echo Painel ngrok de requests: http://127.0.0.1:4040
