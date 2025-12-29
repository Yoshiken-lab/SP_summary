#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上分析システム - Excelデータ取り込み (V2)
V2スキーマ対応版: 報告書ExcelをV2データベースに保存
"""

import pandas as pd
import numpy as np
import re
from pathlib import Path
from datetime import datetime
from database_v2 import get_connection, normalize_manager_name


# 学校名マッピング (報告書Excel → 担当者マスタ)
# 学校名変更や表記揺れに対応するための変換テーブル
SCHOOL_NAME_MAPPINGS = {
    # 名称変更
    '日光市立東中学校': '日光市立日光中学校',
    '社会福祉法人 みどり会 野沢保育園': '社会福祉法人 河内福祉会 のざわ保育園',
    
    # 表記揺れ
    '新宿区落合第二中学校': '新宿区立落合第二中学校',
    '栃木県立白楊高等学校': '栃木県立宇都宮白楊高等学校',
    '認定こども園 常磐大学幼稚園': '常磐大学こども園',
    '小山市立城北小学校': '小山市立小山城北小学校',  # 「小山」の有無
}

class SchoolNotFoundError(Exception):
    """学校がschools_masterに存在しない場合のエラー"""
    def __init__(self, school_names):
        self.school_names = school_names
        message = f"以下の学校がschools_masterに登録されていません:\n" + "\n".join(f"  - {s}" for s in school_names)
        super().__init__(message)


def extract_report_date(file_name):
    """ファイル名から報告書日付を抽出"""
    match = re.search(r'(\d{8})', file_name)
    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, '%Y%m%d').date()
    return None


def parse_month_column(col_name):
    """カラム名から年度と月を抽出"""
    col_str = str(col_name)
    # パターン1: "2025年4月分" → (2025, 4)
    match = re.search(r'(\d{4})年(\d{1,2})月', col_str)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        return (year, month)
    
    # パターン2: "4月分" → (None, 4)
    match = re.search(r'(\d{1,2})月', col_str)
    if match:
        month = int(match.group(1))
        return (None, month)
    
    return (None, None)


def excel_serial_to_month(serial_value):
    """Excelシリアル日付値から月を抽出"""
    try:
        base_date = datetime(1899, 12, 30)
        delta = pd.Timedelta(days=serial_value)
        target_date = base_date + delta
        return target_date.month
    except:
        return None


def normalize_school_name(school_name):
    """
    学校名を正規化(表記揺れ対策)
    
    以下を除去:
    - 接頭辞: 「認定こども園　」「学校法人」「社会福祉法人」など
    - 年度表記: 「(YYYY年度)」「YYYY年度」
    - 補足情報: 「(〇〇カメラ)」など
    
    Args:
        school_name: 元の学校名
    
    Returns:
        str: 正規化された学校名
    """
    normalized = school_name.strip()
    
    # 接頭辞を除去
    prefixes = [
        '認定こども園　',
        '認定こども園',
        '学校法人　',
        '学校法人',
        '社会福祉法人　',
        '社会福祉法人',
        '学校法人ひまわり学園　',
        '学校法人成田学園　',
        '学校法人顕真学園　',
        '学校法人　宮ヶ谷学園　'
    ]
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    
    # 年度表記を除去(末尾)
    normalized = re.sub(r'[(（]\d{4}年度[)）]$', '', normalized).strip()
    normalized = re.sub(r'\d{4}年度\s*', '', normalized).strip()
    
    # 補足情報を除去
    normalized = re.sub(r'[(（][^)）]+[)）]', '', normalized).strip()
    
    # 連続スペースを1つに
    normalized = re.sub(r'\s+', '', normalized)
    
    return normalized


def get_school_id_by_name(cursor, school_name):
    """
    学校名からschool_idを取得(完全一致→部分一致の順で検索)
    
    Args:
        cursor: DBカーソル
        school_name: 学校名
    
    Returns:
        int: school_id (見つからない場合はNone)
    """
    # 0. 学校名マッピングを適用(旧名称→新名称への自動変換)
    school_name = SCHOOL_NAME_MAPPINGS.get(school_name, school_name)
    
    # 1. 完全一致検索
    cursor.execute('''
        SELECT school_id FROM schools_master 
        WHERE school_name = ?
        ORDER BY updated_at DESC
        LIMIT 1
    ''', (school_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    # 2. 部分一致検索(正規化名で)
    normalized_input = normalize_school_name(school_name)
    
    # schools_master全件を取得して正規化名で比較
    cursor.execute('''
        SELECT school_id, school_name FROM schools_master
        ORDER BY updated_at DESC
    ''')
    
    for school_id, master_name in cursor.fetchall():
        normalized_master = normalize_school_name(master_name)
        
        # 完全一致
        if normalized_input == normalized_master:
            return school_id
        
        # どちらかが片方に含まれる場合もマッチ(より短い方がより長い方に含まれる)
        if normalized_input in normalized_master or normalized_master in normalized_input:
            # ただし、長さの差が大きすぎる場合は除外(誤マッチ防止)
            len_diff = abs(len(normalized_input) - len(normalized_master))
            if len_diff <= 10:  # 10文字以内の差なら許容
                return school_id
    
    return None


def import_monthly_totals(xlsx, cursor, report_id):
    """売上シートから月次全体売上を取り込み"""
    df = pd.read_excel(xlsx, sheet_name='売上', header=None)
    
    current_fiscal_year = None
    stats = {'count': 0}
    
    for i, row in df.iterrows():
        cell = str(row[1]) if pd.notna(row[1]) else ''
        
        # 年度ヘッダー検出
        if re.match(r'\d{4}年度', cell):
            current_fiscal_year = int(re.search(r'(\d{4})', cell).group(1))
            continue
        
        # 総売上額の行を検出
        if current_fiscal_year and '総売上額' in cell:
            header_row = df.iloc[i - 1]
            
            for col_idx, header_val in enumerate(header_row):
                if pd.isna(header_val):
                    continue
                
                month = None
                if '月' in str(header_val):
                    match = re.search(r'(\d{1,2})', str(header_val))
                    if match:
                        month = int(match.group(1))
                elif isinstance(header_val, (int, float)):
                    month = excel_serial_to_month(header_val)
                
                if not month:
                    continue
                
                # 各指標を取得
                total_sales = df.iloc[i, col_idx] if pd.notna(df.iloc[i, col_idx]) else None
                direct_sales = None
                studio_sales = None
                school_count = None
                budget = None
                
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
                    elif label.strip() == '予算':
                        budget = val if pd.notna(val) else None
                
                if total_sales:
                    cursor.execute('''
                        INSERT OR REPLACE INTO monthly_totals
                        (report_id, fiscal_year, month, total_sales, direct_sales, 
                         studio_sales, school_count, budget)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (report_id, current_fiscal_year, month, total_sales,
                          direct_sales, studio_sales, school_count, budget))
                    stats['count'] += 1
    
    return stats


def import_branch_monthly_sales(xlsx, cursor, report_id):
    """売上シートから事業所別月次売上を取り込み"""
    df = pd.read_excel(xlsx, sheet_name='売上', header=None)
    
    # 「■売上　各事業所」セクションを検出
    start_row = None
    for i, row in df.iterrows():
        cell = str(row[1]) if pd.notna(row[1]) else ''
        if '各事業所' in cell and '売上' in cell:
            start_row = i
            break
    
    if start_row is None:
        return {'count': 0}
    
    # 年度を抽出(次の行)
    fiscal_year_row = start_row + 1
    fy_text = str(df.iloc[fiscal_year_row, 1]) if pd.notna(df.iloc[fiscal_year_row, 1]) else ''
    match = re.search(r'(\d{4})年度', fy_text)
    if not match:
        return {'count': 0}
    fiscal_year = int(match.group(1))
    
    # 月のマッピング(Excelシリアル値 → 月)
    month_row_idx = start_row + 2
    month_cols = []
    for col_idx in range(2, len(df.columns)):
        val = df.iloc[month_row_idx, col_idx]
        if pd.notna(val):
            try:
                # Excelシリアル値をdatetimeに変換
                date_val = pd.to_datetime(val, unit='D', origin='1899-12-30')
                month = date_val.month
                month_cols.append((col_idx, month))
            except:
                continue
    
    # 事業所データを読み取り
    stats = {'count': 0}
    for i in range(start_row + 3, len(df)):
        branch_name_val = df.iloc[i, 1]
        if pd.isna(branch_name_val):
            break
        
        branch_name = str(branch_name_val).strip()
        
        # 除外するキーワード
        if branch_name in ['予算', '予算比', '昨年差', '昨年比', '合計', '']:
            continue
        
        # 各月の売上を登録
        for col_idx, month in month_cols:
            sales = df.iloc[i, col_idx]
            if pd.notna(sales) and float(sales) != 0:
                cursor.execute('''
                    INSERT OR REPLACE INTO branch_monthly_sales
                    (report_id, fiscal_year, month, branch_name, sales, budget)
                    VALUES (?, ?, ?, ?, ?, NULL)
                ''', (report_id, fiscal_year, month, branch_name, float(sales)))
                stats['count'] += 1
    
    return stats


def import_manager_monthly_sales(xlsx, cursor, report_id):
    """売上シートから担当者別月次売上を取り込み"""
    df = pd.read_excel(xlsx, sheet_name='売上', header=None)
    
    stats = {'count': 0}
    
    # ■売上 担当者別 セクションを探す
    for i in range(len(df)):
        cell = str(df.iloc[i, 1]) if pd.notna(df.iloc[i, 1]) else ''
        
        # 担当者別売上セクションのヘッダーを検出
        if '売上' in cell and '担当者別' in cell and '■' in cell:
            # このセクション内で年度ごとに処理
            j = i + 1
            while j < len(df):
                year_cell = str(df.iloc[j, 1]) if pd.notna(df.iloc[j, 1]) else ''
                
                # 次のセクション(■)が来たら終了
                if '■' in year_cell:
                    break
                
                # 年度ヘッダー検出: "YYYY年度 担当者別"
                year_match = re.search(r'(\d{4})年度', year_cell)
                if year_match and '担当者別' in year_cell:
                    fiscal_year = int(year_match.group(1))
                    
                    # ヘッダー行は年度ヘッダーの次の行 (空行があってもその次)
                    header_row_idx = j + 1
                    # 空行をスキップ
                    while header_row_idx < len(df):
                        header_cell = str(df.iloc[header_row_idx, 1]) if pd.notna(df.iloc[header_row_idx, 1]) else ''
                        # "年度"や"担当者別"を含む行もスキップ
                        if header_cell.strip() == '' or ('年度' in header_cell and '担当者別' in header_cell):
                            header_row_idx += 1
                        else:
                            break

                    
                    if header_row_idx >= len(df):
                        break
                    
                    header_row = df.iloc[header_row_idx]
                    
                    # 月カラムのマッピング
                    month_cols = []
                    for col_idx, header_val in enumerate(header_row):
                        if pd.isna(header_val):
                            continue
                        month = None
                        if '月' in str(header_val):
                            match = re.search(r'(\d{1,2})', str(header_val))
                            if match:
                                month = int(match.group(1))
                        elif isinstance(header_val, (int, float)):
                            month = excel_serial_to_month(header_val)
                        
                        if month:
                            month_cols.append((col_idx, month))
                    
                    # データ行を読み取る
                    data_row_idx = header_row_idx + 1
                    while data_row_idx < len(df):
                        manager_name = df.iloc[data_row_idx, 1]
                        
                        # 空行またはデータなし
                        if pd.isna(manager_name) or str(manager_name).strip() == '':
                            data_row_idx += 1
                            continue
                        
                        manager_name_str = str(manager_name).strip()
                        
                        # 次の年度ヘッダーまたはセクションヘッダーが来たら終了
                        if '年度' in manager_name_str or '■' in manager_name_str:
                            j = data_row_idx - 1  # 外側のループで再処理できるように
                            break
                        
                        manager_name_str = normalize_manager_name(manager_name_str, cursor.connection)
                        
                        # 各月の売上を取得
                        for col_idx, month in month_cols:
                            sales = df.iloc[data_row_idx, col_idx]
                            if pd.notna(sales) and float(sales) != 0:
                                cursor.execute('''
                                    INSERT OR REPLACE INTO manager_monthly_sales
                                    (report_id, fiscal_year, month, manager, sales)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (report_id, fiscal_year, month, manager_name_str, float(sales)))
                                stats['count'] += 1
                        
                        data_row_idx += 1
                
                j += 1
            
            # セクション終了、次のセクションを探す
            break
    
    return stats


def import_school_monthly_sales(xlsx, cursor, report_id, sheet_name, fiscal_year):
    """学校別月次売上を取り込み"""
    df = pd.read_excel(xlsx, sheet_name=sheet_name, header=None)
    
    # ヘッダー行を探す
    header_row_idx = None
    for i, row in df.iterrows():
        if pd.notna(row[1]):
            val = str(row[1])
            if '担当者' in val or val == '担当':
                header_row_idx = i
                break
    
    if header_row_idx is None:
        print(f"  警告: {sheet_name} でヘッダー行が見つかりません")
        return {'count': 0, 'unmatched_schools': []}
    
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
    
    stats = {'count': 0, 'unmatched_schools': []}
    
    # データ行を処理
    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]
        
        school_name = row[col_mapping.get('school', 3)]
        if pd.isna(school_name) or str(school_name).strip() == '':
            continue
        
        school_name = str(school_name).strip()
        manager = str(row[col_mapping.get('manager', 1)]).strip() if pd.notna(row[col_mapping.get('manager', 1)]) else None
        studio = str(row[col_mapping.get('studio', 2)]).strip() if pd.notna(row[col_mapping.get('studio', 2)]) else None
        
        # 担当者名正規化
        if manager:
            manager = normalize_manager_name(manager, cursor.connection)
        
        # 学校IDを取得(完全一致)
        school_id = get_school_id_by_name(cursor, school_name)
        if school_id is None:
            if school_name not in stats['unmatched_schools']:
                stats['unmatched_schools'].append(school_name)
            continue
        
        # 月別売上を登録
        for col_idx, fy, month in month_cols:
            sales = row[col_idx]
            if pd.notna(sales) and float(sales) != 0:
                cursor.execute('''
                    INSERT OR REPLACE INTO school_monthly_sales
                    (report_id, fiscal_year, month, school_id, manager, studio, sales)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (report_id, fy, month, school_id, manager, studio, float(sales)))
                stats['count'] += 1
    
    return stats


def import_event_sales(xlsx, cursor, report_id, sheet_name, fiscal_year):
    """イベント別売上を取り込み"""
    df = pd.read_excel(xlsx, sheet_name=sheet_name, header=None)
    
    # ヘッダー行を探す(全列を検索)
    header_row_idx = None
    for i, row in df.iterrows():
        for col_idx in range(len(row)):
            if pd.notna(row[col_idx]) and '学校名' in str(row[col_idx]):
                header_row_idx = i
                break
        if header_row_idx is not None:
            break
    
    if header_row_idx is None:
        print(f"  警告: {sheet_name} でヘッダー行が見つかりません")
        return {'count': 0, 'unmatched_schools': []}
    
    # ヘッダー解析
    header = df.iloc[header_row_idx]
    col_mapping = {}
    month_cols = []
    
    for col_idx, val in enumerate(header):
        if pd.isna(val):
            continue
        val_str = str(val)
        
        if '事業所' in val_str:
            col_mapping['branch'] = col_idx
        elif '学校名' in val_str:
            col_mapping['school'] = col_idx
        elif 'イベント名' in val_str:
            col_mapping['event'] = col_idx
        elif '開始日' in val_str or 'イベント日' in val_str:
            col_mapping['event_date'] = col_idx
        elif '月' in val_str:
            fy, month = parse_month_column(val_str)
            if month:
                month_cols.append((col_idx, fy or fiscal_year, month))
    
    stats = {'count': 0, 'unmatched_schools': []}
    
    # データ行を処理
    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]
        
        school_name = row[col_mapping.get('school', 2)]
        if pd.isna(school_name) or str(school_name).strip() == '':
            continue
        
        school_name = str(school_name).strip()
        branch = str(row[col_mapping.get('branch', 1)]).strip() if pd.notna(row[col_mapping.get('branch', 1)]) else None
        event_name = str(row[col_mapping.get('event', 3)]).strip() if pd.notna(row[col_mapping.get('event', 3)]) else None
        event_date = row[col_mapping.get('event_date', 4)] if 'event_date' in col_mapping else None
        
        # イベント日付を文字列に変換
        if pd.notna(event_date):
            if isinstance(event_date, datetime):
                event_date = event_date.date()
            else:
                event_date = str(event_date)
        else:
            event_date = None
        
        # 学校IDを取得
        school_id = get_school_id_by_name(cursor, school_name)
        if school_id is None:
            if school_name not in stats['unmatched_schools']:
                stats['unmatched_schools'].append(school_name)
            continue
        
        # 月別売上を登録
        for col_idx, fy, month in month_cols:
            sales = row[col_idx]
            if pd.notna(sales) and float(sales) != 0:
                cursor.execute('''
                    INSERT OR REPLACE INTO event_sales
                    (report_id, fiscal_year, month, branch, school_id, 
                     event_name, event_date, sales)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (report_id, fy, month, branch, school_id, event_name, event_date, float(sales)))
                stats['count'] += 1
    
    return stats


def import_member_rates(xlsx, cursor, report_id, report_date, sheet_name='会員率'):
    """会員率を取り込み"""
    # シート名を検索(日付が含まれる場合がある)
    sheet_names = pd.ExcelFile(xlsx).sheet_names
    target_sheet = None
    for sname in sheet_names:
        if '会員率' in sname:
            target_sheet = sname
            break
    
    if target_sheet is None:
        print(f"  警告: 会員率シートが見つかりません")
        return {'count': 0, 'unmatched_schools': []}
    
    df = pd.read_excel(xlsx, sheet_name=target_sheet, header=None)
    
    # ヘッダー行を探す(全列を検索)
    header_row_idx = None
    for i, row in df.iterrows():
        for col_idx in range(len(row)):
            if pd.notna(row[col_idx]) and '学校名' in str(row[col_idx]):
                header_row_idx = i
                break
        if header_row_idx is not None:
            break
    
    if header_row_idx is None:
        print(f"  警告: {target_sheet} でヘッダー行が見つかりません")
        return {'count': 0, 'unmatched_schools': []}
    
    # シート名から取得日を抽出
    snapshot_date = report_date  # デフォルトは報告書日付
    # 「■会員率（12月27日現在）」のような形式から日付を抽出
    date_match = re.search(r'(\d{1,2})月(\d{1,2})日', target_sheet)
    if date_match:
        month = int(date_match.group(1))
        day = int(date_match.group(2))
        # 年度を推定(4月以降ならreport_dateの年、それ以前なら翌年)
        year = report_date.year
        if month < 4 and report_date.month >= 4:
            year += 1
        elif month >= 4 and report_date.month < 4:
            year -= 1
        try:
            from datetime import date
            snapshot_date = date(year, month, day)
        except:
            snapshot_date = report_date
    
    # ヘッダー解析
    header = df.iloc[header_row_idx]
    col_mapping = {
        'school_id': None,
        'school': None,
        'grade': None,
        'total_students': None,
        'member_count': None
    }
    
    for col_idx, val in enumerate(header):
        if pd.isna(val):
            continue
        val_str = str(val)
        
        if '学校ID' in val_str:
            col_mapping['school_id'] = col_idx
        elif '学校名' in val_str:
            col_mapping['school'] = col_idx
        elif '学年' in val_str:
            col_mapping['grade'] = col_idx
        elif '生徒数' in val_str:
            col_mapping['total_students'] = col_idx
        elif '会員' in val_str and '登録' in val_str:
            col_mapping['member_count'] = col_idx
    
    stats = {'count': 0, 'unmatched_schools': []}
    
    # 会員率シートから学校情報を収集し、未登録学校を自動追加
    if col_mapping['school_id'] and col_mapping['school']:
        schools_to_add = {}
        
        # 学校情報を収集(重複除去)
        for i in range(header_row_idx + 1, len(df)):
            row = df.iloc[i]
            school_id_val = row[col_mapping['school_id']]
            school_name_val = row[col_mapping['school']]
            
            if pd.notna(school_id_val) and pd.notna(school_name_val):
                school_id = int(school_id_val)
                school_name = str(school_name_val).strip()
                if school_id not in schools_to_add:
                    schools_to_add[school_id] = school_name
        
        # schools_masterに未登録の学校を追加
        cursor.execute('SELECT MAX(logical_school_id) FROM schools_master')
        next_logical_id = (cursor.fetchone()[0] or 0) + 1
        
        added_count = 0
        for school_id, school_name in schools_to_add.items():
            cursor.execute('SELECT school_id FROM schools_master WHERE school_id = ?', (school_id,))
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO schools_master 
                    (school_id, logical_school_id, school_name, base_school_name, 
                     fiscal_year, region, attribute, studio, manager, updated_at)
                    VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, CURRENT_TIMESTAMP)
                ''', (school_id, next_logical_id, school_name, school_name))
                next_logical_id += 1
                added_count += 1
        
        cursor.connection.commit()
        if added_count > 0:
            print(f"  会員率シートから{added_count}校をschools_masterに自動追加しました")
    
    # データ行を処理
    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]
        
        school_name = row[col_mapping['school']] if col_mapping['school'] else None
        if pd.isna(school_name) or str(school_name).strip() == '':
            continue
        
        school_name = str(school_name).strip()
        
        # 学校IDを取得
        school_id = get_school_id_by_name(cursor, school_name)
        if school_id is None:
            if school_name not in stats['unmatched_schools']:
                stats['unmatched_schools'].append(school_name)
            continue
        
        # 学年
        grade = row[col_mapping['grade']] if col_mapping['grade'] else None
        if pd.isna(grade):
            continue
        grade = str(grade).strip()
        
        # 生徒数と会員数
        total_students = row[col_mapping['total_students']] if col_mapping['total_students'] else None
        member_count = row[col_mapping['member_count']] if col_mapping['member_count'] else None
        
        # 会員率を計算
        member_rate = None
        if pd.notna(total_students) and pd.notna(member_count):
            total_students = float(total_students)
            member_count = float(member_count)
            if total_students > 0:
                member_rate = member_count / total_students
        
        # データを登録
        cursor.execute('''
            INSERT OR REPLACE INTO member_rates
            (report_id, snapshot_date, school_id, grade, member_rate, 
             total_students, member_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (report_id, snapshot_date, school_id, grade, member_rate,
              int(total_students) if pd.notna(total_students) else None,
              int(member_count) if pd.notna(member_count) else None))
        stats['count'] += 1
    
    return stats


def import_excel_v2(file_path, db_path=None):
    """
    報告書Excelファイル全体をV2 DBに取り込み
    
    Returns:
        dict: {
            'success': bool,
            'report_id': int,
            'stats': dict,
            'error': str (エラー時のみ)
        }
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return {'success': False, 'error': f'ファイルが見つかりません: {file_path}'}
    
    # 報告書日付を抽出
    report_date = extract_report_date(file_path.name)
    if not report_date:
        return {'success': False, 'error': 'ファイル名から日付を抽出できません'}
    
    try:
        conn = get_connection(db_path)
        cursor = conn.cursor()
        
        # 既存の同じ日付の報告書を削除
        cursor.execute('SELECT id FROM reports WHERE report_date = ?', (report_date,))
        existing = cursor.fetchone()
        if existing:
            print(f"既存の報告書(ID: {existing[0]})を削除します")
            cursor.execute('DELETE FROM reports WHERE id = ?', (existing[0],))
        
        # 報告書メタデータを登録
        cursor.execute('''
            INSERT INTO reports (file_name, report_date)
            VALUES (?, ?)
        ''', (file_path.name, report_date))
        report_id = cursor.lastrowid
        
        print(f"\n報告書インポート開始: {file_path.name}")
        print(f"  Report ID: {report_id}")
        print(f"  報告書日付: {report_date}")
        
        xlsx = pd.ExcelFile(file_path)
        all_stats = {}
        all_unmatched_schools = []
        
        # 1. 月次全体売上
        print("\n[1/6] 月次全体売上を取り込み中...")
        stats = import_monthly_totals(xlsx, cursor, report_id)
        all_stats['monthly_totals'] = stats['count']
        print(f"  → {stats['count']}件を取り込みました")
        
        # 2. 事業所別売上
        print("\n[2/6] 事業所別売上を取り込み中...")
        stats = import_branch_monthly_sales(xlsx, cursor, report_id)
        all_stats['branch_monthly_sales'] = stats['count']
        print(f"  → {stats['count']}件を取り込みました")
        
        # 3. 担当者別月次売上
        print("\n[3/6] 担当者別月次売上を取り込み中...")
        stats = import_manager_monthly_sales(xlsx, cursor, report_id)
        all_stats['manager_monthly_sales'] = stats['count']
        print(f"  → {stats['count']}件を取り込みました")
        
        # 4. 学校別月次売上(複数年度)
        print("\n[4/6] 学校別月次売上を取り込み中...")
        school_sales_count = 0
        for sheet_name in xlsx.sheet_names:
            if '学校別' in sheet_name and '比較' not in sheet_name:
                # シート名から年度を抽出
                match = re.search(r'(\d{4})年度', sheet_name)
                if match:
                    fiscal_year = int(match.group(1))
                    print(f"  {sheet_name} を処理中...")
                    stats = import_school_monthly_sales(xlsx, cursor, report_id, sheet_name, fiscal_year)
                    school_sales_count += stats['count']
                    all_unmatched_schools.extend(stats['unmatched_schools'])
        all_stats['school_monthly_sales'] = school_sales_count
        print(f"  → {school_sales_count}件を取り込みました")
        
        # 5. イベント別売上(複数年度)
        print("\n[5/6] イベント別売上を取り込み中...")
        event_sales_count = 0
        for sheet_name in xlsx.sheet_names:
            if 'イベント別' in sheet_name:
                match = re.search(r'(\d{4})年度', sheet_name)
                if match:
                    fiscal_year = int(match.group(1))
                    print(f"  {sheet_name} を処理中...")
                    stats = import_event_sales(xlsx, cursor, report_id, sheet_name, fiscal_year)
                    event_sales_count += stats['count']
                    all_unmatched_schools.extend(stats['unmatched_schools'])
        all_stats['event_sales'] = event_sales_count
        print(f"  → {event_sales_count}件を取り込みました")
        
        # 6. 会員率
        print("\n[6/6] 会員率を取り込み中...")
        stats = import_member_rates(xlsx, cursor, report_id, report_date)
        all_stats['member_rates'] = stats['count']
        all_unmatched_schools.extend(stats['unmatched_schools'])
        print(f"  → {stats['count']}件を取り込みました")
        
        # 未登録学校のチェック
        all_unmatched_schools = list(set(all_unmatched_schools))
        if all_unmatched_schools:
            conn.rollback()
            conn.close()
            raise SchoolNotFoundError(all_unmatched_schools)
        
        # コミット
        conn.commit()
        conn.close()
        
        print("\n✅ インポート完了")
        print(f"統計: {all_stats}")
        
        return {
            'success': True,
            'report_id': report_id,
            'stats': all_stats
        }
        
    except SchoolNotFoundError as e:
        return {
            'success': False,
            'error': str(e),
            'unmatched_schools': e.school_names
        }
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}',
            'traceback': traceback.format_exc()
        }


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("使い方:")
        print("  python importer_v2.py <報告書Excelファイル>")
        sys.exit(1)
    
    result = import_excel_v2(sys.argv[1])
    
    if result['success']:
        print(f"\n成功: Report ID {result['report_id']}")
    else:
        print(f"\nエラー: {result['error']}")
        if 'unmatched_schools' in result:
            print("\n未登録学校:")
            for school in result['unmatched_schools']:
                print(f"  - {school}")
