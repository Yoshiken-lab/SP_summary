from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import argparse

# 公開ディレクトリ設定
WEB_DIR = 'public_dashboards'
DEFAULT_PORT = 8000

class NoCacheRequestHandler(SimpleHTTPRequestHandler):
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
    args = parser.parse_args()
    
    # カレントディレクトリを移動（public_dashboardsの一つ上を想定）
    if os.path.exists(WEB_DIR):
        os.chdir(WEB_DIR)
        
    server_address = ('', args.port)
    httpd = HTTPServer(server_address, NoCacheRequestHandler)
    print(f"========================================================")
    print(f"  Dashboard Server (No-Cache Mode) Started")
    print(f"  Port: {args.port}")
    print(f"========================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
