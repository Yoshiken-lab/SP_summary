from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import argparse
from datetime import datetime

# 公開ディレクトリ設定
WEB_DIR = 'public_dashboards'
DEFAULT_PORT = 8000

class NoCacheRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # 要求ログは「時刻 + アクセス元IP」のみ出力
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        client_ip = self.client_address[0] if self.client_address else '-'
        print(f"[ACCESS] {timestamp} {client_ip}", flush=True)

    def handle(self):
        # クライアント切断時のスタックトレースを抑制
        try:
            super().handle()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

    def end_headers(self):
        # キャッシュ無効化ヘッダーを追加
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

if __name__ == '__main__':
    # コマンドライン引数のパース
    parser = argparse.ArgumentParser(
        description='ダッシュボード公開用HTTPサーバー（キャッシュ無効化）'
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=DEFAULT_PORT,
        help=f'サーバーポート番号（デフォルト: {DEFAULT_PORT}）'
    )
    parser.add_argument(
        '--host',
        type=str,
        default=os.getenv('HOST', '0.0.0.0'),
        help='バインドホスト（デフォルト: 0.0.0.0）'
    )
    args = parser.parse_args()
    
    # カレントディレクトリを移動（public_dashboardsの一つ上を想定）
    if os.path.exists(WEB_DIR):
        os.chdir(WEB_DIR)
        
    server_address = (args.host, args.port)
    httpd = HTTPServer(server_address, NoCacheRequestHandler)
    print(f"========================================================", flush=True)
    print(f"  Dashboard Server (No-Cache Mode) Started", flush=True)
    print(f"  Host: {args.host}", flush=True)
    print(f"  Port: {args.port}", flush=True)
    print(f"========================================================", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
