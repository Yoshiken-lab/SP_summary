"""
売上集計モジュール
SP_sales_ver1.1 の sales.py から移植・リファクタリング
"""
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable
import logging

from .summary import SalesSummary, SalesSummaryResult

logger = logging.getLogger(__name__)


class SchoolMasterMismatchError(Exception):
    """マスタに存在しない学校がある場合の例外"""
    def __init__(self, unmatched_schools: list):
        self.unmatched_schools = unmatched_schools
        message = f"マスタに登録されていない学校が{len(unmatched_schools)}件あります。担当者マスタを更新してください。"
        super().__init__(message)


@dataclass
class SchoolSalesRecord:
    """学校別売上レコード"""
    salesman: str
    photostudio: str
    school_name: str
    sales: float


@dataclass
class BranchSalesRecord:
    """事業所別売上レコード"""
    branch_name: str
    sales: float


@dataclass
class EventSalesRecord:
    """イベント別売上レコード"""
    branch_name: str
    school_name: str
    event_name: str
    event_start_date: str
    sales: float


@dataclass
class SalesmanSalesRecord:
    """担当者別売上レコード"""
    salesman: str
    sales: float
    schools: List[SchoolSalesRecord] = field(default_factory=list)


@dataclass
class AggregationResult:
    """集計結果全体を格納するデータクラス"""
    summary: SalesSummaryResult = None
    branch_sales: List[BranchSalesRecord] = field(default_factory=list)
    salesman_sales: List[SalesmanSalesRecord] = field(default_factory=list)
    school_sales: List[SchoolSalesRecord] = field(default_factory=list)
    event_sales: List[EventSalesRecord] = field(default_factory=list)
    unmatched_schools: List[str] = field(default_factory=list)


