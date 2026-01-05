"""
データベースサービス
Ver2対応版: importer_v2.pyとdashboard_v2.pyを活用
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

    Ver2版: importer_v2.py, dashboard_v2.pyを活用してDB保存・ダッシュボード生成を行う
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Args:
            db_path: データベースファイルパス
        """
        self.db_path = db_path or BASE_DIR / "schoolphoto_v2.db"

    def save_to_database(self, excel_path: Path) -> bool:
        """
        報告書ExcelをデータベースにインポートVer2版）

        Args:
            excel_path: 報告書Excelファイルパス

        Returns:
            bool: 成功/失敗
        """
        try:
            # Ver2のimporterを使用
            from importer_v2 import import_excel_v2

            result = import_excel_v2(str(excel_path), str(self.db_path))
            
            if result['success']:
                logger.info(f"データベース保存完了: {excel_path}")
                logger.info(f"  Report ID: {result['report_id']}")
                logger.info(f"  Stats: {result.get('stats', {})}")
                return True
            else:
                error_msg = result.get('error', '不明なエラー')
                logger.error(f"データベース保存失敗: {error_msg}")
                return False

        except ImportError as e:
            logger.error(f"importer_v2.pyのインポートに失敗: {e}")
            return False
        except Exception as e:
            logger.error(f"データベース保存エラー: {e}")
            return False

    def generate_dashboard(self, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        ダッシュボードHTMLを生成（Ver2版）

        Args:
            output_path: 出力先パス（省略時はデフォルト）

        Returns:
            Path: 生成されたHTMLファイルパス、失敗時はNone
        """
        try:
            # Ver2のdashboardを使用
            from dashboard_v2 import generate_dashboard

            result_path = generate_dashboard(
                db_path=str(self.db_path),
                output_dir=str(output_path.parent) if output_path else None
            )
            logger.info(f"ダッシュボード生成完了: {result_path}")
            return Path(result_path)

        except ImportError as e:
            logger.error(f"dashboard_v2.pyのインポートに失敗: {e}")
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
        データベースの状態を取得（Ver2版）

        Returns:
            dict: 統計情報
        """
        try:
            from database_v2 import get_connection

            conn = get_connection(str(self.db_path))
            cursor = conn.cursor()

            # Ver2スキーマの各テーブルのレコード数を取得
            tables = [
                "reports", "schools_master", "monthly_totals",
                "school_monthly_sales", "event_sales", "member_rates",
                "branch_monthly_sales", "manager_monthly_sales"
            ]

            stats = {}
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[table] = cursor.fetchone()[0]
                except Exception as e:
                    logger.warning(f"テーブル {table} の取得に失敗: {e}")
                    stats[table] = 0

            conn.close()
            return stats

        except Exception as e:
            logger.error(f"データベース状態取得エラー: {e}")
            return {}

    def check_month_exists(self, year: int, month: int) -> bool:
        """
        指定した年月のデータが既にDBに存在するかチェック（Ver2版）

        Args:
            year: 年（例: 2025）
            month: 月（1-12）

        Returns:
            bool: データが存在する場合True
        """
        try:
            from database_v2 import get_connection

            conn = get_connection(str(self.db_path))
            cursor = conn.cursor()

            # report_dateから該当する年月のデータを検索
            # report_dateは YYYY-MM-DD 形式なので、YYYY-MM で前方一致検索
            date_pattern = f"{year:04d}-{month:02d}%"
            
            cursor.execute('''
                SELECT COUNT(*) FROM reports
                WHERE report_date LIKE ?
            ''', (date_pattern,))

            count = cursor.fetchone()[0]
            conn.close()

            return count > 0

        except Exception as e:
            logger.error(f"月データ存在チェックエラー: {e}")
            return False
