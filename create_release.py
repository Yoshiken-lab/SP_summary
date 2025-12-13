#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
リリースパッケージ作成スクリプト

exeファイルと必要なファイルをまとめたリリースフォルダを作成します。

使い方:
    python create_release.py
"""

import shutil
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent


def create_release():
    """リリースパッケージを作成"""
    print('=' * 50)
    print('リリースパッケージ作成')
    print('=' * 50)

    # リリースフォルダ名
    release_name = f'SP_SalesSystem_{datetime.now().strftime("%Y%m%d")}'
    release_dir = BASE_DIR / 'release' / release_name

    # 既存のリリースフォルダがあれば削除
    if release_dir.exists():
        shutil.rmtree(release_dir)

    release_dir.mkdir(parents=True)

    print(f'\nリリースフォルダ: {release_dir}')

    # コピーするファイル/フォルダのリスト
    files_to_copy = [
        # exe
        ('dist/SP_SalesSystem.exe', 'SP_SalesSystem.exe'),
        # サーバー関連
        ('run_server.py', 'run_server.py'),
        ('config.py', 'config.py'),
        ('database.py', 'database.py'),
        ('dashboard.py', 'dashboard.py'),
        ('importer.py', 'importer.py'),
        ('main.py', 'main.py'),
        ('member_rate_chart.py', 'member_rate_chart.py'),
        ('member_rate_page.py', 'member_rate_page.py'),
        ('alerts.py', 'alerts.py'),
        # データベース
        ('schoolphoto.db', 'schoolphoto.db'),
    ]

    folders_to_copy = [
        ('app/backend', 'app/backend'),
        ('app/frontend/dist', 'app/frontend/dist'),
    ]

    # appフォルダの追加ファイル
    app_files = [
        ('app/__init__.py', 'app/__init__.py'),
        ('app/config.py', 'app/config.py'),
    ]

    # ファイルをコピー
    print('\nファイルをコピー中...')
    for src, dst in files_to_copy:
        src_path = BASE_DIR / src
        dst_path = release_dir / dst
        if src_path.exists():
            shutil.copy2(src_path, dst_path)
            print(f'  [OK] {src}')
        else:
            print(f'  [NG] {src} (見つかりません)')

    # フォルダをコピー
    print('\nフォルダをコピー中...')
    for src, dst in folders_to_copy:
        src_path = BASE_DIR / src
        dst_path = release_dir / dst
        if src_path.exists():
            # __pycache__を除外してコピー
            shutil.copytree(
                src_path, dst_path,
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'nul')
            )
            print(f'  [OK] {src}/')
        else:
            print(f'  [NG] {src}/ (見つかりません)')

    # appフォルダの追加ファイルをコピー
    print('\nappフォルダの追加ファイルをコピー中...')
    for src, dst in app_files:
        src_path = BASE_DIR / src
        dst_path = release_dir / dst
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if src_path.exists():
            shutil.copy2(src_path, dst_path)
            print(f'  [OK] {src}')
        else:
            print(f'  [NG] {src} (見つかりません)')

    # 使い方ファイルを作成
    readme_content = """スクールフォト 売上集計システム
================================

【使い方】
1. SP_SalesSystem.exe をダブルクリックして起動
2. 「サーバー起動」ボタンをクリック
3. 「ブラウザで開く」ボタンでWebアプリにアクセス

【注意事項】
- 初回起動時、Windowsファイアウォールの警告が出る場合があります
- 「プライベートネットワーク」へのアクセスを許可してください
- 終了時は必ず「サーバー停止」ボタンを押してから閉じてください

【アクセスURL】
http://127.0.0.1:8089

【必要環境】
- Windows 10/11
- Python 3.10以上（同梱のexeを使用する場合は不要）

【ファイル構成】
- SP_SalesSystem.exe : ランチャーアプリ
- run_server.py : サーバー起動スクリプト
- app/ : Webアプリケーション
- schoolphoto.db : データベース
"""

    readme_path = release_dir / 'README.txt'
    readme_path.write_text(readme_content, encoding='utf-8')
    print('\n  [OK] README.txt を作成')

    print('\n' + '=' * 50)
    print('リリースパッケージ作成完了！')
    print('=' * 50)
    print(f'\n出力先: {release_dir}')

    # サイズを計算
    total_size = sum(f.stat().st_size for f in release_dir.rglob('*') if f.is_file())
    print(f'合計サイズ: {total_size / 1024 / 1024:.1f} MB')

    return release_dir


if __name__ == '__main__':
    create_release()
