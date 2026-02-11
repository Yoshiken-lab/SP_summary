"""
売上集計モジュール
SP_sales_ver1.1 の sales.py から移植・リファクタリング
"""
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
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
    # カラム名定数
    COL_SCHOOL_NAME = "学校名"
    COL_SCHOOL_ID = "学校ID"
    COL_MASTER_ID = "ID"
    COL_BRANCH = "事業所"
    COL_SALESMAN = "担当"
    COL_STUDIO = "写真館"
    COL_SUBTOTAL = "小計"
    COL_TAX = "うち消費税"
    COL_EVENT_NAME = "イベント名"
    COL_EVENT_START = "キャンペーン期間(開始)"

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
        self.sales_df = self._normalize_text_columns(sales_df.copy())
        self.master_df = self._normalize_text_columns(master_df.copy())
        self.progress_callback = progress_callback

        # フィルタリング済みデータ
        self.filtered_df: Optional[pd.DataFrame] = None
        # マスタ紐付け済みデータ
        self.matched_df: Optional[pd.DataFrame] = None
        # 学校数
        self.school_count: int = 0
        # 集計結果
        self.result = AggregationResult()

        # 集計用マップ
        self.master_id_to_index: Dict[int, int] = {}
        self.master_name_to_index: Dict[str, int] = {}

    def _notify_progress(self, message: str, percentage: int):
        """進捗を通知"""
        logger.info(f"[{percentage}%] {message}")
        if self.progress_callback:
            self.progress_callback(message, percentage)

    def _normalize_text_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """全文字列カラムの前後空白のみを除去（中間空白は維持）"""
        normalized = df.copy()
        for col in normalized.columns:
            if pd.api.types.is_object_dtype(normalized[col]) or pd.api.types.is_string_dtype(normalized[col]):
                normalized[col] = normalized[col].apply(
                    lambda x: x.strip() if isinstance(x, str) else x
                )
        return normalized

    def _normalize_id_series(self, series: pd.Series) -> pd.Series:
        """学校IDを比較しやすい型へ正規化"""
        return pd.to_numeric(series, errors="coerce").astype("Int64")

    def _prepare_lookup_maps(self) -> None:
        """マスタの学校ID/学校名検索用マップを作成"""
        if self.COL_MASTER_ID in self.master_df.columns:
            self.master_df["_master_school_id_norm"] = self._normalize_id_series(
                self.master_df[self.COL_MASTER_ID]
            )
        else:
            self.master_df["_master_school_id_norm"] = pd.Series(
                pd.array([pd.NA] * len(self.master_df), dtype="Int64"),
                index=self.master_df.index
            )

        if self.COL_SCHOOL_NAME in self.master_df.columns:
            self.master_df["_master_school_name_norm"] = self.master_df[
                self.COL_SCHOOL_NAME
            ].apply(lambda x: x.strip() if isinstance(x, str) else x)
        else:
            self.master_df["_master_school_name_norm"] = ""

        self.master_id_to_index = {}
        self.master_name_to_index = {}

        id_series = self.master_df["_master_school_id_norm"]
        duplicated_ids = id_series[id_series.notna() & id_series.duplicated()].drop_duplicates()
        if not duplicated_ids.empty:
            logger.warning(
                f"担当者マスタで学校ID重複を検出: {duplicated_ids.astype(int).tolist()} (先頭行を採用)"
            )

        name_series = self.master_df["_master_school_name_norm"]
        duplicated_names = name_series[
            name_series.notna() & (name_series != "") & name_series.duplicated()
        ].drop_duplicates()
        if not duplicated_names.empty:
            logger.warning(
                f"担当者マスタで学校名重複を検出: {duplicated_names.tolist()} (先頭行を採用)"
            )

        for idx, row in self.master_df.iterrows():
            school_id = row["_master_school_id_norm"]
            school_name = row["_master_school_name_norm"]

            if pd.notna(school_id):
                self.master_id_to_index.setdefault(int(school_id), int(idx))

            if isinstance(school_name, str) and school_name:
                self.master_name_to_index.setdefault(school_name, int(idx))

    def _attach_master_matches(self) -> None:
        """
        フィルタ済み売上へ、ID優先・名称フォールバックでマスタ行を割当

        1売上行に対してマスタ行は1つのみ割当する（重複集計防止）
        """
        if self.filtered_df is None:
            return

        df = self.filtered_df.copy()

        if self.COL_SCHOOL_ID in df.columns:
            df["_sales_school_id_norm"] = self._normalize_id_series(df[self.COL_SCHOOL_ID])
        else:
            df["_sales_school_id_norm"] = pd.Series(
                pd.array([pd.NA] * len(df), dtype="Int64"),
                index=df.index
            )

        if self.COL_SCHOOL_NAME in df.columns:
            df["_sales_school_name_norm"] = df[self.COL_SCHOOL_NAME].apply(
                lambda x: x.strip() if isinstance(x, str) else x
            )
        else:
            df["_sales_school_name_norm"] = ""

        df["_net_sales"] = df[self.COL_SUBTOTAL] - df[self.COL_TAX]

        id_match_index = df["_sales_school_id_norm"].map(self.master_id_to_index)
        name_match_index = df["_sales_school_name_norm"].map(self.master_name_to_index)

        matched_index = id_match_index.where(id_match_index.notna(), name_match_index)
        df["_matched_master_index"] = pd.to_numeric(matched_index, errors="coerce").astype("Int64")

        df["_match_type"] = "unmatched"
        df.loc[id_match_index.notna(), "_match_type"] = "id"
        df.loc[id_match_index.isna() & name_match_index.notna(), "_match_type"] = "name"

        # ID一致で学校名がズレる場合は警告のみ（ID優先）
        id_hit_mask = id_match_index.notna()
        if id_hit_mask.any():
            master_name_by_id = pd.to_numeric(
                id_match_index[id_hit_mask], errors="coerce"
            ).astype("Int64").map(self.master_df["_master_school_name_norm"])
            name_mismatch_mask = id_hit_mask.copy()
            name_mismatch_mask.loc[id_hit_mask] = (
                df.loc[id_hit_mask, "_sales_school_name_norm"] != master_name_by_id
            )
            mismatch_count = int(name_mismatch_mask.sum())
            if mismatch_count > 0:
                logger.warning(
                    f"学校ID一致だが学校名不一致の売上行を検出: {mismatch_count}件（ID優先で集計）"
                )

        self.filtered_df = df

        matched_df = df[df["_matched_master_index"].notna()].copy()
        if matched_df.empty:
            self.matched_df = matched_df
            return

        matched_df["_matched_master_index"] = matched_df["_matched_master_index"].astype(int)
        matched_df["_master_branch"] = matched_df["_matched_master_index"].map(
            self.master_df.get(self.COL_BRANCH, pd.Series("", index=self.master_df.index))
        ).fillna("")
        matched_df["_master_salesman"] = matched_df["_matched_master_index"].map(
            self.master_df.get(self.COL_SALESMAN, pd.Series("", index=self.master_df.index))
        ).fillna("")
        matched_df["_master_studio"] = matched_df["_matched_master_index"].map(
            self.master_df.get(self.COL_STUDIO, pd.Series("", index=self.master_df.index))
        ).fillna("")
        matched_df["_master_school_name"] = matched_df["_matched_master_index"].map(
            self.master_df.get(self.COL_SCHOOL_NAME, pd.Series("", index=self.master_df.index))
        ).fillna("")

        self.matched_df = matched_df

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

        # Step 1.2: マスタ照合マップ作成（ID優先・名称フォールバック）
        self._prepare_lookup_maps()
        self._attach_master_matches()
        self._notify_progress("売上データのマスタ紐づけ完了", 11)

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
        school_names = self.sales_df[self.COL_SCHOOL_NAME].drop_duplicates()
        self.school_count = len(school_names)
        logger.info(f"実施学校数: {self.school_count}")

        # 状態フィルタリング（キャンセル除外）
        status_col = "状態（未出荷・発送済み）"
        if status_col in self.sales_df.columns:
            self.filtered_df = self.sales_df[
                ~self.sales_df[status_col].isin(self.EXCLUDE_STATUS)
            ].copy()
        else:
            self.filtered_df = self.sales_df.copy()

        # 商品名フィルタリング
        if "商品名" in self.filtered_df.columns:
            self.filtered_df = self.filtered_df[
                self.filtered_df["商品名"] != self.EXCLUDE_PRODUCT
            ].copy()

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
                    school_name_raw = row.get('学校名', '')
                    school_name = (
                        str(school_name_raw).strip()
                        if pd.notna(school_name_raw) else ''
                    )
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
        売上データの学校が今回のExcelマスタに存在するかチェック

        Raises:
            SchoolMasterMismatchError: マスタに存在しない学校がある場合
        """
        if self.filtered_df is None:
            self.result.unmatched_schools = []
            return

        unmatched_df = self.filtered_df[self.filtered_df["_match_type"] == "unmatched"]
        if unmatched_df.empty:
            self.result.unmatched_schools = []
            return

        unmatched_names = sorted(
            {
                str(name)
                for name in unmatched_df["_sales_school_name_norm"].dropna().unique()
                if str(name)
            }
        )
        if not unmatched_names:
            id_names = []
            for school_id in unmatched_df["_sales_school_id_norm"].dropna().unique():
                id_names.append(f"学校ID:{int(school_id)}")
            unmatched_names = sorted(id_names) if id_names else ["学校名不明"]
        self.result.unmatched_schools = unmatched_names

        unmatched_details = (
            unmatched_df
            .groupby(["_sales_school_id_norm", "_sales_school_name_norm"], dropna=False)
            .size()
            .reset_index(name="rows")
            .sort_values("rows", ascending=False)
        )
        logger.warning(f"マスタ未登録データを検出: {len(unmatched_df)}件")
        for _, row in unmatched_details.head(20).iterrows():
            school_id = row["_sales_school_id_norm"]
            school_name = row["_sales_school_name_norm"]
            school_id_text = "" if pd.isna(school_id) else int(school_id)
            logger.warning(
                f"  - 学校ID={school_id_text}, 学校名={school_name}, 件数={int(row['rows'])}"
            )

        raise SchoolMasterMismatchError(unmatched_names)

    def _aggregate_total_sales(self) -> None:
        """全体売上を集計"""
        summary = SalesSummary(self.filtered_df, self.school_count)
        self.result.summary = summary.calculate()

    def _aggregate_by_branch(self) -> None:
        """事業所別の売上を集計"""
        if self.matched_df is None:
            self.result.branch_sales = []
            return

        master_sales = self.matched_df.groupby("_matched_master_index")["_net_sales"].sum()
        branch_series = (
            self.master_df[self.COL_BRANCH].fillna("").astype(str)
            if self.COL_BRANCH in self.master_df.columns
            else pd.Series("", index=self.master_df.index)
        )
        branches = branch_series.drop_duplicates().tolist()

        for branch_name in branches:
            branch_indices = branch_series[branch_series == branch_name].index
            branch_total = float(master_sales.reindex(branch_indices, fill_value=0).sum())
            self.result.branch_sales.append(
                BranchSalesRecord(branch_name=branch_name, sales=branch_total)
            )
            logger.info(f"事業所 {branch_name}: {branch_total:,.0f}円")

    def _aggregate_by_salesman(self) -> None:
        """担当者別の売上を集計"""
        self.result.salesman_sales = []
        self.result.school_sales = []

        if self.matched_df is None:
            return

        master_sales = self.matched_df.groupby("_matched_master_index")["_net_sales"].sum()
        salesman_series = (
            self.master_df[self.COL_SALESMAN].fillna("").astype(str)
            if self.COL_SALESMAN in self.master_df.columns
            else pd.Series("", index=self.master_df.index)
        )
        salesmen = salesman_series.drop_duplicates().tolist()

        for salesman in salesmen:
            salesman_rows = self.master_df[salesman_series == salesman]

            salesman_total = 0.0
            school_records: List[SchoolSalesRecord] = []

            for master_idx, row in salesman_rows.iterrows():
                school_sales = float(master_sales.get(master_idx, 0))
                salesman_total += school_sales

                if abs(school_sales) < 1e-9:
                    continue

                school_records.append(SchoolSalesRecord(
                    salesman=salesman,
                    photostudio=row.get(self.COL_STUDIO, ""),
                    school_name=row.get(self.COL_SCHOOL_NAME, ""),
                    sales=school_sales
                ))

            self.result.salesman_sales.append(
                SalesmanSalesRecord(
                    salesman=salesman,
                    sales=salesman_total,
                    schools=school_records
                )
            )
            self.result.school_sales.extend(school_records)
            logger.info(f"担当者 {salesman}: {salesman_total:,.0f}円")

    def _aggregate_by_event(self) -> None:
        """イベント別の売上を集計"""
        self.result.event_sales = []
        if self.matched_df is None or self.matched_df.empty:
            logger.info("イベント別集計完了: 0件")
            return

        if self.COL_EVENT_NAME not in self.matched_df.columns:
            logger.warning("イベント名カラムが存在しないため、イベント別集計をスキップします")
            return

        event_df = self.matched_df.copy()
        event_df["_event_name"] = event_df[self.COL_EVENT_NAME].fillna("").astype(str)
        if self.COL_EVENT_START in event_df.columns:
            event_df["_event_start"] = event_df[self.COL_EVENT_START].fillna("").astype(str)
        else:
            event_df["_event_start"] = ""

        grouped = (
            event_df
            .groupby(
                ["_master_branch", "_master_school_name", "_event_name", "_event_start"],
                dropna=False
            )["_net_sales"]
            .sum()
            .reset_index()
        )

        for _, row in grouped.iterrows():
            self.result.event_sales.append(EventSalesRecord(
                branch_name=row["_master_branch"],
                school_name=row["_master_school_name"],
                event_name=row["_event_name"],
                event_start_date=row["_event_start"],
                sales=float(row["_net_sales"])
            ))

        logger.info(f"イベント別集計完了: {len(self.result.event_sales)}件")
