#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上分析システム - Excelデータ取り込み

売上報告書Excelファイルを読み込み、SQLiteデータベースに蓄積する
"""

import pandas as pd
import numpy as np
import re
import os
from pathlib import Path
from datetime import datetime
from database import (
    get_connection, init_database,
    get_or_create_school, get_or_create_event,
    apply_salesman_alias
)


def normalize_brackets(text):
    """半角括弧を全角括弧に統一"""
    if text is None:
        return None
    text = str(text)
    text = text.replace('(', '（').replace(')', '）')
    return text


def extract_report_date(file_name):
    """ファイル名から報告書日付を抽出"""
    match = re.search(r'(\d{8})', file_name)
    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, '%Y%m%d').date()
    return datetime.now().date()


def parse_month_column(col_name):
    """カラム名から年度と月を抽出（例: "2025年4月分" → (2025, 4) or "4月分" → (None, 4)）"""
    col_str = str(col_name)

    # パターン1: 「2025年4月分」のように年と月が含まれる場合
    match = re.search(r'(\d{4})年(\d{1,2})月', col_str)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        # 年度計算（4月始まり）
        fiscal_year = year if month >= 4 else year - 1
        return fiscal_year, month

    # パターン2: 「4月分」のように月だけの場合
    match = re.search(r'(\d{1,2})月', col_str)
    if match:
        month = int(match.group(1))
        return None, month  # 年度はNone（呼び出し元でデフォルト年度を使用）

    return None, None


def determine_fiscal_year_from_month(month):
    """月から年度を推定（4月始まり）"""
    # 4-12月 → 当年度、1-3月 → 前年度
    # ただし、年の情報がないので呼び出し元で調整が必要
    return None  # 使用しない


def excel_serial_to_month(serial_value):
    """Excelシリアル日付値から月を抽出"""
    try:
        if isinstance(serial_value, (int, float)) and 40000 < serial_value < 60000:
            # Excelシリアル値を日付に変換
            date = pd.Timestamp('1899-12-30') + pd.Timedelta(days=int(serial_value))
            return date.month
    except:
        pass
    return None


def import_sales_summary(xlsx, cursor, report_id):
    """売上シートから月別サマリーを取り込み"""
    df = pd.read_excel(xlsx, sheet_name='売上', header=None)

    current_fiscal_year = None

    for i, row in df.iterrows():
        # 年度ヘッダーを探す
        cell = str(row[1]) if pd.notna(row[1]) else ''
        if re.match(r'\d{4}年度', cell):
            current_fiscal_year = int(re.search(r'(\d{4})', cell).group(1))
            continue

        # 月ヘッダー行の次に総売上額などがある
        if current_fiscal_year and '総売上額' in cell:
            # この行のデータを取得
            header_row = df.iloc[i - 1]  # 1つ上が月ヘッダー

            for col_idx, header_val in enumerate(header_row):
                if pd.isna(header_val):
                    continue

                month = None
                # パターン1: 「4月」「2024年4月」などの文字列形式
                if '月' in str(header_val):
                    match = re.search(r'(\d{1,2})', str(header_val))
                    if match:
                        month = int(match.group(1))
                # パターン2: Excelシリアル日付値（45748.0など）
                elif isinstance(header_val, (int, float)):
                    month = excel_serial_to_month(header_val)

                if month:

                    # 各指標を取得
                    total_sales = df.iloc[i, col_idx] if pd.notna(df.iloc[i, col_idx]) else None
                    direct_sales = None
                    studio_sales = None
                    school_count = None
                    budget = None
                    budget_rate = None
                    yoy_rate = None

                    # 後続行から他の指標を取得
                    for j in range(i + 1, min(i + 10, len(df))):
                        label = str(df.iloc[j, 1]) if pd.notna(df.iloc[j, 1]) else ''
                        val = df.iloc[j, col_idx]

                        if '直取引' in label:
                            direct_sales = val if pd.notna(val) else None
                        elif '写真館・学校' in label:
                            studio_sales = val if pd.notna(val) else None
                        elif 'イベント実施学校数' in label:
                            school_count = int(val) if pd.notna(val) else None
                        elif '予算比' in label:
                            budget_rate = float(val) if pd.notna(val) else None
                        elif '昨年比' in label:
                            yoy_rate = float(val) if pd.notna(val) else None
                        elif label.strip() == '予算':
                            budget = val if pd.notna(val) else None

                    if total_sales:
                        cursor.execute('''
                            INSERT OR REPLACE INTO monthly_summary
                            (report_id, fiscal_year, month, total_sales, direct_sales,
                             studio_school_sales, school_count, budget, budget_rate, yoy_rate)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (report_id, current_fiscal_year, month, total_sales,
                              direct_sales, studio_sales, school_count, budget,
                              budget_rate, yoy_rate))


def import_school_sales(xlsx, cursor, report_id, sheet_name, fiscal_year):
    """学校別売上シートを取り込み"""
    df = pd.read_excel(xlsx, sheet_name=sheet_name, header=None)

    # ヘッダー行を探す（「担当者」または「担当」を探す）
    header_row_idx = None
    for i, row in df.iterrows():
        if pd.notna(row[1]):
            val = str(row[1])
            if '担当者' in val or val == '担当':
                header_row_idx = i
                break

    if header_row_idx is None:
        print(f"  警告: {sheet_name} でヘッダー行が見つかりません")
        return

    # ヘッダー解析
    header = df.iloc[header_row_idx]
    col_mapping = {}
    month_cols = []

    for col_idx, val in enumerate(header):
        if pd.isna(val):
            continue
        val_str = str(val)

        if '担当' in val_str:
            col_mapping['manager'] = col_idx
        elif '写真館' in val_str:
            col_mapping['studio'] = col_idx
        elif '学校名' in val_str:
            col_mapping['school'] = col_idx
        elif '月' in val_str:
            fy, month = parse_month_column(val_str)
            if month:
                month_cols.append((col_idx, fy or fiscal_year, month))

    # データ行を処理
    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]

        school_name = row[col_mapping.get('school', 3)]
        if pd.isna(school_name) or str(school_name).strip() == '':
            continue

        school_name = str(school_name).strip()
        manager = normalize_brackets(str(row[col_mapping.get('manager', 1)]).strip()) if pd.notna(row[col_mapping.get('manager', 1)]) else None
        studio = str(row[col_mapping.get('studio', 2)]).strip() if pd.notna(row[col_mapping.get('studio', 2)]) else None

        # 担当者名変換マッピングを適用
        if manager:
            manager = apply_salesman_alias(manager)

        # 学校マスタに登録/更新
        school_id = get_or_create_school(cursor, school_name, manager=manager, studio_name=studio)

        # 月別売上を登録（担当者情報も保存）
        for col_idx, fy, month in month_cols:
            sales = row[col_idx]
            if pd.notna(sales) and float(sales) != 0:
                cursor.execute('''
                    INSERT OR REPLACE INTO school_sales
                    (report_id, school_id, fiscal_year, month, sales, manager)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (report_id, school_id, fy, month, float(sales), manager))


def import_event_sales(xlsx, cursor, report_id, sheet_name, fiscal_year):
    """イベント別売上シートを取り込み"""
    df = pd.read_excel(xlsx, sheet_name=sheet_name, header=None)

    # ヘッダー行を探す
    header_row_idx = None
    for i, row in df.iterrows():
        if pd.notna(row[1]) and '事業所' in str(row[1]):
            header_row_idx = i
            break

    if header_row_idx is None:
        print(f"  警告: {sheet_name} でヘッダー行が見つかりません")
        return

    # ヘッダー解析
    header = df.iloc[header_row_idx]
    col_mapping = {}
    month_cols = []

    for col_idx, val in enumerate(header):
        if pd.isna(val):
            continue
        val_str = str(val)

        if '事業所' in val_str:
            col_mapping['region'] = col_idx
        elif '学校名' in val_str:
            col_mapping['school'] = col_idx
        elif 'イベント名' in val_str:
            col_mapping['event'] = col_idx
        elif 'イベント開始日' in val_str or '開始日' in val_str:
            col_mapping['start_date'] = col_idx
        elif '月' in val_str:
            fy, month = parse_month_column(val_str)
            if month:
                month_cols.append((col_idx, fy or fiscal_year, month))

    # データ行を処理
    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]

        school_name = row[col_mapping.get('school', 2)]
        if pd.isna(school_name) or str(school_name).strip() == '':
            continue

        school_name = str(school_name).strip()
        event_name = str(row[col_mapping.get('event', 3)]).strip() if pd.notna(row[col_mapping.get('event', 3)]) else None
        region = str(row[col_mapping.get('region', 1)]).strip() if pd.notna(row[col_mapping.get('region', 1)]) else None

        # イベント開始日
        start_date = None
        if 'start_date' in col_mapping:
            raw_date = row[col_mapping['start_date']]
            if pd.notna(raw_date):
                if isinstance(raw_date, datetime):
                    start_date = raw_date.date()
                elif isinstance(raw_date, (int, float)):
                    # Excelシリアル値の場合
                    try:
                        start_date = pd.Timestamp('1899-12-30') + pd.Timedelta(days=int(raw_date))
                        start_date = start_date.date()
                    except:
                        pass

        if not event_name:
            continue

        # 学校マスタに登録/更新
        school_id = get_or_create_school(cursor, school_name, region=region)

        # イベントを登録/更新
        event_id = get_or_create_event(cursor, school_id, event_name, start_date, fiscal_year)

        # 月別売上を登録
        for col_idx, fy, month in month_cols:
            sales = row[col_idx]
            if pd.notna(sales) and float(sales) != 0:
                cursor.execute('''
                    INSERT OR REPLACE INTO event_sales
                    (report_id, event_id, fiscal_year, month, sales)
                    VALUES (?, ?, ?, ?, ?)
                ''', (report_id, event_id, fy, month, float(sales)))


def import_member_rates(xlsx, cursor, report_id, report_date, sheet_name='会員率'):
    """会員率シートを取り込み"""
    df = pd.read_excel(xlsx, sheet_name=sheet_name, header=None)

    # ヘッダー行を探す
    header_row_idx = None
    for i, row in df.iterrows():
        if pd.notna(row[1]) and '学校ID' in str(row[1]):
            header_row_idx = i
            break

    if header_row_idx is None:
        print("  警告: 会員率シートでヘッダー行が見つかりません")
        return

    # ヘッダー解析
    header = df.iloc[header_row_idx]
    col_mapping = {}

    for col_idx, val in enumerate(header):
        if pd.isna(val):
            continue
        val_str = str(val)

        if '学校ID' in val_str:
            col_mapping['school_id_col'] = col_idx
        elif '学校名' in val_str:
            col_mapping['school'] = col_idx
        elif '属性' in val_str:
            col_mapping['attribute'] = col_idx
        elif '写真館' in val_str:
            col_mapping['studio'] = col_idx
        elif '年度' in val_str:
            col_mapping['fiscal_year'] = col_idx
        elif '卒業' in val_str:
            col_mapping['grade_category'] = col_idx
        elif 'お子様' in val_str or '学年' in val_str:
            col_mapping['grade_name'] = col_idx
        elif '生徒数' in val_str:
            col_mapping['student_count'] = col_idx
        elif '有効会員' in val_str or '登録数' in val_str:
            col_mapping['member_count'] = col_idx

    # データ行を処理
    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]

        school_name = row[col_mapping.get('school', 2)]
        if pd.isna(school_name) or str(school_name).strip() == '':
            continue

        school_name = str(school_name).strip()
        # 元データの学校IDを取得
        external_id = None
        if 'school_id_col' in col_mapping:
            ext_id_val = row[col_mapping['school_id_col']]
            if pd.notna(ext_id_val):
                external_id = int(ext_id_val)

        attribute = str(row[col_mapping.get('attribute', 3)]).strip() if pd.notna(row[col_mapping.get('attribute', 3)]) else None
        studio = str(row[col_mapping.get('studio', 4)]).strip() if pd.notna(row[col_mapping.get('studio', 4)]) else None

        # 年度
        fiscal_year = None
        if 'fiscal_year' in col_mapping:
            fy_val = row[col_mapping['fiscal_year']]
            if pd.notna(fy_val):
                fiscal_year = int(fy_val)

        grade_category = str(row[col_mapping.get('grade_category', 6)]).strip() if pd.notna(row[col_mapping.get('grade_category', 6)]) else None
        grade_name = str(row[col_mapping.get('grade_name', 7)]).strip() if pd.notna(row[col_mapping.get('grade_name', 7)]) else None

        student_count = 0
        if 'student_count' in col_mapping:
            val = row[col_mapping['student_count']]
            if pd.notna(val):
                student_count = int(val)

        member_count = 0
        if 'member_count' in col_mapping:
            val = row[col_mapping['member_count']]
            if pd.notna(val):
                member_count = int(val)

        # 会員率計算
        member_rate = member_count / student_count if student_count > 0 else 0

        # 学校マスタに登録/更新（external_idを使用）
        school_id = get_or_create_school(cursor, school_name, external_id=external_id, attribute=attribute, studio_name=studio)

        # 会員率データを登録
        cursor.execute('''
            INSERT INTO member_rates
            (report_id, school_id, fiscal_year, grade_category, grade_name,
             student_count, member_count, member_rate, snapshot_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (report_id, school_id, fiscal_year, grade_category, grade_name,
              student_count, member_count, member_rate, report_date))


def import_school_comparison(xlsx, cursor, report_id):
    """学校別売り上げ比較シートを取り込み"""
    df = pd.read_excel(xlsx, sheet_name='学校別売り上げ比較', header=None)

    # ヘッダー行を探す（「担当者」または「担当」を探す）
    header_row_idx = None
    for i, row in df.iterrows():
        if pd.notna(row[1]):
            val = str(row[1])
            if '担当者' in val or val == '担当':
                header_row_idx = i
                break

    if header_row_idx is None:
        print("  警告: 学校別売り上げ比較シートでヘッダー行が見つかりません")
        return

    # ヘッダー解析
    header = df.iloc[header_row_idx]
    col_mapping = {}
    year_cols = []

    for col_idx, val in enumerate(header):
        if pd.isna(val):
            continue
        val_str = str(val)

        if '担当' in val_str:
            col_mapping['manager'] = col_idx
        elif '写真館' in val_str:
            col_mapping['studio'] = col_idx
        elif '学校名' in val_str:
            col_mapping['school'] = col_idx
        elif '年度売上' in val_str:
            match = re.search(r'(\d{4})', val_str)
            if match:
                year_cols.append((col_idx, int(match.group(1))))

    # データ行を処理
    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]

        school_name = row[col_mapping.get('school', 3)]
        if pd.isna(school_name) or str(school_name).strip() == '':
            continue

        school_name = str(school_name).strip()
        manager = normalize_brackets(str(row[col_mapping.get('manager', 1)]).strip()) if pd.notna(row[col_mapping.get('manager', 1)]) else None
        studio = str(row[col_mapping.get('studio', 2)]).strip() if pd.notna(row[col_mapping.get('studio', 2)]) else None

        # 担当者名変換マッピングを適用
        if manager:
            manager = apply_salesman_alias(manager)

        # 学校マスタに登録/更新
        school_id = get_or_create_school(cursor, school_name, manager=manager, studio_name=studio)

        # 年度別売上を登録
        for col_idx, fiscal_year in year_cols:
            sales = row[col_idx]
            if pd.notna(sales):
                cursor.execute('''
                    INSERT OR REPLACE INTO school_yearly_sales
                    (report_id, school_id, fiscal_year, total_sales)
                    VALUES (?, ?, ?, ?)
                ''', (report_id, school_id, fiscal_year, float(sales)))


def extract_fiscal_year_from_sheet_name(sheet_name):
    """シート名から年度を抽出（例: '学校別（2024年度）' → 2024）"""
    # パターン1: 「2024年度」形式
    match = re.search(r'(\d{4})年度', sheet_name)
    if match:
        return int(match.group(1))
    # パターン2: 「(2024)」や「（2024）」形式
    match = re.search(r'[（(](\d{4})[）)]', sheet_name)
    if match:
        return int(match.group(1))
    return None


def detect_fiscal_year_from_path(file_path):
    """ファイルパスから年度を推測（2024年度フォルダなら2024年度）"""
    path_str = str(file_path)

    # 優先度1: 「2024年度」形式（年度が明示されている）
    match = re.search(r'(\d{4})年度', path_str)
    if match:
        return int(match.group(1))

    # 優先度2: 「2024年」形式（後方互換性のため残すが、非推奨）
    # ※この場合、ファイル作成日を見て年度を判定
    match = re.search(r'(\d{4})年[^度]', path_str)
    if match:
        folder_year = int(match.group(1))
        # ファイル名から日付を抽出して、年度との整合性を確認
        date_match = re.search(r'(\d{4})(\d{2})(\d{2})', file_path.name)
        if date_match:
            file_year = int(date_match.group(1))
            file_month = int(date_match.group(2))
            # ファイル作成日から年度を計算
            file_fiscal_year = file_year if file_month >= 4 else file_year - 1
            # フォルダの年と異なる場合は警告（ただしファイルの年度を優先）
            if file_fiscal_year != folder_year:
                print(f"  警告: フォルダ年({folder_year})とファイル年度({file_fiscal_year})が異なります")
            return file_fiscal_year
        return folder_year

    # 優先度3: ファイル名から日付を抽出して年度を推測
    date_match = re.search(r'(\d{4})(\d{2})(\d{2})', file_path.name)
    if date_match:
        year = int(date_match.group(1))
        month = int(date_match.group(2))
        # 4月始まりの年度計算
        return year if month >= 4 else year - 1

    return 2024  # デフォルト


def import_excel(file_path, db_path=None):
    """Excelファイル全体を取り込み"""
    file_path = Path(file_path)
    print(f"取り込み開始: {file_path.name}")

    # DB初期化
    init_database(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    try:
        # 報告書情報を登録
        report_date = extract_report_date(file_path.name)

        # 既に取り込み済みかチェック
        cursor.execute('SELECT id FROM reports WHERE file_name = ?', (file_path.name,))
        existing = cursor.fetchone()
        if existing:
            print(f"  既に取り込み済みです。スキップします。")
            return existing[0]

        cursor.execute('''
            INSERT INTO reports (file_name, file_path, report_date)
            VALUES (?, ?, ?)
        ''', (file_path.name, str(file_path), report_date))
        report_id = cursor.lastrowid
        print(f"  報告書ID: {report_id}, 日付: {report_date}")

        # Excelファイルを開く
        xlsx = pd.ExcelFile(file_path, engine='openpyxl')
        sheet_names = xlsx.sheet_names

        # パスから年度を推測（2024年フォルダなら2024年度）
        default_fiscal_year = detect_fiscal_year_from_path(file_path)
        print(f"  デフォルト年度: {default_fiscal_year}")

        # 各シートを取り込み
        if '売上' in sheet_names:
            print("  売上サマリーを取り込み中...")
            import_sales_summary(xlsx, cursor, report_id)

        for sheet_name in sheet_names:
            if '学校別' in sheet_name and '比較' not in sheet_name:
                # シート名から年度を抽出（優先）、なければパスから推測した年度を使用
                fiscal_year = extract_fiscal_year_from_sheet_name(sheet_name)
                if fiscal_year is None:
                    fiscal_year = default_fiscal_year
                    print(f"  警告: {sheet_name}から年度を抽出できません。デフォルト年度({default_fiscal_year})を使用します")
                print(f"  {sheet_name}を取り込み中（{fiscal_year}年度）...")
                import_school_sales(xlsx, cursor, report_id, sheet_name, fiscal_year)

            elif 'イベント別' in sheet_name:
                # シート名から年度を抽出（優先）、なければパスから推測した年度を使用
                fiscal_year = extract_fiscal_year_from_sheet_name(sheet_name)
                if fiscal_year is None:
                    fiscal_year = default_fiscal_year
                    print(f"  警告: {sheet_name}から年度を抽出できません。デフォルト年度({default_fiscal_year})を使用します")
                print(f"  {sheet_name}を取り込み中（{fiscal_year}年度）...")
                import_event_sales(xlsx, cursor, report_id, sheet_name, fiscal_year)

        # 会員率シートを探す（「会員率」を含むシート名）
        member_rate_sheet = None
        for sheet_name in sheet_names:
            if '会員率' in sheet_name:
                member_rate_sheet = sheet_name
                break

        if member_rate_sheet:
            print(f"  {member_rate_sheet}を取り込み中...")
            import_member_rates(xlsx, cursor, report_id, report_date, member_rate_sheet)

        if '学校別売り上げ比較' in sheet_names:
            print("  学校別売り上げ比較を取り込み中...")
            import_school_comparison(xlsx, cursor, report_id)

        conn.commit()
        print(f"取り込み完了: {file_path.name}")
        return report_id

    finally:
        conn.close()


def sync_school_master(master_file_path, db_path=None):
    """
    学校マスタファイルからDBを同期

    処理内容:
    1. マスタの外部IDでDBを検索
    2. 見つかった場合: 学校名を最新に更新
    3. 見つからない場合: 学校名で検索して外部IDを紐付け
    4. どちらも見つからない場合: 新規登録

    Args:
        master_file_path: 学校マスタExcelファイルのパス
        db_path: DBパス（省略時はデフォルト）
    """
    from database import normalize_school_name

    master_path = Path(master_file_path)
    print(f"学校マスタ同期開始: {master_path.name}")

    # マスタファイル読み込み
    df = pd.read_excel(master_path, header=0)

    # カラム名を正規化（Unnamed列を除外）
    df = df.dropna(axis=1, how='all')

    # 必要なカラムを特定
    id_col = None
    name_col = None
    region_col = None
    manager_col = None
    studio_col = None

    for col in df.columns:
        col_str = str(col)
        if col_str == 'ID' or 'ID' in col_str:
            id_col = col
        elif '学校名' in col_str:
            name_col = col
        elif '事業所' in col_str:
            region_col = col
        elif '担当' in col_str:
            manager_col = col
        elif '写真館' in col_str:
            studio_col = col

    if id_col is None or name_col is None:
        print("  エラー: IDまたは学校名カラムが見つかりません")
        return

    print(f"  カラム検出: ID={id_col}, 学校名={name_col}, 事業所={region_col}, 担当={manager_col}, 写真館={studio_col}")

    # DB接続
    from database import get_connection, init_database
    init_database(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    stats = {
        'updated_name': 0,      # 学校名を更新
        'linked_extid': 0,      # 外部IDを紐付け
        'new_school': 0,        # 新規登録
        'already_synced': 0,    # 既に同期済み
        'skipped': 0,           # スキップ
    }

    try:
        for _, row in df.iterrows():
            external_id = row[id_col]
            school_name = row[name_col]

            # 無効な行をスキップ
            if pd.isna(external_id) or pd.isna(school_name):
                stats['skipped'] += 1
                continue

            external_id = int(external_id)
            school_name = str(school_name).strip()
            normalized_name = normalize_school_name(school_name)

            region = str(row[region_col]).strip() if region_col and pd.notna(row[region_col]) else None
            manager = str(row[manager_col]).strip() if manager_col and pd.notna(row[manager_col]) else None
            studio = str(row[studio_col]).strip() if studio_col and pd.notna(row[studio_col]) else None

            # 1. 外部IDで検索
            cursor.execute('SELECT school_id FROM school_external_ids WHERE external_id = ?', (external_id,))
            ext_row = cursor.fetchone()

            if ext_row:
                # 外部IDが既に登録済み → 学校名を更新
                school_id = ext_row[0]
                cursor.execute('SELECT school_name FROM schools WHERE id = ?', (school_id,))
                current_name = cursor.fetchone()[0]

                if current_name != normalized_name:
                    # 新しい名前が既に別の学校として存在するかチェック
                    cursor.execute('SELECT id FROM schools WHERE school_name = ? AND id != ?',
                                   (normalized_name, school_id))
                    existing_row = cursor.fetchone()

                    if existing_row:
                        # 同名の学校が既に存在 → 統合が必要
                        # この場合は名前を更新せず、ログのみ出力
                        print(f"  警告: 学校名の競合 - {current_name} を {normalized_name} に更新できません（同名の学校が既存）")
                        stats['skipped'] += 1
                    else:
                        # 学校名が変更されている場合、更新
                        cursor.execute('UPDATE schools SET school_name = ? WHERE id = ?',
                                       (normalized_name, school_id))
                        print(f"  学校名更新: {current_name} → {normalized_name} (外部ID:{external_id})")
                        stats['updated_name'] += 1
                else:
                    stats['already_synced'] += 1

                # 属性情報も更新
                _update_school_attrs(cursor, school_id, region, manager, studio)
            else:
                # 2. 外部IDがない → 学校名で検索
                cursor.execute('SELECT id FROM schools WHERE school_name = ?', (normalized_name,))
                name_row = cursor.fetchone()

                if name_row:
                    # 学校名で見つかった → 外部IDを紐付け
                    school_id = name_row[0]
                    cursor.execute('''
                        INSERT OR IGNORE INTO school_external_ids (external_id, school_id, original_name)
                        VALUES (?, ?, ?)
                    ''', (external_id, school_id, school_name))
                    print(f"  外部ID紐付け: {normalized_name} ← 外部ID:{external_id}")
                    stats['linked_extid'] += 1

                    # 属性情報も更新
                    _update_school_attrs(cursor, school_id, region, manager, studio)
                else:
                    # 3. どちらも見つからない → 新規登録
                    cursor.execute('''
                        INSERT INTO schools (school_name, region, manager, studio_name)
                        VALUES (?, ?, ?, ?)
                    ''', (normalized_name, region, manager, studio))
                    school_id = cursor.lastrowid

                    cursor.execute('''
                        INSERT INTO school_external_ids (external_id, school_id, original_name)
                        VALUES (?, ?, ?)
                    ''', (external_id, school_id, school_name))
                    print(f"  新規登録: {normalized_name} (外部ID:{external_id})")
                    stats['new_school'] += 1

        conn.commit()
        print(f"\n同期完了:")
        print(f"  学校名更新: {stats['updated_name']}件")
        print(f"  外部ID紐付け: {stats['linked_extid']}件")
        print(f"  新規登録: {stats['new_school']}件")
        print(f"  同期済み: {stats['already_synced']}件")
        print(f"  スキップ: {stats['skipped']}件")

    finally:
        conn.close()


def _update_school_attrs(cursor, school_id, region, manager, studio):
    """学校の属性情報を更新（値がある場合のみ）"""
    updates = []
    params = []
    if region:
        updates.append('region = ?')
        params.append(region)
    if manager:
        # 担当者名変換マッピングを適用
        manager = apply_salesman_alias(manager)
        updates.append('manager = ?')
        params.append(manager)
    if studio:
        updates.append('studio_name = ?')
        params.append(studio)

    if updates:
        params.append(school_id)
        cursor.execute(f'UPDATE schools SET {", ".join(updates)} WHERE id = ?', params)


def import_all_from_directory(directory_path, db_path=None):
    """ディレクトリ内の全Excelファイルを取り込み"""
    directory = Path(directory_path)
    imported_count = 0

    # フォルダ内のフォルダを探索（スクールフォト売り上げ報告書_YYYYMMDD形式）
    for folder in sorted(directory.iterdir()):
        if folder.is_dir() and 'スクールフォト売り上げ報告書' in folder.name:
            # フォルダ内のExcelファイルを探す
            for xlsx_file in folder.glob('*.xlsx'):
                if not xlsx_file.name.startswith('~$'):  # 一時ファイルを除外
                    try:
                        import_excel(xlsx_file, db_path)
                        imported_count += 1
                    except Exception as e:
                        print(f"  エラー: {xlsx_file.name} - {e}")

    print(f"\n取り込み完了: {imported_count}件のファイルを処理しました")
    return imported_count


def import_excel_with_stats(file_path, db_path=None):
    """
    Excelファイルを取り込み、統計情報とreport_idを返す
    
    Returns:
        dict: {
            'success': bool,
            'report_id': int,
            'stats': {
                'school_sales': int,
                'monthly_summary': int,
                'event_sales': int
            },
            'error': str (エラー時のみ)
        }
    """
    file_path = Path(file_path)
    print(f"取り込み開始: {file_path.name}")

    # DB初期化
    init_database(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    try:
        # 報告書情報を登録
        report_date = extract_report_date(file_path.name)

        # 既に取り込み済みかチェック
        cursor.execute('SELECT id FROM reports WHERE file_name = ?', (file_path.name,))
        existing = cursor.fetchone()
        if existing:
            print(f"  既に取り込み済みです。スキップします。")
            conn.close()
            return {
                'success': False,
                'error': f'ファイル「{file_path.name}」は既に取り込み済みです'
            }

        cursor.execute('''
            INSERT INTO reports (file_name, file_path, report_date)
            VALUES (?, ?, ?)
        ''', (file_path.name, str(file_path), report_date))
        report_id = cursor.lastrowid
        print(f"  報告書ID: {report_id}, 日付: {report_date}")

        # Excelファイルを開く
        xlsx = pd.ExcelFile(file_path, engine='openpyxl')
        sheet_names = xlsx.sheet_names

        # パスから年度を推測
        default_fiscal_year = detect_fiscal_year_from_path(file_path)
        print(f"  デフォルト年度: {default_fiscal_year}")

        # 統計情報を初期化
        stats = {
            'school_sales': 0,
            'monthly_summary': 0,
            'event_sales': 0
        }

        # 各シートを取り込み
        if '売上' in sheet_names:
            print("  売上サマリーを取り込み中...")
            import_sales_summary(xlsx, cursor, report_id)
            # 月別サマリー件数を取得
            cursor.execute('SELECT COUNT(*) FROM monthly_summary WHERE report_id = ?', (report_id,))
            stats['monthly_summary'] = cursor.fetchone()[0]

        for sheet_name in sheet_names:
            if '学校別' in sheet_name and '比較' not in sheet_name:
                fiscal_year = extract_fiscal_year_from_sheet_name(sheet_name)
                if fiscal_year is None:
                    fiscal_year = default_fiscal_year
                print(f"  {sheet_name}を取り込み中({fiscal_year}年度)...")
                import_school_sales(xlsx, cursor, report_id, sheet_name, fiscal_year)

            elif 'イベント別' in sheet_name:
                fiscal_year = extract_fiscal_year_from_sheet_name(sheet_name)
                if fiscal_year is None:
                    fiscal_year = default_fiscal_year
                print(f"  {sheet_name}を取り込み中({fiscal_year}年度)...")
                import_event_sales(xlsx, cursor, report_id, sheet_name, fiscal_year)

        # 学校別売上件数を取得
        cursor.execute('SELECT COUNT(*) FROM school_sales WHERE report_id = ?', (report_id,))
        stats['school_sales'] = cursor.fetchone()[0]

        # イベント別売上件数を取得
        cursor.execute('SELECT COUNT(*) FROM event_sales WHERE report_id = ?', (report_id,))
        stats['event_sales'] = cursor.fetchone()[0]

        # 会員率シートを探す
        member_rate_sheet = None
        for sheet_name in sheet_names:
            if '会員率' in sheet_name:
                member_rate_sheet = sheet_name
                break

        if member_rate_sheet:
            print(f"  {member_rate_sheet}を取り込み中...")
            import_member_rates(xlsx, cursor, report_id, report_date, member_rate_sheet)

        if '学校別売り上げ比較' in sheet_names:
            print("  学校別売り上げ比較を取り込み中...")
            import_school_comparison(xlsx, cursor, report_id)

        # データが1件も取り込まれていない場合はエラー
        if stats['school_sales'] == 0 and stats['monthly_summary'] == 0 and stats['event_sales'] == 0:
            conn.rollback()
            print(f"  エラー: 想定されたシート形式ではありません")
            return {
                'success': False,
                'error': f'想定されたエクセル形式ではありません。「売上」「学校別」「イベント別」シートが見つかりませんでした'
            }

        conn.commit()
        print(f"取り込み完了: {file_path.name}")
        print(f"  学校別売上: {stats['school_sales']}件, 月別サマリー: {stats['monthly_summary']}件, イベント別売上: {stats['event_sales']}件")
        
        return {
            'success': True,
            'report_id': report_id,
            'stats': stats
        }

    except Exception as e:
        conn.rollback()
        print(f"取り込みエラー: {e}")
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        conn.close()


def rollback_reports(report_ids, db_path=None):
    """
    指定したreport_idのデータを全て削除(ロールバック)
    
    Args:
        report_ids: list of int, 削除するreport_idのリスト
        db_path: DBパス(省略時はデフォルト)
    """
    if not report_ids:
        return

    conn = get_connection(db_path)
    cursor = conn.cursor()

    try:
        placeholders = ','.join(['?' for _ in report_ids])
        
        # 関連データを削除
        cursor.execute(f'DELETE FROM monthly_summary WHERE report_id IN ({placeholders})', report_ids)
        cursor.execute(f'DELETE FROM school_sales WHERE report_id IN ({placeholders})', report_ids)
        cursor.execute(f'DELETE FROM event_sales WHERE report_id IN ({placeholders})', report_ids)
        cursor.execute(f'DELETE FROM member_rates WHERE report_id IN ({placeholders})', report_ids)
        cursor.execute(f'DELETE FROM school_yearly_sales WHERE report_id IN ({placeholders})', report_ids)
        
        # 最後にreportsテーブルから削除
        cursor.execute(f'DELETE FROM reports WHERE id IN ({placeholders})', report_ids)
        
        conn.commit()
        print(f"ロールバック完了: report_ids={report_ids}")
    except Exception as e:
        conn.rollback()
        print(f"ロールバックエラー: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("使い方:")
        print("  python importer.py <Excelファイル>")
        print("  python importer.py <ディレクトリ> --all")
        sys.exit(1)

    target = sys.argv[1]

    if len(sys.argv) > 2 and sys.argv[2] == '--all':
        import_all_from_directory(target)
    else:
        import_excel(target)
