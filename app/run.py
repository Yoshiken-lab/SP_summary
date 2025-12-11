"""
アプリケーション起動スクリプト
"""
import argparse
import sys
import os
from pathlib import Path

# パス設定
APP_DIR = Path(__file__).parent
BASE_DIR = APP_DIR.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(APP_DIR))


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='スクールフォト売上管理システム'
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=int(os.getenv('PORT', 8080)),
        help='サーバーポート番号（デフォルト: 8080）'
    )
    parser.add_argument(
        '--host',
        type=str,
        default=os.getenv('HOST', '127.0.0.1'),
        help='ホストアドレス（デフォルト: 127.0.0.1）'
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
    from backend.api import create_app
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
