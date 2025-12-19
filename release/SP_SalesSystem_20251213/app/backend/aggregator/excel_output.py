"""
Excel出力モジュール
SP_sales_ver1.1 の output.py から移植・リファクタリング
"""
import pandas as pd
from pathlib import Path
from typing import Optional
import logging
from datetime import datetime

from .sales import AggregationResult, SchoolSalesRecord, EventSalesRecord

logger = logging.getLogger(__name__)


class ExcelExporter:
    """
    Excel出力クラス

    使用例:
        exporter = ExcelExporter(result, output_dir=Path.home() / "Downloads")
        filepath = exporter.export()
    """

    def __init__(
        self,
        result: AggregationResult,
        output_dir: Optional[Path] = None,
        filename: Optional[str] = None,
        accounts_df: Optional[pd.DataFrame] = None
    ):
        """
        Args:
            result: 集計結果
            output_dir: 出力ディレクトリ（デフォルト: ~/Downloads）
            filename: 出力ファイル名（デフォルト: SP_SalesResult_YYYYMM.xlsx）
            accounts_df: 会員率計算済みデータフレーム
        """
        self.result = result
        self.output_dir = output_dir or Path.home() / "Downloads"
        self.accounts_df = accounts_df

        # ファイル名生成
        if filename:
            self.filename = filename
        else:
            now = datetime.now()
            self.filename = f"SP_SalesResult_{now.strftime('%Y%m')}.xlsx"

        self.filepath = self.output_dir / self.filename

    def export(self) -> Path:
        """
        Excelファイルを出力

        Returns:
            Path: 出力ファイルパス
        """
        logger.info(f"Excel出力開始: {self.filepath}")

        # 出力ディレクトリ作成
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # ExcelWriterで複数シートを書き込み
        with pd.ExcelWriter(self.filepath, engine="openpyxl") as writer:
            self._write_summary_sheet(writer)
            self._write_school_sheet(writer)
            self._write_event_sheet(writer)
            if self.accounts_df is not None:
                self._write_accounts_sheet(writer)
            if self.result.unmatched_schools:
                self._write_unmatched_sheet(writer)

        logger.info(f"Excel出力完了: {self.filepath}")
        return self.filepath

    def _write_summary_sheet(self, writer: pd.ExcelWriter) -> None:
        """集計結果シートを出力"""
        # 全体集計
        summary_data = {
            "項目": [
                "総売り上げ",
                "内、直取引",
                "内、写真館・学校",
                "イベント実施学校数",
                "売上額/実施学校数"
            ],
            "集計結果": [
                self.result.summary.total_sales,
                self.result.summary.direct_sales,
                self.result.summary.studio_sales,
                self.result.summary.school_count,
                self.result.summary.sales_per_school
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name="集計結果", index=False, startrow=0)

        # 事業所別（7行目から）
        if self.result.branch_sales:
            branch_data = {
                "事業所": [b.branch_name for b in self.result.branch_sales],
                "売り上げ": [b.sales for b in self.result.branch_sales]
            }
            branch_df = pd.DataFrame(branch_data)
            branch_df.to_excel(
                writer, sheet_name="集計結果",
                index=False, startrow=7, header=True
            )

        # 担当者別（12行目 + 事業所数 から）
        if self.result.salesman_sales:
            start_row = 7 + len(self.result.branch_sales) + 2
            salesman_data = {
                "担当者": [s.salesman for s in self.result.salesman_sales],
                "売り上げ": [s.sales for s in self.result.salesman_sales]
            }
            salesman_df = pd.DataFrame(salesman_data)
            salesman_df.to_excel(
                writer, sheet_name="集計結果",
                index=False, startrow=start_row, header=True
            )

    def _write_school_sheet(self, writer: pd.ExcelWriter) -> None:
        """学校別シートを出力"""
        if not self.result.school_sales:
            return

        school_data = {
            "担当者": [s.salesman for s in self.result.school_sales],
            "写真館": [s.photostudio for s in self.result.school_sales],
            "学校名": [s.school_name for s in self.result.school_sales],
            "売り上げ": [s.sales for s in self.result.school_sales]
        }
        school_df = pd.DataFrame(school_data)
        school_df.to_excel(writer, sheet_name="学校別", index=False)

    def _write_event_sheet(self, writer: pd.ExcelWriter) -> None:
        """イベント別シートを出力"""
        if not self.result.event_sales:
            return

        event_data = {
            "事業所": [e.branch_name for e in self.result.event_sales],
            "学校名": [e.school_name for e in self.result.event_sales],
            "イベント名": [e.event_name for e in self.result.event_sales],
            "イベント開始日": [e.event_start_date for e in self.result.event_sales],
            "売り上げ": [e.sales for e in self.result.event_sales]
        }
        event_df = pd.DataFrame(event_data)
        event_df.to_excel(writer, sheet_name="イベント別", index=False)

    def _write_accounts_sheet(self, writer: pd.ExcelWriter) -> None:
        """会員率シートを出力"""
        self.accounts_df.to_excel(writer, sheet_name="会員率", index=False)

    def _write_unmatched_sheet(self, writer: pd.ExcelWriter) -> None:
        """一致しない学校シートを出力"""
        unmatched_data = {
            "学校名": self.result.unmatched_schools + [
                "↑の学校は事業所・担当者ごとの集計結果に反映されません"
            ]
        }
        unmatched_df = pd.DataFrame(unmatched_data)
        unmatched_df.to_excel(writer, sheet_name="一致しない学校", index=False)
