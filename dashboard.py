#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上分析システム - ダッシュボード生成

アラートと分析結果を視覚的なHTMLダッシュボードとして出力
"""

import json
from datetime import datetime
from pathlib import Path
from database import get_connection
from alerts import get_all_alerts, get_current_fiscal_year
from analytics import get_all_analytics


def get_available_fiscal_years(db_path=None):
    """DBに存在する年度一覧を取得（降順）"""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT DISTINCT fiscal_year FROM school_sales
        UNION
        SELECT DISTINCT fiscal_year FROM monthly_summary
        ORDER BY fiscal_year DESC
    ''')
    years = [row[0] for row in cursor.fetchall()]
    conn.close()

    return years if years else [get_current_fiscal_year()]


def get_summary_stats(db_path=None, target_fy=None):
    """サマリー統計を取得"""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    current_fy = target_fy if target_fy else get_current_fiscal_year()
    prev_fy = current_fy - 1

    # 最新の報告書情報
    cursor.execute('SELECT id, report_date FROM reports ORDER BY report_date DESC LIMIT 1')
    row = cursor.fetchone()
    latest_report_id = row[0] if row else None
    report_date = row[1] if row else datetime.now().strftime('%Y-%m-%d')

    # 今年度累計売上
    cursor.execute('''
        SELECT SUM(total_sales) FROM monthly_summary
        WHERE report_id = ? AND fiscal_year = ?
    ''', (latest_report_id, current_fy))
    current_total = cursor.fetchone()[0] or 0

    # 今年度にデータがある月を取得
    cursor.execute('''
        SELECT month FROM monthly_summary
        WHERE report_id = ? AND fiscal_year = ?
    ''', (latest_report_id, current_fy))
    current_months = [row[0] for row in cursor.fetchall()]

    # 前年度同期売上（今年度と同じ月のみ集計）
    if current_months:
        placeholders = ','.join(['?' for _ in current_months])
        cursor.execute(f'''
            SELECT SUM(total_sales) FROM monthly_summary
            WHERE report_id = ? AND fiscal_year = ? AND month IN ({placeholders})
        ''', (latest_report_id, prev_fy, *current_months))
        prev_total = cursor.fetchone()[0] or 0
    else:
        prev_total = 0

    # 平均予算達成率
    cursor.execute('''
        SELECT AVG(budget_rate) FROM monthly_summary
        WHERE report_id = ? AND fiscal_year = ? AND budget_rate IS NOT NULL
    ''', (latest_report_id, current_fy))
    avg_budget_rate = cursor.fetchone()[0] or 0

    # 学校数
    cursor.execute('SELECT COUNT(*) FROM schools')
    school_count = cursor.fetchone()[0]

    # 今年度イベント数
    cursor.execute('SELECT COUNT(*) FROM events WHERE fiscal_year = ?', (current_fy,))
    event_count = cursor.fetchone()[0]

    # 月別データ（今年度）
    cursor.execute('''
        SELECT month, total_sales, budget, yoy_rate
        FROM monthly_summary
        WHERE report_id = ? AND fiscal_year = ?
        ORDER BY CASE WHEN month >= 4 THEN month - 4 ELSE month + 8 END
    ''', (latest_report_id, current_fy))

    monthly_data = []
    for row in cursor.fetchall():
        monthly_data.append({
            'month': row[0],
            'sales': row[1] or 0,
            'budget': row[2] or 0,
            'yoy': row[3] or 0
        })

    # 前年度の月別売上を取得
    cursor.execute('''
        SELECT month, total_sales
        FROM monthly_summary
        WHERE report_id = ? AND fiscal_year = ?
        ORDER BY CASE WHEN month >= 4 THEN month - 4 ELSE month + 8 END
    ''', (latest_report_id, prev_fy))

    prev_monthly_data = {row[0]: row[1] or 0 for row in cursor.fetchall()}

    # 今年度データに前年度売上を追加
    for item in monthly_data:
        item['prev_sales'] = prev_monthly_data.get(item['month'], 0)

    conn.close()

    return {
        'report_date': report_date,
        'fiscal_year': current_fy,
        'current_total': current_total,
        'prev_total': prev_total,
        'yoy_rate': current_total / prev_total if prev_total > 0 else 0,
        'avg_budget_rate': avg_budget_rate,
        'school_count': school_count,
        'event_count': event_count,
        'monthly_data': monthly_data
    }


def generate_html_dashboard(db_path=None, output_path=None):
    """HTMLダッシュボードを生成"""

    # 利用可能な年度一覧を取得
    available_years = get_available_fiscal_years(db_path)

    # 各年度のサマリーデータを取得
    all_years_stats = {}
    for year in available_years:
        all_years_stats[year] = get_summary_stats(db_path, target_fy=year)

    # デフォルトは最新年度
    stats = all_years_stats[available_years[0]] if available_years else get_summary_stats(db_path)
    alerts = get_all_alerts(db_path)
    analytics = get_all_analytics(db_path)

    # アラート件数
    alert_counts = {k: len(v) for k, v in alerts.items()}
    total_alerts = sum(alert_counts.values())

    # 月別チャートデータ
    months_labels = [f"{d['month']}月" for d in stats['monthly_data']]
    sales_data = [d['sales'] for d in stats['monthly_data']]
    budget_data = [d['budget'] for d in stats['monthly_data']]
    prev_sales_data = [d['prev_sales'] for d in stats['monthly_data']]

    # 会員率推移グラフ用のデータを取得
    from member_rate_chart import (get_filter_options, get_member_rate_trend_by_school,
                                   get_member_rate_trend_by_attribute, get_sales_filter_options,
                                   get_sales_trend_by_school, get_sales_trend_by_studio,
                                   get_event_sales_by_school, get_monthly_sales_by_branch,
                                   get_monthly_sales_by_person)
    filter_options = get_filter_options(db_path)
    sales_filter_options = get_sales_filter_options(db_path)

    # 事業所別・担当者別の月別売上データを取得（年度別）
    # 2024年度と2025年度のデータを取得（2023年度は売上データ未収集のためスキップ）
    target_years_for_branch = [y for y in available_years if y >= 2024]
    branch_sales_data = get_monthly_sales_by_branch(db_path, target_years=target_years_for_branch)
    person_sales_data = get_monthly_sales_by_person(db_path, target_years=target_years_for_branch)

    # 会員率データを事前取得（年度別）
    # 2024年度と2025年度のデータを取得（2023年度は会員率データ未収集のためスキップ）
    target_years_for_member = [y for y in available_years if y >= 2024]

    all_school_data = {}
    for school in filter_options['schools']:
        for year in target_years_for_member:
            data_all = get_member_rate_trend_by_school(school['id'], by_grade=False, target_fy=year, db_path=db_path)
            if data_all and data_all.get('current_year', {}).get('dates'):
                all_school_data[f"school_{school['id']}_all_{year}"] = data_all
            data_grade = get_member_rate_trend_by_school(school['id'], by_grade=True, target_fy=year, db_path=db_path)
            if data_grade and data_grade.get('current_year'):
                all_school_data[f"school_{school['id']}_grade_{year}"] = data_grade

    all_attribute_data = {}
    for attr in filter_options['attributes']:
        for year in target_years_for_member:
            data = get_member_rate_trend_by_attribute(attr, target_fy=year, db_path=db_path)
            if data and data.get('current_year', {}).get('dates'):
                all_attribute_data[f"attr_{attr}_{year}"] = data

    # 売上推移データを事前取得（年度別）
    # 全年度のデータを取得（2023年度以降で売上データがある学校は表示可能）
    target_years = available_years

    all_sales_school_data = {}
    all_event_sales_data = {}
    for school in sales_filter_options['schools']:
        for year in target_years:
            data = get_sales_trend_by_school(school['id'], target_fy=year, db_path=db_path)
            # 指定した年度のデータが実際に存在する場合のみ保存
            # （フォールバックで別年度のデータが返ってきた場合は保存しない）
            if data and data.get('fiscal_year') == year and (data['current_year']['dates'] or data['prev_year']['dates']):
                all_sales_school_data[f"school_{school['id']}_{year}"] = data
        # イベント別売上も取得
        event_data = get_event_sales_by_school(school['id'], db_path=db_path)
        if event_data:
            all_event_sales_data[f"school_{school['id']}"] = event_data

    all_sales_studio_data = {}
    for studio in sales_filter_options['studios']:
        for year in target_years:
            data = get_sales_trend_by_studio(studio, target_fy=year, db_path=db_path)
            # 指定した年度のデータが実際に存在する場合のみ保存
            if data and data.get('fiscal_year') == year and (data['current_year']['dates'] or data['prev_year']['dates']):
                all_sales_studio_data[f"studio_{studio}_{year}"] = data

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>スクールフォト売上分析ダッシュボード</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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
        .alert-section {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            margin-bottom: 24px;
        }}
        .alert-section h3 {{
            font-size: 18px;
            color: #1a1a2e;
            margin-bottom: 20px;
        }}
        .alert-category-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }}
        .alert-category {{
            background: #f8fafc;
            border-radius: 12px;
            padding: 16px;
            border: 1px solid #e2e8f0;
        }}
        .alert-category-title {{
            font-size: 14px;
            font-weight: 600;
            color: #475569;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 2px solid #e2e8f0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .alert-category-title.positive {{ border-bottom-color: #10b981; color: #059669; }}
        .alert-category-title.warning {{ border-bottom-color: #f59e0b; color: #d97706; }}
        .alert-category-title.analysis {{ border-bottom-color: #3b82f6; color: #2563eb; }}
        .alert-tabs {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .alert-tab {{
            padding: 8px 14px;
            border-radius: 6px;
            background: white;
            color: #333;
            cursor: pointer;
            font-weight: 500;
            font-size: 13px;
            border: 1px solid #e2e8f0;
            transition: all 0.2s;
        }}
        .alert-tab:hover {{
            border-color: #3b82f6;
            color: #3b82f6;
        }}
        .alert-tab.active {{
            background: #3b82f6;
            color: white;
            border-color: #3b82f6;
        }}
        .alert-tab.positive {{ border-color: #10b981; color: #059669; }}
        .alert-tab.positive:hover {{ background: #ecfdf5; }}
        .alert-tab.positive.active {{ background: #10b981; color: white; }}
        .alert-tab.warning {{ border-color: #f59e0b; color: #d97706; }}
        .alert-tab.warning:hover {{ background: #fffbeb; }}
        .alert-tab.warning.active {{ background: #f59e0b; color: white; }}
        .alert-tab .badge {{
            background: #ef4444;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            margin-left: 6px;
        }}
        .alert-tab.positive .badge {{ background: #10b981; }}
        .alert-content {{ display: none; }}
        .alert-content.active {{ display: block; }}
        .alert-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .alert-table th {{
            text-align: left;
            padding: 12px 8px;
            background: #f8fafc;
            border-bottom: 2px solid #e2e8f0;
            font-weight: 600;
            color: #475569;
            white-space: nowrap;
        }}
        .alert-table td {{
            padding: 10px 8px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .alert-table tr:hover {{ background: #f8fafc; }}
        .alert-table th.sortable {{ cursor: pointer; user-select: none; }}
        .alert-table th.sortable:hover {{ background: #e2e8f0; }}
        .alert-table th.sortable::after {{ content: ' ↕'; opacity: 0.3; font-size: 10px; }}
        .alert-table th.sortable.asc::after {{ content: ' ↑'; opacity: 1; }}
        .alert-table th.sortable.desc::after {{ content: ' ↓'; opacity: 1; }}
        .alert-controls {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            align-items: center;
            margin-bottom: 16px;
            padding: 12px;
            background: #f8fafc;
            border-radius: 8px;
        }}
        .alert-controls label {{ font-size: 13px; color: #475569; font-weight: 500; }}
        .alert-controls select {{
            padding: 6px 12px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            font-size: 13px;
            background: white;
        }}
        .alert-header {{
            display: flex;
            justify-content: flex-end;
            margin-bottom: 12px;
        }}
        .csv-download-btn {{
            padding: 6px 14px;
            border: 1px solid #3b82f6;
            border-radius: 6px;
            background: #3b82f6;
            color: white;
            font-size: 13px;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .csv-download-btn:hover {{
            background: #2563eb;
        }}
        .alert-controls .csv-download-btn {{
            margin-left: auto;
        }}
        .pagination {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid #e2e8f0;
        }}
        .pagination button {{
            padding: 6px 12px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            background: white;
            cursor: pointer;
            font-size: 13px;
        }}
        .pagination button:hover:not(:disabled) {{ background: #f0f0f0; }}
        .pagination button:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .pagination button.active {{ background: #3b82f6; color: white; border-color: #3b82f6; }}
        .pagination .page-info {{ font-size: 13px; color: #666; margin: 0 8px; }}
        .status-badge {{
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
        }}
        .status-badge.danger {{ background: #fef2f2; color: #dc2626; }}
        .status-badge.warning {{ background: #fffbeb; color: #d97706; }}
        .status-badge.success {{ background: #ecfdf5; color: #059669; }}
        .status-badge.info {{ background: #eff6ff; color: #2563eb; }}
        .analysis-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 24px;
            margin-bottom: 24px;
        }}
        .analysis-card {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .analysis-card h4 {{
            font-size: 16px;
            color: #1a1a2e;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .trend-item {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .trend-item:last-child {{ border-bottom: none; }}
        .trend-up {{ color: #10b981; }}
        .trend-down {{ color: #ef4444; }}
        .comparison-container {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-top: 16px;
        }}
        .comparison-column {{
            background: #f8fafc;
            border-radius: 8px;
            padding: 16px;
        }}
        .comparison-column h4 {{
            font-size: 14px;
            font-weight: 600;
            color: #475569;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 2px solid #3b82f6;
        }}
        .comparison-column.left h4 {{ border-bottom-color: #3b82f6; }}
        .comparison-column.right h4 {{ border-bottom-color: #8b5cf6; }}
        .comparison-event {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            background: white;
            border-radius: 6px;
            margin-bottom: 8px;
            border: 1px solid #e2e8f0;
        }}
        .comparison-event-name {{
            font-weight: 500;
            color: #1a1a2e;
        }}
        .comparison-event-date {{
            font-size: 12px;
            color: #666;
            margin-left: 8px;
        }}
        .comparison-event-sales {{
            font-weight: 600;
            color: #059669;
        }}
        .comparison-summary {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #e2e8f0;
            display: flex;
            justify-content: space-between;
            font-size: 14px;
            font-weight: 600;
        }}
        .comparison-empty {{
            text-align: center;
            padding: 20px;
            color: #888;
            font-size: 13px;
        }}
        .footer {{
            text-align: center;
            color: rgba(255,255,255,0.7);
            padding: 20px;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>スクールフォト売上分析ダッシュボード</h1>
                <p class="date">レポート日: {stats['report_date']}</p>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 12px; color: #666;">蓄積データ</div>
                <div style="font-size: 20px; font-weight: bold;">{stats['school_count']}校 / {stats['event_count']}イベント</div>
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
        </div>

        <!-- 月別売上推移セクション -->
        <div class="chart-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h3 style="margin: 0; border: none; padding: 0;">月別売上推移</h3>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <label style="font-size: 14px; color: #666; font-weight: 600;">年度:</label>
                    <select id="monthlySalesYearSelect" onchange="changeMonthlySalesYear()" style="padding: 8px 14px; border: 2px solid #3b82f6; border-radius: 8px; font-size: 14px; font-weight: 600; color: #1a1a2e; cursor: pointer; background: white;">
                        {chr(10).join([f'<option value="{y}" {"selected" if y == stats["fiscal_year"] else ""}>{y}年度</option>' for y in available_years])}
                    </select>
                </div>
            </div>
            <div style="display: flex; gap: 0; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0;">
                <button id="tabMonthly" onclick="switchMonthlySalesTab('monthly')" class="monthly-tab active" style="padding: 10px 20px; border: none; background: transparent; font-size: 14px; font-weight: 600; color: #3b82f6; cursor: pointer; border-bottom: 3px solid #3b82f6; margin-bottom: -2px;">月ごと</button>
                <button id="tabBranch" onclick="switchMonthlySalesTab('branch')" class="monthly-tab" style="padding: 10px 20px; border: none; background: transparent; font-size: 14px; font-weight: 600; color: #666; cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px;">事業所ごと</button>
                <button id="tabPerson" onclick="switchMonthlySalesTab('person')" class="monthly-tab" style="padding: 10px 20px; border: none; background: transparent; font-size: 14px; font-weight: 600; color: #666; cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px;">担当者ごと</button>
            </div>

            <!-- 月ごとパネル -->
            <div id="monthlyPanel" class="monthly-panel">
                <canvas id="salesChart"></canvas>
            </div>

            <!-- 事業所ごとパネル -->
            <div id="branchPanel" class="monthly-panel" style="display: none;">
                <div style="display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap;">
                    <div>
                        <label style="font-size: 12px; color: #666; font-weight: 600; margin-right: 8px;">事業所:</label>
                        <select id="branchFilter" onchange="renderBranchChart()" style="padding: 8px 12px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 150px;">
                            <option value="">-- 全事業所 --</option>
                        </select>
                    </div>
                </div>
                <canvas id="branchSalesChart"></canvas>
            </div>

            <!-- 担当者ごとパネル -->
            <div id="personPanel" class="monthly-panel" style="display: none;">
                <div style="display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; align-items: flex-end;">
                    <div>
                        <label style="font-size: 12px; color: #666; font-weight: 600; margin-right: 8px;">事業所:</label>
                        <select id="personBranchFilter" onchange="filterPersonByBranch()" style="padding: 8px 12px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 150px;">
                            <option value="">-- 選択してください --</option>
                        </select>
                    </div>
                    <div>
                        <label style="font-size: 12px; color: #666; font-weight: 600; margin-right: 8px;">担当者:</label>
                        <select id="personFilter" onchange="renderPersonChart()" style="padding: 8px 12px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 150px;">
                            <option value="">-- 選択してください --</option>
                        </select>
                    </div>
                </div>
                <div id="personChartMessage" style="text-align: center; padding: 60px 20px; color: #888; font-size: 14px;">事業所または担当者を選択してください</div>
                <canvas id="personSalesChart" style="display: none;"></canvas>
            </div>
        </div>

        <!-- 詳細グラフセクション（会員率推移・学校別売上推移） -->
        <div class="chart-card">
            <div style="display: flex; justify-content: flex-start; align-items: center; margin-bottom: 16px;">
                <div style="display: flex; gap: 0; border-bottom: 2px solid #e2e8f0;">
                    <button id="tabMemberRate" onclick="switchDetailTab('memberRate')" class="detail-tab active" style="padding: 12px 24px; border: none; background: transparent; font-size: 16px; font-weight: 600; color: #3b82f6; cursor: pointer; border-bottom: 3px solid #3b82f6; margin-bottom: -2px;">会員率推移</button>
                    <button id="tabSales" onclick="switchDetailTab('sales')" class="detail-tab" style="padding: 12px 24px; border: none; background: transparent; font-size: 16px; font-weight: 600; color: #666; cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px;">学校別売上推移</button>
                </div>
            </div>

            <!-- 会員率推移グラフ -->
            <div id="memberRatePanel" class="detail-panel">
                <div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; margin-bottom: 16px;">
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 12px; color: #666; font-weight: 600;">写真館</label>
                        <select id="filterStudio" style="padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 180px;">
                            <option value="">-- 全て --</option>
                            {chr(10).join([f'<option value="{studio}">{studio}</option>' for studio in filter_options['studios']])}
                        </select>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 12px; color: #666; font-weight: 600;">属性</label>
                        <select id="filterAttribute" style="padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 180px;">
                            <option value="">-- 全て --</option>
                            {chr(10).join([f'<option value="{attr}">{attr}</option>' for attr in filter_options['attributes']])}
                        </select>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 12px; color: #666; font-weight: 600;">学校名</label>
                        <select id="filterSchool" style="padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 250px;">
                            <option value="">-- 写真館/属性で絞り込み --</option>
                        </select>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 12px; color: #666; font-weight: 600;">年度</label>
                        <select id="detailYearSelect" onchange="changeDetailYear()" style="padding: 10px 14px; border: 2px solid #3b82f6; border-radius: 8px; font-size: 14px; font-weight: 600; color: #1a1a2e; cursor: pointer; background: white; min-width: 120px;">
                            {chr(10).join([f'<option value="{y}" {"selected" if y == stats["fiscal_year"] else ""}>{y}年度</option>' for y in available_years])}
                        </select>
                    </div>
                    <button onclick="searchMemberRate()" style="padding: 10px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; background: #3b82f6; color: white;">検索</button>
                    <button onclick="resetMemberRateFilters()" style="padding: 10px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; background: #e2e8f0; color: #475569;">リセット</button>
                </div>

                <div style="display: flex; flex-wrap: wrap; gap: 24px; align-items: center; margin-bottom: 20px;">
                    <div id="gradeOptionGroup" style="display: flex; align-items: center; gap: 8px;">
                        <input type="radio" name="gradeMode" id="gradeAll" value="all" checked style="width: 18px; height: 18px; accent-color: #3b82f6;">
                        <label for="gradeAll" style="font-size: 14px; color: #333; cursor: pointer;">全学年まとめて</label>
                        <input type="radio" name="gradeMode" id="gradeEach" value="each" style="width: 18px; height: 18px; accent-color: #3b82f6;">
                        <label for="gradeEach" style="font-size: 14px; color: #333; cursor: pointer;">学年別に表示</label>
                    </div>
                    <button onclick="exportMemberRateCSV()" style="padding: 10px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; background: #e2e8f0; color: #475569;">CSVエクスポート</button>
                </div>

                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h4 id="memberRateChartTitle" style="font-size: 16px; color: #1a1a2e;">学校または属性を選択してください</h4>
                    <span id="memberRateChartInfo" style="font-size: 13px; color: #666;"></span>
                </div>

                <div style="position: relative; height: 400px;">
                    <canvas id="memberRateChart"></canvas>
                </div>
            </div>

            <!-- 学校別売上推移グラフ -->
            <div id="salesPanel" class="detail-panel" style="display: none;">
                <div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; margin-bottom: 16px;">
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 12px; color: #666; font-weight: 600;">事業所</label>
                        <select id="salesFilterBranch" style="padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 150px;">
                            <option value="">-- 全て --</option>
                            {chr(10).join([f'<option value="{b}">{b}</option>' for b in sales_filter_options['branches']])}
                        </select>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 12px; color: #666; font-weight: 600;">担当者</label>
                        <select id="salesFilterPerson" style="padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 150px;">
                            <option value="">-- 全て --</option>
                            {chr(10).join([f'<option value="{p}">{p}</option>' for p in sales_filter_options['persons']])}
                        </select>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 12px; color: #666; font-weight: 600;">写真館</label>
                        <select id="salesFilterStudio" style="padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 180px;">
                            <option value="">-- 全て --</option>
                            {chr(10).join([f'<option value="{s}">{s}</option>' for s in sales_filter_options['studios']])}
                        </select>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 12px; color: #666; font-weight: 600;">学校名</label>
                        <select id="salesFilterSchool" style="padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 250px;">
                            <option value="">-- 絞り込みで選択 --</option>
                        </select>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 12px; color: #666; font-weight: 600;">年度</label>
                        <select id="salesYearSelect" onchange="changeSalesYear()" style="padding: 10px 14px; border: 2px solid #3b82f6; border-radius: 8px; font-size: 14px; font-weight: 600; color: #1a1a2e; cursor: pointer; background: white; min-width: 120px;">
                            {chr(10).join([f'<option value="{y}" {"selected" if y == stats["fiscal_year"] else ""}>{y}年度</option>' for y in available_years])}
                        </select>
                    </div>
                    <button onclick="searchSalesTrend()" style="padding: 10px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; background: #3b82f6; color: white;">検索</button>
                    <button onclick="resetSalesFilters()" style="padding: 10px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; background: #e2e8f0; color: #475569;">リセット</button>
                </div>

                <div style="display: flex; flex-wrap: wrap; gap: 24px; align-items: center; margin-bottom: 20px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <input type="checkbox" id="showSalesPrevYear" checked style="width: 18px; height: 18px; accent-color: #3b82f6;">
                        <label for="showSalesPrevYear" style="font-size: 14px; color: #333; cursor: pointer;">前年度を表示</label>
                    </div>
                    <button onclick="exportSalesCSV()" style="padding: 10px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; background: #e2e8f0; color: #475569;">CSVエクスポート</button>
                </div>

                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h4 id="salesChartTitle" style="font-size: 16px; color: #1a1a2e;">写真館または学校を選択してください</h4>
                    <span id="salesChartInfo" style="font-size: 13px; color: #666;"></span>
                </div>

                <div style="position: relative; height: 400px;">
                    <canvas id="salesTrendChart"></canvas>
                </div>

                <!-- イベント別内訳セクション -->
                <div id="eventBreakdownSection" style="display: none; margin-top: 24px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
                    <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 16px; flex-wrap: wrap;">
                        <h4 style="font-size: 14px; color: #1a1a2e; margin: 0;">イベント別売上内訳</h4>
                        <div style="display: flex; align-items: center; gap: 8px; background: #f8fafc; padding: 8px 12px; border-radius: 8px;">
                            <span style="font-size: 13px; color: #666; font-weight: 500;">並び替え:</span>
                            <select id="eventSortType" onchange="updateEventSort()" style="padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; cursor: pointer;">
                                <option value="sales_desc">売上（高い順）</option>
                                <option value="sales_asc">売上（低い順）</option>
                                <option value="date_desc">開始日（新しい順）</option>
                                <option value="date_asc">開始日（古い順）</option>
                            </select>
                        </div>
                    </div>
                    <div id="eventBreakdownContainer" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 16px;"></div>
                </div>
            </div>
        </div>

        <!-- 条件別集計 -->
        <div class="alert-section">
            <h3>条件別集計</h3>
            <div class="alert-category-container">
                <!-- ポジティブ（売上・実績） -->
                <div class="alert-category">
                    <div class="alert-category-title positive">📊 売上・実績</div>
                    <div class="alert-tabs">
                        <button class="alert-tab positive active" onclick="showAlert('rapid_growth')" id="tab-rapid_growth">売上好調校</button>
                        <button class="alert-tab positive" onclick="showAlert('new_schools')" id="tab-new_schools">新規開始校</button>
                    </div>
                </div>
                <!-- 要注意・改善 -->
                <div class="alert-category">
                    <div class="alert-category-title warning">⚠️ 要注意・改善</div>
                    <div class="alert-tabs">
                        <button class="alert-tab warning" onclick="showAlert('no_events')" id="tab-no_events">今年度未実施</button>
                        <button class="alert-tab warning" onclick="showAlert('decline')" id="tab-decline">会員率・売上低下</button>
                        <button class="alert-tab warning" onclick="showAlert('studio_decline')" id="tab-studio_decline">写真館別低下</button>
                    </div>
                </div>
                <!-- 分析・トレンド -->
                <div class="alert-category">
                    <div class="alert-category-title analysis">📈 トレンド分析</div>
                    <div class="alert-tabs">
                        <button class="alert-tab" onclick="showAlert('member_rate_trend')" id="tab-member_rate_trend">会員率改善校</button>
                        <button class="alert-tab" onclick="showAlert('unit_price')" id="tab-unit_price">売上単価分析</button>
                    </div>
                </div>
                <!-- イベント関連 -->
                <div class="alert-category">
                    <div class="alert-category-title analysis">📅 イベント関連</div>
                    <div class="alert-tabs">
                        <button class="alert-tab" onclick="showAlert('new_event_low')" id="tab-new_event_low">イベント開始日別売上</button>
                        <button class="alert-tab" onclick="showAlert('yearly_comparison')" id="tab-yearly_comparison">年度別イベント比較</button>
                    </div>
                </div>
            </div>

            <!-- 今年度未実施 -->
            <div id="alert-no_events" class="alert-content">
                <div class="alert-header">
                    <button class="csv-download-btn" onclick="downloadAlertCSV('no_events')">📥 CSV出力</button>
                </div>
                <div id="no_events-table-container"></div>
                <div id="no_events-pagination" class="pagination"></div>
            </div>

            <!-- イベント開始日別会員率 -->
            <div id="alert-new_event_low" class="alert-content">
                <div class="alert-controls">
                    <label>年:</label>
                    <select id="new_event_low-year-filter" style="padding: 6px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; background: white;">
                        {' '.join([f'<option value="{y}">{y}年</option>' for y in available_years])}
                    </select>
                    <label>月:</label>
                    <select id="new_event_low-month-filter" style="padding: 6px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; background: white;">
                        <option value="">-</option>
                        <option value="01">1月</option>
                        <option value="02">2月</option>
                        <option value="03">3月</option>
                        <option value="04">4月</option>
                        <option value="05">5月</option>
                        <option value="06">6月</option>
                        <option value="07">7月</option>
                        <option value="08">8月</option>
                        <option value="09">9月</option>
                        <option value="10">10月</option>
                        <option value="11">11月</option>
                        <option value="12">12月</option>
                    </select>
                    <label>日:</label>
                    <select id="new_event_low-day-filter" style="padding: 6px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; background: white;">
                        <option value="">-</option>
                        {' '.join([f'<option value="{str(d).zfill(2)}">{d}日</option>' for d in range(1, 32)])}
                    </select>
                    <span style="margin: 0 8px; color: #666; font-size: 13px;">に公開したイベントを</span>
                    <button onclick="filterNewEventLowByDate()" style="padding: 6px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; font-size: 13px; cursor: pointer;">表示する</button>
                    <button class="csv-download-btn" onclick="downloadAlertCSV('new_event_low')">📥 CSV出力</button>
                </div>
                <div id="new_event_low-message" style="text-align: center; padding: 40px 20px; color: #888; font-size: 14px;">年を選択して「表示する」をクリックしてください</div>
                <div id="new_event_low-table-container" style="display: none;"></div>
                <div id="new_event_low-pagination" class="pagination" style="display: none;"></div>
            </div>

            <!-- 会員率・売上低下 -->
            <div id="alert-decline" class="alert-content">
                <div class="alert-controls">
                    <label>会員率:</label>
                    <select id="decline-member-rate-filter" onchange="filterDeclineAlert()">
                        <option value="1.0">指定なし</option>
                        <option value="0.5" selected>50%未満</option>
                        <option value="0.4">40%未満</option>
                        <option value="0.3">30%未満</option>
                        <option value="0.2">20%未満</option>
                    </select>
                    <label>売上減少率:</label>
                    <select id="decline-sales-from-filter" onchange="filterDeclineAlert()">
                        <option value="">-</option>
                        <option value="-0.1" selected>10%</option>
                        <option value="-0.2">20%</option>
                        <option value="-0.3">30%</option>
                        <option value="-0.4">40%</option>
                        <option value="-0.5">50%</option>
                        <option value="-0.6">60%</option>
                        <option value="-0.7">70%</option>
                        <option value="-0.8">80%</option>
                        <option value="-0.9">90%</option>
                        <option value="-1.0">100%</option>
                    </select>
                    <span style="margin: 0 4px;">～</span>
                    <select id="decline-sales-to-filter" onchange="filterDeclineAlert()">
                        <option value="">-</option>
                        <option value="-0.1">10%</option>
                        <option value="-0.2">20%</option>
                        <option value="-0.3" selected>30%</option>
                        <option value="-0.4">40%</option>
                        <option value="-0.5">50%</option>
                        <option value="-0.6">60%</option>
                        <option value="-0.7">70%</option>
                        <option value="-0.8">80%</option>
                        <option value="-0.9">90%</option>
                        <option value="-1.0">100%</option>
                    </select>
                    <span style="margin-right: 8px;">減少</span>
                    <button class="csv-download-btn" onclick="downloadAlertCSV('decline')">📥 CSV出力</button>
                </div>
                <div id="decline-table-container"></div>
                <div id="decline-pagination" class="pagination"></div>
            </div>

            <!-- 新規開始校 -->
            <div id="alert-new_schools" class="alert-content">
                <div class="alert-controls">
                    <label>年度:</label>
                    <select id="new_schools-year-filter" onchange="filterNewSchoolsAlert()">
                        {' '.join([f'<option value="{y}">{y}年度</option>' for y in available_years])}
                    </select>
                    <label>月:</label>
                    <select id="new_schools-month-filter" onchange="filterNewSchoolsAlert()">
                        <option value="">指定なし</option>
                        <option value="4">4月</option>
                        <option value="5">5月</option>
                        <option value="6">6月</option>
                        <option value="7">7月</option>
                        <option value="8">8月</option>
                        <option value="9">9月</option>
                        <option value="10">10月</option>
                        <option value="11">11月</option>
                        <option value="12">12月</option>
                        <option value="1">1月</option>
                        <option value="2">2月</option>
                        <option value="3">3月</option>
                    </select>
                    <button class="csv-download-btn" onclick="downloadAlertCSV('new_schools')">📥 CSV出力</button>
                </div>
                <div id="new_schools-table-container"></div>
                <div id="new_schools-pagination" class="pagination"></div>
            </div>

            <!-- 写真館別低下 -->
            <div id="alert-studio_decline" class="alert-content">
                <div class="alert-header">
                    <button class="csv-download-btn" onclick="downloadAlertCSV('studio_decline')">📥 CSV出力</button>
                </div>
                <div id="studio_decline-table-container"></div>
                <div id="studio_decline-pagination" class="pagination"></div>
            </div>

            <!-- 急成長校 -->
            <div id="alert-rapid_growth" class="alert-content active">
                <div class="alert-header">
                    <button class="csv-download-btn" onclick="downloadAlertCSV('rapid_growth')">📥 CSV出力</button>
                </div>
                <div id="rapid_growth-table-container"></div>
                <div id="rapid_growth-pagination" class="pagination"></div>
            </div>

            <!-- 会員率改善校 -->
            <div id="alert-member_rate_trend" class="alert-content">
                <div class="alert-controls">
                    <label>属性:</label>
                    <select id="member_rate_trend-attribute-filter" onchange="updateMemberRateTrendFilters()">
                        <option value="">全て</option>
                    </select>
                    <label>写真館:</label>
                    <select id="member_rate_trend-studio-filter" onchange="updateMemberRateTrendFilters()">
                        <option value="">全て</option>
                    </select>
                    <label>学校名:</label>
                    <select id="member_rate_trend-school-filter" onchange="filterMemberRateTrendAlert()">
                        <option value="">全て</option>
                    </select>
                    <label>年度:</label>
                    <select id="member_rate_trend-year-filter" onchange="filterMemberRateTrendAlert()">
                        {' '.join([f'<option value="{y}">{y}年度</option>' for y in available_years])}
                    </select>
                    <button onclick="filterMemberRateTrendAlert()" style="padding: 6px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; font-size: 13px; cursor: pointer;">絞り込む</button>
                    <button class="csv-download-btn" onclick="downloadAlertCSV('member_rate_trend')">📥 CSV出力</button>
                </div>
                <div id="member_rate_trend-message" style="text-align: center; padding: 40px 20px; color: #888; font-size: 14px;">年度を選択して「絞り込む」をクリックしてください</div>
                <div id="member_rate_trend-table-container" style="display: none;"></div>
                <div id="member_rate_trend-pagination" class="pagination" style="display: none;"></div>
            </div>

            <!-- 売上単価分析 -->
            <div id="alert-unit_price" class="alert-content">
                <div class="alert-controls">
                    <label>属性:</label>
                    <select id="unit_price-attribute-filter" onchange="filterUnitPriceAlert()">
                        <option value="">全て</option>
                    </select>
                    <label>写真館:</label>
                    <select id="unit_price-studio-filter" onchange="filterUnitPriceAlert()">
                        <option value="">全て</option>
                    </select>
                    <label>学校名:</label>
                    <select id="unit_price-school-filter" onchange="filterUnitPriceAlert()">
                        <option value="">全て</option>
                    </select>
                    <button class="csv-download-btn" onclick="downloadAlertCSV('unit_price')">📥 CSV出力</button>
                </div>
                <div id="unit_price-table-container"></div>
                <div id="unit_price-pagination" class="pagination"></div>
            </div>

            <!-- 年度別イベント比較 -->
            <div id="alert-yearly_comparison" class="alert-content">
                <div class="alert-controls">
                    <label>属性:</label>
                    <select id="yearly_comparison-attribute-filter" onchange="updateYearlyComparisonFilters()">
                        <option value="">全て</option>
                    </select>
                    <label>写真館:</label>
                    <select id="yearly_comparison-studio-filter" onchange="updateYearlyComparisonFilters()">
                        <option value="">全て</option>
                    </select>
                    <label>学校<span style="color: #ef4444;">*</span>:</label>
                    <select id="yearly_comparison-school-filter" style="min-width: 200px;" required>
                        <option value="">-- 学校を選択 --</option>
                    </select>
                    <span style="margin: 0 4px; color: #666; font-size: 13px;">で</span>
                    <label>月:</label>
                    <select id="yearly_comparison-month-filter">
                        <option value="">全て</option>
                        <option value="1">1月</option>
                        <option value="2">2月</option>
                        <option value="3">3月</option>
                        <option value="4">4月</option>
                        <option value="5">5月</option>
                        <option value="6">6月</option>
                        <option value="7">7月</option>
                        <option value="8">8月</option>
                        <option value="9">9月</option>
                        <option value="10">10月</option>
                        <option value="11">11月</option>
                        <option value="12">12月</option>
                    </select>
                    <span style="margin: 0 4px; color: #666; font-size: 13px;">に</span>
                    <select id="yearly_comparison-left-year-filter" required>
                        {' '.join([f'<option value="{y}">{y}年度</option>' for y in available_years])}
                    </select>
                    <span style="margin: 0 4px; color: #666; font-size: 13px;">と</span>
                    <select id="yearly_comparison-right-year-filter" required>
                        {' '.join([f'<option value="{y}"' + (' selected' if i == 1 else '') + f'>{y}年度</option>' for i, y in enumerate(available_years)])}
                    </select>
                    <span style="margin: 0 8px; color: #666; font-size: 13px;">で公開したイベントを</span>
                    <button onclick="filterYearlyComparisonAlert()" style="padding: 6px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; font-size: 13px; cursor: pointer;">比較する</button>
                    <button class="csv-download-btn" onclick="downloadYearlyComparisonCSV()">📥 CSV出力</button>
                </div>
                <div id="yearly_comparison-message" style="text-align: center; padding: 40px 20px; color: #888; font-size: 14px;"><span style="color: #ef4444;">*</span>は必須項目です。学校・月・年度を選択して「比較する」をクリックしてください</div>
                <div id="yearly_comparison-container" style="display: none;"></div>
            </div>
        </div>'''

    html += f'''
        <div class="footer">
            Generated by スクールフォト売上分析システム | {datetime.now().strftime('%Y-%m-%d %H:%M')}
        </div>
    </div>

    <script>
        // データ
        const schoolsData = {json.dumps(filter_options['schools'], ensure_ascii=False)};
        const allAttributes = {json.dumps(filter_options['attributes'], ensure_ascii=False)};
        const allStudios = {json.dumps(filter_options['studios'], ensure_ascii=False)};
        const allSchoolData = {json.dumps(all_school_data, ensure_ascii=False)};
        const allAttributeData = {json.dumps(all_attribute_data, ensure_ascii=False)};
        const salesSchoolsData = {json.dumps(sales_filter_options['schools'], ensure_ascii=False)};
        const allBranches = {json.dumps(sales_filter_options['branches'], ensure_ascii=False)};
        const allSalesStudios = {json.dumps(sales_filter_options['studios'], ensure_ascii=False)};
        const allPersons = {json.dumps(sales_filter_options['persons'], ensure_ascii=False)};
        const allSalesAttributes = {json.dumps(sales_filter_options['attributes'], ensure_ascii=False)};
        const allSalesSchoolData = {json.dumps(all_sales_school_data, ensure_ascii=False)};
        const allSalesStudioData = {json.dumps(all_sales_studio_data, ensure_ascii=False)};
        const allEventSalesData = {json.dumps(all_event_sales_data, ensure_ascii=False)};
        const branchSalesData = {json.dumps(branch_sales_data, ensure_ascii=False)};
        const personSalesData = {json.dumps(person_sales_data, ensure_ascii=False)};

        // アラートデータ
        const alertData = {{
            no_events: {json.dumps(alerts.get('no_events_this_year', []), ensure_ascii=False)},
            new_event_low: {json.dumps(alerts.get('new_event_low_registration', []), ensure_ascii=False)},
            decline: {json.dumps(alerts.get('member_rate_decline', []), ensure_ascii=False)},
            new_schools: {json.dumps(alerts.get('new_schools', []), ensure_ascii=False)},
            studio_decline: {json.dumps(alerts.get('studio_performance_decline', []), ensure_ascii=False)},
            rapid_growth: {json.dumps(alerts.get('rapid_growth', []), ensure_ascii=False)},
            member_rate_trend: {json.dumps(alerts.get('member_rate_trend_improved', []), ensure_ascii=False)},
            unit_price: {json.dumps(alerts.get('sales_unit_price', []), ensure_ascii=False)},
            schools_for_filter: {json.dumps(alerts.get('schools_for_filter', []), ensure_ascii=False)}
        }};

        // アラートページング・ソート状態管理
        const alertState = {{
            no_events: {{ page: 1, sortKey: 'prev_year_sales', sortDir: 'desc', data: alertData.no_events }},
            new_event_low: {{ page: 1, sortKey: 'member_rate', sortDir: 'asc', data: alertData.new_event_low }},
            decline: {{ page: 1, sortKey: 'member_rate', sortDir: 'asc', data: [] }},
            new_schools: {{ page: 1, sortKey: 'first_event_date', sortDir: 'desc', data: alertData.new_schools }},
            studio_decline: {{ page: 1, sortKey: 'change_rate', sortDir: 'asc', data: alertData.studio_decline }},
            rapid_growth: {{ page: 1, sortKey: 'growth_rate', sortDir: 'desc', data: alertData.rapid_growth }},
            member_rate_trend: {{ page: 1, sortKey: 'improvement', sortDir: 'desc', data: [] }},
            unit_price: {{ page: 1, sortKey: 'unit_price', sortDir: 'desc', data: alertData.unit_price }},
            yearly_comparison: {{ leftYear: {available_years[0] if available_years else 2025}, rightYear: {available_years[1] if len(available_years) > 1 else 2024}, data: {{ left: [], right: [] }} }}
        }};
        const PAGE_SIZE = 30;

        // 年度別サマリーデータ
        const allYearsStats = {json.dumps({str(k): v for k, v in all_years_stats.items()}, ensure_ascii=False)};
        let currentMonthlySalesYear = {stats['fiscal_year']};
        let currentDetailYear = {stats['fiscal_year']};

        // 月別売上推移の年度切り替え関数（サマリーカードと連動）
        function changeMonthlySalesYear() {{
            const selectedYear = document.getElementById('monthlySalesYearSelect').value;
            currentMonthlySalesYear = parseInt(selectedYear);
            const stats = allYearsStats[selectedYear];

            if (!stats) return;

            // サマリーカードを更新
            document.getElementById('salesCardTitle').textContent = `${{selectedYear}}年度 累計売上`;
            document.getElementById('salesCardValue').textContent = `¥${{stats.current_total.toLocaleString()}}`;
            document.getElementById('salesCardSub').textContent = `前年同期 ¥${{stats.prev_total.toLocaleString()}}`;

            const yoyRate = stats.yoy_rate * 100;
            const yoyEl = document.getElementById('yoyCardValue');
            yoyEl.textContent = `${{yoyRate.toFixed(1)}}%`;
            yoyEl.className = 'card-value ' + (yoyRate >= 100 ? 'success' : yoyRate >= 80 ? 'warning' : 'danger');
            document.getElementById('yoyCardSub').textContent = yoyRate >= 100 ? '成長' : '減少';

            const budgetRate = stats.avg_budget_rate * 100;
            const budgetEl = document.getElementById('budgetCardValue');
            budgetEl.textContent = `${{budgetRate.toFixed(1)}}%`;
            budgetEl.className = 'card-value ' + (budgetRate >= 100 ? 'success' : budgetRate >= 80 ? 'warning' : 'danger');

            // 月別グラフを更新
            updateMonthlyChart(stats);

            // 事業所・担当者グラフも更新（タブが表示されていれば）
            if (document.getElementById('branchPanel').style.display === 'block') {{
                renderBranchChart();
            }}
            if (document.getElementById('personPanel').style.display === 'block') {{
                const branch = document.getElementById('personBranchFilter').value;
                if (branch) {{
                    renderPersonChartByBranch(branch);
                }} else {{
                    const person = document.getElementById('personFilter').value;
                    if (person) {{
                        renderPersonChart();
                    }}
                }}
            }}
        }}

        // 会員率推移の年度切り替え関数
        function changeDetailYear() {{
            const selectedYear = document.getElementById('detailYearSelect').value;
            currentDetailYear = parseInt(selectedYear);
            // 現在表示中のデータがあれば自動的に再検索
            const attr = document.getElementById('filterAttribute').value;
            const schoolId = document.getElementById('filterSchool').value;
            if (attr || schoolId) {{
                searchMemberRate();
            }}
        }}

        // 学校別売上推移の年度切り替え関数
        function changeSalesYear() {{
            const selectedYear = document.getElementById('salesYearSelect').value;
            // 現在表示中のデータがあれば自動的に再検索
            const studio = document.getElementById('salesFilterStudio').value;
            const schoolId = document.getElementById('salesFilterSchool').value;
            if (studio || schoolId) {{
                searchSalesTrend();
            }}
        }}

        // 月別グラフ更新
        function updateMonthlyChart(stats) {{
            if (!mainSalesChart || !stats.monthly_data) return;

            const months = stats.monthly_data.map(d => d.month + '月');
            const salesData = stats.monthly_data.map(d => d.sales);
            const prevSalesData = stats.monthly_data.map(d => d.prev_sales);
            const budgetData = stats.monthly_data.map(d => d.budget);

            mainSalesChart.data.labels = months;
            mainSalesChart.data.datasets[0].data = salesData;
            mainSalesChart.data.datasets[1].data = prevSalesData;
            mainSalesChart.data.datasets[2].data = budgetData;
            mainSalesChart.update();
        }}

        let memberRateChart = null;
        let currentMemberRateData = null;
        let salesTrendChart = null;
        let currentSalesData = null;
        let branchSalesChart = null;
        let personSalesChart = null;
        let mainSalesChart = null;
        let currentEventSortType = 'sales_desc';
        let currentSchoolId = null;

        // 月別売上タブ切り替え
        function switchMonthlySalesTab(tab) {{
            document.querySelectorAll('.monthly-panel').forEach(p => p.style.display = 'none');
            document.querySelectorAll('.monthly-tab').forEach(t => {{
                t.style.color = '#666';
                t.style.borderBottomColor = 'transparent';
            }});

            if (tab === 'monthly') {{
                document.getElementById('monthlyPanel').style.display = 'block';
                document.getElementById('tabMonthly').style.color = '#3b82f6';
                document.getElementById('tabMonthly').style.borderBottomColor = '#3b82f6';
            }} else if (tab === 'branch') {{
                document.getElementById('branchPanel').style.display = 'block';
                document.getElementById('tabBranch').style.color = '#3b82f6';
                document.getElementById('tabBranch').style.borderBottomColor = '#3b82f6';
                initBranchFilter();
                renderBranchChart();
            }} else if (tab === 'person') {{
                document.getElementById('personPanel').style.display = 'block';
                document.getElementById('tabPerson').style.color = '#3b82f6';
                document.getElementById('tabPerson').style.borderBottomColor = '#3b82f6';
                initPersonFilters();
            }}
        }}

        // 事業所フィルター初期化
        function initBranchFilter() {{
            const branchSelect = document.getElementById('branchFilter');
            if (branchSelect.options.length <= 1 && branchSalesData.branches) {{
                branchSalesData.branches.forEach(b => {{
                    const opt = document.createElement('option');
                    opt.value = b;
                    opt.textContent = b;
                    branchSelect.appendChild(opt);
                }});
            }}
        }}

        // 事業所グラフ描画（棒グラフ）- 年度対応
        function renderBranchChart() {{
            const selectedBranch = document.getElementById('branchFilter').value;
            const months = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3];
            const labels = months.map(m => m + '月');
            const ctx = document.getElementById('branchSalesChart').getContext('2d');

            if (branchSalesChart) branchSalesChart.destroy();

            // 選択された年度のデータを取得
            const yearData = branchSalesData.data_by_year?.[currentMonthlySalesYear];
            if (!yearData) {{
                console.log('年度データなし:', currentMonthlySalesYear);
                return;
            }}

            if (!selectedBranch) {{
                // 全事業所の選択年度売上を棒グラフで表示
                const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];
                const datasets = [];
                let colorIdx = 0;

                if (branchSalesData.branches) {{
                    branchSalesData.branches.forEach(branch => {{
                        const data = yearData[branch];
                        if (data) {{
                            datasets.push({{
                                label: branch,
                                data: months.map(m => data.current[m] || 0),
                                backgroundColor: colors[colorIdx % colors.length],
                                borderRadius: 4
                            }});
                            colorIdx++;
                        }}
                    }});
                }}

                branchSalesChart = new Chart(ctx, {{
                    type: 'bar',
                    data: {{ labels, datasets }},
                    options: {{
                        responsive: true,
                        plugins: {{
                            legend: {{ position: 'top' }},
                            title: {{ display: true, text: currentMonthlySalesYear + '年度 事業所別月別売上' }}
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                ticks: {{ callback: v => '¥' + Math.round(v / 10000).toLocaleString() + '万' }}
                            }}
                        }}
                    }}
                }});
            }} else {{
                // 特定事業所の選択年度・前年度・予算を棒グラフで表示
                const data = yearData[selectedBranch];
                if (!data) return;

                const datasets = [
                    {{
                        label: currentMonthlySalesYear + '年度売上',
                        data: months.map(m => data.current[m] || 0),
                        backgroundColor: 'rgba(59, 130, 246, 0.8)',
                        borderRadius: 4
                    }},
                    {{
                        label: (currentMonthlySalesYear - 1) + '年度売上',
                        data: months.map(m => data.prev[m] || 0),
                        backgroundColor: 'rgba(156, 163, 175, 0.6)',
                        borderRadius: 4
                    }},
                    {{
                        label: '予算',
                        data: months.map(m => data.budget[m] || 0),
                        backgroundColor: 'rgba(251, 191, 36, 0.6)',
                        borderRadius: 4
                    }}
                ];

                branchSalesChart = new Chart(ctx, {{
                    type: 'bar',
                    data: {{ labels, datasets }},
                    options: {{
                        responsive: true,
                        plugins: {{
                            legend: {{ position: 'top' }},
                            title: {{ display: true, text: selectedBranch + ' - ' + currentMonthlySalesYear + '年度 月別売上推移' }}
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                ticks: {{ callback: v => '¥' + Math.round(v / 10000).toLocaleString() + '万' }}
                            }}
                        }}
                    }}
                }});
            }}
        }}

        // 担当者フィルター初期化
        function initPersonFilters() {{
            const branchSelect = document.getElementById('personBranchFilter');
            const personSelect = document.getElementById('personFilter');

            if (branchSelect.options.length <= 1 && branchSalesData.branches) {{
                branchSalesData.branches.forEach(b => {{
                    const opt = document.createElement('option');
                    opt.value = b;
                    opt.textContent = b;
                    branchSelect.appendChild(opt);
                }});
            }}

            if (personSelect.options.length <= 1 && personSalesData.persons) {{
                personSalesData.persons.forEach(p => {{
                    const opt = document.createElement('option');
                    opt.value = p;
                    opt.textContent = p;
                    personSelect.appendChild(opt);
                }});
            }}
        }}

        // 事業所選択で担当者を絞り込み
        function filterPersonByBranch() {{
            const branch = document.getElementById('personBranchFilter').value;
            const personSelect = document.getElementById('personFilter');

            // 担当者リストをリセット
            personSelect.innerHTML = '<option value="">-- 選択してください --</option>';

            if (branch && personSalesData.person_branches) {{
                // 選択された事業所に属する担当者だけを表示
                personSalesData.persons?.forEach(p => {{
                    const branches = personSalesData.person_branches[p] || [];
                    if (branches.includes(branch)) {{
                        const opt = document.createElement('option');
                        opt.value = p;
                        opt.textContent = p;
                        personSelect.appendChild(opt);
                    }}
                }});
                // 事業所が選択されたら、その事業所の担当者全員を棒グラフで表示
                renderPersonChartByBranch(branch);
            }} else {{
                // 全担当者を表示
                personSalesData.persons?.forEach(p => {{
                    const opt = document.createElement('option');
                    opt.value = p;
                    opt.textContent = p;
                    personSelect.appendChild(opt);
                }});
                // メッセージを表示
                document.getElementById('personChartMessage').style.display = 'block';
                document.getElementById('personSalesChart').style.display = 'none';
                if (personSalesChart) {{ personSalesChart.destroy(); personSalesChart = null; }}
            }}
        }}

        // 事業所の担当者全員を棒グラフで表示 - 年度対応
        function renderPersonChartByBranch(branch) {{
            const months = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3];
            const labels = months.map(m => m + '月');
            const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];
            const datasets = [];
            let colorIdx = 0;

            // 選択された年度のデータを取得
            const yearData = personSalesData.data_by_year?.[currentMonthlySalesYear];
            if (!yearData) {{
                console.log('担当者年度データなし:', currentMonthlySalesYear);
                return;
            }}

            // 事業所に属する担当者を取得
            const personsInBranch = personSalesData.persons?.filter(p => {{
                const branches = personSalesData.person_branches?.[p] || [];
                return branches.includes(branch);
            }}) || [];

            personsInBranch.forEach(person => {{
                const data = yearData[person];
                if (data) {{
                    datasets.push({{
                        label: person,
                        data: months.map(m => data.current[m] || 0),
                        backgroundColor: colors[colorIdx % colors.length],
                        borderRadius: 4
                    }});
                    colorIdx++;
                }}
            }});

            document.getElementById('personChartMessage').style.display = 'none';
            document.getElementById('personSalesChart').style.display = 'block';

            const ctx = document.getElementById('personSalesChart').getContext('2d');
            if (personSalesChart) personSalesChart.destroy();

            personSalesChart = new Chart(ctx, {{
                type: 'bar',
                data: {{ labels, datasets }},
                options: {{
                    responsive: true,
                    plugins: {{
                        legend: {{ position: 'top' }},
                        title: {{ display: true, text: branch + ' - ' + currentMonthlySalesYear + '年度 担当者別月別売上' }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ callback: v => '¥' + Math.round(v / 10000).toLocaleString() + '万' }}
                        }}
                    }}
                }}
            }});
        }}

        // 特定担当者の棒グラフ描画 - 年度対応
        function renderPersonChart() {{
            const person = document.getElementById('personFilter').value;
            if (!person) {{
                // 事業所が選択されていればその担当者を表示
                const branch = document.getElementById('personBranchFilter').value;
                if (branch) {{
                    renderPersonChartByBranch(branch);
                }} else {{
                    document.getElementById('personChartMessage').style.display = 'block';
                    document.getElementById('personSalesChart').style.display = 'none';
                    if (personSalesChart) {{ personSalesChart.destroy(); personSalesChart = null; }}
                }}
                return;
            }}

            // 選択された年度のデータを取得
            const yearData = personSalesData.data_by_year?.[currentMonthlySalesYear];
            if (!yearData) {{
                console.log('担当者年度データなし:', currentMonthlySalesYear);
                return;
            }}

            const months = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3];
            const labels = months.map(m => m + '月');
            const data = yearData[person];
            if (!data) return;

            const datasets = [
                {{
                    label: currentMonthlySalesYear + '年度売上',
                    data: months.map(m => data.current[m] || 0),
                    backgroundColor: 'rgba(59, 130, 246, 0.8)',
                    borderRadius: 4
                }},
                {{
                    label: (currentMonthlySalesYear - 1) + '年度売上',
                    data: months.map(m => data.prev[m] || 0),
                    backgroundColor: 'rgba(156, 163, 175, 0.6)',
                    borderRadius: 4
                }}
            ];

            document.getElementById('personChartMessage').style.display = 'none';
            document.getElementById('personSalesChart').style.display = 'block';

            const ctx = document.getElementById('personSalesChart').getContext('2d');
            if (personSalesChart) personSalesChart.destroy();

            personSalesChart = new Chart(ctx, {{
                type: 'bar',
                data: {{ labels, datasets }},
                options: {{
                    responsive: true,
                    plugins: {{
                        legend: {{ position: 'top' }},
                        title: {{ display: true, text: person + ' - ' + currentMonthlySalesYear + '年度 月別売上推移' }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ callback: v => '¥' + Math.round(v / 10000).toLocaleString() + '万' }}
                        }}
                    }}
                }}
            }});
        }}

        // 詳細タブ切り替え
        function switchDetailTab(tab) {{
            document.querySelectorAll('.detail-panel').forEach(p => p.style.display = 'none');
            document.querySelectorAll('.detail-tab').forEach(t => {{
                t.style.color = '#666';
                t.style.borderBottomColor = 'transparent';
            }});

            if (tab === 'memberRate') {{
                document.getElementById('memberRatePanel').style.display = 'block';
                document.getElementById('tabMemberRate').style.color = '#3b82f6';
                document.getElementById('tabMemberRate').style.borderBottomColor = '#3b82f6';
            }} else {{
                document.getElementById('salesPanel').style.display = 'block';
                document.getElementById('tabSales').style.color = '#3b82f6';
                document.getElementById('tabSales').style.borderBottomColor = '#3b82f6';
            }}
        }}

        // 会員率フィルター（連動フィルタリング）: 写真館→属性→学校名
        document.getElementById('filterStudio').addEventListener('change', () => updateMemberRateFilters('studio'));
        document.getElementById('filterAttribute').addEventListener('change', () => updateMemberRateFilters('attribute'));

        function updateMemberRateFilters(changedFilter) {{
            const studioSelect = document.getElementById('filterStudio');
            const attrSelect = document.getElementById('filterAttribute');
            const schoolSelect = document.getElementById('filterSchool');

            const currentStudio = studioSelect.value;
            const currentAttr = attrSelect.value;

            // 現在の条件でデータをフィルタリング
            let filtered = schoolsData;
            if (currentStudio) filtered = filtered.filter(s => s.studio === currentStudio);
            if (currentAttr) filtered = filtered.filter(s => s.attribute === currentAttr);

            // 写真館が変更された場合、属性の選択肢を更新
            if (changedFilter === 'studio') {{
                const availableAttrs = [...new Set(filtered.map(s => s.attribute).filter(Boolean))].sort();
                const prevAttr = currentAttr;
                attrSelect.innerHTML = '<option value="">-- 全て --</option>';
                availableAttrs.forEach(attr => {{
                    const opt = document.createElement('option');
                    opt.value = attr;
                    opt.textContent = attr;
                    if (attr === prevAttr) opt.selected = true;
                    attrSelect.appendChild(opt);
                }});
                // 選択していた属性がなくなった場合はリセット
                if (prevAttr && !availableAttrs.includes(prevAttr)) {{
                    filtered = schoolsData.filter(s => !currentStudio || s.studio === currentStudio);
                }}
            }}

            // 属性が変更された場合、写真館の選択肢を更新
            if (changedFilter === 'attribute') {{
                const availableStudios = [...new Set(filtered.map(s => s.studio).filter(Boolean))].sort();
                const prevStudio = currentStudio;
                studioSelect.innerHTML = '<option value="">-- 全て --</option>';
                availableStudios.forEach(studio => {{
                    const opt = document.createElement('option');
                    opt.value = studio;
                    opt.textContent = studio;
                    if (studio === prevStudio) opt.selected = true;
                    studioSelect.appendChild(opt);
                }});
                // 選択していた写真館がなくなった場合はリセット
                if (prevStudio && !availableStudios.includes(prevStudio)) {{
                    filtered = schoolsData.filter(s => !currentAttr || s.attribute === currentAttr);
                }}
            }}

            // 再度最終的なフィルタリング
            const finalStudio = studioSelect.value;
            const finalAttr = attrSelect.value;
            filtered = schoolsData;
            if (finalStudio) filtered = filtered.filter(s => s.studio === finalStudio);
            if (finalAttr) filtered = filtered.filter(s => s.attribute === finalAttr);

            // 学校プルダウンを更新
            schoolSelect.innerHTML = '<option value="">-- 写真館/属性で絞り込み --</option>';
            filtered.forEach(s => {{
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.name;
                schoolSelect.appendChild(opt);
            }});
        }}

        function resetMemberRateFilters() {{
            // 写真館プルダウンを初期状態に復元
            const studioSelect = document.getElementById('filterStudio');
            studioSelect.innerHTML = '<option value="">-- 全て --</option>';
            allStudios.forEach(studio => {{
                const opt = document.createElement('option');
                opt.value = studio;
                opt.textContent = studio;
                studioSelect.appendChild(opt);
            }});

            // 属性プルダウンを初期状態に復元
            const attrSelect = document.getElementById('filterAttribute');
            attrSelect.innerHTML = '<option value="">-- 全て --</option>';
            allAttributes.forEach(attr => {{
                const opt = document.createElement('option');
                opt.value = attr;
                opt.textContent = attr;
                attrSelect.appendChild(opt);
            }});

            document.getElementById('filterSchool').innerHTML = '<option value="">-- 写真館/属性で絞り込み --</option>';
            document.getElementById('gradeAll').checked = true;
        }}

        function searchMemberRate() {{
            const attr = document.getElementById('filterAttribute').value;
            const schoolId = document.getElementById('filterSchool').value;
            const gradeMode = document.querySelector('input[name="gradeMode"]:checked').value;
            const selectedYear = currentDetailYear;  // 年度選択を使用

            if (schoolId) {{
                // 年度を含めたキーで検索
                const key = gradeMode === 'each' ? `school_${{schoolId}}_grade_${{selectedYear}}` : `school_${{schoolId}}_all_${{selectedYear}}`;
                currentMemberRateData = allSchoolData[key];
                document.getElementById('gradeOptionGroup').style.display = 'flex';
            }} else if (attr) {{
                // 年度を含めたキーで検索
                currentMemberRateData = allAttributeData[`attr_${{attr}}_${{selectedYear}}`];
                document.getElementById('gradeOptionGroup').style.display = 'none';
            }} else {{
                alert('属性または学校を選択してください');
                return;
            }}

            if (currentMemberRateData) renderMemberRateChart();
            else alert(selectedYear + '年度のデータが見つかりませんでした');
        }}

        // 日付データを月別に変換（同じ月は最新データを使用）
        function convertToMonthlyData(dates, rates) {{
            const monthlyMap = {{}};
            // 年度の月順序（4月〜3月）
            const fiscalMonthOrder = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3];

            dates.forEach((dateStr, i) => {{
                const date = new Date(dateStr);
                const month = date.getMonth() + 1; // 1-12
                const monthKey = month + '月';

                // 同じ月のデータは後のもの（最新）で上書き
                if (!monthlyMap[month] || new Date(dateStr) > new Date(monthlyMap[month].date)) {{
                    monthlyMap[month] = {{ date: dateStr, rate: rates[i], month: month }};
                }}
            }});

            // 年度順（4月〜3月）にソート
            const result = {{ months: [], rates: [] }};
            fiscalMonthOrder.forEach(m => {{
                if (monthlyMap[m]) {{
                    result.months.push(m + '月');
                    result.rates.push(monthlyMap[m].rate);
                }}
            }});

            return result;
        }}

        function renderMemberRateChart() {{
            if (!currentMemberRateData) return;

            const fiscalYear = currentMemberRateData.fiscal_year || currentDetailYear;
            const baseName = currentMemberRateData.school_name || `${{currentMemberRateData.attribute}}（${{currentMemberRateData.school_count}}校平均）`;
            const title = `${{baseName}} - ${{fiscalYear}}年度`;
            document.getElementById('memberRateChartTitle').textContent = title;
            document.getElementById('memberRateChartInfo').textContent = currentMemberRateData.attribute ? `属性: ${{currentMemberRateData.attribute}}` : '';

            const datasets = [];
            // X軸のラベル（4月〜3月）
            const allMonths = ['4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月', '1月', '2月', '3月'];

            if (currentMemberRateData.by_grade && typeof currentMemberRateData.current_year === 'object' && !Array.isArray(currentMemberRateData.current_year)) {{
                // 学年別表示
                const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];
                let colorIdx = 0;

                for (const [grade, data] of Object.entries(currentMemberRateData.current_year)) {{
                    if (data.dates?.length > 0) {{
                        const monthly = convertToMonthlyData(data.dates, data.rates);
                        datasets.push({{
                            label: `${{grade}}`,
                            data: monthly.months.map((m, i) => ({{ x: m, y: monthly.rates[i] }})),
                            borderColor: colors[colorIdx % colors.length],
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: 4
                        }});
                    }}
                    colorIdx++;
                }}
            }} else {{
                // 全学年まとめて表示
                const current = currentMemberRateData.current_year;
                if (current?.dates?.length > 0) {{
                    const monthly = convertToMonthlyData(current.dates, current.rates);
                    datasets.push({{
                        label: fiscalYear + '年度',
                        data: monthly.months.map((m, i) => ({{ x: m, y: monthly.rates[i] }})),
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 5
                    }});
                }}
            }}

            const ctx = document.getElementById('memberRateChart').getContext('2d');
            if (memberRateChart) memberRateChart.destroy();

            // データの最大値を取得してY軸の最大値を動的に設定
            let maxRate = 100;
            datasets.forEach(ds => {{
                ds.data.forEach(point => {{
                    if (point.y > maxRate) maxRate = point.y;
                }});
            }});
            // 最大値に10%の余裕を持たせ、10刻みに切り上げ
            const yMax = Math.ceil((maxRate * 1.1) / 10) * 10;

            memberRateChart = new Chart(ctx, {{
                type: 'line',
                data: {{ labels: allMonths, datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: true, position: 'top' }},
                        tooltip: {{ callbacks: {{ label: ctx => `${{ctx.dataset.label}}: ${{ctx.parsed.y}}%` }} }}
                    }},
                    scales: {{
                        x: {{ type: 'category', title: {{ display: true, text: '月' }} }},
                        y: {{ min: 0, max: yMax, title: {{ display: true, text: '会員率 (%)' }}, ticks: {{ callback: v => v + '%' }} }}
                    }}
                }}
            }});
        }}

        function exportMemberRateCSV() {{
            if (!currentMemberRateData) {{ alert('先にデータを検索してください'); return; }}
            let csvContent = '';
            const title = currentMemberRateData.school_name || currentMemberRateData.attribute;

            if (currentMemberRateData.by_grade && typeof currentMemberRateData.current_year === 'object') {{
                const grades = Object.keys(currentMemberRateData.current_year);
                csvContent += '日付,年度,' + grades.join(',') + '\\n';
                const firstGrade = grades[0];
                if (currentMemberRateData.current_year[firstGrade]?.dates) {{
                    currentMemberRateData.current_year[firstGrade].dates.forEach((date, i) => {{
                        let row = `${{date}},今年度`;
                        grades.forEach(g => row += ',' + (currentMemberRateData.current_year[g]?.rates?.[i] ?? ''));
                        csvContent += row + '\\n';
                    }});
                }}
            }} else {{
                csvContent += '日付,年度,会員率\\n';
                const current = currentMemberRateData.current_year;
                if (current?.dates) current.dates.forEach((date, i) => csvContent += `${{date}},今年度,${{current.rates[i]}}\\n`);
                const prev = currentMemberRateData.prev_year;
                if (prev?.dates) prev.dates.forEach((date, i) => csvContent += `${{date}},前年度,${{prev.rates[i]}}\\n`);
            }}

            const blob = new Blob(['\\uFEFF' + csvContent], {{ type: 'text/csv;charset=utf-8;' }});
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `会員率推移_${{title}}_${{new Date().toISOString().slice(0, 10)}}.csv`;
            link.click();
        }}

        document.querySelectorAll('input[name="gradeMode"]').forEach(el => el.addEventListener('change', searchMemberRate));

        // 売上推移フィルター（連動フィルタリング）: 事業所→担当者→写真館→学校名
        document.getElementById('salesFilterBranch').addEventListener('change', () => updateSalesFilters('branch'));
        document.getElementById('salesFilterPerson').addEventListener('change', () => updateSalesFilters('person'));
        document.getElementById('salesFilterStudio').addEventListener('change', () => updateSalesFilters('studio'));

        function updateSalesFilters(changedFilter) {{
            const branchSelect = document.getElementById('salesFilterBranch');
            const personSelect = document.getElementById('salesFilterPerson');
            const studioSelect = document.getElementById('salesFilterStudio');
            const schoolSelect = document.getElementById('salesFilterSchool');

            const currentBranch = branchSelect.value;
            const currentPerson = personSelect.value;
            const currentStudio = studioSelect.value;

            // 現在の条件でデータをフィルタリング
            let filtered = salesSchoolsData;
            if (currentBranch) filtered = filtered.filter(s => s.branch === currentBranch);
            if (currentPerson) filtered = filtered.filter(s => s.person === currentPerson);
            if (currentStudio) filtered = filtered.filter(s => s.studio === currentStudio);

            // 事業所が変更された場合
            if (changedFilter === 'branch') {{
                // 担当者の選択肢を更新
                const availablePersons = [...new Set(filtered.map(s => s.person).filter(Boolean))].sort();
                const prevPerson = currentPerson;
                personSelect.innerHTML = '<option value="">-- 全て --</option>';
                availablePersons.forEach(person => {{
                    const opt = document.createElement('option');
                    opt.value = person;
                    opt.textContent = person;
                    if (person === prevPerson) opt.selected = true;
                    personSelect.appendChild(opt);
                }});

                // 写真館の選択肢を更新
                const availableStudios = [...new Set(filtered.map(s => s.studio).filter(Boolean))].sort();
                const prevStudio = currentStudio;
                studioSelect.innerHTML = '<option value="">-- 全て --</option>';
                availableStudios.forEach(studio => {{
                    const opt = document.createElement('option');
                    opt.value = studio;
                    opt.textContent = studio;
                    if (studio === prevStudio) opt.selected = true;
                    studioSelect.appendChild(opt);
                }});
            }}

            // 担当者が変更された場合
            if (changedFilter === 'person') {{
                // 事業所の選択肢を更新
                const availableBranches = [...new Set(filtered.map(s => s.branch).filter(Boolean))].sort();
                const prevBranch = currentBranch;
                branchSelect.innerHTML = '<option value="">-- 全て --</option>';
                availableBranches.forEach(branch => {{
                    const opt = document.createElement('option');
                    opt.value = branch;
                    opt.textContent = branch;
                    if (branch === prevBranch) opt.selected = true;
                    branchSelect.appendChild(opt);
                }});

                // 写真館の選択肢を更新
                const availableStudios = [...new Set(filtered.map(s => s.studio).filter(Boolean))].sort();
                const prevStudio = currentStudio;
                studioSelect.innerHTML = '<option value="">-- 全て --</option>';
                availableStudios.forEach(studio => {{
                    const opt = document.createElement('option');
                    opt.value = studio;
                    opt.textContent = studio;
                    if (studio === prevStudio) opt.selected = true;
                    studioSelect.appendChild(opt);
                }});
            }}

            // 写真館が変更された場合
            if (changedFilter === 'studio') {{
                // 事業所の選択肢を更新
                const availableBranches = [...new Set(filtered.map(s => s.branch).filter(Boolean))].sort();
                const prevBranch = currentBranch;
                branchSelect.innerHTML = '<option value="">-- 全て --</option>';
                availableBranches.forEach(branch => {{
                    const opt = document.createElement('option');
                    opt.value = branch;
                    opt.textContent = branch;
                    if (branch === prevBranch) opt.selected = true;
                    branchSelect.appendChild(opt);
                }});

                // 担当者の選択肢を更新
                const availablePersons = [...new Set(filtered.map(s => s.person).filter(Boolean))].sort();
                const prevPerson = currentPerson;
                personSelect.innerHTML = '<option value="">-- 全て --</option>';
                availablePersons.forEach(person => {{
                    const opt = document.createElement('option');
                    opt.value = person;
                    opt.textContent = person;
                    if (person === prevPerson) opt.selected = true;
                    personSelect.appendChild(opt);
                }});
            }}

            // 再度最終的なフィルタリング
            const finalBranch = branchSelect.value;
            const finalPerson = personSelect.value;
            const finalStudio = studioSelect.value;
            filtered = salesSchoolsData;
            if (finalBranch) filtered = filtered.filter(s => s.branch === finalBranch);
            if (finalPerson) filtered = filtered.filter(s => s.person === finalPerson);
            if (finalStudio) filtered = filtered.filter(s => s.studio === finalStudio);

            // 学校プルダウンを更新
            schoolSelect.innerHTML = '<option value="">-- 絞り込みで選択 --</option>';
            filtered.forEach(s => {{
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.name;
                schoolSelect.appendChild(opt);
            }});
        }}

        function resetSalesFilters() {{
            // 事業所プルダウンを初期状態に復元
            const branchSelect = document.getElementById('salesFilterBranch');
            branchSelect.innerHTML = '<option value="">-- 全て --</option>';
            allBranches.forEach(branch => {{
                const opt = document.createElement('option');
                opt.value = branch;
                opt.textContent = branch;
                branchSelect.appendChild(opt);
            }});

            // 担当者プルダウンを初期状態に復元
            const personSelect = document.getElementById('salesFilterPerson');
            personSelect.innerHTML = '<option value="">-- 全て --</option>';
            allPersons.forEach(person => {{
                const opt = document.createElement('option');
                opt.value = person;
                opt.textContent = person;
                personSelect.appendChild(opt);
            }});

            // 写真館プルダウンを初期状態に復元
            const studioSelect = document.getElementById('salesFilterStudio');
            studioSelect.innerHTML = '<option value="">-- 全て --</option>';
            allSalesStudios.forEach(studio => {{
                const opt = document.createElement('option');
                opt.value = studio;
                opt.textContent = studio;
                studioSelect.appendChild(opt);
            }});

            document.getElementById('salesFilterSchool').innerHTML = '<option value="">-- 絞り込みで選択 --</option>';
            document.getElementById('showSalesPrevYear').checked = true;
            document.getElementById('salesChartTitle').textContent = '写真館または学校を選択してください';
            document.getElementById('salesChartInfo').textContent = '';
            document.getElementById('eventBreakdownSection').style.display = 'none';
            if (salesTrendChart) {{ salesTrendChart.destroy(); salesTrendChart = null; }}
            currentSalesData = null;
        }}

        function searchSalesTrend() {{
            const studio = document.getElementById('salesFilterStudio').value;
            const schoolId = document.getElementById('salesFilterSchool').value;
            const selectedYear = document.getElementById('salesYearSelect').value;

            if (schoolId) {{
                // 年度別キーでデータを取得
                currentSalesData = allSalesSchoolData[`school_${{schoolId}}_${{selectedYear}}`];
                currentSchoolId = schoolId;
                showEventBreakdown(schoolId);
            }} else if (studio) {{
                currentSalesData = allSalesStudioData[`studio_${{studio}}_${{selectedYear}}`];
                currentSchoolId = null;
                document.getElementById('eventBreakdownSection').style.display = 'none';
            }} else {{
                alert('写真館または学校を選択してください');
                return;
            }}

            if (currentSalesData) renderSalesTrendChart();
            else alert('選択した年度のデータが見つかりませんでした');
        }}

        // イベントソート更新
        function updateEventSort() {{
            currentEventSortType = document.getElementById('eventSortType').value;
            if (currentSchoolId) showEventBreakdown(currentSchoolId);
        }}

        function showEventBreakdown(schoolId) {{
            const eventData = allEventSalesData[`school_${{schoolId}}`];
            const container = document.getElementById('eventBreakdownContainer');
            const section = document.getElementById('eventBreakdownSection');

            if (!eventData?.events || (!eventData.events.current_year?.length && !eventData.events.prev_year?.length)) {{
                section.style.display = 'none';
                return;
            }}

            section.style.display = 'block';
            container.innerHTML = '';

            // ソート関数
            let sortFn;
            switch (currentEventSortType) {{
                case 'sales_asc':
                    sortFn = (a, b) => a.sales - b.sales;
                    break;
                case 'sales_desc':
                    sortFn = (a, b) => b.sales - a.sales;
                    break;
                case 'date_asc':
                    sortFn = (a, b) => (a.start_date || '').localeCompare(b.start_date || '');
                    break;
                case 'date_desc':
                    sortFn = (a, b) => (b.start_date || '').localeCompare(a.start_date || '');
                    break;
                default:
                    sortFn = (a, b) => b.sales - a.sales;
            }}

            // 今年度
            if (eventData.events.current_year?.length > 0) {{
                const sorted = [...eventData.events.current_year].sort(sortFn);
                const div = document.createElement('div');
                div.innerHTML = `
                    <h5 style="font-size: 13px; color: #3b82f6; margin-bottom: 8px;">今年度</h5>
                    <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
                        <thead><tr style="background: #f8fafc;">
                            <th style="text-align: left; padding: 8px; border-bottom: 1px solid #e2e8f0;">イベント名</th>
                            <th style="text-align: center; padding: 8px; border-bottom: 1px solid #e2e8f0;">公開開始日</th>
                            <th style="text-align: right; padding: 8px; border-bottom: 1px solid #e2e8f0;">売上</th>
                        </tr></thead>
                        <tbody>${{sorted.map(e => `
                            <tr>
                                <td style="padding: 6px 8px; border-bottom: 1px solid #f0f0f0;">${{e.event_name.length > 25 ? e.event_name.substring(0, 25) + '...' : e.event_name}}</td>
                                <td style="text-align: center; padding: 6px 8px; border-bottom: 1px solid #f0f0f0;">${{e.start_date || '-'}}</td>
                                <td style="text-align: right; padding: 6px 8px; border-bottom: 1px solid #f0f0f0;">¥${{e.sales.toLocaleString()}}</td>
                            </tr>
                        `).join('')}}</tbody>
                        <tfoot><tr style="font-weight: bold; background: #f8fafc;">
                            <td colspan="2" style="padding: 8px;">合計</td>
                            <td style="text-align: right; padding: 8px;">¥${{sorted.reduce((sum, e) => sum + e.sales, 0).toLocaleString()}}</td>
                        </tr></tfoot>
                    </table>`;
                container.appendChild(div);
            }}

            // 前年度
            if (eventData.events.prev_year?.length > 0) {{
                const sorted = [...eventData.events.prev_year].sort(sortFn);
                const div = document.createElement('div');
                div.innerHTML = `
                    <h5 style="font-size: 13px; color: #888; margin-bottom: 8px;">前年度</h5>
                    <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
                        <thead><tr style="background: #f8fafc;">
                            <th style="text-align: left; padding: 8px; border-bottom: 1px solid #e2e8f0;">イベント名</th>
                            <th style="text-align: center; padding: 8px; border-bottom: 1px solid #e2e8f0;">公開開始日</th>
                            <th style="text-align: right; padding: 8px; border-bottom: 1px solid #e2e8f0;">売上</th>
                        </tr></thead>
                        <tbody>${{sorted.map(e => `
                            <tr>
                                <td style="padding: 6px 8px; border-bottom: 1px solid #f0f0f0;">${{e.event_name.length > 25 ? e.event_name.substring(0, 25) + '...' : e.event_name}}</td>
                                <td style="text-align: center; padding: 6px 8px; border-bottom: 1px solid #f0f0f0;">${{e.start_date || '-'}}</td>
                                <td style="text-align: right; padding: 6px 8px; border-bottom: 1px solid #f0f0f0;">¥${{e.sales.toLocaleString()}}</td>
                            </tr>
                        `).join('')}}</tbody>
                        <tfoot><tr style="font-weight: bold; background: #f8fafc;">
                            <td colspan="2" style="padding: 8px;">合計</td>
                            <td style="text-align: right; padding: 8px;">¥${{sorted.reduce((sum, e) => sum + e.sales, 0).toLocaleString()}}</td>
                        </tr></tfoot>
                    </table>`;
                container.appendChild(div);
            }}
        }}

        function renderSalesTrendChart() {{
            if (!currentSalesData) return;

            const showPrevYear = document.getElementById('showSalesPrevYear').checked;
            const selectedYear = parseInt(document.getElementById('salesYearSelect').value);
            let title = currentSalesData.school_name || `${{currentSalesData.studio_name}}（${{currentSalesData.school_count}}校）`;
            document.getElementById('salesChartTitle').textContent = `${{title}} - ${{selectedYear}}年度`;

            const yoy = currentSalesData.yoy ? (currentSalesData.yoy * 100).toFixed(1) : '-';
            document.getElementById('salesChartInfo').textContent = `${{selectedYear}}年度累計: ¥${{currentSalesData.current_total?.toLocaleString() || 0}} / 前年比: ${{yoy}}%`;

            // 固定の月順序（年度順：4月〜3月）
            const monthOrder = ['4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月', '1月', '2月', '3月'];

            // データを月順序にマッピングする関数
            function mapDataToMonthOrder(dates, sales) {{
                const dataMap = {{}};
                dates.forEach((d, i) => {{ dataMap[d] = sales[i]; }});
                return monthOrder.map(m => dataMap[m] ?? null);
            }}

            const datasets = [];
            const current = currentSalesData.current_year;
            if (current?.dates?.length > 0) {{
                datasets.push({{
                    label: selectedYear + '年度',
                    data: mapDataToMonthOrder(current.dates, current.sales),
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 5,
                    spanGaps: true
                }});
            }}

            if (showPrevYear && currentSalesData.prev_year?.dates?.length > 0) {{
                const prev = currentSalesData.prev_year;
                datasets.push({{
                    label: (selectedYear - 1) + '年度',
                    data: mapDataToMonthOrder(prev.dates, prev.sales),
                    borderColor: '#888',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.3,
                    pointRadius: 3,
                    spanGaps: true
                }});
            }}

            const ctx = document.getElementById('salesTrendChart').getContext('2d');
            if (salesTrendChart) salesTrendChart.destroy();

            salesTrendChart = new Chart(ctx, {{
                type: 'line',
                data: {{ labels: monthOrder, datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: true, position: 'top' }},
                        tooltip: {{ callbacks: {{ label: ctx => `${{ctx.dataset.label}}: ¥${{ctx.parsed.y?.toLocaleString() || 0}}` }} }}
                    }},
                    scales: {{
                        x: {{ type: 'category', title: {{ display: true, text: '日付' }} }},
                        y: {{ beginAtZero: true, title: {{ display: true, text: '売上 (円)' }}, ticks: {{ callback: v => '¥' + (v / 10000).toFixed(0) + '万' }} }}
                    }}
                }}
            }});
        }}

        function exportSalesCSV() {{
            if (!currentSalesData) {{ alert('先にデータを検索してください'); return; }}
            let csvContent = '日付,年度,売上\\n';
            const title = currentSalesData.school_name || currentSalesData.studio_name;

            if (currentSalesData.current_year?.dates) {{
                currentSalesData.current_year.dates.forEach((date, i) => csvContent += `${{date}},今年度,${{currentSalesData.current_year.sales[i]}}\\n`);
            }}
            if (currentSalesData.prev_year?.dates) {{
                currentSalesData.prev_year.dates.forEach((date, i) => csvContent += `${{date}},前年度,${{currentSalesData.prev_year.sales[i]}}\\n`);
            }}

            const blob = new Blob(['\\uFEFF' + csvContent], {{ type: 'text/csv;charset=utf-8;' }});
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `売上推移_${{title}}_${{new Date().toISOString().slice(0, 10)}}.csv`;
            link.click();
        }}

        document.getElementById('showSalesPrevYear').addEventListener('change', renderSalesTrendChart);

        // アラートタブ
        function showAlert(type) {{
            document.querySelectorAll('.alert-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.alert-tab').forEach(el => el.classList.remove('active'));
            document.getElementById('alert-' + type).classList.add('active');
            document.getElementById('tab-' + type).classList.add('active');
        }}

        // アラートテーブル共通描画関数
        function renderAlertTable(type, columns, rowRenderer) {{
            const state = alertState[type];
            const data = state.data || [];

            // ソート済みデータを生成（元のデータは保持）
            const sortedData = [...data].sort((a, b) => {{
                let aVal = a[state.sortKey];
                let bVal = b[state.sortKey];
                if (typeof aVal === 'string') aVal = aVal || '';
                if (typeof bVal === 'string') bVal = bVal || '';
                if (state.sortDir === 'asc') return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
                return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
            }});

            const totalPages = Math.ceil(sortedData.length / PAGE_SIZE);
            const startIdx = (state.page - 1) * PAGE_SIZE;
            const displayData = sortedData.slice(startIdx, startIdx + PAGE_SIZE);

            // テーブル生成
            let html = '<table class="alert-table"><thead><tr>';
            columns.forEach(col => {{
                const sortClass = state.sortKey === col.key ? (state.sortDir === 'asc' ? 'asc' : 'desc') : '';
                html += `<th class="sortable ${{sortClass}}" onclick="sortAlertTable('${{type}}', '${{col.key}}')">${{col.label}}</th>`;
            }});
            html += '</tr></thead><tbody>';

            if (displayData.length === 0) {{
                html += `<tr><td colspan="${{columns.length}}" style="text-align:center;color:#888;padding:40px;">データはありません</td></tr>`;
            }} else {{
                displayData.forEach(item => {{ html += rowRenderer(item); }});
            }}
            html += '</tbody></table>';

            document.getElementById(type + '-table-container').innerHTML = html;

            // ページネーション生成
            let paginationHtml = '';
            if (totalPages > 1) {{
                paginationHtml += `<button onclick="changeAlertPage('${{type}}', 1)" ${{state.page === 1 ? 'disabled' : ''}}>&laquo;</button>`;
                paginationHtml += `<button onclick="changeAlertPage('${{type}}', ${{state.page - 1}})" ${{state.page === 1 ? 'disabled' : ''}}>&lt;</button>`;

                // ページ番号
                let startPage = Math.max(1, state.page - 2);
                let endPage = Math.min(totalPages, state.page + 2);
                for (let i = startPage; i <= endPage; i++) {{
                    paginationHtml += `<button class="${{i === state.page ? 'active' : ''}}" onclick="changeAlertPage('${{type}}', ${{i}})">${{i}}</button>`;
                }}

                paginationHtml += `<button onclick="changeAlertPage('${{type}}', ${{state.page + 1}})" ${{state.page === totalPages ? 'disabled' : ''}}>&gt;</button>`;
                paginationHtml += `<button onclick="changeAlertPage('${{type}}', ${{totalPages}})" ${{state.page === totalPages ? 'disabled' : ''}}>&raquo;</button>`;
                paginationHtml += `<span class="page-info">${{sortedData.length}}件中 ${{startIdx + 1}}-${{Math.min(startIdx + PAGE_SIZE, sortedData.length)}}件</span>`;
            }} else if (sortedData.length > 0) {{
                paginationHtml = `<span class="page-info">${{sortedData.length}}件</span>`;
            }}
            document.getElementById(type + '-pagination').innerHTML = paginationHtml;
        }}

        function sortAlertTable(type, key) {{
            const state = alertState[type];
            if (state.sortKey === key) {{
                state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
            }} else {{
                state.sortKey = key;
                state.sortDir = 'asc';
            }}
            state.page = 1;
            renderAlertByType(type);
        }}

        function changeAlertPage(type, page) {{
            alertState[type].page = page;
            renderAlertByType(type);
        }}

        // 各アラートタイプ別描画
        function renderAlertByType(type) {{
            switch(type) {{
                case 'no_events':
                    renderAlertTable('no_events', [
                        {{key: 'school_name', label: '学校名'}},
                        {{key: 'attribute', label: '属性'}},
                        {{key: 'region', label: '事業所'}},
                        {{key: 'studio_name', label: '写真館'}},
                        {{key: 'prev_year_events', label: '前年度イベント数'}},
                        {{key: 'prev_year_sales', label: '前年度売上'}}
                    ], item => `<tr><td>${{item.school_name}}</td><td>${{item.attribute}}</td><td>${{item.region || '-'}}</td><td>${{item.studio_name}}</td><td>${{item.prev_year_events}}件</td><td>¥${{item.prev_year_sales.toLocaleString()}}</td></tr>`);
                    break;
                case 'new_event_low':
                    renderAlertTable('new_event_low', [
                        {{key: 'school_name', label: '学校名'}},
                        {{key: 'attribute', label: '属性'}},
                        {{key: 'studio_name', label: '事業所'}},
                        {{key: 'event_name', label: 'イベント名'}},
                        {{key: 'start_date', label: '開始日'}},
                        {{key: 'member_rate', label: '会員率'}},
                        {{key: 'total_sales', label: '売上'}}
                    ], item => `<tr><td>${{item.school_name}}</td><td>${{item.attribute || '-'}}</td><td>${{item.studio_name || '-'}}</td><td>${{(item.event_name || '').substring(0,30)}}...</td><td>${{item.start_date || '-'}}</td><td>${{(item.member_rate*100).toFixed(1)}}%</td><td>¥${{(item.total_sales || 0).toLocaleString()}}</td></tr>`);
                    break;
                case 'decline':
                    renderAlertTable('decline', [
                        {{key: 'school_name', label: '学校名'}},
                        {{key: 'attribute', label: '属性'}},
                        {{key: 'region', label: '事業所'}},
                        {{key: 'member_rate', label: '会員率'}},
                        {{key: 'current_sales', label: '今年度売上'}},
                        {{key: 'prev_sales', label: '前年度売上'}},
                        {{key: 'sales_change', label: '売上変化'}}
                    ], item => `<tr><td>${{item.school_name}}</td><td>${{item.attribute}}</td><td>${{item.region || '-'}}</td><td>${{(item.member_rate*100).toFixed(1)}}%</td><td>¥${{item.current_sales.toLocaleString()}}</td><td>¥${{item.prev_sales.toLocaleString()}}</td><td class="trend-down">${{(item.sales_change*100).toFixed(1)}}%</td></tr>`);
                    break;
                case 'new_schools':
                    renderAlertTable('new_schools', [
                        {{key: 'school_name', label: '学校名'}},
                        {{key: 'attribute', label: '属性'}},
                        {{key: 'region', label: '事業所'}},
                        {{key: 'studio_name', label: '写真館'}},
                        {{key: 'event_count', label: 'イベント数'}},
                        {{key: 'first_event_date', label: '初回開始日'}},
                        {{key: 'total_sales', label: '売上'}}
                    ], item => `<tr><td>${{item.school_name}}</td><td>${{item.attribute}}</td><td>${{item.region || '-'}}</td><td>${{item.studio_name}}</td><td>${{item.event_count}}件</td><td>${{item.first_event_date || '-'}}</td><td>¥${{item.total_sales.toLocaleString()}}</td></tr>`);
                    break;
                case 'studio_decline':
                    renderAlertTable('studio_decline', [
                        {{key: 'studio_name', label: '写真館名'}},
                        {{key: 'region', label: '事業所'}},
                        {{key: 'current_sales', label: '今年度売上'}},
                        {{key: 'prev_sales', label: '前年度売上'}},
                        {{key: 'change_rate', label: '変化率'}},
                        {{key: 'current_schools', label: '担当校数'}}
                    ], item => `<tr><td>${{item.studio_name}}</td><td>${{item.region || '-'}}</td><td>¥${{item.current_sales.toLocaleString()}}</td><td>¥${{item.prev_sales.toLocaleString()}}</td><td class="trend-down">${{(item.change_rate*100).toFixed(1)}}%</td><td>${{item.current_schools}}校</td></tr>`);
                    break;
                case 'rapid_growth':
                    renderAlertTable('rapid_growth', [
                        {{key: 'school_name', label: '学校名'}},
                        {{key: 'attribute', label: '属性'}},
                        {{key: 'region', label: '事業所'}},
                        {{key: 'studio_name', label: '写真館'}},
                        {{key: 'current_sales', label: '今年度売上'}},
                        {{key: 'prev_sales', label: '前年度売上'}},
                        {{key: 'growth_rate', label: '成長率'}}
                    ], item => `<tr><td>${{item.school_name}}</td><td>${{item.attribute}}</td><td>${{item.region || '-'}}</td><td>${{item.studio_name}}</td><td>¥${{item.current_sales.toLocaleString()}}</td><td>¥${{item.prev_sales.toLocaleString()}}</td><td class="trend-up">+${{(item.growth_rate*100).toFixed(1)}}%</td></tr>`);
                    break;
                case 'member_rate_trend':
                    renderAlertTable('member_rate_trend', [
                        {{key: 'school_name', label: '学校名'}},
                        {{key: 'attribute', label: '属性'}},
                        {{key: 'studio_name', label: '写真館'}},
                        {{key: 'branch_name', label: '事業所'}},
                        {{key: 'current_rate', label: '今年度会員率'}},
                        {{key: 'prev_rate', label: '前年度会員率'}},
                        {{key: 'improvement', label: '改善幅'}}
                    ], item => `<tr><td>${{item.school_name}}</td><td>${{item.attribute || '-'}}</td><td>${{item.studio_name || '-'}}</td><td>${{item.branch_name || '-'}}</td><td>${{(item.current_rate*100).toFixed(1)}}%</td><td>${{(item.prev_rate*100).toFixed(1)}}%</td><td class="trend-up">+${{(item.improvement*100).toFixed(1)}}%</td></tr>`);
                    break;
                case 'unit_price':
                    renderAlertTable('unit_price', [
                        {{key: 'school_name', label: '学校名'}},
                        {{key: 'attribute', label: '属性'}},
                        {{key: 'studio_name', label: '写真館'}},
                        {{key: 'member_rate', label: '会員率'}},
                        {{key: 'total_sales', label: '売上'}},
                        {{key: 'total_members', label: '会員数'}},
                        {{key: 'unit_price', label: '単価'}},
                        {{key: 'attr_avg', label: '属性平均'}},
                        {{key: 'diff', label: '平均比'}}
                    ], item => `<tr><td>${{item.school_name}}</td><td>${{item.attribute || '-'}}</td><td>${{item.studio_name || '-'}}</td><td>${{(item.member_rate*100).toFixed(1)}}%</td><td>¥${{item.total_sales.toLocaleString()}}</td><td>${{item.total_members}}人</td><td>¥${{Math.round(item.unit_price).toLocaleString()}}</td><td>¥${{Math.round(item.attr_avg).toLocaleString()}}</td><td class="${{item.diff >= 0 ? 'trend-up' : 'trend-down'}}">${{item.diff >= 0 ? '+' : ''}}¥${{Math.round(item.diff).toLocaleString()}}</td></tr>`);
                    break;
            }}
        }}

        // 会員率・売上低下フィルタ
        function filterDeclineAlert() {{
            const memberRateThreshold = parseFloat(document.getElementById('decline-member-rate-filter').value);
            const salesFromValue = document.getElementById('decline-sales-from-filter').value;
            const salesToValue = document.getElementById('decline-sales-to-filter').value;

            // 範囲の下限と上限を設定（減少率なので負の値）
            const salesFrom = salesFromValue ? parseFloat(salesFromValue) : null;
            const salesTo = salesToValue ? parseFloat(salesToValue) : null;

            alertState.decline.data = alertData.decline.filter(item => {{
                // 会員率フィルタ
                const memberOk = item.member_rate < memberRateThreshold;

                // 売上減少率の範囲フィルタ
                let salesOk = true;
                if (salesFrom !== null && salesTo !== null) {{
                    // 両方指定: salesFrom(-0.1)からsalesTo(-0.3)の範囲
                    // 例: -0.1 ~ -0.3 は -0.3 <= sales_change <= -0.1
                    salesOk = item.sales_change <= salesFrom && item.sales_change >= salesTo;
                }} else if (salesFrom !== null) {{
                    // 下限のみ指定: salesFrom以上の減少
                    salesOk = item.sales_change <= salesFrom;
                }} else if (salesTo !== null) {{
                    // 上限のみ指定: salesTo以下の減少
                    salesOk = item.sales_change >= salesTo;
                }}
                // 両方未指定なら全件表示

                return memberOk && salesOk;
            }});
            alertState.decline.page = 1;
            renderAlertByType('decline');
        }}

        // 新規開始校フィルタ
        function filterNewSchoolsAlert() {{
            const targetYear = parseInt(document.getElementById('new_schools-year-filter').value);
            const targetMonth = document.getElementById('new_schools-month-filter').value;

            alertState.new_schools.data = alertData.new_schools.filter(item => {{
                // 年度フィルタ（first_event_dateから年度を判定）
                if (!item.first_event_date) return false;
                const date = new Date(item.first_event_date);
                const month = date.getMonth() + 1;
                const year = date.getFullYear();
                const fiscalYear = month >= 4 ? year : year - 1;
                if (fiscalYear !== targetYear) return false;

                // 月フィルタ
                if (targetMonth && month !== parseInt(targetMonth)) return false;
                return true;
            }});
            alertState.new_schools.page = 1;
            renderAlertByType('new_schools');
        }}

        // CSVダウンロード
        function downloadAlertCSV(type) {{
            const data = alertState[type].data;
            if (!data || data.length === 0) {{
                alert('ダウンロードするデータがありません。');
                return;
            }}

            // アラートタイプに応じたカラム定義
            const columnDefs = {{
                'no_events': [
                    {{key: 'school_name', label: '学校名'}},
                    {{key: 'attribute', label: '属性'}},
                    {{key: 'region', label: '事業所'}},
                    {{key: 'studio_name', label: '写真館'}},
                    {{key: 'prev_year_events', label: '前年度イベント数'}},
                    {{key: 'prev_year_sales', label: '前年度売上'}}
                ],
                'new_event_low': [
                    {{key: 'school_name', label: '学校名'}},
                    {{key: 'attribute', label: '属性'}},
                    {{key: 'studio_name', label: '事業所'}},
                    {{key: 'event_name', label: 'イベント名'}},
                    {{key: 'start_date', label: '開始日'}},
                    {{key: 'member_rate', label: '会員率'}},
                    {{key: 'total_sales', label: '売上'}}
                ],
                'decline': [
                    {{key: 'school_name', label: '学校名'}},
                    {{key: 'attribute', label: '属性'}},
                    {{key: 'region', label: '事業所'}},
                    {{key: 'member_rate', label: '会員率'}},
                    {{key: 'current_sales', label: '今年度売上'}},
                    {{key: 'prev_sales', label: '前年度売上'}},
                    {{key: 'sales_change', label: '売上変化'}}
                ],
                'new_schools': [
                    {{key: 'school_name', label: '学校名'}},
                    {{key: 'attribute', label: '属性'}},
                    {{key: 'region', label: '事業所'}},
                    {{key: 'studio_name', label: '写真館'}},
                    {{key: 'event_count', label: 'イベント数'}},
                    {{key: 'first_event_date', label: '開始日'}},
                    {{key: 'total_sales', label: '累計売上'}}
                ],
                'studio_decline': [
                    {{key: 'studio_name', label: '写真館名'}},
                    {{key: 'region', label: '事業所'}},
                    {{key: 'current_schools', label: '担当校数'}},
                    {{key: 'current_sales', label: '今年度売上'}},
                    {{key: 'prev_sales', label: '前年度売上'}},
                    {{key: 'change_rate', label: '変化率'}}
                ],
                'rapid_growth': [
                    {{key: 'school_name', label: '学校名'}},
                    {{key: 'attribute', label: '属性'}},
                    {{key: 'region', label: '事業所'}},
                    {{key: 'studio_name', label: '写真館'}},
                    {{key: 'current_sales', label: '今年度売上'}},
                    {{key: 'prev_sales', label: '前年度売上'}},
                    {{key: 'growth_rate', label: '成長率'}}
                ],
                'member_rate_trend': [
                    {{key: 'school_name', label: '学校名'}},
                    {{key: 'attribute', label: '属性'}},
                    {{key: 'studio_name', label: '写真館'}},
                    {{key: 'branch_name', label: '事業所'}},
                    {{key: 'current_rate', label: '今年度会員率'}},
                    {{key: 'prev_rate', label: '前年度会員率'}},
                    {{key: 'improvement', label: '改善幅'}}
                ],
                'unit_price': [
                    {{key: 'school_name', label: '学校名'}},
                    {{key: 'attribute', label: '属性'}},
                    {{key: 'studio_name', label: '写真館'}},
                    {{key: 'member_rate', label: '会員率'}},
                    {{key: 'total_sales', label: '売上'}},
                    {{key: 'total_members', label: '会員数'}},
                    {{key: 'unit_price', label: '単価'}},
                    {{key: 'attr_avg', label: '属性平均'}},
                    {{key: 'diff', label: '平均比'}}
                ]
            }};

            const columns = columnDefs[type] || [];
            if (columns.length === 0) return;

            // ヘッダー行を作成
            const headers = columns.map(c => c.label);
            let csv = headers.join(',') + '\\n';

            // データ行を作成
            data.forEach(item => {{
                const row = columns.map(c => {{
                    let val = item[c.key];
                    if (val === null || val === undefined) val = '';
                    // 数値フォーマット
                    if (c.key === 'total_sales' || c.key === 'current_sales' || c.key === 'prev_sales') {{
                        val = typeof val === 'number' ? val : '';
                    }} else if (c.key === 'member_rate') {{
                        val = typeof val === 'number' ? (val * 100).toFixed(1) + '%' : val;
                    }} else if (c.key === 'sales_change' || c.key === 'change_rate' || c.key === 'growth_rate') {{
                        val = typeof val === 'number' ? (val >= 0 ? '+' : '') + (val * 100).toFixed(1) + '%' : val;
                    }}
                    // カンマや改行をエスケープ
                    val = String(val).replace(/"/g, '""');
                    if (val.includes(',') || val.includes('\\n') || val.includes('"')) {{
                        val = '"' + val + '"';
                    }}
                    return val;
                }});
                csv += row.join(',') + '\\n';
            }});

            // BOMを追加（Excel対応）
            const bom = '\\uFEFF';
            const blob = new Blob([bom + csv], {{type: 'text/csv;charset=utf-8;'}});
            const url = URL.createObjectURL(blob);

            // ダウンロードリンクを作成
            const alertNames = {{
                'no_events': '今年度未実施',
                'new_event_low': 'イベント開始日別売上',
                'decline': '会員率売上低下',
                'new_schools': '新規開始校',
                'studio_decline': '写真館別低下',
                'rapid_growth': '売上好調校',
                'member_rate_trend': '会員率改善校',
                'unit_price': '売上単価分析'
            }};
            const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
            const filename = `${{alertNames[type] || type}}_${{today}}.csv`;

            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}

        // イベント開始日別売上フィルタ（年・月・日絞り込み）
        function filterNewEventLowByDate() {{
            const selectedYear = document.getElementById('new_event_low-year-filter').value;
            const selectedMonth = document.getElementById('new_event_low-month-filter').value;
            const selectedDay = document.getElementById('new_event_low-day-filter').value;

            if (!selectedYear) {{
                // 年未選択時はメッセージ表示
                document.getElementById('new_event_low-message').style.display = 'block';
                document.getElementById('new_event_low-table-container').style.display = 'none';
                document.getElementById('new_event_low-pagination').style.display = 'none';
                alertState.new_event_low.data = [];
                return;
            }}

            // 選択された年・月・日で絞り込み
            alertState.new_event_low.data = alertData.new_event_low.filter(item => {{
                if (!item.start_date) return false;
                const dateParts = item.start_date.split('-');
                if (dateParts.length < 3) return false;

                const itemYear = dateParts[0];
                const itemMonth = dateParts[1];
                const itemDay = dateParts[2];

                // 年は必須
                if (itemYear !== selectedYear) return false;

                // 月が指定されていれば絞り込み
                if (selectedMonth && itemMonth !== selectedMonth) return false;

                // 日が指定されていれば絞り込み
                if (selectedDay && itemDay !== selectedDay) return false;

                return true;
            }});
            alertState.new_event_low.page = 1;

            // テーブルとページネーションを表示
            document.getElementById('new_event_low-message').style.display = 'none';
            document.getElementById('new_event_low-table-container').style.display = 'block';
            document.getElementById('new_event_low-pagination').style.display = 'flex';

            renderAlertByType('new_event_low');
        }}

        // 初期描画
        function initAlertTables() {{
            // 会員率・売上低下は初期フィルタを適用
            filterDeclineAlert();
            // 他のアラートを描画（new_event_lowは日付選択前は描画しない）
            renderAlertByType('no_events');
            renderAlertByType('new_schools');
            renderAlertByType('studio_decline');
            renderAlertByType('rapid_growth');
            // 売上単価分析は初期表示
            renderAlertByType('unit_price');
            // フィルタ用プルダウンを初期化
            initFilterDropdowns();
        }}

        // フィルタ用プルダウン初期化
        function initFilterDropdowns() {{
            const schools = alertData.schools_for_filter || [];
            const attributes = [...new Set(schools.map(s => s.attribute).filter(a => a))];
            const studios = [...new Set(schools.map(s => s.studio_name).filter(s => s))];
            const branches = [...new Set(schools.map(s => s.branch_name).filter(b => b))];

            // 会員率トレンドのフィルタ
            const mrtAttr = document.getElementById('member_rate_trend-attribute-filter');
            const mrtStudio = document.getElementById('member_rate_trend-studio-filter');
            const mrtSchool = document.getElementById('member_rate_trend-school-filter');

            attributes.forEach(attr => {{
                mrtAttr.innerHTML += `<option value="${{attr}}">${{attr}}</option>`;
            }});
            studios.forEach(studio => {{
                mrtStudio.innerHTML += `<option value="${{studio}}">${{studio}}</option>`;
            }});
            schools.forEach(school => {{
                mrtSchool.innerHTML += `<option value="${{school.school_id || school.id}}">${{school.school_name}}</option>`;
            }});

            // 売上単価分析のフィルタ
            const upAttr = document.getElementById('unit_price-attribute-filter');
            const upStudio = document.getElementById('unit_price-studio-filter');
            const upSchool = document.getElementById('unit_price-school-filter');

            attributes.forEach(attr => {{
                upAttr.innerHTML += `<option value="${{attr}}">${{attr}}</option>`;
            }});
            studios.forEach(studio => {{
                upStudio.innerHTML += `<option value="${{studio}}">${{studio}}</option>`;
            }});
            schools.forEach(school => {{
                upSchool.innerHTML += `<option value="${{school.school_id || school.id}}">${{school.school_name}}</option>`;
            }});

            // 年度別イベント比較のフィルタ
            const ycAttr = document.getElementById('yearly_comparison-attribute-filter');
            const ycStudio = document.getElementById('yearly_comparison-studio-filter');
            const ycSchool = document.getElementById('yearly_comparison-school-filter');

            attributes.forEach(attr => {{
                ycAttr.innerHTML += `<option value="${{attr}}">${{attr}}</option>`;
            }});
            studios.forEach(studio => {{
                ycStudio.innerHTML += `<option value="${{studio}}">${{studio}}</option>`;
            }});
            schools.forEach(school => {{
                ycSchool.innerHTML += `<option value="${{school.school_id || school.id}}">${{school.school_name}}</option>`;
            }});
        }}

        // 会員率トレンドフィルタの連動更新
        function updateMemberRateTrendFilters() {{
            const selectedAttr = document.getElementById('member_rate_trend-attribute-filter').value;
            const selectedStudio = document.getElementById('member_rate_trend-studio-filter').value;

            const schools = alertData.schools_for_filter || [];
            let filteredSchools = schools;

            if (selectedAttr) {{
                filteredSchools = filteredSchools.filter(s => s.attribute === selectedAttr);
            }}
            if (selectedStudio) {{
                filteredSchools = filteredSchools.filter(s => s.studio_name === selectedStudio);
            }}

            const schoolSelect = document.getElementById('member_rate_trend-school-filter');
            schoolSelect.innerHTML = '<option value="">全て</option>';
            filteredSchools.forEach(school => {{
                schoolSelect.innerHTML += `<option value="${{school.school_id || school.id}}">${{school.school_name}}</option>`;
            }});
        }}

        // 会員率トレンドフィルタ実行
        function filterMemberRateTrendAlert() {{
            const selectedAttr = document.getElementById('member_rate_trend-attribute-filter').value;
            const selectedStudio = document.getElementById('member_rate_trend-studio-filter').value;
            const selectedSchool = document.getElementById('member_rate_trend-school-filter').value;

            alertState.member_rate_trend.data = alertData.member_rate_trend.filter(item => {{
                if (selectedAttr && item.attribute !== selectedAttr) return false;
                if (selectedStudio && item.studio_name !== selectedStudio) return false;
                if (selectedSchool && String(item.school_id) !== selectedSchool) return false;
                return true;
            }});
            alertState.member_rate_trend.page = 1;

            document.getElementById('member_rate_trend-message').style.display = 'none';
            document.getElementById('member_rate_trend-table-container').style.display = 'block';
            document.getElementById('member_rate_trend-pagination').style.display = 'flex';

            renderAlertByType('member_rate_trend');
        }}

        // 年度別イベント比較フィルタの連動更新
        function updateYearlyComparisonFilters() {{
            const selectedAttr = document.getElementById('yearly_comparison-attribute-filter').value;
            const selectedStudio = document.getElementById('yearly_comparison-studio-filter').value;

            const schools = alertData.schools_for_filter || [];
            let filteredSchools = schools;

            if (selectedAttr) {{
                filteredSchools = filteredSchools.filter(s => s.attribute === selectedAttr);
            }}
            if (selectedStudio) {{
                filteredSchools = filteredSchools.filter(s => s.studio_name === selectedStudio);
            }}

            const schoolSelect = document.getElementById('yearly_comparison-school-filter');
            schoolSelect.innerHTML = '<option value="">-- 学校を選択 --</option>';
            filteredSchools.forEach(school => {{
                schoolSelect.innerHTML += `<option value="${{school.school_id || school.id}}">${{school.school_name}}</option>`;
            }});
        }}

        // 売上単価分析フィルタ実行
        function filterUnitPriceAlert() {{
            const selectedAttr = document.getElementById('unit_price-attribute-filter').value;
            const selectedStudio = document.getElementById('unit_price-studio-filter').value;
            const selectedSchool = document.getElementById('unit_price-school-filter').value;

            alertState.unit_price.data = alertData.unit_price.filter(item => {{
                if (selectedAttr && item.attribute !== selectedAttr) return false;
                if (selectedStudio && item.studio_name !== selectedStudio) return false;
                if (selectedSchool && String(item.school_id) !== selectedSchool) return false;
                return true;
            }});
            alertState.unit_price.page = 1;
            renderAlertByType('unit_price');
        }}

        // 年度別イベント比較フィルタ実行
        function filterYearlyComparisonAlert() {{
            const selectedSchool = document.getElementById('yearly_comparison-school-filter').value;
            const selectedMonth = document.getElementById('yearly_comparison-month-filter').value;
            const leftYearVal = document.getElementById('yearly_comparison-left-year-filter').value;
            const rightYearVal = document.getElementById('yearly_comparison-right-year-filter').value;

            // 必須フィールドのバリデーション（月は任意）
            const missingFields = [];
            if (!selectedSchool) missingFields.push('学校');
            if (!leftYearVal) missingFields.push('左年度');
            if (!rightYearVal) missingFields.push('右年度');

            if (missingFields.length > 0) {{
                const msgEl = document.getElementById('yearly_comparison-message');
                msgEl.innerHTML = `<span style="color: #ef4444;">必須項目を選択してください: ${{missingFields.join('、')}}</span>`;
                msgEl.style.display = 'block';
                document.getElementById('yearly_comparison-container').style.display = 'none';
                return;
            }}

            const leftYear = parseInt(leftYearVal);
            const rightYear = parseInt(rightYearVal);

            // 学校のイベントを取得してフィルタリング
            const allEvents = alertData.new_event_low || [];
            const schoolEvents = allEvents.filter(e => String(e.school_id) === selectedSchool);

            const leftEvents = schoolEvents.filter(e => {{
                if (!e.start_date) return false;
                const date = new Date(e.start_date);
                const month = date.getMonth() + 1;
                const year = date.getFullYear();
                const fiscalYear = month >= 4 ? year : year - 1;
                if (fiscalYear !== leftYear) return false;
                if (selectedMonth && month !== parseInt(selectedMonth)) return false;
                return true;
            }});

            const rightEvents = schoolEvents.filter(e => {{
                if (!e.start_date) return false;
                const date = new Date(e.start_date);
                const month = date.getMonth() + 1;
                const year = date.getFullYear();
                const fiscalYear = month >= 4 ? year : year - 1;
                if (fiscalYear !== rightYear) return false;
                if (selectedMonth && month !== parseInt(selectedMonth)) return false;
                return true;
            }});

            // 学校情報を取得
            const schoolInfo = alertData.schools_for_filter.find(s => String(s.school_id || s.id) === selectedSchool) || {{}};

            alertState.yearly_comparison.data = {{ left: leftEvents, right: rightEvents }};
            alertState.yearly_comparison.leftYear = leftYear;
            alertState.yearly_comparison.rightYear = rightYear;
            alertState.yearly_comparison.schoolInfo = schoolInfo;

            document.getElementById('yearly_comparison-message').style.display = 'none';
            document.getElementById('yearly_comparison-container').style.display = 'block';

            renderYearlyComparison();
        }}

        // 年度別イベント比較の描画
        function renderYearlyComparison() {{
            const data = alertState.yearly_comparison.data;
            const leftYear = alertState.yearly_comparison.leftYear;
            const rightYear = alertState.yearly_comparison.rightYear;
            const schoolInfo = alertState.yearly_comparison.schoolInfo || {{}};

            let leftTotal = 0;
            let rightTotal = 0;

            let html = `<div style="margin-bottom: 12px; font-weight: 600; color: #1a1a2e;">${{schoolInfo.school_name || '学校名不明'}} <span style="font-weight: normal; color: #666; margin-left: 8px;">${{schoolInfo.attribute || ''}} / ${{schoolInfo.studio_name || ''}}</span></div>`;
            html += '<div class="comparison-container">';

            // 左側（左年度）
            html += '<div class="comparison-column left">';
            html += `<h4>${{leftYear}}年度</h4>`;
            if (data.left.length === 0) {{
                html += '<div class="comparison-empty">イベントなし</div>';
            }} else {{
                data.left.forEach(e => {{
                    const sales = e.total_sales || 0;
                    leftTotal += sales;
                    let dateStr = '-';
                    if (e.start_date) {{
                        const d = new Date(e.start_date);
                        dateStr = `${{d.getMonth() + 1}}月${{d.getDate()}}日公開`;
                    }}
                    html += `<div class="comparison-event"><span><span class="comparison-event-name">${{(e.event_name || '').substring(0, 25)}}</span><span class="comparison-event-date">（${{dateStr}}）</span></span><span class="comparison-event-sales">¥${{sales.toLocaleString()}}</span></div>`;
                }});
            }}
            html += `<div class="comparison-summary"><span>計: ${{data.left.length}}件</span><span>合計: ¥${{leftTotal.toLocaleString()}}</span></div>`;
            html += '</div>';

            // 右側（右年度）
            html += '<div class="comparison-column right">';
            html += `<h4>${{rightYear}}年度</h4>`;
            if (data.right.length === 0) {{
                html += '<div class="comparison-empty">イベントなし</div>';
            }} else {{
                data.right.forEach(e => {{
                    const sales = e.total_sales || 0;
                    rightTotal += sales;
                    let dateStr = '-';
                    if (e.start_date) {{
                        const d = new Date(e.start_date);
                        dateStr = `${{d.getMonth() + 1}}月${{d.getDate()}}日公開`;
                    }}
                    html += `<div class="comparison-event"><span><span class="comparison-event-name">${{(e.event_name || '').substring(0, 25)}}</span><span class="comparison-event-date">（${{dateStr}}）</span></span><span class="comparison-event-sales">¥${{sales.toLocaleString()}}</span></div>`;
                }});
            }}
            html += `<div class="comparison-summary"><span>計: ${{data.right.length}}件</span><span>合計: ¥${{rightTotal.toLocaleString()}}</span></div>`;
            html += '</div>';

            html += '</div>';

            document.getElementById('yearly_comparison-container').innerHTML = html;
        }}

        // 年度別イベント比較CSV出力（縦並び形式）
        function downloadYearlyComparisonCSV() {{
            const data = alertState.yearly_comparison.data;
            const leftYear = alertState.yearly_comparison.leftYear;
            const rightYear = alertState.yearly_comparison.rightYear;
            const schoolInfo = alertState.yearly_comparison.schoolInfo || {{}};

            if ((!data.left || data.left.length === 0) && (!data.right || data.right.length === 0)) {{
                alert('ダウンロードするデータがありません。');
                return;
            }}

            // CSVヘッダー
            let csv = '学校名,属性,事業所,年度,月,イベント名,公開日,売上\\n';

            // 左年度データ
            (data.left || []).forEach(e => {{
                const date = e.start_date ? new Date(e.start_date) : null;
                const month = date ? date.getMonth() + 1 : '';
                csv += `"${{schoolInfo.school_name || ''}}","${{schoolInfo.attribute || ''}}","${{schoolInfo.studio_name || ''}}",${{leftYear}},${{month}},"${{(e.event_name || '').replace(/"/g, '""')}}",${{e.start_date || ''}},${{e.total_sales || 0}}\\n`;
            }});

            // 右年度データ
            (data.right || []).forEach(e => {{
                const date = e.start_date ? new Date(e.start_date) : null;
                const month = date ? date.getMonth() + 1 : '';
                csv += `"${{schoolInfo.school_name || ''}}","${{schoolInfo.attribute || ''}}","${{schoolInfo.studio_name || ''}}",${{rightYear}},${{month}},"${{(e.event_name || '').replace(/"/g, '""')}}",${{e.start_date || ''}},${{e.total_sales || 0}}\\n`;
            }});

            // BOMを追加（Excel対応）
            const bom = '\\uFEFF';
            const blob = new Blob([bom + csv], {{type: 'text/csv;charset=utf-8;'}});
            const url = URL.createObjectURL(blob);

            const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
            const filename = `年度別イベント比較_${{schoolInfo.school_name || '学校'}}_${{today}}.csv`;

            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}

        // 初期グラフ（月ごと売上推移：線グラフ）
        mainSalesChart = new Chart(document.getElementById('salesChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(months_labels)},
                datasets: [
                    {{
                        label: '今年度売上',
                        data: {json.dumps(sales_data)},
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 5
                    }},
                    {{
                        label: '前年度売上',
                        data: {json.dumps(prev_sales_data)},
                        borderColor: '#888',
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        tension: 0.3,
                        pointRadius: 3
                    }},
                    {{
                        label: '予算',
                        data: {json.dumps(budget_data)},
                        borderColor: 'rgba(251, 191, 36, 0.8)',
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        borderDash: [3, 3],
                        tension: 0.3,
                        pointRadius: 3
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ position: 'top' }} }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{ callback: v => '¥' + Math.round(v / 10000).toLocaleString() + '万' }}
                    }}
                }}
            }}
        }});

        // アラートテーブル初期化
        initAlertTables();
    </script>
</body>
</html>
'''

    # ファイル出力
    if output_path is None:
        output_path = Path(__file__).parent / f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


if __name__ == '__main__':
    import sys

    output = sys.argv[1] if len(sys.argv) > 1 else None
    path = generate_html_dashboard(output_path=output)
    print(f"ダッシュボードを生成しました: {path}")
