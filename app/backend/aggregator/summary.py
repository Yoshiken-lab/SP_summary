"""
売上集計計算モジュール
SP_sales_ver1.1 の summary.py から移植・リファクタリング
"""
import pandas as pd
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class SalesSummaryResult:
    """集計結果を格納するデータクラス"""
    total_sales: float = 0.0          # 総売上
    direct_sales: float = 0.0         # 直取引（大塚カラー）
    studio_sales: float = 0.0         # 写真館・学校
    school_count: int = 0             # 実施学校数
    sales_per_school: float = 0.0     # 売上/学校

    def to_dict(self):
        """辞書形式に変換"""
        return {
            'total_sales': self.total_sales,
            'direct_sales': self.direct_sales,
            'studio_sales': self.studio_sales,
            'school_count': self.school_count,
            'sales_per_school': self.sales_per_school
        }


class SalesSummary:
    """
    売上集計計算クラス

    使用例:
        summary = SalesSummary(filtered_df, school_count=50)
        result = summary.calculate()
    """

    # 直取引判定用のキーワード
    DIRECT_SALES_KEYWORD = "大塚カラー"

    def __init__(self, df: pd.DataFrame, school_count: int = 0):
        """
        Args:
            df: フィルタリング済みの売上データ
            school_count: 実施学校数
        """
        self.df = df
        self.school_count = school_count
        self.result = SalesSummaryResult()

    def calculate(self) -> SalesSummaryResult:
        """
        全ての集計を実行

        Returns:
            SalesSummaryResult: 集計結果
        """
        self._calculate_total_sales()
        self._calculate_sales_by_channel()
        return self.result

    def _calculate_total_sales(self) -> None:
        """総売上を計算"""
        subtotal = self.df["小計"].sum()
        tax = self.df["うち消費税"].sum()
        self.result.total_sales = subtotal - tax
        logger.info(f"総売上計算完了: {self.result.total_sales:,.0f}円")

    def _calculate_sales_by_channel(self) -> None:
        """チャネル別（直取引/写真館）の売上を計算"""
        # 写真館名カラムが存在するか確認
        if "写真館名" not in self.df.columns:
            logger.warning("写真館名カラムが存在しません。チャネル別集計をスキップします。")
            self.result.direct_sales = 0
            self.result.studio_sales = self.result.total_sales
            return

        # 大塚カラー（直取引）のデータを抽出
        direct_df = self.df[
            self.df["写真館名"].fillna("").str.contains(self.DIRECT_SALES_KEYWORD)
        ]

        # 直取引の売上計算
        direct_subtotal = direct_df["小計"].sum()
        direct_tax = direct_df["うち消費税"].sum()
        self.result.direct_sales = direct_subtotal - direct_tax

        # 写真館・学校の売上（総売上 - 直取引）
        self.result.studio_sales = self.result.total_sales - self.result.direct_sales

        # 学校数と売上/学校
        self.result.school_count = self.school_count
        if self.school_count > 0:
            self.result.sales_per_school = self.result.total_sales / self.school_count
        else:
            self.result.sales_per_school = 0

        logger.info(f"直取引売上: {self.result.direct_sales:,.0f}円")
        logger.info(f"写真館・学校売上: {self.result.studio_sales:,.0f}円")
        logger.info(f"売上/学校: {self.result.sales_per_school:,.0f}円")
