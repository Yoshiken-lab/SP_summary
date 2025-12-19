"""
データベースサービス
既存のimporter.pyとdashboard.pyを活用
"""
import sys
from pathlib import Path
from typing import Optional
import logging

# 親ディレクトリをパスに追加（既存モジュールをインポートするため）
BASE_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    データベース操作サービス

    既存のimporter.py, dashboard.pyを活用してDB保存・ダッシュボード生成を行う
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Args:
            db_path: データベースファイルパス
        """
        self.db_path = db_path or BASE_DIR / "schoolphoto.db"

    def save_to_database(self, excel_path: Path) -> bool:
        """
        集計結果をデータベースに保存

        Args:
            excel_path: 集計結果Excelファイルパス

        Returns:
            bool: 成功/失敗
        """
        try:
            # 既存のimporterを使用
            from importer import import_excel

            import_excel(str(excel_path))
            logger.info(f"データベース保存完了: {excel_path}")
            return True

        except ImportError as e:
            logger.error(f"importer.pyのインポートに失敗: {e}")
            return False
        except Exception as e:
            logger.error(f"データベース保存エラー: {e}")
            return False

    def generate_dashboard(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        ダッシュボードHTMLを生成

        Args:
            output_path: 出力先パス（省略時はデフォルト）

        Returns:
            Path: 生成されたHTMLファイルパス、失敗時はNone
        """
        try:
            # 既存のdashboardを使用
            from dashboard import generate_html_dashboard

            result_path = generate_html_dashboard(
                str(output_path) if output_path else None
            )
            logger.info(f"ダッシュボード生成完了: {result_path}")
            return Path(result_path)

        except ImportError as e:
            logger.error(f"dashboard.pyのインポートに失敗: {e}")
            return None
        except Exception as e:
            logger.error(f"ダッシュボード生成エラー: {e}")
            return None

    def publish_dashboard(self, publish_path: Path) -> bool:
        """
        ダッシュボードをファイルサーバーに公開

        Args:
            publish_path: 公開先パス

        Returns:
            bool: 成功/失敗
        """
        try:
            # 既存のmain.pyのpublish機能を使用
            from main import publish_dashboard

            publish_dashboard()
            logger.info(f"ダッシュボード公開完了: {publish_path}")
            return True

        except ImportError as e:
            logger.error(f"main.pyのインポートに失敗: {e}")
            return False
        except Exception as e:
            logger.error(f"ダッシュボード公開エラー: {e}")
            return False

    def get_database_status(self) -> dict:
        """
        データベースの状態を取得

        Returns:
            dict: 統計情報
        """
        try:
            from database import get_connection

            conn = get_connection(str(self.db_path))
            cursor = conn.cursor()

            # 各テーブルのレコード数を取得
            tables = [
                "reports", "schools", "monthly_summary",
                "school_sales", "events", "member_rates"
            ]

            stats = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]

            conn.close()
            return stats

        except Exception as e:
            logger.error(f"データベース状態取得エラー: {e}")
            return {}

    def check_month_exists(self, year: int, month: int) -> bool:
        """
        指定した年月のデータが既にDBに存在するかチェック

        Args:
            year: 年（例: 2025）
            month: 月（1-12）

        Returns:
            bool: データが存在する場合True
        """
        try:
            from database import get_connection

            conn = get_connection(str(self.db_path))
            cursor = conn.cursor()

            # 年度計算（4月始まり）
            fiscal_year = year if month >= 4 else year - 1

            # monthly_summaryテーブルで該当月のデータを検索
            cursor.execute('''
                SELECT COUNT(*) FROM monthly_summary
                WHERE fiscal_year = ? AND month = ?
            ''', (fiscal_year, month))

            count = cursor.fetchone()[0]
            conn.close()

            return count > 0

        except Exception as e:
            logger.error(f"月データ存在チェックエラー: {e}")
            return False
