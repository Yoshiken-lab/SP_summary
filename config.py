"""
アプリケーション設定（ルートレベル）
"""
import os
from pathlib import Path


class Config:
    """アプリケーション設定クラス"""

    # サーバー設定
    HOST = os.getenv('HOST', '127.0.0.1')
    PORT = int(os.getenv('PORT', 8089))
    DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'

    # パス設定
    BASE_DIR = Path(__file__).parent
    APP_DIR = BASE_DIR / 'app'
    DB_PATH = BASE_DIR / 'schoolphoto.db'
    OUTPUT_DIR = Path.home() / 'Downloads'
    UPLOAD_DIR = APP_DIR / 'uploads'

    # ダッシュボード公開先（ローカルサーバー公開用）
    PUBLISH_PATH = APP_DIR / 'public_dashboards'
    PUBLISH_FILENAME = 'index.html'

    # GitHub Pages公開設定
    GITHUB_PAGES_REPO_PATH = BASE_DIR / 'sp-dashboard'  # sp-dashboardフォルダのパス
    GITHUB_PAGES_URL = 'https://yoshiken-lab.github.io/sp-dashboard/'

    # ファイルエンコーディング
    CSV_ENCODING = 'cp932'

    # 許可するファイル拡張子
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

    # 最大ファイルサイズ（100MB）
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024

    # 担当者リスト（学校担当者設定で使用）　WEBアプリで使用するリスト※今は使用してない
    MANAGERS = [
        '三室',
        '佐藤（恵）',
        '佐藤（邦）',
        '兵藤',
        '宇梶',
        '小井土',
        '小池',
        '成田',
        '早乙女',
        '星野',
        '春山',
        '林',
        '池田',
        '田中',
        '若林',
        '遅澤',
        '野口',
        '金子',
        '金子（茨）',
    ]

    # 担当者表示順（月次集計Excelでの出力順）
    # 報告書フォーマットに合わせた順序
    MANAGER_DISPLAY_ORDER = [
        '早乙女',
        '金子（貴）',
        '宇梶',
        '三室',
        '林',
        '池田',
        '星野',
        '若林',
        '廣瀬',
        '兵藤',
        '金子（孝）',
        '佐藤（邦）',
        '瀬端',
        '成田',
        '佐藤（恵）',
        '春山',
        '野口',
        '小池',
        '田中',
    ]

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
