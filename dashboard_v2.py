#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上分析システム V2 - ダッシュボード生成

既存ダッシュボードと同じデザイン・機能をV2スキーマで実装
"""

import json
from datetime import datetime
from pathlib import Path
from database_v2 import (
    get_connection, get_rapid_growth_schools, get_new_schools, get_no_events_schools, get_declining_schools
)    


def get_available_fiscal_years(db_path=None):
    """DBに存在する年度一覧を取得（降順）"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DISTINCT fiscal_year FROM monthly_totals
        UNION
        SELECT DISTINCT fiscal_year FROM school_monthly_sales
        ORDER BY fiscal_year DESC
    ''')
    years = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return years if years else [datetime.now().year]


def get_summary_stats(db_path=None, fiscal_year=None):
    """サマリー統計を取得"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # 年度が指定されていない場合は最新年度
    if fiscal_year is None:
        cursor.execute('SELECT MAX(fiscal_year) FROM monthly_totals')
        fiscal_year = cursor.fetchone()[0] or datetime.now().year
    
    prev_fiscal_year = fiscal_year - 1
    
    # 最新の報告書ID
    cursor.execute('SELECT MAX(id) FROM reports')
    latest_report_id = cursor.fetchone()[0]
    
    # 報告書日付
    cursor.execute('SELECT report_date FROM reports WHERE id = ?', (latest_report_id,))
    row = cursor.fetchone()
    report_date = row[0] if row else datetime.now().strftime('%Y-%m-%d')
    
    # 今年度累計売上
    cursor.execute('''
        SELECT SUM(total_sales) FROM monthly_totals
        WHERE report_id = ? AND fiscal_year = ?
    ''', (latest_report_id, fiscal_year))
    current_total = cursor.fetchone()[0] or 0
    
    # 今年度にデータがある月を取得
    cursor.execute('''
        SELECT month FROM monthly_totals
        WHERE report_id = ? AND fiscal_year = ?
    ''', (latest_report_id, fiscal_year))
    current_months = [row[0] for row in cursor.fetchall()]
    
    # 前年度同期売上（今年度と同じ月のみ集計）
    if current_months:
        placeholders = ','.join(['?' for _ in current_months])
        cursor.execute(f'''
            SELECT SUM(total_sales) FROM monthly_totals
            WHERE report_id = ? AND fiscal_year = ? AND month IN ({placeholders})
        ''', (latest_report_id, prev_fiscal_year, *current_months))
        prev_total = cursor.fetchone()[0] or 0
    else:
        prev_total = 0
    
    # 平均予算達成率
    cursor.execute('''
        SELECT AVG(CAST(total_sales AS FLOAT) / NULLIF(budget, 0))
        FROM monthly_totals
        WHERE report_id = ? AND fiscal_year = ? AND budget > 0
    ''', (latest_report_id, fiscal_year))
    avg_budget_rate = cursor.fetchone()[0] or 0
    
    # 学校数
    cursor.execute('SELECT COUNT(DISTINCT school_id) FROM schools_master')
    school_count = cursor.fetchone()[0]
    
    # 今年度イベント数
    cursor.execute('''
        SELECT COUNT(DISTINCT event_name) FROM event_sales
        WHERE fiscal_year = ? AND report_id = ?
    ''', (fiscal_year, latest_report_id))
    event_count = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'report_date': report_date,
        'fiscal_year': fiscal_year,
        'current_total': current_total,
        'prev_total': prev_total,
        'yoy_rate': current_total / prev_total if prev_total > 0 else 0,
        'avg_budget_rate': avg_budget_rate,
        'school_count': school_count,
        'event_count': event_count
    }


def get_monthly_data(db_path=None, fiscal_year=None):
    """月別売上データを取得"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    if fiscal_year is None:
        cursor.execute('SELECT MAX(fiscal_year) FROM monthly_totals')
        fiscal_year = cursor.fetchone()[0]
    
    cursor.execute('SELECT MAX(id) FROM reports')
    latest_report_id = cursor.fetchone()[0]
    
    # 今年度データ
    cursor.execute('''
        SELECT month, total_sales, budget
        FROM monthly_totals
        WHERE report_id = ? AND fiscal_year = ?
        ORDER BY CASE WHEN month >= 4 THEN month - 4 ELSE month + 8 END
    ''', (latest_report_id, fiscal_year))
    
    monthly_data = []
    for row in cursor.fetchall():
        monthly_data.append({
            'month': row[0],
            'sales': row[1] or 0,
            'budget': row[2] or 0
        })
    
    # 前年度データ
    prev_fiscal_year = fiscal_year - 1
    cursor.execute('''
        SELECT month, total_sales
        FROM monthly_totals
        WHERE report_id = ? AND fiscal_year = ?
        ORDER BY CASE WHEN month >= 4 THEN month - 4 ELSE month + 8 END
    ''', (latest_report_id, prev_fiscal_year))
    
    prev_monthly_data = {row[0]: row[1] or 0 for row in cursor.fetchall()}
    
    # 前年度売上を追加
    for item in monthly_data:
        item['prev_sales'] = prev_monthly_data.get(item['month'], 0)
    
    conn.close()
    return monthly_data


def get_branch_sales(db_path=None, fiscal_year=None):
    """事業所別売上データを取得"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    if fiscal_year is None:
        cursor.execute('SELECT MAX(fiscal_year) FROM branch_monthly_sales')
        fiscal_year = cursor.fetchone()[0]
    
    cursor.execute('SELECT MAX(id) FROM reports')
    latest_report_id = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT branch_name, SUM(sales) as total
        FROM branch_monthly_sales
        WHERE fiscal_year = ? AND report_id = ?
        GROUP BY branch_name
        ORDER BY total DESC
    ''', (fiscal_year, latest_report_id))
    
    results = cursor.fetchall()
    conn.close()
    
    return [{'branch': row[0], 'sales': row[1]} for row in results]


def get_top_schools(db_path=None, fiscal_year=None, limit=10):
    """学校別売上TOP10を取得"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    if fiscal_year is None:
        cursor.execute('SELECT MAX(fiscal_year) FROM school_monthly_sales')
        fiscal_year = cursor.fetchone()[0]
    
    cursor.execute('SELECT MAX(id) FROM reports')
    latest_report_id = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT s.school_name, SUM(sm.sales) as total
        FROM school_monthly_sales sm
        JOIN schools_master s ON sm.school_id = s.school_id
        WHERE sm.fiscal_year = ? AND sm.report_id = ?
        GROUP BY sm.school_id, s.school_name
        ORDER BY total DESC
        LIMIT ?
    ''', (fiscal_year, latest_report_id, limit))
    
    results = cursor.fetchall()
    conn.close()
    
    return [{'school': row[0], 'sales': row[1]} for row in results]


def get_branch_monthly_sales(db_path=None, fiscal_year=None):
    """事業所別の月次売上データを取得(当年度と前年度)"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    if fiscal_year is None:
        cursor.execute('SELECT MAX(fiscal_year) FROM branch_monthly_sales')
        fiscal_year = cursor.fetchone()[0]
    
    cursor.execute('SELECT MAX(id) FROM reports')
    latest_report_id = cursor.fetchone()[0]
    
    # 当年度データ
    cursor.execute('''
        SELECT branch_name, month, SUM(sales) as total
        FROM branch_monthly_sales
        WHERE fiscal_year = ? AND report_id = ?
        GROUP BY branch_name, month
        ORDER BY branch_name, CASE WHEN month >= 4 THEN month - 4 ELSE month + 8 END
    ''', (fiscal_year, latest_report_id))
    
    current_results = cursor.fetchall()
    
    # 前年度データ
    prev_fiscal_year = fiscal_year - 1
    cursor.execute('''
        SELECT branch_name, month, SUM(sales) as total
        FROM branch_monthly_sales
        WHERE fiscal_year = ? AND report_id = ?
        GROUP BY branch_name, month
        ORDER BY branch_name, CASE WHEN month >= 4 THEN month - 4 ELSE month + 8 END
    ''', (prev_fiscal_year, latest_report_id))
    
    prev_results = cursor.fetchall()
    conn.close()
    
    # データを整形: {branch: {'current': [{month, sales}, ...], 'prev': [...]}}
    data = {}
    for row in current_results:
        branch, month, sales = row
        if branch not in data:
            data[branch] = {'current': [], 'prev': []}
        data[branch]['current'].append({'month': month, 'sales': sales})
    
    for row in prev_results:
        branch, month, sales = row
        if branch not in data:
            data[branch] = {'current': [], 'prev': []}
        data[branch]['prev'].append({'month': month, 'sales': sales})
    
    return data


