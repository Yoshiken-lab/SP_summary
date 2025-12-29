#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上分析システム V2 - ダッシュボード生成

既存ダッシュボードと同じデザイン・機能をV2スキーマで実装
"""

import json
from datetime import datetime
from pathlib import Path
from database_v2 import get_connection


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


def get_manager_sales(db_path=None, fiscal_year=None):
    """担当者別月次売上データを取得"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    if fiscal_year is None:
        cursor.execute('SELECT MAX(fiscal_year) FROM manager_monthly_sales')
        fiscal_year = cursor.fetchone()[0]
    
    cursor.execute('SELECT MAX(id) FROM reports')
    latest_report_id = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT month, manager, SUM(sales) as total
        FROM manager_monthly_sales
        WHERE fiscal_year = ? AND report_id = ?
        GROUP BY month, manager
        ORDER BY CASE WHEN month >= 4 THEN month - 4 ELSE month + 8 END, manager
    ''', (fiscal_year, latest_report_id))
    
    results = cursor.fetchall()
    conn.close()
    
    # データを整形
    data = {}
    for row in results:
        month, manager, sales = row
        if month not in data:
            data[month] = {}
        data[month][manager] = sales
    
    return data


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


def get_event_sales(db_path=None, fiscal_year=None):
    """イベント別売上データを取得"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    if fiscal_year is None:
        cursor.execute('SELECT MAX(fiscal_year) FROM event_sales')
        fiscal_year = cursor.fetchone()[0]
    
    cursor.execute('SELECT MAX(id) FROM reports')
    latest_report_id = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT event_name, event_date, SUM(sales) as total
        FROM event_sales
        WHERE fiscal_year = ? AND report_id = ?
        GROUP BY event_name, event_date
        ORDER BY event_date
        LIMIT 20
    ''', (fiscal_year, latest_report_id))
    
    results = cursor.fetchall()
    conn.close()
    
    return [{'name': row[0], 'date': row[1], 'sales': row[2]} for row in results]


if __name__ == '__main__':
    # テスト実行
    print("=" * 70)
    print("データ取得関数テスト")
    print("=" * 70)
    
    years = get_available_fiscal_years()
    print(f"\n利用可能な年度: {years}")
    
    for year in years[:2]:  # 最新2年度のみテスト
        print(f"\n--- {year}年度 ---")
        stats = get_summary_stats(fiscal_year=year)
        print(f"累計売上: ¥{stats['current_total']:,.0f}")
        print(f"前年比: {stats['yoy_rate']*100:.1f}%")
        print(f"学校数: {stats['school_count']}")
        print(f"イベント数: {stats['event_count']}")
        
        monthly = get_monthly_data(fiscal_year=year)
        print(f"月次データ: {len(monthly)}件")
        
        branch = get_branch_sales(fiscal_year=year)
        print(f"事業所別: {len(branch)}件")
        if branch:
            print(f"  {branch[0]['branch']}: ¥{branch[0]['sales']:,.0f}")
        
        top_schools = get_top_schools(fiscal_year=year, limit=3)
        print(f"TOP3学校: {len(top_schools)}件")
        if top_schools:
            print(f"  1位: {top_schools[0]['school']}: ¥{top_schools[0]['sales']:,.0f}")
    
    print("\n✅ データ取得関数テスト完了!")
