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
        SELECT DISTINCT school_id, school_name, attribute, studio
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
    
    return [{'id': row[0], 'name': row[1], 'region': row[2], 'studio': row[3]} for row in results]


def get_member_rates_by_school(db_path=None, school_id=None, fiscal_year=None):
    """特定学校の会員率推移を取得（全報告書から）"""
    if school_id is None:
        return []
    
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # 全報告書から学年別データを取得
    cursor.execute('''
        SELECT r.report_date, m.snapshot_date, m.grade, m.member_rate, m.total_students, m.member_count
        FROM member_rates m
        JOIN reports r ON m.report_id = r.id
        WHERE m.school_id = ?
        ORDER BY m.snapshot_date, m.grade
    ''', (school_id,))
    
    results = cursor.fetchall()
    conn.close()
    
    # データを整形 (snapshot_date毎にグループ化)
    data = {}
    for row in results:
        report_date, snapshot_date, grade, rate, total_students, member_count = row
        if snapshot_date not in data:
            data[snapshot_date] = []
        data[snapshot_date].append({
            'grade': grade,
            'rate': rate,
            'total_students': total_students,
            'member_count': member_count
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
    
    # デフォルトは最新年度
    default_year =available_years[0] if available_years else datetime.now().year
    stats = all_years_data[default_year]['stats']
    
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
                <h3 style="margin: 0; border: none; padding: 0;">📈 月別売上推移</h3>
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
            <h3>📚 学校別分析</h3>
            <div style="display: flex; gap: 0; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0;">
                <button id="tabMemberRate" onclick="switchSchoolAnalysisTab('memberRate')" class="school-analysis-tab active" style="padding: 10px 20px; border: none; background: transparent; font-size: 14px; font-weight: 600; color: #3b82f6; cursor: pointer; border-bottom: 3px solid #3b82f6; margin-bottom: -2px;">👥 会員率推移</button>
                <button id="tabSalesTrend" onclick="switchSchoolAnalysisTab('salesTrend')" class="school-analysis-tab" style="padding: 10px 20px; border: none; background: transparent; font-size: 14px; font-weight: 600; color: #666; cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px;">📈 学校別売上推移</button>
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
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <div>
                        <label style="margin-right: 16px;"><input type="radio" name="memberGradeDisplay" value="all" checked> 全学年</label>
                        <label><input type="radio" name="memberGradeDisplay" value="byGrade"> 学年ごと</label>
                    </div>
                    <div>
                        <button onclick="searchMemberRate()" style="padding: 8px 24px; background: #3b82f6; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; margin-right: 8px;">検索</button>
                        <button onclick="resetMemberRateFilters()" style="padding: 8px 24px; background: #6b7280; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; margin-right: 8px;">リセット</button>
                        <button onclick="downloadMemberRateCSV()" style="padding: 8px 24px; background: #10b981; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600;">CSVダウンロード</button>
                    </div>
                </div>
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
                            pointRadius: 0
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
            
            // 担当者リスト（manager_monthly_salesから取得）
            const managers = [];
            Object.values(allYearsData).forEach(yearData => {{
                if (yearData.manager_monthly) {{
                    Object.keys(yearData.manager_monthly).forEach(manager => {{
                        if (!managers.includes(manager)) managers.push(manager);
                    }});
                }}
            }});
            managers.sort();
            const managerSelect = document.getElementById('salesManagerFilter');
            managers.forEach(manager => {{
                const option = document.createElement('option');
                option.value = manager;
                option.textContent = manager;
                managerSelect.appendChild(option);
            }});
            
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
                // allYearsDataから選択した事業所の担当者を抽出
                Object.values(allYearsData).forEach(yearData => {{
                    if (yearData.manager_monthly) {{
                        Object.keys(yearData.manager_monthly).forEach(manager => {{
                            // 担当者データから事業所情報を取得する必要がある
                            // 現状のデータ構造では事業所→担当者の紐付けがないため、
                            // 一旦全担当者を表示
                            if (!filteredManagers.includes(manager)) {{
                                filteredManagers.push(manager);
                            }}
                        }});
                    }}
                }});
                filteredManagers.sort();
            }} else {{
                // 全ての担当者
                Object.values(allYearsData).forEach(yearData => {{
                    if (yearData.manager_monthly) {{
                        Object.keys(yearData.manager_monthly).forEach(manager => {{
                            if (!filteredManagers.includes(manager)) {{
                                filteredManagers.push(manager);
                            }}
                        }});
                    }}
                }});
                filteredManagers.sort();
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
            
            let filtered = schoolsList;
            // 事業所や担当者による写真館の絞り込みは、
            // schools_masterに事業所・担当者情報がないため実装困難
            // 代わりに写真館のユニークリストを表示
            const studios = getUniqueValues(schoolsList, 'studio');
            
            const studioSelect = document.getElementById('salesStudioFilter');
            const currentValue = studioSelect.value;
            studioSelect.innerHTML = '\u003coption value=""\u003e-- 全て --\u003c/option\u003e';
            studios.forEach(studio => {{
                const option = document.createElement('option');
                option.value = studio;
                option.textContent = studio;
                studioSelect.appendChild(option);
            }});
            
            if (studios.includes(currentValue)) {{
                studioSelect.value = currentValue;
            }}
        }}
        
        // 売上タブの学校リスト更新
        function updateSalesSchoolList() {{
            const studio = document.getElementById('salesStudioFilter').value;
            
            let filtered = schoolsList;
            if (studio) filtered = filtered.filter(s => s.studio === studio);
            
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
            if (!schoolId) {{
                alert('学校を選択してください');
                return;
            }}
            
            const schoolData = schoolDetails[schoolId];
            if (!schoolData || !schoolData.member_rates) {{
                alert('この学校の会員率データがありません');
                return;
            }}
            
            const gradeDisplay = document.querySelector('input[name="memberGradeDisplay"]:checked').value;
            renderMemberRateTrend(schoolData.member_rates, gradeDisplay);
        }}
        
        // 会員率推移グラフ描画（月単位集約+年度順ソート）
        function renderMemberRateTrend(memberRateData, gradeDisplay) {{
            if (!memberRateData || Object.keys(memberRateData).length === 0) return;
            
            // 月ごとに集約（最新のデータを採用）
            const monthlyData = {{}};
            Object.keys(memberRateData).forEach(snapshotDate => {{
                const yearMonth = snapshotDate.substring(0, 7); // "2025-11-28" -> "2025-11"
                if (!monthlyData[yearMonth] || snapshotDate > monthlyData[yearMonth].date) {{
                    monthlyData[yearMonth] = {{
                        date: snapshotDate,
                        data: memberRateData[snapshotDate]
                    }};
                }}
            }});
            
            // 年度順にソート（4月始まり）
            const sortedMonths = Object.keys(monthlyData).sort((a, b) => {{
                const [yearA, monthA] = a.split('-').map(Number);
                const [yearB, monthB] = b.split('-').map(Number);
                
                // 年度の計算: 4月以降は同年度、1-3月は前年度
                const fiscalYearA = monthA >= 4 ? yearA : yearA - 1;
                const fiscalYearB = monthB >= 4 ? yearB : yearB - 1;
                
                if (fiscalYearA !== fiscalYearB) return fiscalYearA - fiscalYearB;
                
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
            
            if (gradeDisplay === 'all') {{
                // 全学年の平均
                const avgRates = sortedMonths.map(ym => {{
                    const grades = monthlyData[ym].data;
                    const sum = grades.reduce((acc, g) => acc + (g.rate || 0), 0);
                    return grades.length > 0 ? sum / grades.length : 0;
                }});
                
                datasets = [{{
                    label: '全学年平均',
                    data: avgRates,
                    borderColor: 'rgb(59, 130, 246)',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.4
                }}];
            }} else {{
                // 学年ごと
                const gradeData = {{}};
                sortedMonths.forEach(ym => {{
                    monthlyData[ym].data.forEach(item => {{
                        const grade = item.grade;
                        if (!gradeData[grade]) gradeData[grade] = [];
                        gradeData[grade].push(item.rate);
                    }});
                }});
                
                const colors = [
                    {{ border: 'rgb(59, 130, 246)', bg: 'rgba(59, 130, 246, 0.1)' }},
                    {{ border: 'rgb(16, 185, 129)', bg: 'rgba(16, 185, 129, 0.1)' }},
                    {{ border: 'rgb(245, 158, 11)', bg: 'rgba(245, 158, 11, 0.1)' }}
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
            
            memberRateTrendChart = new Chart(document.getElementById('memberRateTrendChart'), {{
                type: 'line',
                data: {{ labels: labels, datasets: datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{ legend: {{ display: true, position: 'top' }} }},
                    scales: {{
                        y: {{
                            min: 0,
                            max: 1,
                            ticks: {{ callback: function(value) {{ return (value * 100).toFixed(0) + '%'; }} }}
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
            
            // データを年度順にソート（4月始まり）
            const sortedCurrent = [...currentData].sort((a, b) => {{
                const monthA = a.month >= 4 ? a.month - 3 : a.month + 9;
                const monthB = b.month >= 4 ? b.month - 3 : b.month + 9;
                return monthA - monthB;
            }});
            
            const labels = sortedCurrent.map(d => `${{d.month}}月`);
            
            // 累積売上を計算
            let cumulative = 0;
            const currentSales = sortedCurrent.map(d => {{
                cumulative += d.sales;
                return cumulative;
            }});
            
            // 前年度データも年度順にソートして累積計算
            const sortedPrev = [...prevData].sort((a, b) => {{
                const monthA = a.month >= 4 ? a.month - 3 : a.month + 9;
                const monthB = b.month >= 4 ? b.month - 3 : b.month + 9;
                return monthA - monthB;
            }});
            
            const prevSalesMap = {{}};
            sortedPrev.forEach(d => {{ prevSalesMap[d.month] = d.sales; }});
            
            let prevCumulative = 0;
            const prevSales = sortedCurrent.map(d => {{
                const monthlySales = prevSalesMap[d.month] || 0;
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


if __name__ == '__main__':
    output_file = generate_dashboard()
    print(f"\n生成されたファイルをブラウザで開いてください:")
    print(f"  {output_file}")
