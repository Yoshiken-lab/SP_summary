"""
ファイル処理サービス
"""
import pandas as pd
from pathlib import Path
from typing import Tuple, Optional
import logging
import shutil

logger = logging.getLogger(__name__)


class FileHandler:
    """
    ファイル処理クラス

    CSV/Excelファイルの読み込みとバリデーションを担当
    """

    # CSVエンコーディング
    CSV_ENCODING = "cp932"

    def __init__(self, upload_dir: Path):
        """
        Args:
            upload_dir: アップロードファイル保存ディレクトリ
        """
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save_uploaded_file(self, file_storage, filename: str) -> Path:
        """
        アップロードファイルを保存

        Args:
            file_storage: FlaskのFileStorageオブジェクト
            filename: 保存ファイル名

        Returns:
            Path: 保存先パス
        """
        filepath = self.upload_dir / filename
        file_storage.save(str(filepath))
        logger.info(f"ファイル保存: {filepath}")
        return filepath

    def read_sales_csv(self, filepath: Path) -> pd.DataFrame:
        """
        売上データCSVを読み込み

        Args:
            filepath: CSVファイルパス

        Returns:
            pd.DataFrame: 売上データ
        """
        df = pd.read_csv(filepath, encoding=self.CSV_ENCODING)
        logger.info(f"売上データ読み込み: {len(df)}件")

        # 必須カラムチェック
        required_cols = ["学校名", "小計", "うち消費税"]
        self._validate_columns(df, required_cols, "売上データ")

        return df

    def read_accounts_csv(self, filepath: Path) -> pd.DataFrame:
        """
        会員データCSVを読み込み

        Args:
            filepath: CSVファイルパス

        Returns:
            pd.DataFrame: 会員データ
        """
        df = pd.read_csv(filepath, encoding=self.CSV_ENCODING)
        logger.info(f"会員データ読み込み: {len(df)}件")

        # 必須カラムチェック
        required_cols = ["生徒数", "有効会員登録数"]
        self._validate_columns(df, required_cols, "会員データ")

        return df

    def read_master_excel(self, filepath: Path) -> pd.DataFrame:
        """
        担当者マスタExcelを読み込み

        Args:
            filepath: Excelファイルパス

        Returns:
            pd.DataFrame: マスタデータ
        """
        df = pd.read_excel(filepath, sheet_name=0)
        logger.info(f"マスタデータ読み込み: {len(df)}件")

        # 必須カラムチェック
        required_cols = ["学校名", "事業所", "担当"]
        self._validate_columns(df, required_cols, "マスタデータ")

        return df

    def _validate_columns(
        self, df: pd.DataFrame, required: list, name: str
    ) -> None:
        """
        必須カラムの存在チェック

        Args:
            df: データフレーム
            required: 必須カラムリスト
            name: データ名（エラーメッセージ用）

        Raises:
            ValueError: 必須カラムが不足している場合
        """
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(
                f"{name}に必須カラムがありません: {missing}"
            )

    def cleanup_uploads(self) -> None:
        """アップロードディレクトリをクリーンアップ"""
        if self.upload_dir.exists():
            for file in self.upload_dir.iterdir():
                if file.is_file():
                    file.unlink()
            logger.info("アップロードファイルをクリーンアップしました")
