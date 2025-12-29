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
            'top_schools': get_top_schools(db_path, year)
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
        
        <div class="chart-card">
            <h3>📈 月別売上推移</h3>
            <canvas id="monthlyChart"></canvas>
        </div>
        
        <div class="chart-card">
            <h3>🏢 事業所別売上</h3>
            <canvas id="branchChart"></canvas>
        </div>
        
        <div class="chart-card">
            <h3>🏫 学校別売上 TOP10</h3>
            <canvas id="schoolChart"></canvas>
        </div>
    </div>
    
    <script>
        // 全年度のデータ
        const allYearsData = {json.dumps(all_years_data, ensure_ascii=False, indent=2)};
        
        let monthlyChart, branchChart, schoolChart;
        
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
            updateBranchChart(data.branch);
            updateSchoolChart(data.top_schools);
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
        
        // 初期表示
        const initialYear = parseInt(document.getElementById('yearSelect').value);
        const initialData = allYearsData[initialYear];
        updateMonthlyChart(initialData.monthly);
        updateBranchChart(initialData.branch);
        updateSchoolChart(initialData.top_schools);
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
