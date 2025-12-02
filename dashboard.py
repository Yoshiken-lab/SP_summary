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

    # 前年度同期売上
    cursor.execute('''
        SELECT SUM(total_sales) FROM monthly_summary
        WHERE report_id = ? AND fiscal_year = ?
    ''', (latest_report_id, prev_fy))
    prev_total = cursor.fetchone()[0] or 0

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

    # 事業所別・担当者別の月別売上データを取得
    branch_sales_data = get_monthly_sales_by_branch(db_path)
    person_sales_data = get_monthly_sales_by_person(db_path)

    # 会員率データを事前取得
    all_school_data = {}
    for school in filter_options['schools']:
        data_all = get_member_rate_trend_by_school(school['id'], by_grade=False, db_path=db_path)
        if data_all:
            all_school_data[f"school_{school['id']}_all"] = data_all
        data_grade = get_member_rate_trend_by_school(school['id'], by_grade=True, db_path=db_path)
        if data_grade:
            all_school_data[f"school_{school['id']}_grade"] = data_grade

    all_attribute_data = {}
    for attr in filter_options['attributes']:
        data = get_member_rate_trend_by_attribute(attr, db_path=db_path)
        if data:
            all_attribute_data[f"attr_{attr}"] = data

    # 売上推移データを事前取得
    all_sales_school_data = {}
    all_event_sales_data = {}
    for school in sales_filter_options['schools']:
        data = get_sales_trend_by_school(school['id'], db_path=db_path)
        if data:
            all_sales_school_data[f"school_{school['id']}"] = data
        # イベント別売上も取得
        event_data = get_event_sales_by_school(school['id'], db_path=db_path)
        if event_data:
            all_event_sales_data[f"school_{school['id']}"] = event_data

    all_sales_studio_data = {}
    for studio in sales_filter_options['studios']:
        data = get_sales_trend_by_studio(studio, db_path=db_path)
        if data:
            all_sales_studio_data[f"studio_{studio}"] = data

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
        .alert-tabs {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 16px;
        }}
        .alert-tab {{
            padding: 10px 20px;
            border-radius: 8px;
            background: #f0f0f0;
            color: #333;
            cursor: pointer;
            font-weight: 500;
            border: none;
            transition: all 0.3s;
        }}
        .alert-tab:hover, .alert-tab.active {{
            background: #3b82f6;
            color: white;
        }}
        .alert-tab .badge {{
            background: #ef4444;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            margin-left: 6px;
        }}
        .alert-tab.success .badge {{ background: #10b981; }}
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
            <div style="display: flex; align-items: center; gap: 24px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <label style="font-size: 14px; color: #666; font-weight: 600;">年度:</label>
                    <select id="fiscalYearSelect" onchange="changeFiscalYear()" style="padding: 10px 16px; border: 2px solid #3b82f6; border-radius: 8px; font-size: 16px; font-weight: 600; color: #1a1a2e; cursor: pointer; background: white;">
                        {chr(10).join([f'<option value="{y}" {"selected" if y == stats["fiscal_year"] else ""}>{y}年度</option>' for y in available_years])}
                    </select>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 12px; color: #666;">蓄積データ</div>
                    <div style="font-size: 20px; font-weight: bold;">{stats['school_count']}校 / {stats['event_count']}イベント</div>
                </div>
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
                <div class="card-title">要対応アラート</div>
                <div class="card-value {'danger' if total_alerts > 20 else 'warning' if total_alerts > 0 else 'success'}">{total_alerts}件</div>
                <div class="card-sub">詳細は下記参照</div>
            </div>
        </div>

        <!-- 月別売上推移セクション -->
        <div class="chart-card">
            <h3>月別売上推移</h3>
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
            <div style="display: flex; gap: 0; margin-bottom: 20px; border-bottom: 2px solid #e2e8f0;">
                <button id="tabMemberRate" onclick="switchDetailTab('memberRate')" class="detail-tab active" style="padding: 12px 24px; border: none; background: transparent; font-size: 16px; font-weight: 600; color: #3b82f6; cursor: pointer; border-bottom: 3px solid #3b82f6; margin-bottom: -2px;">会員率推移</button>
                <button id="tabSales" onclick="switchDetailTab('sales')" class="detail-tab" style="padding: 12px 24px; border: none; background: transparent; font-size: 16px; font-weight: 600; color: #666; cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px;">学校別売上推移</button>
            </div>

            <!-- 会員率推移グラフ -->
            <div id="memberRatePanel" class="detail-panel">
                <div style="display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; margin-bottom: 16px;">
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 12px; color: #666; font-weight: 600;">属性</label>
                        <select id="filterAttribute" style="padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 180px;">
                            <option value="">-- 全て --</option>
                            {chr(10).join([f'<option value="{attr}">{attr}</option>' for attr in filter_options['attributes']])}
                        </select>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 12px; color: #666; font-weight: 600;">写真館</label>
                        <select id="filterStudio" style="padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 180px;">
                            <option value="">-- 全て --</option>
                            {chr(10).join([f'<option value="{studio}">{studio}</option>' for studio in filter_options['studios']])}
                        </select>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 6px;">
                        <label style="font-size: 12px; color: #666; font-weight: 600;">学校名</label>
                        <select id="filterSchool" style="padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 250px;">
                            <option value="">-- 属性/写真館で絞り込み --</option>
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
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <input type="checkbox" id="showPrevYear" checked style="width: 18px; height: 18px; accent-color: #3b82f6;">
                        <label for="showPrevYear" style="font-size: 14px; color: #333; cursor: pointer;">前年度を表示</label>
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
                        <label style="font-size: 12px; color: #666; font-weight: 600;">写真館</label>
                        <select id="salesFilterStudio" style="padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 180px;">
                            <option value="">-- 全て --</option>
                            {chr(10).join([f'<option value="{s}">{s}</option>' for s in sales_filter_options['studios']])}
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
                        <label style="font-size: 12px; color: #666; font-weight: 600;">学校名</label>
                        <select id="salesFilterSchool" style="padding: 10px 14px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 14px; min-width: 250px;">
                            <option value="">-- 絞り込みで選択 --</option>
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

        <!-- アラート一覧 -->
        <div class="alert-section">
            <h3>アラート一覧</h3>
            <div class="alert-tabs">
                <button class="alert-tab active" onclick="showAlert('no_events')">
                    今年度未実施 <span class="badge">{alert_counts.get('no_events_this_year', 0)}</span>
                </button>
                <button class="alert-tab" onclick="showAlert('new_event_low')">
                    直近開始で会員率低 <span class="badge">{alert_counts.get('new_event_low_registration', 0)}</span>
                </button>
                <button class="alert-tab" onclick="showAlert('decline')">
                    会員率・売上低下 <span class="badge">{alert_counts.get('member_rate_decline', 0)}</span>
                </button>
                <button class="alert-tab success" onclick="showAlert('new_schools')">
                    新規開始校 <span class="badge">{alert_counts.get('new_schools', 0)}</span>
                </button>
                <button class="alert-tab" onclick="showAlert('studio_decline')">
                    写真館別低下 <span class="badge">{alert_counts.get('studio_performance_decline', 0)}</span>
                </button>
                <button class="alert-tab success" onclick="showAlert('rapid_growth')">
                    急成長校 <span class="badge">{alert_counts.get('rapid_growth', 0)}</span>
                </button>
            </div>
'''

    # アラートテーブル生成（今年度未実施）
    html += '''
            <div id="alert-no_events" class="alert-content active">
                <table class="alert-table">
                    <thead><tr><th>学校名</th><th>属性</th><th>写真館</th><th>前年度イベント数</th><th>前年度売上</th><th>状態</th></tr></thead>
                    <tbody>
'''
    for item in alerts.get('no_events_this_year', []):
        html += f'<tr><td>{item["school_name"]}</td><td>{item["attribute"]}</td><td>{item["studio_name"]}</td><td>{item["prev_year_events"]}件</td><td>¥{item["prev_year_sales"]:,.0f}</td><td><span class="status-badge {item["level"]}">要確認</span></td></tr>'
    if not alerts.get('no_events_this_year'):
        html += '<tr><td colspan="6" style="text-align:center;color:#888;padding:40px;">アラートはありません</td></tr>'
    html += '</tbody></table></div>'

    # 直近開始で会員率低
    html += '''
            <div id="alert-new_event_low" class="alert-content">
                <table class="alert-table">
                    <thead><tr><th>学校名</th><th>イベント名</th><th>開始日</th><th>経過日数</th><th>会員率</th><th>状態</th></tr></thead>
                    <tbody>
'''
    for item in alerts.get('new_event_low_registration', []):
        html += f'<tr><td>{item["school_name"]}</td><td>{item["event_name"][:30]}...</td><td>{item["start_date"]}</td><td>{item["days_since_start"]}日</td><td>{item["member_rate"]*100:.1f}%</td><td><span class="status-badge {item["level"]}">要フォロー</span></td></tr>'
    if not alerts.get('new_event_low_registration'):
        html += '<tr><td colspan="6" style="text-align:center;color:#888;padding:40px;">アラートはありません</td></tr>'
    html += '</tbody></table></div>'

    # 会員率・売上低下
    html += '''
            <div id="alert-decline" class="alert-content">
                <table class="alert-table">
                    <thead><tr><th>学校名</th><th>属性</th><th>会員率</th><th>今年度売上</th><th>前年度売上</th><th>売上変化</th><th>状態</th></tr></thead>
                    <tbody>
'''
    for item in alerts.get('member_rate_decline', []):
        html += f'<tr><td>{item["school_name"]}</td><td>{item["attribute"]}</td><td>{item["member_rate"]*100:.1f}%</td><td>¥{item["current_sales"]:,.0f}</td><td>¥{item["prev_sales"]:,.0f}</td><td class="trend-down">{item["sales_change"]*100:+.1f}%</td><td><span class="status-badge {item["level"]}">要対応</span></td></tr>'
    if not alerts.get('member_rate_decline'):
        html += '<tr><td colspan="7" style="text-align:center;color:#888;padding:40px;">アラートはありません</td></tr>'
    html += '</tbody></table></div>'

    # 新規開始校
    html += '''
            <div id="alert-new_schools" class="alert-content">
                <table class="alert-table">
                    <thead><tr><th>学校名</th><th>属性</th><th>写真館</th><th>イベント数</th><th>初回開始日</th><th>売上</th></tr></thead>
                    <tbody>
'''
    for item in alerts.get('new_schools', []):
        html += f'<tr><td>{item["school_name"]}</td><td>{item["attribute"]}</td><td>{item["studio_name"]}</td><td>{item["event_count"]}件</td><td>{item["first_event_date"] or "-"}</td><td>¥{item["total_sales"]:,.0f}</td></tr>'
    if not alerts.get('new_schools'):
        html += '<tr><td colspan="6" style="text-align:center;color:#888;padding:40px;">新規開始校はありません</td></tr>'
    html += '</tbody></table></div>'

    # 写真館別低下
    html += '''
            <div id="alert-studio_decline" class="alert-content">
                <table class="alert-table">
                    <thead><tr><th>写真館名</th><th>今年度売上</th><th>前年度売上</th><th>変化率</th><th>担当校数</th><th>状態</th></tr></thead>
                    <tbody>
'''
    for item in alerts.get('studio_performance_decline', []):
        html += f'<tr><td>{item["studio_name"]}</td><td>¥{item["current_sales"]:,.0f}</td><td>¥{item["prev_sales"]:,.0f}</td><td class="trend-down">{item["change_rate"]*100:+.1f}%</td><td>{item["current_schools"]}校</td><td><span class="status-badge {item["level"]}">要確認</span></td></tr>'
    if not alerts.get('studio_performance_decline'):
        html += '<tr><td colspan="6" style="text-align:center;color:#888;padding:40px;">アラートはありません</td></tr>'
    html += '</tbody></table></div>'

    # 急成長校
    html += '''
            <div id="alert-rapid_growth" class="alert-content">
                <table class="alert-table">
                    <thead><tr><th>学校名</th><th>属性</th><th>写真館</th><th>今年度売上</th><th>前年度売上</th><th>成長率</th></tr></thead>
                    <tbody>
'''
    for item in alerts.get('rapid_growth', []):
        html += f'<tr><td>{item["school_name"]}</td><td>{item["attribute"]}</td><td>{item["studio_name"]}</td><td>¥{item["current_sales"]:,.0f}</td><td>¥{item["prev_sales"]:,.0f}</td><td class="trend-up">{item["growth_rate"]*100:+.1f}%</td></tr>'
    if not alerts.get('rapid_growth'):
        html += '<tr><td colspan="6" style="text-align:center;color:#888;padding:40px;">該当校はありません</td></tr>'
    html += '</tbody></table></div></div>'

    # 分析セクション
    html += '''
        <div class="analysis-grid">
            <div class="analysis-card">
                <h4>会員率連続低下校</h4>
'''
    for item in analytics.get('member_rate_trends', [])[:8]:
        html += f'<div class="trend-item"><span>{item["school_name"][:25]}</span><span class="trend-down">{item["start_rate"]*100:.1f}% → {item["current_rate"]*100:.1f}%</span></div>'
    if not analytics.get('member_rate_trends'):
        html += '<p style="color:#888;text-align:center;padding:20px;">データなし</p>'
    html += '</div>'

    html += '''
            <div class="analysis-card">
                <h4>成長カーブ評価（遅れている学校）</h4>
'''
    for item in analytics.get('growth_curves', {}).get('evaluations', [])[:8]:
        if item['status'] == 'behind' and item['expected_rate']:
            html += f'<div class="trend-item"><span>{item["school_name"][:25]}</span><span class="trend-down">現在{item["current_rate"]*100:.1f}% (期待{item["expected_rate"]*100:.1f}%)</span></div>'
    if not [x for x in analytics.get('growth_curves', {}).get('evaluations', []) if x['status'] == 'behind']:
        html += '<p style="color:#888;text-align:center;padding:20px;">遅れている学校はありません</p>'
    html += '</div>'

    html += '''
            <div class="analysis-card">
                <h4>属性別 平均会員率</h4>
'''
    for item in analytics.get('by_attribute', []):
        if item['avg_member_rate']:
            rate = item['avg_member_rate'] * 100
            color = '#10b981' if rate >= 60 else '#f59e0b' if rate >= 40 else '#ef4444'
            html += f'<div class="trend-item"><span>{item["attribute"]} ({item["school_count"]}校)</span><span style="color:{color}">{rate:.1f}%</span></div>'
    html += '</div></div>'

    html += f'''
        <div class="footer">
            Generated by スクールフォト売上分析システム | {datetime.now().strftime('%Y-%m-%d %H:%M')}
        </div>
    </div>

    <script>
        // データ
        const schoolsData = {json.dumps(filter_options['schools'], ensure_ascii=False)};
        const allSchoolData = {json.dumps(all_school_data, ensure_ascii=False)};
        const allAttributeData = {json.dumps(all_attribute_data, ensure_ascii=False)};
        const salesSchoolsData = {json.dumps(sales_filter_options['schools'], ensure_ascii=False)};
        const allSalesSchoolData = {json.dumps(all_sales_school_data, ensure_ascii=False)};
        const allSalesStudioData = {json.dumps(all_sales_studio_data, ensure_ascii=False)};
        const allEventSalesData = {json.dumps(all_event_sales_data, ensure_ascii=False)};
        const branchSalesData = {json.dumps(branch_sales_data, ensure_ascii=False)};
        const personSalesData = {json.dumps(person_sales_data, ensure_ascii=False)};

        // 年度別サマリーデータ
        const allYearsStats = {json.dumps({str(k): v for k, v in all_years_stats.items()}, ensure_ascii=False)};
        let currentFiscalYear = {stats['fiscal_year']};

        // 年度切り替え関数
        function changeFiscalYear() {{
            const selectedYear = document.getElementById('fiscalYearSelect').value;
            currentFiscalYear = parseInt(selectedYear);
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

        // 事業所グラフ描画（棒グラフ）
        function renderBranchChart() {{
            const selectedBranch = document.getElementById('branchFilter').value;
            const months = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3];
            const labels = months.map(m => m + '月');
            const ctx = document.getElementById('branchSalesChart').getContext('2d');

            if (branchSalesChart) branchSalesChart.destroy();

            if (!selectedBranch) {{
                // 全事業所の今年度売上を棒グラフで表示
                const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];
                const datasets = [];
                let colorIdx = 0;

                if (branchSalesData.branches) {{
                    branchSalesData.branches.forEach(branch => {{
                        const data = branchSalesData.data[branch];
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
                        plugins: {{ legend: {{ position: 'top' }} }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                ticks: {{ callback: v => '¥' + (v / 1000000).toFixed(1) + 'M' }}
                            }}
                        }}
                    }}
                }});
            }} else {{
                // 特定事業所の今年度・前年度・予算を棒グラフで表示
                const data = branchSalesData.data[selectedBranch];
                if (!data) return;

                const datasets = [
                    {{
                        label: '今年度売上',
                        data: months.map(m => data.current[m] || 0),
                        backgroundColor: 'rgba(59, 130, 246, 0.8)',
                        borderRadius: 4
                    }},
                    {{
                        label: '前年度売上',
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
                            title: {{ display: true, text: selectedBranch + ' - 月別売上推移' }}
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                ticks: {{ callback: v => '¥' + (v / 1000000).toFixed(1) + 'M' }}
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

        // 事業所の担当者全員を棒グラフで表示
        function renderPersonChartByBranch(branch) {{
            const months = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3];
            const labels = months.map(m => m + '月');
            const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];
            const datasets = [];
            let colorIdx = 0;

            // 事業所に属する担当者を取得
            const personsInBranch = personSalesData.persons?.filter(p => {{
                const branches = personSalesData.person_branches?.[p] || [];
                return branches.includes(branch);
            }}) || [];

            personsInBranch.forEach(person => {{
                const data = personSalesData.data[person];
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
                        title: {{ display: true, text: branch + ' - 担当者別月別売上' }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ callback: v => '¥' + (v / 1000000).toFixed(1) + 'M' }}
                        }}
                    }}
                }}
            }});
        }}

        // 特定担当者の棒グラフ描画
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

            const months = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3];
            const labels = months.map(m => m + '月');
            const data = personSalesData.data[person];
            if (!data) return;

            const datasets = [
                {{
                    label: '今年度売上',
                    data: months.map(m => data.current[m] || 0),
                    backgroundColor: 'rgba(59, 130, 246, 0.8)',
                    borderRadius: 4
                }},
                {{
                    label: '前年度売上',
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
                        title: {{ display: true, text: person + ' - 月別売上推移' }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ callback: v => '¥' + (v / 1000000).toFixed(1) + 'M' }}
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

        // 会員率フィルター
        document.getElementById('filterAttribute').addEventListener('change', filterMemberRateSchools);
        document.getElementById('filterStudio').addEventListener('change', filterMemberRateSchools);

        function filterMemberRateSchools() {{
            const attr = document.getElementById('filterAttribute').value;
            const studio = document.getElementById('filterStudio').value;
            const schoolSelect = document.getElementById('filterSchool');

            let filtered = schoolsData;
            if (attr) filtered = filtered.filter(s => s.attribute === attr);
            if (studio) filtered = filtered.filter(s => s.studio === studio);

            schoolSelect.innerHTML = '<option value="">-- 属性/写真館で絞り込み --</option>';
            filtered.forEach(s => {{
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.name;
                schoolSelect.appendChild(opt);
            }});
        }}

        function resetMemberRateFilters() {{
            document.getElementById('filterAttribute').value = '';
            document.getElementById('filterStudio').value = '';
            document.getElementById('filterSchool').innerHTML = '<option value="">-- 属性/写真館で絞り込み --</option>';
            document.getElementById('gradeAll').checked = true;
            document.getElementById('showPrevYear').checked = true;
        }}

        function searchMemberRate() {{
            const attr = document.getElementById('filterAttribute').value;
            const schoolId = document.getElementById('filterSchool').value;
            const gradeMode = document.querySelector('input[name="gradeMode"]:checked').value;

            if (schoolId) {{
                const key = gradeMode === 'each' ? `school_${{schoolId}}_grade` : `school_${{schoolId}}_all`;
                currentMemberRateData = allSchoolData[key];
                document.getElementById('gradeOptionGroup').style.display = 'flex';
            }} else if (attr) {{
                currentMemberRateData = allAttributeData[`attr_${{attr}}`];
                document.getElementById('gradeOptionGroup').style.display = 'none';
            }} else {{
                alert('属性または学校を選択してください');
                return;
            }}

            if (currentMemberRateData) renderMemberRateChart();
            else alert('データが見つかりませんでした');
        }}

        function renderMemberRateChart() {{
            if (!currentMemberRateData) return;

            const showPrevYear = document.getElementById('showPrevYear').checked;
            const title = currentMemberRateData.school_name || `${{currentMemberRateData.attribute}}（${{currentMemberRateData.school_count}}校平均）`;
            document.getElementById('memberRateChartTitle').textContent = title;
            document.getElementById('memberRateChartInfo').textContent = currentMemberRateData.attribute ? `属性: ${{currentMemberRateData.attribute}}` : '';

            const datasets = [];

            if (currentMemberRateData.by_grade && typeof currentMemberRateData.current_year === 'object' && !Array.isArray(currentMemberRateData.current_year)) {{
                const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];
                let colorIdx = 0;

                for (const [grade, data] of Object.entries(currentMemberRateData.current_year)) {{
                    if (data.dates?.length > 0) {{
                        datasets.push({{
                            label: `${{grade}}（今年度）`,
                            data: data.dates.map((d, i) => ({{ x: d, y: data.rates[i] }})),
                            borderColor: colors[colorIdx % colors.length],
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: 4
                        }});
                    }}

                    if (showPrevYear && currentMemberRateData.prev_year?.[grade]?.dates?.length > 0) {{
                        const prevData = currentMemberRateData.prev_year[grade];
                        datasets.push({{
                            label: `${{grade}}（前年度）`,
                            data: prevData.dates.map((d, i) => ({{ x: d, y: prevData.rates[i] }})),
                            borderColor: colors[colorIdx % colors.length],
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            tension: 0.3,
                            pointRadius: 3
                        }});
                    }}
                    colorIdx++;
                }}
            }} else {{
                const current = currentMemberRateData.current_year;
                if (current?.dates?.length > 0) {{
                    datasets.push({{
                        label: '今年度',
                        data: current.dates.map((d, i) => ({{ x: d, y: current.rates[i] }})),
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 5
                    }});
                }}

                if (showPrevYear && currentMemberRateData.prev_year?.dates?.length > 0) {{
                    const prev = currentMemberRateData.prev_year;
                    datasets.push({{
                        label: '前年度',
                        data: prev.dates.map((d, i) => ({{ x: d, y: prev.rates[i] }})),
                        borderColor: '#888',
                        backgroundColor: 'transparent',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        tension: 0.3,
                        pointRadius: 3
                    }});
                }}
            }}

            const ctx = document.getElementById('memberRateChart').getContext('2d');
            if (memberRateChart) memberRateChart.destroy();

            memberRateChart = new Chart(ctx, {{
                type: 'line',
                data: {{ datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: true, position: 'top' }},
                        tooltip: {{ callbacks: {{ label: ctx => `${{ctx.dataset.label}}: ${{ctx.parsed.y}}%` }} }}
                    }},
                    scales: {{
                        x: {{ type: 'category', title: {{ display: true, text: '日付' }} }},
                        y: {{ min: 0, max: 100, title: {{ display: true, text: '会員率 (%)' }}, ticks: {{ callback: v => v + '%' }} }}
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

        document.getElementById('showPrevYear').addEventListener('change', renderMemberRateChart);
        document.querySelectorAll('input[name="gradeMode"]').forEach(el => el.addEventListener('change', searchMemberRate));

        // 売上推移フィルター
        document.getElementById('salesFilterBranch').addEventListener('change', filterSalesSchools);
        document.getElementById('salesFilterStudio').addEventListener('change', filterSalesSchools);
        document.getElementById('salesFilterPerson').addEventListener('change', filterSalesSchools);

        function filterSalesSchools() {{
            const branch = document.getElementById('salesFilterBranch').value;
            const studio = document.getElementById('salesFilterStudio').value;
            const person = document.getElementById('salesFilterPerson').value;
            const schoolSelect = document.getElementById('salesFilterSchool');

            let filtered = salesSchoolsData;
            if (branch) filtered = filtered.filter(s => s.branch === branch);
            if (studio) filtered = filtered.filter(s => s.studio === studio);
            if (person) filtered = filtered.filter(s => s.person === person);

            schoolSelect.innerHTML = '<option value="">-- 絞り込みで選択 --</option>';
            filtered.forEach(s => {{
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.name;
                schoolSelect.appendChild(opt);
            }});
        }}

        function resetSalesFilters() {{
            document.getElementById('salesFilterBranch').value = '';
            document.getElementById('salesFilterStudio').value = '';
            document.getElementById('salesFilterPerson').value = '';
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

            if (schoolId) {{
                currentSalesData = allSalesSchoolData[`school_${{schoolId}}`];
                currentSchoolId = schoolId;
                showEventBreakdown(schoolId);
            }} else if (studio) {{
                currentSalesData = allSalesStudioData[`studio_${{studio}}`];
                currentSchoolId = null;
                document.getElementById('eventBreakdownSection').style.display = 'none';
            }} else {{
                alert('写真館または学校を選択してください');
                return;
            }}

            if (currentSalesData) renderSalesTrendChart();
            else alert('データが見つかりませんでした');
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
            let title = currentSalesData.school_name || `${{currentSalesData.studio_name}}（${{currentSalesData.school_count}}校）`;
            document.getElementById('salesChartTitle').textContent = title;

            const yoy = currentSalesData.yoy ? (currentSalesData.yoy * 100).toFixed(1) : '-';
            document.getElementById('salesChartInfo').textContent = `今年度累計: ¥${{currentSalesData.current_total?.toLocaleString() || 0}} / 前年比: ${{yoy}}%`;

            const datasets = [];
            const current = currentSalesData.current_year;
            if (current?.dates?.length > 0) {{
                datasets.push({{
                    label: '今年度',
                    data: current.dates.map((d, i) => ({{ x: d, y: current.sales[i] }})),
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 5
                }});
            }}

            if (showPrevYear && currentSalesData.prev_year?.dates?.length > 0) {{
                const prev = currentSalesData.prev_year;
                datasets.push({{
                    label: '前年度',
                    data: prev.dates.map((d, i) => ({{ x: d, y: prev.sales[i] }})),
                    borderColor: '#888',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.3,
                    pointRadius: 3
                }});
            }}

            const ctx = document.getElementById('salesTrendChart').getContext('2d');
            if (salesTrendChart) salesTrendChart.destroy();

            salesTrendChart = new Chart(ctx, {{
                type: 'line',
                data: {{ datasets }},
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
            event.target.classList.add('active');
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
                        ticks: {{ callback: v => '¥' + (v / 1000000).toFixed(1) + 'M' }}
                    }}
                }}
            }}
        }});
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
