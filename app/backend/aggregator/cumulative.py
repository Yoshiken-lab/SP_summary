"""
累積集計モジュール
web_app の SalesSummaryProcessor から移植・リファクタリング
"""
import pandas as pd
from pathlib import Path
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side
import logging

logger = logging.getLogger(__name__)


class CumulativeAggregator:
    """
    累積集計クラス
    月次集計結果を年度累積表に追記する

    使用例:
        aggregator = CumulativeAggregator(input_path, output_path, year=2024, month=12)
        result = aggregator.process()
    """

    def __init__(
        self,
        input_path: Path,
        output_dir: Path,
        year: int,
        month: int,
        fiscal_year: int
    ):
        """
        Args:
            input_path: 月次集計結果Excelファイルのパス
            output_dir: 出力先ディレクトリ
            year: 対象年（例: 2024）
            month: 対象月（例: 12）
            fiscal_year: 年度（例: 2024 → 2024年度）
        """
        self.input_path = Path(input_path)
        self.output_dir = Path(output_dir)
        self.year = year
        self.month = month
        self.fiscal_year = fiscal_year

        # 月カラム名
        self.month_col_name = f"{year}年{month}月分"

        # 出力ファイル名
        self.output_filename = f"SP_年度累計_{fiscal_year}.xlsx"
        self.output_path = self.output_dir / self.output_filename

        # 結果
        self.school_count = 0
        self.event_count = 0

    def process(self) -> dict:
        """
        累積集計を実行

        Returns:
            dict: 処理結果
        """
        logger.info(f"累積集計開始: {self.month_col_name}")
        logger.info(f"入力ファイル: {self.input_path}")
        logger.info(f"出力ファイル: {self.output_path}")

        # 入力ファイル読み込み
        input_xl = pd.ExcelFile(self.input_path)

        # シート存在チェック
        if '学校別' not in input_xl.sheet_names:
            raise ValueError("入力ファイルに「学校別」シートがありません")
        if 'イベント別' not in input_xl.sheet_names:
            raise ValueError("入力ファイルに「イベント別」シートがありません")

        df_school = pd.read_excel(input_xl, sheet_name='学校別')
        df_event = pd.read_excel(input_xl, sheet_name='イベント別')

        logger.info(f"学校別: {len(df_school)}件")
        logger.info(f"イベント別: {len(df_event)}件")

        # 出力ファイルの処理
        if self.output_path.exists() and self._is_valid_existing_file():
            logger.info("既存ファイルに追記します")
            self._update_existing_file(df_school, df_event)
        else:
            logger.info("新規ファイルを作成します")
            self._create_new_file(df_school, df_event)

        logger.info("累積集計完了")

        return {
            'status': 'success',
            'schoolCount': self.school_count,
            'eventCount': self.event_count,
            'outputPath': str(self.output_path),
            'outputFilename': self.output_filename
        }

    def _is_valid_existing_file(self) -> bool:
        """既存ファイルが有効なデータを持っているかチェック"""
        try:
            xl = pd.ExcelFile(self.output_path)
            if '学校別' not in xl.sheet_names:
                return False
            df = pd.read_excel(xl, sheet_name='学校別')
            if df.empty or '担当者' not in df.columns:
                return False
            return True
        except Exception:
            return False

    def _create_new_file(self, df_school: pd.DataFrame, df_event: pd.DataFrame):
        """新規ファイルを作成"""
        # 学校別シートのデータ準備
        school_data = df_school[['担当者', '写真館', '学校名', '売り上げ']].copy()
        school_data = school_data.rename(columns={'売り上げ': self.month_col_name})
        school_data['総計'] = school_data[self.month_col_name]

        # イベント別シートのデータ準備
        event_data = df_event[['事業所', '学校名', 'イベント名', 'イベント開始日', '売り上げ']].copy()
        event_data = event_data.rename(columns={'売り上げ': self.month_col_name})
        event_data['総計'] = event_data[self.month_col_name]

        # Excelファイルに書き込み
        with pd.ExcelWriter(self.output_path, engine='openpyxl') as writer:
            school_data.to_excel(writer, sheet_name='学校別', index=False)
            event_data.to_excel(writer, sheet_name='イベント別', index=False)

        # スタイル適用
        self._apply_styles()

        self.school_count = len(school_data)
        self.event_count = len(event_data)

        logger.info(f"学校別シート: {self.school_count}行")
        logger.info(f"イベント別シート: {self.event_count}行")

    def _update_existing_file(self, df_school: pd.DataFrame, df_event: pd.DataFrame):
        """既存ファイルに月列を追加"""
        # 既存ファイル読み込み
        existing_school = pd.read_excel(self.output_path, sheet_name='学校別')
        existing_event = pd.read_excel(self.output_path, sheet_name='イベント別')

        # 学校別の更新
        updated_school = self._merge_school_data(existing_school, df_school)

        # イベント別の更新
        updated_event = self._merge_event_data(existing_event, df_event)

        # Excelファイルに書き込み
        with pd.ExcelWriter(self.output_path, engine='openpyxl') as writer:
            updated_school.to_excel(writer, sheet_name='学校別', index=False)
            updated_event.to_excel(writer, sheet_name='イベント別', index=False)

        # スタイル適用
        self._apply_styles()

        self.school_count = len(updated_school)
        self.event_count = len(updated_event)

        logger.info(f"学校別シート: {self.school_count}行")
        logger.info(f"イベント別シート: {self.event_count}行")

    def _merge_school_data(self, existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
        """学校別データをマージ"""
        new_data = new_df[['担当者', '写真館', '学校名', '売り上げ']].copy()
        new_data = new_data.rename(columns={'売り上げ': self.month_col_name})

        if '総計' in existing_df.columns:
            existing_df = existing_df.drop(columns=['総計'])

        if self.month_col_name in existing_df.columns:
            existing_df = existing_df.drop(columns=[self.month_col_name])

        key_cols = ['担当者', '写真館', '学校名']
        merged = pd.merge(existing_df, new_data, on=key_cols, how='outer')
        merged = self._reorder_month_columns(merged, key_cols)

        month_cols = [col for col in merged.columns if '年' in col and '月分' in col]
        merged['総計'] = merged[month_cols].fillna(0).sum(axis=1).astype(int)

        return merged

    def _merge_event_data(self, existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
        """イベント別データをマージ"""
        new_data = new_df[['事業所', '学校名', 'イベント名', 'イベント開始日', '売り上げ']].copy()
        new_data = new_data.rename(columns={'売り上げ': self.month_col_name})

        if '総計' in existing_df.columns:
            existing_df = existing_df.drop(columns=['総計'])

        if self.month_col_name in existing_df.columns:
            existing_df = existing_df.drop(columns=[self.month_col_name])

        key_cols = ['事業所', '学校名', 'イベント名', 'イベント開始日']

        if 'イベント開始日' in existing_df.columns:
            existing_df['イベント開始日'] = pd.to_datetime(existing_df['イベント開始日']).dt.date
        if 'イベント開始日' in new_data.columns:
            new_data['イベント開始日'] = pd.to_datetime(new_data['イベント開始日']).dt.date

        merged = pd.merge(existing_df, new_data, on=key_cols, how='outer')
        merged = self._reorder_month_columns(merged, key_cols)

        month_cols = [col for col in merged.columns if '年' in col and '月分' in col]
        merged['総計'] = merged[month_cols].fillna(0).sum(axis=1).astype(int)

        return merged

    def _reorder_month_columns(self, df: pd.DataFrame, key_cols: list) -> pd.DataFrame:
        """月列を年月順に並べ替え"""
        month_cols = [col for col in df.columns if '年' in col and '月分' in col]

        def parse_month_col(col):
            try:
                parts = col.replace('年', ' ').replace('月分', '').split()
                return (int(parts[0]), int(parts[1]))
            except Exception:
                return (9999, 99)

        month_cols_sorted = sorted(month_cols, key=parse_month_col)
        other_cols = [col for col in df.columns if col not in month_cols and col != '総計']
        new_order = other_cols + month_cols_sorted
        if '総計' in df.columns:
            new_order.append('総計')

        return df[new_order]

    def _apply_styles(self):
        """Excelファイルにスタイルを適用"""
        wb = openpyxl.load_workbook(self.output_path)

        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]

            # ヘッダースタイル
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal='center')
                cell.border = thin_border

            # データセルの罫線
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=ws.max_column):
                for cell in row:
                    cell.border = thin_border

            # 列幅の自動調整
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if cell.value:
                            cell_length = sum(2 if ord(c) > 127 else 1 for c in str(cell.value))
                            max_length = max(max_length, cell_length)
                    except Exception:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width

        wb.save(self.output_path)
