@echo off
chcp 65001 > nul
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║  スクールフォト 売上集計システム（開発モード）              ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo このスクリプトは開発用です。
echo Flask APIとVite開発サーバーを同時に起動します。
echo.

cd /d "%~dp0"

REM Flask API起動（バックグラウンド）
echo [1/2] Flask APIを起動中...
start "Flask API" cmd /c "python run.py --port 8080 --debug"

REM 少し待機
timeout /t 2 > nul

REM Vite開発サーバー起動
echo [2/2] Vite開発サーバーを起動中...
cd frontend

REM node_modulesの確認
if not exist "node_modules" (
    echo npm パッケージをインストール中...
    call npm install
)

echo.
echo フロントエンド: http://localhost:5173
echo バックエンドAPI: http://localhost:8080
echo.

call npm run dev