def get_manager_monthly_sales(db_path=None, fiscal_year=None):
    """担当者別の月次売上データを取得(当年度と前年度)"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    if fiscal_year is None:
        cursor.execute('SELECT MAX(fiscal_year) FROM manager_monthly_sales')
        fiscal_year = cursor.fetchone()[0]
    
    cursor.execute('SELECT MAX(id) FROM reports')
    latest_report_id = cursor.fetchone()[0]
    
    # 当年度データ
    cursor.execute('''
        SELECT manager, month, SUM(sales) as total
        FROM manager_monthly_sales
        WHERE fiscal_year = ? AND report_id = ?
        GROUP BY manager, month
        ORDER BY manager, CASE WHEN month >= 4 THEN month - 4 ELSE month + 8 END
    ''', (fiscal_year, latest_report_id))
    
    current_results = cursor.fetchall()
    
    # 前年度データ
    prev_fiscal_year = fiscal_year - 1
    cursor.execute('''
        SELECT manager, month, SUM(sales) as total
        FROM manager_monthly_sales
        WHERE fiscal_year = ? AND report_id = ?
        GROUP BY manager, month
        ORDER BY manager, CASE WHEN month >= 4 THEN month - 4 ELSE month + 8 END
    ''', (prev_fiscal_year, latest_report_id))
    
    prev_results = cursor.fetchall()
    conn.close()
    
    # データを整形: {manager: {'current': [{month, sales}, ...], 'prev': [...]}}
    data = {}
    for row in current_results:
        manager, month, sales = row
        if manager not in data:
            data[manager] = {'current': [], 'prev': []}
        data[manager]['current'].append({'month': month, 'sales': sales})
    
    for row in prev_results:
        manager, month, sales = row
        if manager not in data:
            data[manager] = {'current': [], 'prev': []}
        data[manager]['prev'].append({'month': month, 'sales': sales})
    
    return data


def get_schools_list(db_path=None):
    """学校一覧を取得（会員率・売上推移グラフ用）"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DISTINCT school_id, school_name, attribute, studio, region, manager
        FROM schools_master
        WHERE school_id IN (
            SELECT DISTINCT school_id FROM member_rates
            UNION
            SELECT DISTINCT school_id FROM school_monthly_sales
        )
        ORDER BY school_name
    ''')
    
    results = cursor.fetchall()
    conn.close()
    
    return [{'id': row[0], 'name': row[1], 'region': row[2], 'studio': row[3], 'branch': row[4], 'manager': row[5]} for row in results]


def get_member_rates_by_school(db_path=None, school_id=None, fiscal_year=None):
    """特定学校の会員率推移を取得（指定年度の全月データ）"""
    if school_id is None:
        return []
    
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # 年度未指定の場合は最新年度を取得
    if fiscal_year is None:
        cursor.execute('''
            SELECT MAX(
                CASE 
                    WHEN CAST(strftime('%m', snapshot_date) AS INTEGER) >= 4 
                    THEN CAST(strftime('%Y', snapshot_date) AS INTEGER)
                    ELSE CAST(strftime('%Y', snapshot_date) AS INTEGER) - 1
                END
            ) as max_fy
            FROM member_rates
            WHERE school_id = ?
        ''', (school_id,))
        result = cursor.fetchone()
        fiscal_year = result[0] if result and result[0] else 2025
    
    # 各snapshot_dateごとの最新report_idを使用（指定年度のみ）
    cursor.execute('''
        WITH latest_snapshots AS (
            SELECT snapshot_date, MAX(report_id) as max_report_id
            FROM member_rates
            WHERE school_id = ?
              AND (
                CASE 
                    WHEN CAST(strftime('%m', snapshot_date) AS INTEGER) >= 4 
                    THEN CAST(strftime('%Y', snapshot_date) AS INTEGER)
                    ELSE CAST(strftime('%Y', snapshot_date) AS INTEGER) - 1
                END
              ) = ?
            GROUP BY snapshot_date
        )
        SELECT m.snapshot_date, m.grade, m.member_rate, m.total_students, m.member_count
        FROM member_rates m
        JOIN latest_snapshots ls ON m.snapshot_date = ls.snapshot_date AND m.report_id = ls.max_report_id
        WHERE m.school_id = ? AND m.grade != '全学年'
        ORDER BY m.snapshot_date, m.grade
    ''', (school_id, fiscal_year, school_id))
    
    grade_results = cursor.fetchall()
    
    # 全学年合計データをSQL内で計算（指定年度のみ）
    cursor.execute('''
        WITH latest_snapshots AS (
            SELECT snapshot_date, MAX(report_id) as max_report_id
            FROM member_rates
            WHERE school_id = ?
              AND (
                CASE 
                    WHEN CAST(strftime('%m', snapshot_date) AS INTEGER) >= 4 
                    THEN CAST(strftime('%Y', snapshot_date) AS INTEGER)
                    ELSE CAST(strftime('%Y', snapshot_date) AS INTEGER) - 1
                END
              ) = ?
            GROUP BY snapshot_date
        )
        SELECT 
            m.snapshot_date,
            SUM(m.total_students) as sum_total,
            SUM(m.member_count) as sum_member,
            ROUND(CAST(SUM(m.member_count) AS FLOAT) / NULLIF(SUM(m.total_students), 0) * 100, 1) as calc_rate
        FROM member_rates m
        JOIN latest_snapshots ls ON m.snapshot_date = ls.snapshot_date AND m.report_id = ls.max_report_id
        WHERE m.school_id = ? AND m.grade != '全学年'
        GROUP BY m.snapshot_date
        ORDER BY m.snapshot_date
    ''', (school_id, fiscal_year, school_id))
    
    all_grade_results = cursor.fetchall()
    conn.close()
    
    # データを整形 (snapshot_date毎にグループ化)
    data = {}
    
    # 学年別データを追加
    for row in grade_results:
        snapshot_date, grade, rate, total_students, member_count = row
        if snapshot_date not in data:
            data[snapshot_date] = []
        # DB内のrateは小数形式（0.862）なので100倍してパーセント形式に変換
        rate_percent = round(rate * 100, 1) if rate is not None else 0
        data[snapshot_date].append({
            'grade': grade,
            'rate': rate_percent,
            'total_students': total_students,
            'member_count': member_count
        })
    
    # 全学年合計データを追加（SQL側で計算済み）
    for row in all_grade_results:
        snapshot_date, sum_total, sum_member, calc_rate = row
        if snapshot_date not in data:
            data[snapshot_date] = []
        data[snapshot_date].append({
            'grade': '全学年',
            'rate': calc_rate or 0,
            'total_students': sum_total,
            'member_count': sum_member
        })
    
    return data





def get_school_monthly_sales(db_path=None, school_id=None):
    """特定学校の月次売上推移を取得（全年度）"""
    if school_id is None:
        return {}
    
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT MAX(id) FROM reports')
    latest_report_id = cursor.fetchone()[0]
    
    # 全年度のデータを取得
    cursor.execute('''
        SELECT fiscal_year, month, sales
        FROM school_monthly_sales
        WHERE school_id = ? AND report_id = ?
        ORDER BY fiscal_year DESC, month
    ''', (school_id, latest_report_id))
    
    results = cursor.fetchall()
    conn.close()
    
    # 年度ごとに整形
    data = {}
    for row in results:
        fiscal_year, month, sales = row
        if fiscal_year not in data:
            data[fiscal_year] = []
        data[fiscal_year].append({'month': month, 'sales': sales})
    
    return data


def get_event_sales_data(db_path=None, fiscal_year=None, limit=10):
    """イベント別売上TOPを取得"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    if fiscal_year is None:
        cursor.execute('SELECT MAX(fiscal_year) FROM event_sales')
        fiscal_year = cursor.fetchone()[0]
    
    cursor.execute('SELECT MAX(id) FROM reports')
    latest_report_id = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT event_name, SUM(sales) as total
        FROM event_sales
        WHERE fiscal_year = ? AND report_id = ?
        GROUP BY event_name
        ORDER BY total DESC
        LIMIT ?
    ''', (fiscal_year, latest_report_id, limit))
    
    results = cursor.fetchall()
    conn.close()
    
    return [{'event': row[0], 'sales': row[1]} for row in results]


