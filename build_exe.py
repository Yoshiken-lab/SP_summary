#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exe化ビルドスクリプト

PyInstallerを使ってランチャーをexe化します。

使い方:
    python build_exe.py
"""

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent


def check_pyinstaller():
    """PyInstallerがインストールされているか確認"""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False


def install_pyinstaller():
    """PyInstallerをインストール"""
    print('PyInstallerをインストール中...')
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
    print('インストール完了')


def build_exe():
    """exeファイルをビルド"""
    print('=' * 50)
    print('スクールフォト売上集計システム - exe化')
    print('=' * 50)

    # PyInstallerの確認
    if not check_pyinstaller():
        install_pyinstaller()

    # ビルドコマンド
    launcher_path = BASE_DIR / 'launcher.py'
    icon_path = BASE_DIR / 'icon.ico'

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',           # 単一exeファイル
        '--windowed',          # コンソールウィンドウを表示しない
        '--name', 'SP_SalesSystem',  # 出力ファイル名
        '--clean',             # ビルド前にキャッシュをクリア
    ]

    # アイコンがあれば追加
    if icon_path.exists():
        cmd.extend(['--icon', str(icon_path)])

    # 追加データ（run_server.pyなど）
    # PyInstallerはランチャーのみexe化し、
    # 実際のサーバーは別プロセスで起動するため、
    # 他のファイルはexeと同じフォルダに配置する必要がある

    cmd.append(str(launcher_path))

    print(f'\nビルドコマンド: {" ".join(cmd)}\n')

    # ビルド実行
    subprocess.check_call(cmd, cwd=str(BASE_DIR))

    print('\n' + '=' * 50)
    print('ビルド完了！')
    print('=' * 50)
    print(f'\n出力先: {BASE_DIR / "dist" / "SP_SalesSystem.exe"}')
    print('\n【重要】exe実行時に必要なファイル:')
    print('  以下のファイル/フォルダをexeと同じ場所にコピーしてください:')
    print('  - run_server.py')
    print('  - app/ (フロントエンド・バックエンド)')
    print('  - config.py')
    print('  - database.py')
    print('  - dashboard.py')
    print('  - importer.py')
    print('  - member_rate_chart.py')
    print('  - main.py')
    print('  - schoolphoto.db (データベース)')


if __name__ == '__main__':
    build_exe()
