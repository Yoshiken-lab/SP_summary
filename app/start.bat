@echo off
chcp 65001 > nul
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║  スクールフォト 売上集計システム                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM Pythonの確認
python --version > nul 2>&1
if errorlevel 1 (
    echo [エラー] Pythonがインストールされていません
    pause
    exit /b 1
)

REM 依存パッケージのインストール確認
echo 依存パッケージを確認中...
pip show flask > nul 2>&1
if errorlevel 1 (
    echo 依存パッケージをインストール中...
    pip install -r requirements.txt
)

REM ポート設定（デフォルト: 8080）
if "%PORT%"=="" set PORT=8080

echo.
echo サーバーを起動します...
echo URL: http://127.0.0.1:%PORT%
echo.
echo ブラウザが自動で開かない場合は、上記URLにアクセスしてください。
echo 停止するには Ctrl+C を押してください。
echo.

REM ブラウザを開く
start http://127.0.0.1:%PORT%

REM サーバー起動
python run.py --port %PORT%

pause
