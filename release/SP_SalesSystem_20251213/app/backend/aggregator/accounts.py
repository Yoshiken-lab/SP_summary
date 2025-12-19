"""
会員率計算モジュール
SP_sales_ver1.1 の accounts.py から移植・リファクタリング
"""
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class MemberRateRecord:
    """会員率レコード"""
    school_name: str
    student_count: int
    member_count: int
    member_rate: float  # パーセンテージ（例: 85.5）
    member_rate_str: str  # フォーマット済み（例: "85.5%"）


class AccountsCalculator:
    """
    会員率計算クラス

    使用例:
        calculator = AccountsCalculator(accounts_df)
        result_df = calculator.calculate()
    """

    # 除外する列
    COLUMNS_TO_DROP = ["送料設定", "延長購入"]

    def __init__(self, df: pd.DataFrame):
        """
        Args:
            df: 会員データ（有効会員登録数、生徒数を含む）
        """
        self.df = df.copy()
        self.result_df: Optional[pd.DataFrame] = None

    def calculate(self) -> pd.DataFrame:
        """
        会員率を計算

        Returns:
            pd.DataFrame: 会員率列が追加されたデータフレーム
        """
        # 有効会員登録数が空白のデータを除外
        valid_df = self.df.dropna(subset=["有効会員登録数"], how="any")
        logger.info(f"有効データ数: {len(valid_df)}件（元データ: {len(self.df)}件）")

        # 有効会員登録数を-1調整（元のロジックを維持）
        valid_df = valid_df.copy()
        valid_df.loc[:, "有効会員登録数"] = valid_df["有効会員登録数"] - 1

        # 不要な列を削除（存在する場合のみ）
        for col in self.COLUMNS_TO_DROP:
            if col in valid_df.columns:
                valid_df = valid_df.drop(columns=[col])

        # 会員率を計算
        member_rates = []
        for idx in range(len(valid_df)):
            row = valid_df.iloc[idx]
            student_count = row["生徒数"]
            member_count = row["有効会員登録数"]

            # ゼロ除算対策（元のロジックのバグを修正: or → and）
            if member_count != 0 and student_count != 0:
                rate = round(member_count / student_count * 100, 1)
            else:
                rate = 0.0

            member_rates.append(rate)

        # 会員率列を追加
        valid_df = valid_df.reset_index(drop=True)
        valid_df["会員率"] = member_rates

        # パーセント表記にフォーマット
        valid_df["会員率"] = valid_df["会員率"].apply(
            lambda x: f"{x:.1f}%" if pd.notna(x) else "0.0%"
        )

        self.result_df = valid_df
        logger.info(f"会員率計算完了: {len(valid_df)}件")

        return self.result_df

    def get_summary(self) -> dict:
        """
        会員率のサマリーを取得

        Returns:
            dict: 平均会員率、最高/最低などの統計情報
        """
        if self.result_df is None:
            self.calculate()

        # パーセント文字列から数値に変換
        rates = self.result_df["会員率"].str.rstrip("%").astype(float)

        return {
            "count": len(rates),
            "average": round(rates.mean(), 1),
            "max": round(rates.max(), 1),
            "min": round(rates.min(), 1),
            "median": round(rates.median(), 1)
        }
