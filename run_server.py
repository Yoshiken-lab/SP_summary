#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
サーバー起動スクリプト

使い方:
    python run_server.py [--port PORT] [--host HOST] [--debug]
"""

import argparse
import sys
import os
from pathlib import Path

# パス設定
BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / 'app'
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(APP_DIR))

# デフォルト設定
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8089


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='スクールフォト売上集計システム サーバー'
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=int(os.getenv('PORT', DEFAULT_PORT)),
        help=f'サーバーポート番号（デフォルト: {DEFAULT_PORT}）'
    )
    parser.add_argument(
        '--host',
        type=str,
        default=os.getenv('HOST', DEFAULT_HOST),
        help=f'ホストアドレス（デフォルト: {DEFAULT_HOST}）'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='デバッグモードで起動'
    )

    args = parser.parse_args()

    # 環境変数に設定
    os.environ['PORT'] = str(args.port)
    os.environ['HOST'] = args.host
    if args.debug:
        os.environ['DEBUG'] = 'true'

    # アプリケーション作成
    from app.backend.api import create_app
    app = create_app()

    print(f"""
============================================================
  スクールフォト 売上集計システム
============================================================
  サーバー起動中...
  URL: http://{args.host}:{args.port}

  停止するには Ctrl+C を押してください
============================================================
    """)

    # サーバー起動
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )


if __name__ == '__main__':
    main()
