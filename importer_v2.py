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


def import_manager_monthly_sales(xlsx, cursor, report_id):
    """売上シートから担当者別月次売上を取り込み"""
    df = pd.read_excel(xlsx, sheet_name='売上', header=None)
    
    current_fiscal_year = None
    stats = {'count': 0}
    
    for i, row in df.iterrows():
        cell = str(row[1]) if pd.notna(row[1]) else ''
        
        # 年度ヘッダー検出
        if re.match(r'\d{4}年度', cell):
            current_fiscal_year = int(re.search(r'(\d{4})', cell).group(1))
            continue
        
        # 担当者別売上セクション検出
        if current_fiscal_year and '売上　担当者別' in cell:
            header_row_idx = i + 1
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
            for data_row_idx in range(header_row_idx + 1, len(df)):
                manager_name = df.iloc[data_row_idx, 1]
                if pd.isna(manager_name) or str(manager_name).strip() == '':
                    continue
                
                # 次のセクションヘッダーが来たら終了
                if '■' in str(manager_name):
                    break
                
                manager_name = str(manager_name).strip()
                manager_name = normalize_manager_name(manager_name, cursor.connection)
                
                # 各月の売上を取得
                for col_idx, month in month_cols:
                    sales = df.iloc[data_row_idx, col_idx]
                    if pd.notna(sales) and float(sales) != 0:
                        cursor.execute('''
                            INSERT OR REPLACE INTO manager_monthly_sales
                            (report_id, fiscal_year, month, manager, sales)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (report_id, current_fiscal_year, month, manager_name, float(sales)))
                        stats['count'] += 1
    
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
    
    # ヘッダー行を探す
    header_row_idx = None
    for i, row in df.iterrows():
        if pd.notna(row[1]) and '学校名' in str(row[1]):
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
    
    # ヘッダー行を探す
    header_row_idx = None
    for i, row in df.iterrows():
        if pd.notna(row[1]) and '学校名' in str(row[1]):
            header_row_idx = i
            break
    
    if header_row_idx is None:
        print(f"  警告: {target_sheet} でヘッダー行が見つかりません")
        return {'count': 0, 'unmatched_schools': []}
    
    # ヘッダー解析
    header = df.iloc[header_row_idx]
    col_mapping = {'school': None, 'grades': []}
    
    for col_idx, val in enumerate(header):
        if pd.isna(val):
            continue
        val_str = str(val)
        
        if '学校名' in val_str:
            col_mapping['school'] = col_idx
        elif ('年' in val_str or '歳' in val_str) and '会員率' in val_str:
            # 学年名を抽出
            grade = val_str.replace('会員率', '').strip()
            col_mapping['grades'].append((col_idx, grade))
    
    stats = {'count': 0, 'unmatched_schools': []}
    
    # データ行を処理
    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]
        
        school_name = row[col_mapping['school']]
        if pd.isna(school_name) or str(school_name).strip() == '':
            continue
        
        school_name = str(school_name).strip()
        
        # 学校IDを取得
        school_id = get_school_id_by_name(cursor, school_name)
        if school_id is None:
            if school_name not in stats['unmatched_schools']:
                stats['unmatched_schools'].append(school_name)
            continue
        
        # 各学年の会員率を登録
        for col_idx, grade in col_mapping['grades']:
            member_rate = row[col_idx]
            if pd.notna(member_rate):
                # パーセント値を小数に変換(100% → 1.0)
                if isinstance(member_rate, str) and '%' in member_rate:
                    member_rate = float(member_rate.replace('%', '')) / 100
                elif isinstance(member_rate, (int, float)):
                    # 既に小数の場合はそのまま、100以上なら/100
                    if member_rate > 1:
                        member_rate = member_rate / 100
                
                cursor.execute('''
                    INSERT OR REPLACE INTO member_rates
                    (report_id, snapshot_date, school_id, grade, member_rate, 
                     total_students, member_count)
                    VALUES (?, ?, ?, ?, ?, NULL, NULL)
                ''', (report_id, report_date, school_id, grade, float(member_rate)))
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
        print("\n[1/5] 月次全体売上を取り込み中...")
        stats = import_monthly_totals(xlsx, cursor, report_id)
        all_stats['monthly_totals'] = stats['count']
        print(f"  → {stats['count']}件を取り込みました")
        
        # 2. 担当者別月次売上
        print("\n[2/5] 担当者別月次売上を取り込み中...")
        stats = import_manager_monthly_sales(xlsx, cursor, report_id)
        all_stats['manager_monthly_sales'] = stats['count']
        print(f"  → {stats['count']}件を取り込みました")
        
        # 3. 学校別月次売上(複数年度)
        print("\n[3/5] 学校別月次売上を取り込み中...")
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
        
        # 4. イベント別売上(複数年度)
        print("\n[4/5] イベント別売上を取り込み中...")
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
        
        # 5. 会員率
        print("\n[5/5] 会員率を取り込み中...")
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