def get_member_rate_distribution(db_path=None, fiscal_year=None):
    """会員率分布データ(散布図用)を取得"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    if fiscal_year is None:
        cursor.execute('SELECT MAX(fiscal_year) FROM member_rates')
        fiscal_year = cursor.fetchone()[0]
    
    cursor.execute('SELECT MAX(id) FROM reports')
    latest_report_id = cursor.fetchone()[0]
    
    # 最新のスナップショット日付を取得
    cursor.execute('''
        SELECT MAX(snapshot_date) FROM member_rates
        WHERE report_id = ?
    ''', (latest_report_id,))
    latest_date = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT s.school_name, m.total_students, m.member_rate, s.region
        FROM member_rates m
        JOIN schools_master s ON m.school_id = s.school_id
        WHERE m.report_id = ? AND m.snapshot_date = ?
          AND m.total_students > 0 AND m.member_rate IS NOT NULL
    ''', (latest_report_id, latest_date))
    
    results = cursor.fetchall()
    conn.close()
    
    return [{
        'school': row[0],
        'total_students': row[1],
        'rate': row[2],
        'region': row[3] or '未分類'
    } for row in results]


def generate_dashboard(db_path=None, output_dir=None):
    """ダッシュボードHTMLを生成"""
    
    if output_dir is None:
        output_dir = Path.cwd()
    else:
        output_dir = Path(output_dir)
    
    # 利用可能な年度一覧を取得
    available_years = get_available_fiscal_years(db_path)
    
    # 各年度のデータを取得
    all_years_data = {}
    for year in available_years:
        all_years_data[year] = {
            'stats': get_summary_stats(db_path, year),
            'monthly': get_monthly_data(db_path, year),
            'branch': get_branch_sales(db_path, year),
            'branch_monthly': get_branch_monthly_sales(db_path, year),
            'manager_monthly': get_manager_monthly_sales(db_path, year),
            'top_schools': get_top_schools(db_path, year, limit=20),
            'top_events': get_event_sales_data(db_path, year, limit=10),
            'member_rates': get_member_rate_distribution(db_path, year)
        }
    
    # 学校一覧を取得（全年度共通）
    schools_list = get_schools_list(db_path)
    
    # 学校別の詳細データを収集（売上推移と会員率）
    school_details = {}
    for school in schools_list:
        school_id = school['id']
        school_details[school_id] = {
            'name': school['name'],
            'monthly_sales': get_school_monthly_sales(db_path, school_id),
            'member_rates': get_member_rates_by_school(db_path, school_id)
        }
    
    # 条件別集計データを取得
    rapid_growth_data = get_rapid_growth_schools(db_path)
    
    # デフォルトは最新年度
    default_year =available_years[0] if available_years else datetime.now().year
    stats = all_years_data[default_year]['stats']
    
    # 売上好調校データの取得（今年度のみ）
    print("   売上好調校データを取得中...")
    rapid_growth_schools = get_rapid_growth_schools(db_path, target_fy=default_year)
    rapid_growth_data = [
        {
            'school_name': r['school_name'],
            'attribute': r['attribute'],
            'studio': r['studio'],
            'manager': r['manager'],
            'region': r['region'],
            'current_sales': r['current_sales'],
            'prev_sales': r['prev_sales'],
            'growth_rate': r['growth_rate']
        }
        for r in rapid_growth_schools
    ]
    
    # 新規開始校データの取得（全年度）
    print("   新規開始校データを取得中...")
    new_schools_all = {}
    for y in available_years:
        schools = get_new_schools(db_path, target_fy=y)
        new_schools_all[y] = [
            {
                'school_name': r['school_name'],
                'attribute': r['attribute'],
                'studio': r['studio'],
                'manager': r['manager'],
                'region': r['region'],
                'current_sales': r['current_sales'],
                'prev_sales': r['prev_sales'],
                'growth_rate': r['growth_rate']
            }
            for r in schools
        ]
    
    # 今年度未実施校データの取得（全年度）
    print("   今年度未実施校データを取得中...")
    no_events_all = {}
    for y in available_years:
        schools = get_no_events_schools(db_path, target_fy=y)
        no_events_all[y] = [
            {
                'school_name': r['school_name'],
                'attribute': r['attribute'],
                'studio': r['studio'],
                'manager': r['manager'],
                'region': r['region'],
                'current_sales': r['current_sales'],
                'prev_sales': r['prev_sales'],
                'growth_rate': r['growth_rate']
            }
            for r in schools
        ]
    
    # 会員率・売上低下校データの取得（今年度のみ・ベース条件での取得）
    print("   会員率・売上低下校データを取得中...")
    decline_data_raw = get_declining_schools(db_path, target_fy=default_year, member_rate_threshold=1.1, sales_decline_threshold=0.0)
    print(f"   -> 取得件数: {len(decline_data_raw)}件")
    decline_data = [
        {
            'school_name': r['school_name'],
            'attribute': r['attribute'],
            'studio': r['studio'],
            'manager': r['manager'],
            'region': r['region'],
            'current_sales': r['current_sales'],
            'prev_sales': r['prev_sales'],
            'growth_rate': r['growth_rate'],
            'member_rate': r['member_rate']
        }
        for r in decline_data_raw
    ]

    # HTMLファイル名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'dashboard_{timestamp}.html'
    
    # HTML生成
    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>スクールフォト売上分析ダッシュボード V2</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', 'Hiragino Sans', 'Meiryo', sans-serif;
            background: linear-gradient(135deg, #3b82f6 0%, #1e40af 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1600px; margin: 0 auto; }}
        .header {{
            background: white;
            border-radius: 16px;
            padding: 24px 32px;
            margin-bottom: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{ font-size: 28px; color: #1a1a2e; }}
        .header .date {{ color: #666; font-size: 14px; }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .card-title {{
            font-size: 12px;
            color: #666;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .card-value {{
            font-size: 28px;
            font-weight: 700;
            color: #1a1a2e;
        }}
        .card-value.success {{ color: #10b981; }}
        .card-value.warning {{ color: #f59e0b; }}
        .card-value.danger {{ color: #ef4444; }}
        .card-sub {{ font-size: 12px; color: #888; margin-top: 4px; }}
        .chart-card {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            margin-bottom: 24px;
        }}
        .chart-card h3 {{
            font-size: 18px;
            color: #1a1a2e;
            margin-bottom: 20px;
            border-bottom: 2px solid #3b82f6;
            padding-bottom: 10px;
        }}
        canvas {{ max-height: 400px; }}
        select {{
            padding: 8px 14px;
            border: 2px solid #3b82f6;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            color: #1a1a2e;
            cursor: pointer;
            background: white;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>📊 スクールフォト売上分析ダッシュボード V2</h1>
                <p class="date" id="reportDate">レポート日: {stats['report_date']}</p>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 12px; color: #666;">年度選択</div>
                <select id="yearSelect" onchange="switchYear()" style="min-width: 150px; margin-top: 8px;">
                    {chr(10).join([f'<option value="{y}" {"selected" if y == default_year else ""}>{y}年度</option>' for y in available_years])}
                </select>
            </div>
        </div>
        
        <div class="summary-cards">
            <div class="card">
                <div class="card-title" id="salesCardTitle">{stats['fiscal_year']}年度 累計売上</div>
                <div class="card-value" id="salesCardValue">¥{stats['current_total']:,.0f}</div>
                <div class="card-sub" id="salesCardSub">前年同期 ¥{stats['prev_total']:,.0f}</div>
            </div>
            <div class="card">
                <div class="card-title">前年比</div>
                <div class="card-value {'success' if stats['yoy_rate'] >= 1 else 'warning' if stats['yoy_rate'] >= 0.8 else 'danger'}" id="yoyCardValue">{stats['yoy_rate']*100:.1f}%</div>
                <div class="card-sub" id="yoyCardSub">{'成長' if stats['yoy_rate'] >= 1 else '減少'}</div>
            </div>
            <div class="card">
                <div class="card-title">平均予算達成率</div>
                <div class="card-value {'success' if stats['avg_budget_rate'] >= 1 else 'warning' if stats['avg_budget_rate'] >= 0.8 else 'danger'}" id="budgetCardValue">{stats['avg_budget_rate']*100:.1f}%</div>
                <div class="card-sub">目標: 100%</div>
            </div>
            <div class="card">
                <div class="card-title">学校/イベント数</div>
                <div class="card-value" id="countCardValue">{stats['school_count']}/{stats['event_count']}</div>
                <div class="card-sub">蓄積データ</div>
            </div>
        </div>
        
        <!-- 月別売上推移セクション -->
        <div class="chart-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h3 style="margin: 0; border: none; padding: 0;">月別売上推移</h3>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <label style="font-size: 14px; color: #666; font-weight: 600;">年度:</label>
                    <select id="monthlySalesYearSelect" onchange="changeMonthlySalesYear()" style="padding: 8px 14px; border: 2px solid #3b82f6; border-radius: 8px; font-size: 14px; font-weight: 600; color: #1a1a2e; cursor: pointer; background: white;">
                        {chr(10).join([f'<option value="{y}" {"selected" if y == default_year else ""}>{y}年度</option>' for y in available_years])}
                    </select>
                </div>
            </div>
            <div style="display: flex; gap: 0; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0;">
                <button id="tabMonthly" onclick="switchMonthlySalesTab('monthly')" class="monthly-tab active" style="padding: 10px 20px; border: none; background: transparent; font-size: 14px; font-weight: 600; color: #3b82f6; cursor: pointer; border-bottom: 3px solid #3b82f6; margin-bottom: -2px;">月ごと</button>
                <button id="tabBranch" onclick="switchMonthlySalesTab('branch')" class="monthly-tab" style="padding: 10px 20px; border: none; background: transparent; font-size: 14px; font-weight: 600; color: #666; cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px;">事業所ごと</button>
                <button id="tabManager" onclick="switchMonthlySalesTab('manager')" class="monthly-tab" style="padding: 10px 20px; border: none; background: transparent; font-size: 14px; font-weight: 600; color: #666; cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px;">担当者ごと</button>
            </div>
            
            <!-- 月ごとパネル -->
            <div id="monthlyPanel" class="monthly-panel">
                <canvas id="monthlyChart"></canvas>
            </div>
            
            <!-- 事業所ごとパネル -->
            <div id="branchMonthlyPanel" class="monthly-panel" style="display: none;">
                <div style="margin-bottom: 16px;">
                    <label style="font-size: 12px; color: #666; font-weight: 600; margin-right: 8px;">事業所:</label>
                    <select id="branchFilter" onchange="renderBranchMonthlyChart()" style="padding: 8px 12px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 150px;">
                        <option value="">-- 全事業所 --</option>
                    </select>
                </div>
                <canvas id="branchMonthlyChart"></canvas>
            </div>
            
            <!-- 担当者ごとパネル -->
            <div id="managerPanel" class="monthly-panel" style="display: none;">
                <div style="margin-bottom: 16px;">
                    <label style="font-size: 12px; color: #666; font-weight: 600; margin-right: 8px;">担当者:</label>
                    <select id="managerFilter" onchange="renderManagerChart()" style="padding: 8px 12px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 200px;">
                        <option value="">-- 選択してください --</option>
                    </select>
                </div>
                <div id="managerChartMessage" style="text-align: center; padding: 60px 20px; color: #888; font-size: 14px;">担当者を選択してください</div>
                <canvas id="managerChart" style="display: none;"></canvas>
            </div>
        </div>
        
        
        <!-- 学校別分析セクション -->
        <div class="chart-card">
            <h3>学校別分析</h3>
            <div style="display: flex; gap: 0; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0;">
                <button id="tabMemberRate" class="school-analysis-tab active" onclick="switchSchoolAnalysisTab('memberRate')" style="padding: 12px 24px; background: none; border: none; border-bottom: 3px solid #3b82f6; color: #3b82f6; font-weight: 600; cursor: pointer; font-size: 14px;">会員率推移</button>
                <button id="tabSalesTrend" class="school-analysis-tab" onclick="switchSchoolAnalysisTab('salesTrend')" style="padding: 12px 24px; background: none; border: none; border-bottom: 3px solid transparent; color: #666; font-weight: 600; cursor: pointer; font-size: 14px;">学校別売上推移</button>
            </div>
            
            <!-- 会員率推移パネル -->
            <div id="memberRatePanel" class="school-analysis-panel">
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;">
                    <div>
                        <label style="font-size: 12px; color: #666; font-weight: 600; display: block; margin-bottom: 4px;">写真館:</label>
                        <select id="memberStudioFilter" onchange="updateMemberRegionList(); updateMemberSchoolList();" style="width: 100%; padding: 8px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px;">
                            <option value="">-- 全て --</option>
                        </select>
                    </div>
                    <div>
                        <label style="font-size: 12px; color: #666; font-weight: 600; display: block; margin-bottom: 4px;">属性:</label>
                        <select id="memberRegionFilter" onchange="updateMemberSchoolList();" style="width: 100%; padding: 8px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px;">
                            <option value="">-- 全て --</option>
                        </select>
                    </div>
                    <div>
                        <label style="font-size: 12px; color: #666; font-weight: 600; display: block; margin-bottom: 4px;">学校名:</label>
                        <select id="memberSchoolFilter" style="width: 100%; padding: 8px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px;">
                            <option value="">-- 選択してください --</option>
                        </select>
                    </div>
                    <div>
                        <label style="font-size: 12px; color: #666; font-weight: 600; display: block; margin-bottom: 4px;">年度:</label>
                        <select id="memberYearFilter" style="width: 100%; padding: 8px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px;">
                        </select>
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 16px;">
                    <label style="font-size: 12px; color: #666; font-weight: 600;">表示:</label>
                    <label style="font-size: 14px; cursor: pointer;">
                        <input type="radio" name="gradeDisplay" value="all" checked> 全学年
                    </label>
                    <label style="font-size: 14px; cursor: pointer;">
                        <input type="radio" name="gradeDisplay" value="grade"> 学年ごと
                    </label>
                    <button onclick="searchMemberRate()" style="padding: 8px 24px; background: #3b82f6; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; margin-left: auto;">検索</button>
                    <button onclick="resetMemberRate()" style="padding: 8px 24px; background: #94a3b8; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;">リセット</button>
                </div>        <button onclick="downloadMemberRateCSV()" style="padding: 8px 24px; background: #10b981; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;">CSVダウンロード</button>
                <canvas id="memberRateTrendChart"></canvas>
            </div>
            
            <!-- 学校別売上推移パネル -->
            <div id="salesTrendPanel" class="school-analysis-panel" style="display: none;">
                <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 16px;">
                    <div>
                        <label style="font-size: 12px; color: #666; font-weight: 600; display: block; margin-bottom: 4px;">事業所:</label>
                        <select id="salesBranchFilter" onchange="updateSalesManagerList(); updateSalesStudioList(); updateSalesSchoolList();" style="width: 100%; padding: 8px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px;">
                            <option value="">-- 全て --</option>
                        </select>
                    </div>
                    <div>
                        <label style="font-size: 12px; color: #666; font-weight: 600; display: block; margin-bottom: 4px;">担当者:</label>
                        <select id="salesManagerFilter" onchange="updateSalesStudioList(); updateSalesSchoolList();" style="width: 100%; padding: 8px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px;">
                            <option value="">-- 全て --</option>
                        </select>
                    </div>
                    <div>
                        <label style="font-size: 12px; color: #666; font-weight: 600; display: block; margin-bottom: 4px;">写真館:</label>
                        <select id="salesStudioFilter" onchange="updateSalesSchoolList();" style="width: 100%; padding: 8px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px;">
                            <option value="">-- 全て --</option>
                        </select>
                    </div>
                    <div>
                        <label style="font-size: 12px; color: #666; font-weight: 600; display: block; margin-bottom: 4px;">学校名:</label>
                        <select id="salesSchoolFilter" style="width: 100%; padding: 8px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px;">
                            <option value="">-- 選択してください --</option>
                        </select>
                    </div>
                    <div>
                        <label style="font-size: 12px; color: #666; font-weight: 600; display: block; margin-bottom: 4px;">年度:</label>
                        <select id="salesYearFilter" style="width: 100%; padding: 8px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px;">
                        </select>
                    </div>
                </div>
                <div style="display: flex; justify-content: flex-end; margin-bottom: 16px;">
                    <button onclick="searchSalesTrend()" style="padding: 8px 24px; background: #3b82f6; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; margin-right: 8px;">検索</button>
                    <button onclick="resetSalesTrendFilters()" style="padding: 8px 24px; background: #6b7280; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; margin-right: 8px;">リセット</button>
                    <button onclick="downloadSalesTrendCSV()" style="padding: 8px 24px; background: #10b981; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;">CSVダウンロード</button>
                </div>
                <canvas id="salesTrendChart"></canvas>
            </div>
        </div>
    </div>
    
    <script>
        // 全年度のデータ
        const allYearsData = {json.dumps(all_years_data, ensure_ascii=False, indent=2)};
        const schoolDetails = {json.dumps(school_details, ensure_ascii=False)};
        const schoolsList = {json.dumps(schools_list, ensure_ascii=False)};
        
        let monthlyChart, branchChart, schoolChart, branchMonthlyChart, managerChart, eventChart, memberChart;
        let currentMonthlySalesYear = {default_year};
        let currentTab = 'monthly';
        let currentDetailTab = 'school';

        // 詳細分析セクションのタブ切り替え
        // 詳細分析セクションのタブ切り替え
        function switchDetailTab(tab) {{
            currentDetailTab = tab;
            
            document.querySelectorAll('.detail-tab').forEach(btn => {{
                btn.style.color = '#666';
                btn.style.borderBottomColor = 'transparent';
                btn.classList.remove('active');
            }});
            
            const activeTab = document.getElementById(tab === 'school' ? 'tabSchool' : tab === 'event' ? 'tabEvent' : 'tabMember');
            activeTab.style.color = '#3b82f6';
            activeTab.style.borderBottomColor = '#3b82f6';
            activeTab.classList.add('active');
            
            document.getElementById('schoolPanel').style.display = tab === 'school' ? 'block' : 'none';
            document.getElementById('eventPanel').style.display = tab === 'event' ? 'block' : 'none';
            document.getElementById('memberPanel').style.display = tab === 'member' ? 'block' : 'none';
            
            // グラフ再描画（サイズ調整のため）
            const yearData = allYearsData[currentMonthlySalesYear]; // 年度は月別売上と同じものを使用
            if (tab === 'school') {{
                updateSchoolChart(yearData.top_schools);
            }} else if (tab === 'event') {{
                updateEventChart(yearData.top_events);
            }} else if (tab === 'member') {{
                updateMemberChart(yearData.member_rates);
            }}
        }}
        
        // 月別売上推移セクションのタブ切り替え
        function switchMonthlySalesTab(tab) {{
            currentTab = tab;
            
            // タブのスタイル更新
            document.querySelectorAll('.monthly-tab').forEach(btn => {{
                btn.style.color = '#666';
                btn.style.borderBottomColor = 'transparent';
                btn.classList.remove('active');
            }});
            
            const activeTab = document.getElementById(tab === 'monthly' ? 'tabMonthly' : tab === 'branch' ? 'tabBranch' : 'tabManager');
            activeTab.style.color = '#3b82f6';
            activeTab.style.borderBottomColor = '#3b82f6';
            activeTab.classList.add('active');
            
            // パネルの表示切り替え
            document.getElementById('monthlyPanel').style.display = tab === 'monthly' ? 'block' : 'none';
            document.getElementById('branchMonthlyPanel').style.display = tab === 'branch' ? 'block' : 'none';
            document.getElementById('managerPanel').style.display = tab === 'manager' ? 'block' : 'none';
            
            // データ更新
            const yearData = allYearsData[currentMonthlySalesYear];
            if (tab === 'branch') {{
                updateBranchMonthlySelectors(yearData.branch_monthly);
                renderBranchMonthlyChart();
            }} else if (tab === 'manager') {{
                updateManagerSelectors(yearData.manager_monthly);
                renderManagerChart();
            }}
        }}
        
        // 月別売上推移セクション専用の年度切り替え
        function changeMonthlySalesYear() {{
            currentMonthlySalesYear = parseInt(document.getElementById('monthlySalesYearSelect').value);
            const yearData = allYearsData[currentMonthlySalesYear];
            
            // 現在のタブに応じてグラフ更新
            if (currentTab === 'monthly') {{
                updateMonthlyChart(yearData.monthly);
            }} else if (currentTab === 'branch') {{
                updateBranchMonthlySelectors(yearData.branch_monthly);
                renderBranchMonthlyChart();
            }} else if (currentTab === 'manager') {{
                updateManagerSelectors(yearData.manager_monthly);
                renderManagerChart();
            }}
        }}
        
        // 事業所別月次売上のセレクター更新
        function updateBranchMonthlySelectors(branchMonthlyData) {{
            const branchFilter = document.getElementById('branchFilter');
            branchFilter.innerHTML = '<option value="">-- 全事業所 --</option>';
            
            if (!branchMonthlyData || Object.keys(branchMonthlyData).length === 0) {{
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'この年度はデータがありません';
                option.disabled = true;
                branchFilter.appendChild(option);
                return;
            }}
            
            Object.keys(branchMonthlyData).forEach(branch => {{
                const option = document.createElement('option');
                option.value = branch;
                option.textContent = branch;
                branchFilter.appendChild(option);
            }});
        }}
        
        // 事業所別月次売上グラフ描画
        function renderBranchMonthlyChart() {{
            const yearData = allYearsData[currentMonthlySalesYear];
            const branchFilter = document.getElementById('branchFilter');
            const selectedBranch = branchFilter.value;
            
            const canvas = document.getElementById('branchMonthlyChart');
            
            if (!selectedBranch || !yearData.branch_monthly[selectedBranch]) {{
                // 全事業所の場合、または選択なしの場合
                if (branchMonthlyChart) branchMonthlyChart.destroy();
                return;
            }}
            
            const branchData = yearData.branch_monthly[selectedBranch];
            const currentData = branchData.current || [];
            const prevData = branchData.prev || [];
            
            // 月ラベルとデータの準備
            const labels = currentData.map(d => `${{d.month}}月`);
            const currentSales = currentData.map(d => d.sales);
            
            // 前年度データを月でマッピング
            const prevSalesMap = {{}};
            prevData.forEach(d => {{
                prevSalesMap[d.month] = d.sales;
            }});
            const prevSales = currentData.map(d => prevSalesMap[d.month] || 0);
            
            if (branchMonthlyChart) branchMonthlyChart.destroy();
            
            branchMonthlyChart = new Chart(canvas, {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: [
                        {{
                            label: `${{selectedBranch}} ${{currentMonthlySalesYear}}年度`,
                            data: currentSales,
                            backgroundColor: 'rgba(59, 130, 246, 0.8)'
                        }},
                        {{
                            label: `${{selectedBranch}} ${{currentMonthlySalesYear - 1}}年度`,
                            data: prevSales,
                            backgroundColor: 'rgba(156, 163, 175, 0.6)'
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{ legend: {{ display: true, position: 'top' }} }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ callback: function(value) {{ return '¥' + value.toLocaleString(); }} }}
                        }}
                    }}
                }}
            }});
        }}
        
        // 担当者セレクター更新
        function updateManagerSelectors(managerMonthlyData) {{
            const managerFilter = document.getElementById('managerFilter');
            managerFilter.innerHTML = '<option value="">-- 選択してください --</option>';
            
            if (!managerMonthlyData || Object.keys(managerMonthlyData).length === 0) {{
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'この年度はデータがありません';
                option.disabled = true;
                managerFilter.appendChild(option);
                
                // メッセージを表示
                const canvas = document.getElementById('managerChart');
                const message = document.getElementById('managerChartMessage');
                canvas.style.display = 'none';
                message.style.display = 'block';
                message.textContent = 'この年度は担当者別データがありません';
                return;
            }}
            
            Object.keys(managerMonthlyData).forEach(manager => {{
                const option = document.createElement('option');
                option.value = manager;
                option.textContent = manager;
                managerFilter.appendChild(option);
            }});
            
            // デフォルトメッセージに戻す
            const message = document.getElementById('managerChartMessage');
            message.textContent = '担当者を選択してください';
        }}
        
        // 担当者別月次売上グラフ描画
        function renderManagerChart() {{
            const yearData = allYearsData[currentMonthlySalesYear];
            const managerFilter = document.getElementById('managerFilter');
            const selectedManager = managerFilter.value;
            
            const canvas = document.getElementById('managerChart');
            const message = document.getElementById('managerChartMessage');
            
            if (!selectedManager || !yearData.manager_monthly[selectedManager]) {{
                if (managerChart) managerChart.destroy();
                canvas.style.display = 'none';
                message.style.display = 'block';
                return;
            }}
            
            canvas.style.display = 'block';
            message.style.display = 'none';
            
            const managerData = yearData.manager_monthly[selectedManager];
            const currentData = managerData.current || [];
            const prevData = managerData.prev || [];
            
            // 月ラベルとデータの準備
            const labels = currentData.map(d => `${{d.month}}月`);
            const currentSales = currentData.map(d => d.sales);
            
            // 前年度データを月でマッピング
            const prevSalesMap = {{}};
            prevData.forEach(d => {{
                prevSalesMap[d.month] = d.sales;
            }});
            const prevSales = currentData.map(d => prevSalesMap[d.month] || 0);
            
            if (managerChart) managerChart.destroy();
            
            managerChart = new Chart(canvas, {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: [
                        {{
                            label: `${{selectedManager}} ${{currentMonthlySalesYear}}年度`,
                            data: currentSales,
                            backgroundColor: 'rgba(59, 130, 246, 0.8)'
                        }},
                        {{
                            label: `${{selectedManager}} ${{currentMonthlySalesYear - 1}}年度`,
                            data: prevSales,
                            backgroundColor: 'rgba(156, 163, 175, 0.6)'
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{ legend: {{ display: true, position: 'top' }} }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ callback: function(value) {{ return '¥' + value.toLocaleString(); }} }}
                        }}
                    }}
                }}
            }});
        }}
        
        function switchYear() {{
            const year = parseInt(document.getElementById('yearSelect').value);
            const data = allYearsData[year];
            
            // サマリーカード更新
            document.getElementById('reportDate').textContent = `レポート日: ${{data.stats.report_date}}`;
            document.getElementById('salesCardTitle').textContent = `${{year}}年度 累計売上`;
            document.getElementById('salesCardValue').textContent = `¥${{data.stats.current_total.toLocaleString()}}`;
            document.getElementById('salesCardSub').textContent = `前年同期 ¥${{data.stats.prev_total.toLocaleString()}}`;
            
            const yoyRate = data.stats.yoy_rate * 100;
            document.getElementById('yoyCardValue').textContent = `${{yoyRate.toFixed(1)}}%`;
            document.getElementById('yoyCardValue').className = yoyRate >= 100 ? 'card-value success' : yoyRate >= 80 ? 'card-value warning' : 'card-value danger';
            document.getElementById('yoyCardSub').textContent = yoyRate >= 100 ? '成長' : '減少';
            
            const budgetRate = data.stats.avg_budget_rate * 100;
            document.getElementById('budgetCardValue').textContent = `${{budgetRate.toFixed(1)}}%`;
            document.getElementById('budgetCardValue').className = budgetRate >= 100 ? 'card-value success' : budgetRate >= 80 ? 'card-value warning' : 'card-value danger';
            
            document.getElementById('countCardValue').textContent = `${{data.stats.school_count}}/${{data.stats.event_count}}`;
            
            // グラフ更新
            updateMonthlyChart(data.monthly);
            // updateBranchChart(data.branch); // 削除
            
            // 現在の詳細タブに応じて更新
            if (currentDetailTab === 'school') {{
                updateSchoolChart(data.top_schools);
            }} else if (currentDetailTab === 'event') {{
                updateEventChart(data.top_events);
            }} else if (currentDetailTab === 'member') {{
                updateMemberChart(data.member_rates);
            }}
        }}
        
        function updateMonthlyChart(monthlyData) {{
            const labels = monthlyData.map(d => `${{d.month}}月`);
            const salesData = monthlyData.map(d => d.sales);
            const budgetData = monthlyData.map(d => d.budget);
            const prevSalesData = monthlyData.map(d => d.prev_sales);
            
            if (monthlyChart) monthlyChart.destroy();
            
            monthlyChart = new Chart(document.getElementById('monthlyChart'), {{
                type: 'line',
                data: {{
                    labels: labels,
                    datasets: [
                        {{
                            label: '今年度売上',
                            data: salesData,
                            borderColor: 'rgb(59, 130, 246)',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            tension: 0.4,
                            fill: true
                        }},
                        {{
                            label: '前年度売上',
                            data: prevSalesData,
                            borderColor: 'rgb(156, 163, 175)',
                            backgroundColor: 'rgba(156, 163, 175, 0.1)',
                            tension: 0.4,
                            borderDash: [5, 5]
                        }},
                        {{
                            label: '予算',
                            data: budgetData,
                            borderColor: 'rgb(239, 68, 68)',
                            borderDash: [10, 5],
                            borderWidth: 2,
                            pointRadius: 4,
                            pointBackgroundColor: 'rgb(239, 68, 68)',
                            tension: 0.4
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{ display: true, position: 'top' }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{
                                callback: function(value) {{
                                    return '¥' + value.toLocaleString();
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        }}
        
        function updateBranchChart(branchData) {{
            if (branchData.length === 0) {{
                if (branchChart) branchChart.destroy();
                return;
            }}
            
            const labels = branchData.map(d => d.branch);
            const salesData = branchData.map(d => d.sales);
            
            if (branchChart) branchChart.destroy();
            
            branchChart = new Chart(document.getElementById('branchChart'), {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: [{{
                        label: '売上',
                        data: salesData,
                        backgroundColor: [
                            'rgba(59, 130, 246, 0.8)',
                            'rgba(16, 185, 129, 0.8)',
                            'rgba(245, 158, 11, 0.8)',
                            'rgba(139, 92, 246, 0.8)'
                        ]
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{
                                callback: function(value) {{
                                    return '¥' + value.toLocaleString();
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        }}
        
        function updateSchoolChart(schoolData) {{
            const labels = schoolData.map(d => d.school);
            const salesData = schoolData.map(d => d.sales);
            
            if (schoolChart) schoolChart.destroy();
            
            schoolChart = new Chart(document.getElementById('schoolChart'), {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: [{{
                        label: '売上',
                        data: salesData,
                        backgroundColor: 'rgba(59, 130, 246, 0.8)'
                    }}]
                }},
                options: {{
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        x: {{
                            beginAtZero: true,
                            ticks: {{
                                callback: function(value) {{
                                    return '¥' + value.toLocaleString();
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        }}
        
        function updateEventChart(eventData) {{
            if (!eventData || eventData.length === 0) return;

            const labels = eventData.map(d => d.event);
            const salesData = eventData.map(d => d.sales);
            
            if (eventChart) eventChart.destroy();
            
            eventChart = new Chart(document.getElementById('eventChart'), {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: [{{
                        label: '売上',
                        data: salesData,
                        backgroundColor: 'rgba(16, 185, 129, 0.8)'
                    }}]
                }},
                options: {{
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        x: {{
                            beginAtZero: true,
                            ticks: {{
                                callback: function(value) {{
                                    return '¥' + value.toLocaleString();
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        }}

        function updateMemberChart(memberData) {{
            if (!memberData || memberData.length === 0) return;

            // 散布図データ作成
            const scatterData = memberData.map(d => ({{
                x: d.total_students,
                y: d.rate,
                school: d.school,
                region: d.region
            }}));

            if (memberChart) memberChart.destroy();

            memberChart = new Chart(document.getElementById('memberChart'), {{
                type: 'scatter',
                data: {{
                    datasets: [{{
                        label: '会員率分布',
                        data: scatterData,
                        backgroundColor: 'rgba(245, 158, 11, 0.6)',
                        borderColor: 'rgba(245, 158, 11, 1)',
                        borderWidth: 1,
                        pointRadius: 5,
                        pointHoverRadius: 8
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    const point = context.raw;
                                    return `${{point.school}}: ${{((point.y * 100).toFixed(1))}}% (${{point.x}}名)`;
                                }}
                            }}
                        }},
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        x: {{
                            type: 'linear',
                            position: 'bottom',
                            title: {{ display: true, text: '児童・生徒数' }},
                            beginAtZero: true
                        }},
                        y: {{
                            title: {{ display: true, text: '会員率' }},
                            min: 0,
                            max: 1.1,
                            ticks: {{
                                callback: function(value) {{
                                    return (value * 100).toFixed(0) + '%';
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        }}
        
        
        // 学校別分析セクション用変数
        let memberRateTrendChart, salesTrendChart;
        let currentSchoolAnalysisTab = 'memberRate';
        
        // ユニークな値を抽出するヘルパー関数
        function getUniqueValues(array, key) {{
            return [...new Set(array.map(item => item[key]).filter(val => val))].sort();
        }}
        
        // フィルター初期化
        function initializeSchoolAnalysisFilters() {{
            // 写真館リスト
            const studios = getUniqueValues(schoolsList, 'studio');
            const studioSelects = [document.getElementById('memberStudioFilter'), document.getElementById('salesStudioFilter')];
            studioSelects.forEach(select => {{
                studios.forEach(studio => {{
                    const option = document.createElement('option');
                    option.value = studio;
                    option.textContent = studio;
                    select.appendChild(option);
                }});
            }});
            
            // 属性（地区）リスト
            const regions = getUniqueValues(schoolsList, 'region');
            const regionSelect = document.getElementById('memberRegionFilter');
            regions.forEach(region => {{
                const option = document.createElement('option');
                option.value = region;
                option.textContent = region;
                regionSelect.appendChild(option);
            }});
            
            // 事業所リスト（branch_monthly_salesから取得）
            const branches = [];
            Object.values(allYearsData).forEach(yearData => {{
                if (yearData.branch_monthly) {{
                    Object.keys(yearData.branch_monthly).forEach(branch => {{
                        if (!branches.includes(branch)) branches.push(branch);
                    }});
                }}
            }});
            branches.sort();
            const branchSelect = document.getElementById('salesBranchFilter');
            branches.forEach(branch => {{
                const option = document.createElement('option');
                option.value = branch;
                option.textContent = branch;
                branchSelect.appendChild(option);
            }});
            
            // 担当者・写真館リストを初期化（カスケーディングフィルター対応）
            updateSalesManagerList();
            updateSalesStudioList();
            
            // 学校リスト初期化
            updateMemberSchoolList();
            updateSalesSchoolList();
            
            // 年度リスト初期化
            const years = Object.keys(allYearsData).sort((a, b) => b - a);
            const yearSelects = [document.getElementById('memberYearFilter'), document.getElementById('salesYearFilter')];
            yearSelects.forEach(select => {{
                years.forEach(year => {{
                    const option = document.createElement('option');
                    option.value = year;
                    option.textContent = `${{year}}年度`;
                    select.appendChild(option);
                }});
            }});
        }}
        
        // 会員率タブの属性リスト更新（写真館に応じて絞り込み）
        function updateMemberRegionList() {{
            const studio = document.getElementById('memberStudioFilter').value;
            
            let filteredRegions = [];
            if (studio) {{
                // 選択した写真館が担当している属性（学校種）のみ
                filteredRegions = [...new Set(
                    schoolsList
                        .filter(s => s.studio === studio)
                        .map(s => s.region)
                        .filter(r => r)
                )].sort();
            }} else {{
                // 全ての属性
                filteredRegions = getUniqueValues(schoolsList, 'region');
            }}
            
            const regionSelect = document.getElementById('memberRegionFilter');
            const currentValue = regionSelect.value;
            regionSelect.innerHTML = '\u003coption value=""\u003e-- 全て --\u003c/option\u003e';
            filteredRegions.forEach(region => {{
                const option = document.createElement('option');
                option.value = region;
                option.textContent = region;
                regionSelect.appendChild(option);
            }});
            
            // 以前の選択を復元（可能なら）
            if (filteredRegions.includes(currentValue)) {{
                regionSelect.value = currentValue;
            }} else {{
                regionSelect.value = '';
            }}
        }}
        
        // 会員率タブの学校リスト更新
        function updateMemberSchoolList() {{
            const studio = document.getElementById('memberStudioFilter').value;
            const region = document.getElementById('memberRegionFilter').value;
            
            let filtered = schoolsList;
            if (studio) filtered = filtered.filter(s => s.studio === studio);
            if (region) filtered = filtered.filter(s => s.region === region);
            
            const schoolSelect = document.getElementById('memberSchoolFilter');
            schoolSelect.innerHTML = '\u003coption value=""\u003e-- 選択してください --\u003c/option\u003e';
            filtered.forEach(school => {{
                const option = document.createElement('option');
                option.value = school.id;
                option.textContent = school.name;
                schoolSelect.appendChild(option);
            }});
        }}
        
        // 売上タブの担当者リスト更新（事業所に応じて絞り込み）
        function updateSalesManagerList() {{
            const branch = document.getElementById('salesBranchFilter').value;
            
            let filteredManagers = [];
            if (branch) {{
                // 選択した事業所の担当者のみ
                filteredManagers = [...new Set(
                    schoolsList
                        .filter(s => s.branch === branch)
                        .map(s => s.manager)
                        .filter(m => m)
                )].sort();
            }} else {{
                // 全ての担当者
                filteredManagers = [...new Set(
                    schoolsList
                        .map(s => s.manager)
                        .filter(m => m)
                )].sort();
            }}
            
            const managerSelect = document.getElementById('salesManagerFilter');
            const currentValue = managerSelect.value;
            managerSelect.innerHTML = '\u003coption value=""\u003e-- 全て --\u003c/option\u003e';
            filteredManagers.forEach(manager => {{
                const option = document.createElement('option');
                option.value = manager;
                option.textContent = manager;
                managerSelect.appendChild(option);
            }});
            
            if (filteredManagers.includes(currentValue)) {{
                managerSelect.value = currentValue;
            }}
        }}
        
        // 売上タブの写真館リスト更新（事業所・担当者に応じて絞り込み）
        function updateSalesStudioList() {{
            const branch = document.getElementById('salesBranchFilter').value;
            const manager = document.getElementById('salesManagerFilter').value;
            
            let filteredStudios = [];
            let filtered = schoolsList;
            
            // 事業所で絞り込み
            if (branch) {{
                filtered = filtered.filter(s => s.branch === branch);
            }}
            
            // 担当者で絞り込み
            if (manager) {{
                filtered = filtered.filter(s => s.manager === manager);
            }}
            
            // 写真館の一覧を取得
            filteredStudios = [...new Set(
                filtered
                    .map(s => s.studio)
                    .filter(st => st)
            )].sort();
            
            const studioSelect = document.getElementById('salesStudioFilter');
            const currentValue = studioSelect.value;
            studioSelect.innerHTML = '\u003coption value=""\u003e-- 全て --\u003c/option\u003e';
            filteredStudios.forEach(studio => {{
                const option = document.createElement('option');
                option.value = studio;
                option.textContent = studio;
                studioSelect.appendChild(option);
            }});
            
            if (filteredStudios.includes(currentValue)) {{
                studioSelect.value = currentValue;
            }}
        }}
        
        // 売上タブの学校リスト更新
        function updateSalesSchoolList() {{
            const branch = document.getElementById('salesBranchFilter').value;
            const manager = document.getElementById('salesManagerFilter').value;
            const studio = document.getElementById('salesStudioFilter').value;
            
            let filtered = schoolsList;
            
            // 事業所で絞り込み
            if (branch) {{
                filtered = filtered.filter(s => s.branch === branch);
            }}
            
            // 担当者で絞り込み
            if (manager) {{
                filtered = filtered.filter(s => s.manager === manager);
            }}
            
            // 写真館で絞り込み
            if (studio) {{
                filtered = filtered.filter(s => s.studio === studio);
            }}
            
            const schoolSelect = document.getElementById('salesSchoolFilter');
            schoolSelect.innerHTML = '\u003coption value=""\u003e-- 選択してください --\u003c/option\u003e';
            filtered.forEach(school => {{
                const option = document.createElement('option');
                option.value = school.id;
                option.textContent = school.name;
                schoolSelect.appendChild(option);
            }});
        }}
        
        // タブ切り替え
        function switchSchoolAnalysisTab(tab) {{
            currentSchoolAnalysisTab = tab;
            
            document.querySelectorAll('.school-analysis-tab').forEach(btn => {{
                btn.style.color = '#666';
                btn.style.borderBottomColor = 'transparent';
                btn.classList.remove('active');
            }});
            
            const activeTab = document.getElementById(tab === 'memberRate' ? 'tabMemberRate' : 'tabSalesTrend');
            activeTab.style.color = '#3b82f6';
            activeTab.style.borderBottomColor = '#3b82f6';
            activeTab.classList.add('active');
            
            document.getElementById('memberRatePanel').style.display = tab === 'memberRate' ? 'block' : 'none';
            document.getElementById('salesTrendPanel').style.display = tab === 'salesTrend' ? 'block' : 'none';
        }}
        
        // 会員率推移検索
        function searchMemberRate() {{
            const schoolId = document.getElementById('memberSchoolFilter').value;
            const year = parseInt(document.getElementById('memberYearFilter').value);
            
            if (!schoolId) {{
                alert('学校を選択してください');
                return;
            }}
            
            const schoolData = schoolDetails[schoolId];
            if (!schoolData || !schoolData.member_rates) {{
                alert('この学校の会員率データがありません');
                return;
            }}
            
            const gradeDisplay = document.querySelector('input[name="gradeDisplay"]:checked').value;
            renderMemberRateTrend(schoolData.member_rates, gradeDisplay, year);
        }}
        
        // 会員率推移グラフ描画（月単位集約+年度順ソート+年度フィルター）
        function renderMemberRateTrend(memberRateData, gradeDisplay, selectedYear) {{
            if (!memberRateData || Object.keys(memberRateData).length === 0) return;
            
            // 月ごとに集約（最新のデータを採用）
            const monthlyData = {{}};
            Object.keys(memberRateData).forEach(snapshotDate => {{
                const yearMonth = snapshotDate.substring(0, 7); // "2025-11-28" -> "2025-11"
                const [year, month] = yearMonth.split('-').map(Number);
                
                // 年度を計算
                const fiscalYear = month >= 4 ? year : year - 1;
                
                // 選択された年度のデータのみを集約
                if (fiscalYear === selectedYear) {{
                    if (!monthlyData[yearMonth] || snapshotDate > monthlyData[yearMonth].date) {{
                        monthlyData[yearMonth] = {{
                            date: snapshotDate,
                            data: memberRateData[snapshotDate]
                        }};
                    }}
                }}
            }});
            
            // データがない場合は警告
            if (Object.keys(monthlyData).length === 0) {{
                alert(`${{selectedYear}}年度の会員率データがありません`);
                if (memberRateTrendChart) memberRateTrendChart.destroy();
                return;
            }}
            
            // 年度順にソート（4月始まり）
            const sortedMonths = Object.keys(monthlyData).sort((a, b) => {{
                const [yearA, monthA] = a.split('-').map(Number);
                const [yearB, monthB] = b.split('-').map(Number);
                
                // 同一年度内では月順（月を年度順に変換: 4->1, 5->2, ..., 3->12）
                const fiscalMonthA = monthA >= 4 ? monthA - 3 : monthA + 9;
                const fiscalMonthB = monthB >= 4 ? monthB - 3 : monthB + 9;
                return fiscalMonthA - fiscalMonthB;
            }});
            
            // ラベルは月のみ（例: "4月", "5月", ...）
            const labels = sortedMonths.map(ym => {{
                const month = parseInt(ym.split('-')[1]);
                return `${{month}}月`;
            }});
            
            let datasets = [];
            let maxRate = 0;  // 最大値を追跡
            
            if (gradeDisplay === 'all') {{
                // 全学年データを使用（SQL側で正しく計算済み）
                const avgRates = sortedMonths.map(ym => {{
                    const grades = monthlyData[ym].data;
                    // '全学年'というgradeのデータを探す
                    const allGradeData = grades.find(g => g.grade === '全学年');
                    if (allGradeData) {{
                        maxRate = Math.max(maxRate, allGradeData.rate);
                        return allGradeData.rate;
                    }}
                    // '全学年'がない場合は0（エラー回避）
                    return 0;
                }});
                
                datasets = [{{
                    label: '全学年',
                    data: avgRates,
                    borderColor: 'rgb(59, 130, 246)',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.4
                }}];
            }} else {{
                // 学年ごと（全学年を除外）
                const gradeData = {{}};
                sortedMonths.forEach(ym => {{
                    monthlyData[ym].data.forEach(item => {{
                        const grade = item.grade;
                        // '全学年'は除外（学年別表示では不要）
                        if (grade === '全学年') return;
                        
                        if (!gradeData[grade]) gradeData[grade] = [];
                        gradeData[grade].push(item.rate);
                        maxRate = Math.max(maxRate, item.rate);
                    }});
                }});
                
                const colors = [
                    {{ border: 'rgb(59, 130, 246)', bg: 'rgba(59, 130, 246, 0.1)' }},    // 青
                    {{ border: 'rgb(16, 185, 129)', bg: 'rgba(16, 185, 129, 0.1)' }},    // 緑
                    {{ border: 'rgb(245, 158, 11)', bg: 'rgba(245, 158, 11, 0.1)' }},    // オレンジ
                    {{ border: 'rgb(239, 68, 68)', bg: 'rgba(239, 68, 68, 0.1)' }},      // 赤
                    {{ border: 'rgb(168, 85, 247)', bg: 'rgba(168, 85, 247, 0.1)' }},    // 紫
                    {{ border: 'rgb(236, 72, 153)', bg: 'rgba(236, 72, 153, 0.1)' }}     // ピンク
                ];
                
                datasets = Object.keys(gradeData).map((grade, index) => {{
                    const color = colors[index % colors.length];
                    return {{
                        label: grade,
                        data: gradeData[grade],
                        borderColor: color.border,
                        backgroundColor: color.bg,
                        tension: 0.4
                    }};
                }});
            }}
            
            if (memberRateTrendChart) memberRateTrendChart.destroy();
            
            // Y軸の最大値を計算（データの最大値の1.1倍、最低でも100%）
            const yMax = Math.max(100, maxRate * 1.1);
            
            memberRateTrendChart = new Chart(document.getElementById('memberRateTrendChart'), {{
                type: 'line',
                data: {{ labels: labels, datasets: datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{ 
                        legend: {{ display: true, position: 'top' }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    const label = context.dataset.label || '';
                                    const value = context.parsed.y;
                                    return label + ': ' + value.toFixed(1) + '%';
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        y: {{
                            min: 0,
                            max: yMax,
                            ticks: {{ callback: function(value) {{ return value.toFixed(0) + '%'; }} }}
                        }}
                    }}
                }}
            }});
        }}
        
        // 学校別売上推移検索
        function searchSalesTrend() {{
            const schoolId = document.getElementById('salesSchoolFilter').value;
            if (!schoolId) {{
                alert('学校を選択してください');
                return;
            }}
            
            const schoolData = schoolDetails[schoolId];
            if (!schoolData || !schoolData.monthly_sales) {{
                alert('この学校の売上データがありません');
                return;
            }}
            
            const year = parseInt(document.getElementById('salesYearFilter').value);
            renderSalesTrend(schoolData.monthly_sales, year);
        }}
        
        // 学校別売上推移グラフ描画（累積表示）
        function renderSalesTrend(salesData, year) {{
            if (!salesData || Object.keys(salesData).length === 0) return;
            
            const currentData = salesData[year] || [];
            const prevData = salesData[year - 1] || [];
            
            if (currentData.length === 0) {{
                alert(`${{year}}年度のデータがありません`);
                return;
            }}
            
            // 現在の年月を取得
            const currentDate = new Date();
            const currentYear = currentDate.getFullYear();
            const currentMonth = currentDate.getMonth() + 1;  // 1-12
            
            // 年度の4月から現在月までの全ての月を生成
            // 年度: year年4月 ～ (year+1)年3月
            const allMonths = [];
            
            // 4月～12月（year年に属する月）
            for (let m = 4; m <= 12; m++) {{
                if (year > currentYear) break;  // 未来の年度
                if (year === currentYear && m > currentMonth) break;  // 未来の月
                allMonths.push(m);
            }}
            
            // 1月～3月（year+1年に属する月）
            for (let m = 1; m <= 3; m++) {{
                const nextYear = year + 1;
                if (nextYear > currentYear) break;  // 未来の年
                if (nextYear === currentYear && m > currentMonth) break;  // 未来の月
                allMonths.push(m);
            }}
            
            if (allMonths.length === 0) {{
                alert(`${{year}}年度のデータ期間がありません`);
                return;
            }}
            
            // 売上データをマップに変換
            const currentSalesMap = {{}};
            currentData.forEach(d => {{
                currentSalesMap[d.month] = d.sales;
            }});
            
            const prevSalesMap = {{}};
            prevData.forEach(d => {{
                prevSalesMap[d.month] = d.sales;
            }});
            
            // 年度順にソート
            const sortedMonths = allMonths.sort((a, b) => {{
                const fiscalMonthA = a >= 4 ? a - 3 : a + 9;
                const fiscalMonthB = b >= 4 ? b - 3 : b + 9;
                return fiscalMonthA - fiscalMonthB;
            }});
            
            const labels = sortedMonths.map(m => `${{m}}月`);
            
            // 累積売上を計算（データがない月は前月の累積値を維持）
            let cumulative = 0;
            const currentSales = sortedMonths.map(m => {{
                const monthlySales = currentSalesMap[m] || 0;
                cumulative += monthlySales;
                return cumulative;
            }});
            
            // 前年度データも同様に累積計算
            let prevCumulative = 0;
            const prevSales = sortedMonths.map(m => {{
                const monthlySales = prevSalesMap[m] || 0;
                prevCumulative += monthlySales;
                return prevCumulative;
            }});
            
            if (salesTrendChart) salesTrendChart.destroy();
            
            salesTrendChart = new Chart(document.getElementById('salesTrendChart'), {{
                type: 'line',
                data: {{
                    labels: labels,
                    datasets: [
                        {{
                            label: `${{year}}年度（累積）`,
                            data: currentSales,
                            borderColor: 'rgb(59, 130, 246)',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            tension: 0.4
                        }},
                        {{
                            label: `${{year - 1}}年度（累積）`,
                            data: prevSales,
                            borderColor: 'rgb(156, 163, 175)',
                            backgroundColor: 'rgba(156, 163, 175, 0.1)',
                            tension: 0.4,
                            borderDash: [5, 5]
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{ legend: {{ display: true, position: 'top' }} }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ callback: function(value) {{ return '¥' + value.toLocaleString(); }} }}
                        }}
                    }}
                }}
            }});
        }}
        
        // リセット関数
        function resetMemberRateFilters() {{
            document.getElementById('memberStudioFilter').value = '';
            document.getElementById('memberRegionFilter').value = '';
            document.getElementById('memberSchoolFilter').value = '';
            document.getElementById('memberYearFilter').selectedIndex = 0;
            document.querySelector('input[name="memberGradeDisplay"][value="all"]').checked = true;
            if (memberRateTrendChart) memberRateTrendChart.destroy();
            updateMemberSchoolList();
        }}
        
        function resetSalesTrendFilters() {{
            document.getElementById('salesBranchFilter').value = '';
            document.getElementById('salesManagerFilter').value = '';
            document.getElementById('salesStudioFilter').value = '';
            document.getElementById('salesSchoolFilter').value = '';
            document.getElementById('salesYearFilter').selectedIndex = 0;
            if (salesTrendChart) salesTrendChart.destroy();
            updateSalesSchoolList();
        }}
        
        // CSV出力関数
        function downloadMemberRateCSV() {{
            if (!memberRateTrendChart || !memberRateTrendChart.data) {{
                alert('グラフを表示してからダウンロードしてください');
                return;
            }}
            
            const data = memberRateTrendChart.data;
            const labels = data.labels;
            const datasets = data.datasets;
            
            let csv = 'スナップショット日付,' + datasets.map(d => d.label).join(',') + '\\n';
            labels.forEach((label, i) => {{
                csv += label + ',' + datasets.map(d => ((d.data[i] || 0) * 100).toFixed(1) + '%').join(',') + '\\n';
            }});
            
            downloadCSV(csv, '会員率推移.csv');
        }}
        
        function downloadSalesTrendCSV() {{
            if (!salesTrendChart || !salesTrendChart.data) {{
                alert('グラフを表示してからダウンロードしてください');
                return;
            }}
            
            const data = salesTrendChart.data;
            const labels = data.labels;
            const datasets = data.datasets;
            
            let csv = '月,' + datasets.map(d => d.label).join(',') + '\\n';
            labels.forEach((label, i) => {{
                csv += label + ',' + datasets.map(d => (d.data[i] || 0).toLocaleString()).join(',') + '\\n';
            }});
            
            downloadCSV(csv, '学校別売上推移.csv');
        }}
        
        function downloadCSV(csvContent, filename) {{
            const bom = '\\uFEFF';
            const blob = new Blob([bom + csvContent], {{ type: 'text/csv;charset=utf-8;' }});
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = filename;
            link.click();
        }}
        
        // 初期表示
        const initialYear = parseInt(document.getElementById('yearSelect').value);
        const initialData = allYearsData[initialYear];
        updateMonthlyChart(initialData.monthly);
        
        // 学校別分析フィルター初期化
        initializeSchoolAnalysisFilters();
    </script>
    
    <!-- 条件別集計セクション -->
    <div class="alert-section" style="margin: 40px 0; padding: 30px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        <h2 style="font-size: 24px; margin-bottom: 30px; color: #333;">条件別集計</h2>
        
        <!-- カテゴリコンテナ -->
        <div class="alert-category-container" style="display: flex; gap: 20px; margin-bottom: 30px;">
            <!-- 売上・実績カテゴリ -->
            <div class="alert-category" style="flex: 1; padding: 20px; background: #f0fdf4; border-radius: 8px; border: 2px solid #86efac;">
                <div class="alert-category-title" style="font-weight: bold; color: #166534; margin-bottom: 15px; font-size: 16px;">📊 売上・実績</div>
                <div class="alert-tabs" style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <button onclick="showAlert('rapid_growth')" id="tab-rapid_growth" class="alert-tab active" style="padding: 8px 16px; background: #22c55e; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">売上好調校</button>
                    <button onclick="showAlert('new_schools')" id="tab-new_schools" class="alert-tab" style="padding: 8px 16px; background: #e5e7eb; color: #374151; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">新規開始校</button>
                </div>
            </div>
            
            <!-- 要注意・改善カテゴリ -->
            <div class="alert-category" style="flex: 1; padding: 20px; background: #fff7ed; border-radius: 8px; border: 2px solid #fed7aa;">
                <div class="alert-category-title" style="font-weight: bold; color: #9a3412; margin-bottom: 15px; font-size: 16px;">⚠️ 要注意・改善</div>
                <div class="alert-tabs" style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <button onclick="showAlert('no_events')" id="tab-no_events" class="alert-tab" style="padding: 8px 16px; background: #e5e7eb; color: #374151; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">今年度未実施校</button>
                    <button onclick="showAlert('decline')" id="tab-decline" class="alert-tab" style="padding: 8px 16px; background: #e5e7eb; color: #374151; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">会員率・売上低下</button>
                </div>
            </div>
        </div>
        
        <!-- 売上好調校タブコンテンツ -->
        <div id="alert-rapid_growth" class="alert-content active" style="display: block;">
            <div class="alert-header" style="display: flex; justify-content: flex-end; margin-bottom: 15px;">
                <button class="csv-download-btn" onclick="downloadAlertCSV('rapid_growth')" style="padding: 8px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">📥 CSV出力</button>
            </div>
            <div id="rapid_growth-table-container"></div>
            <div id="rapid_growth-pagination" class="pagination" style="display: flex; gap: 10px; justify-content: center; margin-top: 20px;"></div>
        </div>

        <!-- 新規開始校タブコンテンツ -->
        <div id="alert-new_schools" class="alert-content" style="display: none;">
            <div class="alert-filters" style="display: flex; gap: 15px; margin-bottom: 20px; align-items: center; background: #f9fafb; padding: 15px; border-radius: 8px; border: 1px solid #e5e7eb;">
                <label style="font-weight: bold; color: #374151;">対象年度:</label>
                <select id="newSchoolsYearFilter" onchange="renderAlertTable('new_schools', 1)" style="padding: 8px; border: 1px solid #d1d5db; border-radius: 6px; min-width: 120px; background: white;">
                    <!-- JSで生成 -->
                </select>
            </div>
            <div class="alert-header" style="display: flex; justify-content: flex-end; margin-bottom: 15px;">
                <button class="csv-download-btn" onclick="downloadAlertCSV('new_schools')" style="padding: 8px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">📥 CSV出力</button>
            </div>
            <div id="new_schools-table-container"></div>
            <div id="new_schools-pagination" class="pagination" style="display: flex; gap: 10px; justify-content: center; margin-top: 20px;"></div>
        </div>

        <!-- 今年度未実施校タブコンテンツ -->
        <div id="alert-no_events" class="alert-content" style="display: none;">
            <div class="alert-filters" style="display: flex; gap: 15px; margin-bottom: 20px; align-items: center; background: #f9fafb; padding: 15px; border-radius: 8px; border: 1px solid #e5e7eb;">
                <label style="font-weight: bold; color: #374151;">対象年度:</label>
                <select id="noEventsYearFilter" onchange="renderAlertTable('no_events', 1)" style="padding: 8px; border: 1px solid #d1d5db; border-radius: 6px; min-width: 120px; background: white;">
                    <!-- JSで生成 -->
                </select>
            </div>
            <div class="alert-header" style="display: flex; justify-content: flex-end; margin-bottom: 15px;">
                <button class="csv-download-btn" onclick="downloadAlertCSV('no_events')" style="padding: 8px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">📥 CSV出力</button>
            </div>
            <div id="no_events-table-container"></div>
            <div id="no_events-pagination" class="pagination" style="display: flex; gap: 10px; justify-content: center; margin-top: 20px;"></div>
        </div>

        <!-- 会員率・売上低下タブコンテンツ -->
        <div id="alert-decline" class="alert-content" style="display: none;">
            <div class="alert-filters" style="display: flex; gap: 15px; margin-bottom: 20px; align-items: center; background: #f9fafb; padding: 15px; border-radius: 8px; border: 1px solid #e5e7eb; flex-wrap: wrap;">
                <div style="display: flex; align-items: center; gap: 5px;">
                    <label style="font-weight: bold; color: #374151;">会員率:</label>
                    <select id="declineMemberRateFilter" onchange="renderAlertTable('decline', 1)" style="padding: 6px; border: 1px solid #d1d5db; border-radius: 4px;">
                        <option value="110">指定なし</option>
                        <option value="50">50%未満</option>
                        <option value="40">40%未満</option>
                        <option value="30">30%未満</option>
                        <option value="20">20%未満</option>
                        <option value="10">10%未満</option>
                    </select>
                </div>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <label style="font-weight: bold; color: #374151;">売上減少率:</label>
                    <select id="declineSalesMin" onchange="renderAlertTable('decline', 1)" style="padding: 6px; border: 1px solid #d1d5db; border-radius: 4px;">
                        <option value="0">0%</option>
                        <option value="10" selected>10%</option>
                        <option value="20">20%</option>
                        <option value="30">30%</option>
                        <option value="40">40%</option>
                        <option value="50">50%</option>
                        <option value="60">60%</option>
                        <option value="70">70%</option>
                        <option value="80">80%</option>
                        <option value="90">90%</option>
                        <option value="100">100%</option>
                    </select>
                    <span>～</span>
                    <select id="declineSalesMax" onchange="renderAlertTable('decline', 1)" style="padding: 6px; border: 1px solid #d1d5db; border-radius: 4px;">
                        <option value="200"> - </option>
                        <option value="10">10%</option>
                        <option value="20">20%</option>
                        <option value="30">30%</option>
                        <option value="40">40%</option>
                        <option value="50">50%</option>
                        <option value="60">60%</option>
                        <option value="70">70%</option>
                        <option value="80">80%</option>
                        <option value="90">90%</option>
                        <option value="100">100%</option>
                    </select>
                    <span>減少</span>
                </div>
            </div>
            <div class="alert-header" style="display: flex; justify-content: flex-end; margin-bottom: 15px;">
                <button class="csv-download-btn" onclick="downloadAlertCSV('decline')" style="padding: 8px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px;">📥 CSV出力</button>
            </div>
            <div id="decline-table-container"></div>
            <div id="decline-pagination" class="pagination" style="display: flex; gap: 10px; justify-content: center; margin-top: 20px;"></div>
        </div>
    </div>
    
    <script>
        // 条件別集計データ
        const rapidGrowthData = {json.dumps(rapid_growth_data, ensure_ascii=False)};
        const newSchoolsAllData = {json.dumps(new_schools_all, ensure_ascii=False)};
        const noEventsAllData = {json.dumps(no_events_all, ensure_ascii=False)};
        const declineBaseData = {json.dumps(decline_data, ensure_ascii=False)};
        
        const alertsData = {{
            'rapid_growth': rapidGrowthData,
            'new_schools': [], // 初期値は空、ロード時に設定
            'no_events': [],
            'decline': declineBaseData
        }};
        
        let currentAlertPage = 1;
        const alertPageSize = 30;
        
        // タブ切り替え
        function showAlert(alertType) {{
            // 全タブコンテンツを非表示
            document.querySelectorAll('.alert-content').forEach(el => el.style.display = 'none');
            // 全タブボタンを非アクティブ化
            document.querySelectorAll('.alert-tab').forEach(el => {{
                el.classList.remove('active');
                el.style.background = '#e5e7eb';
                el.style.color = '#374151';
            }});
            
            // 選択タブを表示
            const contentEl = document.getElementById(`alert-${{alertType}}`);
            if (contentEl) contentEl.style.display = 'block';
            
            // 選択タブボタンをアクティブ化
            const tabEl = document.getElementById(`tab-${{alertType}}`);
            if (tabEl) {{
                tabEl.classList.add('active');
                tabEl.style.background = '#22c55e';
                tabEl.style.color = 'white';
            }}
            
            // データをレンダリング
            renderAlertTable(alertType, 1);
        }}
        
        // テーブルレンダリング
        function renderAlertTable(alertType, page) {{
            currentAlertPage = page;
            
            // データ取得ロジック分岐
            let data = [];
            if (alertType === 'new_schools') {{
                const year = document.getElementById('newSchoolsYearFilter').value;
                if (year && newSchoolsAllData[year]) {{
                    data = newSchoolsAllData[year];
                }}
                alertsData['new_schools'] = data; // CSV出力用に保存
            }} else if (alertType === 'no_events') {{
                const yearElement = document.getElementById('noEventsYearFilter');
                const year = yearElement ? yearElement.value : null;
                if (year && noEventsAllData[year]) {{
                    data = noEventsAllData[year];
                }}
                alertsData['no_events'] = data;
            }} else if (alertType === 'decline') {{
                const memberRateThreshold = parseFloat(document.getElementById('declineMemberRateFilter').value) / 100;
                const salesMin = parseFloat(document.getElementById('declineSalesMin').value) / 100;
                const salesMax = parseFloat(document.getElementById('declineSalesMax').value) / 100;
                
                if (declineBaseData) {{
                    data = declineBaseData.filter(row => {{
                        const declineRate = -row.growth_rate;
                        return row.member_rate < memberRateThreshold && declineRate >= salesMin && declineRate <= salesMax;
                    }});
                }}
                alertsData['decline'] = data;
            }} else {{
                data = alertsData[alertType] || [];
            }}
            
            const container = document.getElementById(`${{alertType}}-table-container`);
            if (!container) return;
            
            if (data.length === 0) {{
                container.innerHTML = '<p style="text-align: center; padding: 40px; color: #888;">データがありません</p>';
                return;
            }}
            
            // ページネーション
            const startIdx = (page - 1) * alertPageSize;
            const endIdx = startIdx + alertPageSize;
            const pageData = data.slice(startIdx, endIdx);
            
            // テーブル生成
            let html = '<table style="width: 100%; border-collapse: collapse; font-size: 14px;">';
            html += '<thead><tr style="background: #f3f4f6; border-bottom: 2px solid #e5e7eb;">';
            html += '<th style="padding: 12px; text-align: left;">学校名</th>';
            html += '<th style="padding: 12px; text-align: left;">属性</th>';
            html += '<th style="padding: 12px; text-align: left;">写真館</th>';
            
            if (alertType === 'new_schools') {{
                html += '<th style="padding: 12px; text-align: right;">今年度売上</th>';
            }} else if (alertType === 'no_events') {{
                html += '<th style="padding: 12px; text-align: right;">前年度売上</th>';
            }} else if (alertType === 'decline') {{
                html += '<th style="padding: 12px; text-align: right;">会員率</th>';
                html += '<th style="padding: 12px; text-align: right;">売上変化率</th>';
                html += '<th style="padding: 12px; text-align: right;">今年度売上</th>';
                html += '<th style="padding: 12px; text-align: right;">前年度売上</th>';
            }} else {{
                html += '<th style="padding: 12px; text-align: right;">今年度売上</th>';
                html += '<th style="padding: 12px; text-align: right;">前年度売上</th>';
                html += '<th style="padding: 12px; text-align: right;">成長率</th>';
            }}
            html += '</tr></thead><tbody>';
            
            pageData.forEach((row, idx) => {{
                const bgColor = idx % 2 === 0 ? '#ffffff' : '#f9fafb';
                html += `<tr style="background: ${{bgColor}}; border-bottom: 1px solid #e5e7eb;">`;
                html += `<td style="padding: 12px;">${{row.school_name}}</td>`;
                html += `<td style="padding: 12px;">${{row.attribute || '-'}}</td>`;
                html += `<td style="padding: 12px;">${{row.studio || '-'}}</td>`;
                
                if (alertType === 'no_events') {{
                    html += `<td style="padding: 12px; text-align: right;">¥${{row.prev_sales.toLocaleString()}}</td>`;
                }} else if (alertType === 'decline') {{
                    const rateColor = row.member_rate < 0.2 ? '#ef4444' : '#f97316';
                    html += `<td style="padding: 12px; text-align: right; color: ${{rateColor}}; font-weight: bold;">${{(row.member_rate * 100).toFixed(1)}}%</td>`;
                    html += `<td style="padding: 12px; text-align: right; color: #ef4444; font-weight: bold;">${{(row.growth_rate * 100).toFixed(1)}}%</td>`;
                    html += `<td style="padding: 12px; text-align: right;">¥${{row.current_sales.toLocaleString()}}</td>`;
                    html += `<td style="padding: 12px; text-align: right;">¥${{row.prev_sales.toLocaleString()}}</td>`;
                }} else {{
                    html += `<td style="padding: 12px; text-align: right;">¥${{row.current_sales.toLocaleString()}}</td>`;
                    if (alertType !== 'new_schools') {{
                        html += `<td style="padding: 12px; text-align: right;">¥${{row.prev_sales.toLocaleString()}}</td>`;
                        html += `<td style="padding: 12px; text-align: right; color: #16a34a; font-weight: bold;">+${{(row.growth_rate * 100).toFixed(1)}}%</td>`;
                    }}
                }}
                html += '</tr>';
            }});
            
            html += '</tbody></table>';
            container.innerHTML = html;
            
            // ページネーション
            const totalCount = data.length;
            renderPagination(alertType, totalCount, page);
        }}
        
        // ページネーション
        function renderPagination(alertType, totalCount, currentPage) {{
            const totalPages = Math.ceil(totalCount / alertPageSize);
            const paginationEl = document.getElementById(`${{alertType}}-pagination`);
            if (!paginationEl || totalPages <= 1) {{
                if (paginationEl) paginationEl.innerHTML = '';
                return;
            }}
            
            let html = '';
            if (currentPage > 1) {{
                html += `<button onclick="renderAlertTable('${{alertType}}', ${{currentPage - 1}})" style="padding: 6px 12px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer;">前へ</button>`;
            }}
            html += `<span style="padding: 6px 12px; color: #666;">${{currentPage}} / ${{totalPages}}</span>`;
            if (currentPage < totalPages) {{
                html += `<button onclick="renderAlertTable('${{alertType}}', ${{currentPage + 1}})" style="padding: 6px 12px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer;">次へ</button>`;
            }}
            paginationEl.innerHTML = html;
        }}
        
        // CSV出力
        function downloadAlertCSV(alertType) {{
            const data = alertsData[alertType] || [];
            if (data.length === 0) {{
                alert('データがありません');
                return;
            }}
            
            // CSVヘッダーとデータ生成
            let csv = '学校名,属性,写真館,担当者,地区,今年度売上,前年度売上,成長率';
            if (alertType === 'decline') csv += ',会員率';
            csv += '\\n';
            
            data.forEach(row => {{
                csv += `\"${{row.school_name}}\",`;
                csv += `\"${{row.attribute || ''}}\",`;
                csv += `\"${{row.studio || ''}}\",`;
                csv += `\"${{row.manager || ''}}\",`;
                csv += `\"${{row.region || ''}}\",`;
                csv += `${{row.current_sales}},`;
                csv += `${{row.prev_sales}},`;
                csv += `${{(row.growth_rate * 100).toFixed(1)}}%\\n`;
            }});
            
            const bom = '\\uFEFF';
            const blob = new Blob([bom + csv], {{ type: 'text/csv;charset=utf-8;' }});
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            if (alertType === 'new_schools') link.download = '新規開始校.csv';
            else if (alertType === 'no_events') link.download = '今年度未実施校.csv';
            else if (alertType === 'decline') link.download = '会員率・売上低下校.csv';
            else link.download = '売上好調校.csv';
            link.click();
        }}
        
        // 初期表示
        
        // 新規開始校用年度フィルター初期化(Available Yearsを使用)
        const newSchoolsYearSelect = document.getElementById('newSchoolsYearFilter');
        Object.keys(newSchoolsAllData).sort((a,b) => b-a).forEach(year => {{
            const option = document.createElement('option');
            option.value = year;
            option.textContent = year + '年度';
            newSchoolsYearSelect.appendChild(option);
        }});
        // デフォルトを選択
        if (newSchoolsYearSelect.options.length > 0) {{
            newSchoolsYearSelect.selectedIndex = 0;
        }}
        
        
        // 今年度未実施校用年度フィルター初期化(Available Yearsを使用)
        const noEventsYearSelect = document.getElementById('noEventsYearFilter');
        Object.keys(noEventsAllData).sort((a,b) => b-a).forEach(year => {{
            const option = document.createElement('option');
            option.value = year;
            option.textContent = year + '年度';
            noEventsYearSelect.appendChild(option);
        }});
        if (noEventsYearSelect.options.length > 0) {{
            noEventsYearSelect.selectedIndex = 0;
        }}
        
        renderAlertTable('rapid_growth', 1);
    </script>
</body>
</html>
'''
    
    # ファイルに書き込み
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✅ ダッシュボードを生成しました:")
    print(f"   {output_file}")
    print(f"\n📊 データ統計:")
    print(f"   利用可能な年度: {', '.join(map(str, available_years))}")
    print(f"   デフォルト年度: {default_year}")
    print(f"   累計売上: ¥{stats['current_total']:,.0f}")
    
    return str(output_file)


from member_rate_page import generate_member_rate_page

if __name__ == '__main__':
    output_file = generate_dashboard()
    print(f"\n生成されたファイルをブラウザで開いてください:")
    print(f"  {output_file}")
    
    # 会員率推移グラフページも更新
    chart_page = generate_member_rate_page()
    print(f"  {chart_page}")
