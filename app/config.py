"""
アプリケーション設定
"""
import os
from pathlib import Path


class Config:
    """アプリケーション設定クラス"""

    # サーバー設定
    HOST = os.getenv('HOST', '127.0.0.1')
    PORT = int(os.getenv('PORT', 8080))
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'

    # パス設定
    APP_DIR = Path(__file__).parent
    BASE_DIR = APP_DIR.parent
    DB_PATH = BASE_DIR / 'schoolphoto.db'
    OUTPUT_DIR = Path.home() / 'Downloads'
    UPLOAD_DIR = APP_DIR / 'uploads'

    # ダッシュボード公開先（ローカルサーバー公開用）
    PUBLISH_PATH = APP_DIR / 'public_dashboards'
    PUBLISH_FILENAME = 'dashboard.html'

    # GitHub Pages公開設定
    GITHUB_PAGES_REPO_PATH = BASE_DIR / 'sp-dashboard'  # sp-dashboardフォルダのパス
    GITHUB_PAGES_URL = 'https://yoshiken-lab.github.io/sp-dashboard/'

    # ファイルエンコーディング
    CSV_ENCODING = 'cp932'

    # 許可するファイル拡張子
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

    # 最大ファイルサイズ（16MB）
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    @classmethod
    def init_app(cls):
        """アプリケーション初期化時の設定"""
        # アップロードディレクトリ作成
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    """開発環境設定"""
    DEBUG = True


class ProductionConfig(Config):
    """本番環境設定"""
    DEBUG = False


# 設定マッピング
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    """現在の設定を取得"""
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])