class SalesAggregator:
    """
    売上データ集計クラス

    使用例:
        aggregator = SalesAggregator(sales_df, master_df)
        result = aggregator.aggregate_all()
    """

    # 除外する状態
    EXCLUDE_STATUS = ["キャンセル済み", "自動キャンセル"]
    # 除外する商品名
    EXCLUDE_PRODUCT = "卒業・卒園アルバム アルバム（学校納品）"

    def __init__(
        self,
        sales_df: pd.DataFrame,
        master_df: pd.DataFrame,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ):
        """
        Args:
            sales_df: 売上データ（CSV読み込み）
            master_df: 担当者マスタデータ（XLSX読み込み）
            progress_callback: 進捗通知用コールバック (message, percentage)
        """
        self.sales_df = sales_df.copy()
        self.master_df = master_df.copy()
        self.progress_callback = progress_callback

        # フィルタリング済みデータ
        self.filtered_df: Optional[pd.DataFrame] = None
        # 学校数
        self.school_count: int = 0
        # 集計結果
        self.result = AggregationResult()

    def _notify_progress(self, message: str, percentage: int):
        """進捗を通知"""
        logger.info(f"[{percentage}%] {message}")
        if self.progress_callback:
            self.progress_callback(message, percentage)

    def aggregate_all(self) -> AggregationResult:
        """
        全ての集計を実行

        Returns:
            AggregationResult: 集計結果
        """
        self._notify_progress("データ前処理を開始", 0)

        # Step 1: データフィルタリング
        self._filter_data()
        self._notify_progress("データフィルタリング完了", 10)

        # Step 1.5: schools_master更新（V2 DBに保存）
        self._update_schools_master()
        self._notify_progress("学校マスタ更新完了", 12)

        # Step 2: 学校マスタチェック
        self._check_school_master()
        self._notify_progress("学校マスタチェック完了", 15)

        # Step 3: 全体売上集計
        self._aggregate_total_sales()
        self._notify_progress("全体売上集計完了", 25)

        # Step 4: 事業所別集計
        self._aggregate_by_branch()
        self._notify_progress("事業所別集計完了", 45)

        # Step 5: 担当者別集計
        self._aggregate_by_salesman()
        self._notify_progress("担当者別集計完了", 65)

        # Step 6: イベント別集計
        self._aggregate_by_event()
        self._notify_progress("イベント別集計完了", 85)

        self._notify_progress("集計完了", 100)
        return self.result

    def _filter_data(self) -> None:
        """売上データをフィルタリング"""
        # 学校数をカウント（重複除去）
        school_names = self.sales_df["学校名"].drop_duplicates()
        self.school_count = len(school_names)
        logger.info(f"実施学校数: {self.school_count}")

        # 状態フィルタリング（キャンセル除外）
        status_col = "状態（未出荷・発送済み）"
        if status_col in self.sales_df.columns:
            self.filtered_df = self.sales_df[
                ~self.sales_df[status_col].isin(self.EXCLUDE_STATUS)
            ]
        else:
            self.filtered_df = self.sales_df.copy()

        # 商品名フィルタリング
        if "商品名" in self.filtered_df.columns:
            self.filtered_df = self.filtered_df[
                self.filtered_df["商品名"] != self.EXCLUDE_PRODUCT
            ]

        logger.info(f"フィルタリング後データ: {len(self.filtered_df)}件")

    def _update_schools_master(self) -> None:
        """
        担当者マスタからschools_masterテーブルを更新

        担当者マスタの情報をもとに、V2データベースのschools_masterテーブルを更新する。
        学校名末尾の「(YYYY年度)」表記を検出し、logical_school_idで統合する。
        """
        try:
            import sys
            from pathlib import Path
            # database_v2モジュールをインポート
            sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
            from database_v2 import get_connection
            
            conn = get_connection()
            cursor = conn.cursor()
            
            logger.info("schools_master更新を開始")
            
            # logical_school_idの割り当て用カウンター
            next_logical_id = 1
            cursor.execute('SELECT MAX(logical_school_id) FROM schools_master')
            row = cursor.fetchone()
            if row[0]:
                next_logical_id = row[0] + 1
            
            # 学校名とlogical_school_idのマッピング
            base_name_to_logical_id = {}
            
            updated_count = 0
            inserted_count = 0
            skipped_count = 0
            
            for _, row in self.master_df.iterrows():
                try:
                    school_id = row.get('ID')  # マスタファイルのカラム名は'ID'
                    school_name = str(row.get('学校名', '')).strip()  # 先頭・末尾スペース削除
                    region = str(row.get('事業所', '')).strip() if pd.notna(row.get('事業所')) else ''
                    manager = str(row.get('担当', '')).strip() if pd.notna(row.get('担当')) else ''
                    studio = str(row.get('写真館', '')).strip() if pd.notna(row.get('写真館')) else ''
                    attribute = str(row.get('属性', '')).strip() if pd.notna(row.get('属性')) else ''
                    
                    if pd.isna(school_id) or pd.isna(school_name) or school_name == '':
                        logger.debug(f"スキップ(NaN/空): school_id={school_id}, name={school_name}")
                        skipped_count += 1
                        continue
                    
                    school_id = int(school_id)
                    school_name = str(school_name).strip()  # 念のため再度strip
                    
                    # 基本学校名と年度を抽出
                    import re
                    match = re.search(r'(.+?)(?:[(](\d{4})年度[)])?$', school_name)
                    if match:
                        base_school_name = match.group(1).strip()
                        fiscal_year = int(match.group(2)) if match.group(2) else None
                    else:
                        base_school_name = school_name
                        fiscal_year = None
                    
                    # logical_school_idを決定
                    if base_school_name in base_name_to_logical_id:
                        logical_school_id = base_name_to_logical_id[base_school_name]
                    else:
                        logical_school_id = next_logical_id
                        base_name_to_logical_id[base_school_name] = logical_school_id
                        next_logical_id += 1
                    
                    # schools_masterテーブルに保存（INSERT OR REPLACE）
                    cursor.execute('''
                        INSERT OR REPLACE INTO schools_master 
                        (school_id, logical_school_id, school_name, base_school_name, 
                         fiscal_year, region, attribute, studio, manager, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (school_id, logical_school_id, school_name, base_school_name,
                          fiscal_year, region, attribute, studio, manager))
                    
                    # 既存レコードかどうかで判定
                    if cursor.rowcount > 0:
                        inserted_count += 1
                    else:
                        updated_count += 1
                        
                except Exception as row_error:
                    logger.warning(f"学校登録エラー(スキップ): {school_name if 'school_name' in locals() else 'Unknown'} - {row_error}")
                    skipped_count += 1
                    continue
            
            conn.commit()
            conn.close()
            
            logger.info(f"schools_master更新完了: 新規{inserted_count}件, 更新{updated_count}件, スキップ{skipped_count}件")
            
        except Exception as e:
            logger.error(f"schools_master更新エラー: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # エラーが発生しても集計は続行する
            logger.warning("schools_master更新をスキップして集計を続行します")

    def _check_school_master(self) -> None:
        """
        売上データの学校がマスタに存在するかチェック

        Raises:
            SchoolMasterMismatchError: マスタに存在しない学校がある場合
        """
        sales_schools = set(self.sales_df["学校名"].unique())
        master_schools = set(self.master_df["学校名"].unique())

        unmatched = sales_schools - master_schools
        self.result.unmatched_schools = list(unmatched)

        if unmatched:
            logger.warning(f"マスタにない学校: {len(unmatched)}件")
            for school in unmatched:
                logger.warning(f"  - {school}")
            # マスタ不一致エラーをスロー（担当者別以降の集計を中断）
            raise SchoolMasterMismatchError(list(unmatched))

    def _aggregate_total_sales(self) -> None:
        """全体売上を集計"""
        summary = SalesSummary(self.filtered_df, self.school_count)
        self.result.summary = summary.calculate()

    def _aggregate_by_branch(self) -> None:
        """事業所別の売上を集計"""
        # 事業所一覧を取得
        branches = self.master_df["事業所"].drop_duplicates().reset_index(drop=True)

        for branch_name in branches:
            # 事業所に属する学校を取得
            branch_schools = self.master_df[
                self.master_df["事業所"] == branch_name
            ]["学校名"].tolist()

            # 売上を集計
            branch_sales = 0
            for school in branch_schools:
                school_df = self.filtered_df[self.filtered_df["学校名"] == school]
                subtotal = school_df["小計"].sum()
                tax = school_df["うち消費税"].sum()
                branch_sales += subtotal - tax

            self.result.branch_sales.append(
                BranchSalesRecord(branch_name=branch_name, sales=branch_sales)
            )
            logger.info(f"事業所 {branch_name}: {branch_sales:,.0f}円")

    def _aggregate_by_salesman(self) -> None:
        """担当者別の売上を集計"""
        # 担当者一覧を取得
        salesmen = self.master_df["担当"].drop_duplicates().reset_index(drop=True)

        for salesman in salesmen:
            # 担当者の学校を取得
            salesman_schools = self.master_df[
                self.master_df["担当"] == salesman
            ]

            salesman_total = 0
            school_records = []

            for _, row in salesman_schools.iterrows():
                school_name = row["学校名"]
                photostudio = row.get("写真館", "")

                # 学校の売上を集計
                school_df = self.filtered_df[self.filtered_df["学校名"] == school_name]

                if not school_df.empty:
                    subtotal = school_df["小計"].sum()
                    tax = school_df["うち消費税"].sum()
                    school_sales = subtotal - tax

                    school_records.append(SchoolSalesRecord(
                        salesman=salesman,
                        photostudio=photostudio,
                        school_name=school_name,
                        sales=school_sales
                    ))
                    salesman_total += school_sales

            self.result.salesman_sales.append(
                SalesmanSalesRecord(
                    salesman=salesman,
                    sales=salesman_total,
                    schools=school_records
                )
            )
            # 学校別売上も全体リストに追加
            self.result.school_sales.extend(school_records)

            logger.info(f"担当者 {salesman}: {salesman_total:,.0f}円")

    def _aggregate_by_event(self) -> None:
        """イベント別の売上を集計"""
        # 事業所一覧を取得
        branches = self.master_df["事業所"].drop_duplicates().reset_index(drop=True)

        for branch_name in branches:
            # 事業所に属する学校を取得
            branch_schools = self.master_df[
                self.master_df["事業所"] == branch_name
            ]["学校名"].tolist()

            for school_name in branch_schools:
                # 学校のイベント一覧を取得
                school_df = self.filtered_df[self.filtered_df["学校名"] == school_name]

                if school_df.empty:
                    continue

                events = school_df["イベント名"].drop_duplicates().reset_index(drop=True)

                for event_name in events:
                    # イベントの売上を集計
                    event_df = school_df[school_df["イベント名"] == event_name]
                    subtotal = event_df["小計"].sum()
                    tax = event_df["うち消費税"].sum()
                    event_sales = subtotal - tax

                    # イベント開始日を取得
                    start_date_col = "キャンペーン期間(開始)"
                    if start_date_col in event_df.columns:
                        start_date = event_df[start_date_col].iloc[0]
                        if pd.isna(start_date):
                            start_date = ""
                        else:
                            start_date = str(start_date)
                    else:
                        start_date = ""

                    self.result.event_sales.append(EventSalesRecord(
                        branch_name=branch_name,
                        school_name=school_name,
                        event_name=event_name,
                        event_start_date=start_date,
                        sales=event_sales
                    ))

        logger.info(f"イベント別集計完了: {len(self.result.event_sales)}件")
