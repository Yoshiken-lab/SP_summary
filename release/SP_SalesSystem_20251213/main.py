#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上分析システム - メインスクリプト

使い方:
    # 新しいExcelファイルを取り込む
    python main.py import <Excelファイル>

    # ディレクトリ内の全ファイルを取り込む
    python main.py import <ディレクトリ> --all

    # ダッシュボードを生成
    python main.py dashboard [出力ファイル名]

    # ダッシュボードを生成してファイルサーバーに公開
    python main.py publish

    # DB初期化（既存データ削除）
    python main.py init --force
"""

import sys
import os
import shutil
from pathlib import Path

# 現在のディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from database import init_database, DEFAULT_DB_PATH
from importer import import_excel, import_all_from_directory, sync_school_master
from dashboard import generate_html_dashboard
from member_rate_page import generate_member_rate_page

# ファイルサーバーの公開先パス
PUBLISH_PATH = Path(r"\\192.168.11.51\homes\dashboard")
PUBLISH_FILENAME = "dashboard.html"


def show_help():
    print(__doc__)
    print("コマンド一覧:")
    print("  import <ファイル/ディレクトリ> [--all]  - Excelデータを取り込み")
    print("  dashboard [出力ファイル]                - ダッシュボード生成")
    print("  publish                                 - ダッシュボード生成＆ファイルサーバーに公開")
    print("  chart [出力ファイル]                    - 会員率推移グラフページ生成")
    print("  all                                     - 全ページ生成")
    print("  init [--force]                          - DB初期化")
    print("  status                                  - DB状態確認")
    print("  sync-master <マスタファイル>            - 学校マスタ同期")


def publish_dashboard():
    """ダッシュボード生成＆ファイルサーバーに公開"""
    print("ダッシュボードを生成中...")
    local_path = generate_html_dashboard()
    print(f"  ローカル: {local_path}")

    # ファイルサーバーにコピー
    if not PUBLISH_PATH.exists():
        PUBLISH_PATH.mkdir(parents=True, exist_ok=True)
        print(f"  フォルダを作成しました: {PUBLISH_PATH}")

    dest_path = PUBLISH_PATH / PUBLISH_FILENAME
    shutil.copy2(local_path, dest_path)
    print(f"  公開先: {dest_path}")
    print(f"\n公開完了！")
    print(f"アクセスURL: {dest_path}")
    return dest_path


def show_status():
    """DBの状態を表示"""
    import sqlite3

    if not DEFAULT_DB_PATH.exists():
        print("データベースが存在しません。")
        print("先に `python main.py import <ディレクトリ> --all` でデータを取り込んでください。")
        return

    conn = sqlite3.connect(DEFAULT_DB_PATH)
    cursor = conn.cursor()

    print("=" * 50)
    print("データベース状態")
    print("=" * 50)

    tables = ['reports', 'schools', 'events', 'member_rates']
    for table in tables:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f"  {table}: {count:,}件")

    cursor.execute('SELECT MIN(report_date), MAX(report_date) FROM reports')
    row = cursor.fetchone()
    if row[0]:
        print(f"\n  データ期間: {row[0]} ～ {row[1]}")

    conn.close()


def main():
    if len(sys.argv) < 2:
        show_help()
        return

    command = sys.argv[1].lower()

    if command == 'import':
        if len(sys.argv) < 3:
            print("エラー: 取り込み対象を指定してください")
            return

        target = sys.argv[2]

        if '--all' in sys.argv:
            import_all_from_directory(target)
        else:
            import_excel(target)

    elif command == 'dashboard':
        output = sys.argv[2] if len(sys.argv) > 2 else None
        path = generate_html_dashboard(output_path=output)
        print(f"ダッシュボードを生成しました: {path}")

    elif command == 'publish':
        # ダッシュボード生成＆ファイルサーバーに公開
        try:
            publish_dashboard()
        except Exception as e:
            print(f"\nエラー: ファイルサーバーへのコピーに失敗しました")
            print(f"  {e}")

    elif command == 'chart':
        output = sys.argv[2] if len(sys.argv) > 2 else None
        path = generate_member_rate_page(output_path=output)
        print(f"会員率推移グラフページを生成しました: {path}")

    elif command == 'all':
        # 全ページ生成
        dashboard_path = generate_html_dashboard()
        chart_path = generate_member_rate_page()
        print(f"生成完了:")
        print(f"  ダッシュボード: {dashboard_path}")
        print(f"  会員率推移グラフ: {chart_path}")

    elif command == 'init':
        if '--force' in sys.argv:
            if DEFAULT_DB_PATH.exists():
                os.remove(DEFAULT_DB_PATH)
                print("既存のDBを削除しました")
            init_database()
        else:
            print("警告: このコマンドは既存データを削除します")
            print("続行するには `python main.py init --force` を実行してください")

    elif command == 'status':
        show_status()

    elif command == 'sync-master':
        if len(sys.argv) < 3:
            print("エラー: マスタファイルを指定してください")
            print("使い方: python main.py sync-master <マスタファイル.xlsx>")
            return
        master_file = sys.argv[2]
        sync_school_master(master_file)

    elif command in ['help', '-h', '--help']:
        show_help()

    else:
        print(f"不明なコマンド: {command}")
        show_help()


if __name__ == '__main__':
    main()
