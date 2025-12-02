#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上分析システム - 会員率推移グラフページ生成

インタラクティブな会員率推移グラフページを生成する
"""

import json
from datetime import datetime
from pathlib import Path
from member_rate_chart import (
    get_filter_options,
    get_member_rate_trend_by_school,
    get_member_rate_trend_by_attribute
)


def generate_member_rate_page(db_path=None, output_path=None):
    """会員率推移グラフページを生成"""

    # フィルターオプション取得
    options = get_filter_options(db_path)

    # 全データを事前に取得してJSONとして埋め込む
    all_school_data = {}
    for school in options['schools']:
        # 全学年まとめ
        data_all = get_member_rate_trend_by_school(school['id'], by_grade=False, db_path=db_path)
        if data_all:
            all_school_data[f"school_{school['id']}_all"] = data_all

        # 学年別
        data_grade = get_member_rate_trend_by_school(school['id'], by_grade=True, db_path=db_path)
        if data_grade:
            all_school_data[f"school_{school['id']}_grade"] = data_grade

    # 属性別データ
    all_attribute_data = {}
    for attr in options['attributes']:
        data = get_member_rate_trend_by_attribute(attr, db_path=db_path)
        if data:
            all_attribute_data[f"attr_{attr}"] = data

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>会員率推移グラフ - スクールフォト分析</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@2.0.0/dist/chartjs-plugin-annotation.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', 'Hiragino Sans', 'Meiryo', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{
            background: white;
            border-radius: 16px;
            padding: 24px 32px;
            margin-bottom: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .header h1 {{ font-size: 24px; color: #1a1a2e; margin-bottom: 8px; }}
        .header .back-link {{ color: #667eea; text-decoration: none; font-size: 14px; }}
        .header .back-link:hover {{ text-decoration: underline; }}
        .filter-section {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .filter-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            align-items: flex-end;
            margin-bottom: 16px;
        }}
        .filter-group {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .filter-group label {{
            font-size: 12px;
            color: #666;
            font-weight: 600;
        }}
        .filter-group select, .filter-group input {{
            padding: 10px 14px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            font-size: 14px;
            min-width: 200px;
            transition: border-color 0.3s;
        }}
        .filter-group select:focus, .filter-group input:focus {{
            outline: none;
            border-color: #667eea;
        }}
        .btn {{
            padding: 10px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .btn-primary {{
            background: #667eea;
            color: white;
        }}
        .btn-primary:hover {{ background: #5a6fd6; }}
        .btn-secondary {{
            background: #e2e8f0;
            color: #475569;
        }}
        .btn-secondary:hover {{ background: #cbd5e1; }}
        .option-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 24px;
            align-items: center;
        }}
        .option-group {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .option-group input[type="radio"],
        .option-group input[type="checkbox"] {{
            width: 18px;
            height: 18px;
            accent-color: #667eea;
        }}
        .option-group label {{
            font-size: 14px;
            color: #333;
            cursor: pointer;
        }}
        .chart-section {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .chart-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        .chart-header h3 {{ font-size: 18px; color: #1a1a2e; }}
        .chart-info {{
            display: flex;
            gap: 16px;
            font-size: 13px;
            color: #666;
        }}
        .chart-container {{
            position: relative;
            height: 400px;
        }}
        .legend-custom {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid #e2e8f0;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
        }}
        .legend-line {{
            width: 30px;
            height: 3px;
            border-radius: 2px;
        }}
        .legend-line.dashed {{
            background: repeating-linear-gradient(90deg, #888, #888 5px, transparent 5px, transparent 10px);
        }}
        .legend-line.dotted {{
            background: repeating-linear-gradient(90deg, #aaa, #aaa 2px, transparent 2px, transparent 6px);
        }}
        .data-table {{
            margin-top: 24px;
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .data-table th {{
            text-align: left;
            padding: 12px 8px;
            background: #f8fafc;
            border-bottom: 2px solid #e2e8f0;
            font-weight: 600;
            color: #475569;
        }}
        .data-table td {{
            padding: 10px 8px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .no-data {{
            text-align: center;
            padding: 60px;
            color: #888;
        }}
        .footer {{
            text-align: center;
            color: rgba(255,255,255,0.7);
            padding: 20px;
            font-size: 13px;
        }}
        .hidden {{ display: none; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <a href="javascript:history.back()" class="back-link">← ダッシュボードに戻る</a>
            <h1>会員率推移グラフ</h1>
        </div>

        <div class="filter-section">
            <div class="filter-row">
                <div class="filter-group">
                    <label>属性</label>
                    <select id="filterAttribute">
                        <option value="">-- 全て --</option>
                        {generate_options(options['attributes'])}
                    </select>
                </div>
                <div class="filter-group">
                    <label>写真館</label>
                    <select id="filterStudio">
                        <option value="">-- 全て --</option>
                        {generate_options(options['studios'])}
                    </select>
                </div>
                <div class="filter-group">
                    <label>学校名</label>
                    <select id="filterSchool">
                        <option value="">-- 属性/写真館で絞り込み --</option>
                    </select>
                </div>
                <button class="btn btn-primary" onclick="search()">検索</button>
                <button class="btn btn-secondary" onclick="resetFilters()">リセット</button>
            </div>
            <div class="option-row">
                <div class="option-group" id="gradeOptionGroup">
                    <input type="radio" name="gradeMode" id="gradeAll" value="all" checked>
                    <label for="gradeAll">全学年まとめて</label>
                    <input type="radio" name="gradeMode" id="gradeEach" value="each">
                    <label for="gradeEach">学年別に表示</label>
                </div>
                <div class="option-group">
                    <input type="checkbox" id="showPrevYear" checked>
                    <label for="showPrevYear">前年度を表示</label>
                </div>
                <div class="option-group">
                    <input type="checkbox" id="showExpected" checked>
                    <label for="showExpected">期待値（属性平均）を表示</label>
                </div>
                <button class="btn btn-secondary" onclick="exportCSV()">CSVエクスポート</button>
            </div>
        </div>

        <div class="chart-section">
            <div class="chart-header">
                <h3 id="chartTitle">学校または属性を選択してください</h3>
                <div class="chart-info">
                    <span id="chartInfo"></span>
                </div>
            </div>
            <div class="chart-container">
                <canvas id="memberRateChart"></canvas>
            </div>
            <div class="legend-custom" id="customLegend"></div>
        </div>

        <div class="chart-section" id="tableSection" style="display:none;">
            <h3>データ一覧</h3>
            <table class="data-table" id="dataTable">
                <thead></thead>
                <tbody></tbody>
            </table>
        </div>

        <div class="footer">
            Generated by スクールフォト売上分析システム | {datetime.now().strftime('%Y-%m-%d %H:%M')}
        </div>
    </div>

    <script>
        // データ埋め込み
        const schoolsData = {json.dumps(options['schools'], ensure_ascii=False)};
        const allSchoolData = {json.dumps(all_school_data, ensure_ascii=False)};
        const allAttributeData = {json.dumps(all_attribute_data, ensure_ascii=False)};

        let chart = null;
        let currentData = null;

        // 属性・写真館でフィルタリング
        document.getElementById('filterAttribute').addEventListener('change', filterSchools);
        document.getElementById('filterStudio').addEventListener('change', filterSchools);

        function filterSchools() {{
            const attr = document.getElementById('filterAttribute').value;
            const studio = document.getElementById('filterStudio').value;
            const schoolSelect = document.getElementById('filterSchool');

            // 学校リストをフィルタリング
            let filtered = schoolsData;
            if (attr) {{
                filtered = filtered.filter(s => s.attribute === attr);
            }}
            if (studio) {{
                filtered = filtered.filter(s => s.studio === studio);
            }}

            // プルダウン更新
            schoolSelect.innerHTML = '<option value="">-- 属性/写真館で絞り込み --</option>';
            filtered.forEach(s => {{
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.name;
                schoolSelect.appendChild(opt);
            }});
        }}

        function resetFilters() {{
            document.getElementById('filterAttribute').value = '';
            document.getElementById('filterStudio').value = '';
            document.getElementById('filterSchool').innerHTML = '<option value="">-- 属性/写真館で絞り込み --</option>';
            document.getElementById('gradeAll').checked = true;
            document.getElementById('showPrevYear').checked = true;
            document.getElementById('showExpected').checked = true;
        }}

        function search() {{
            const attr = document.getElementById('filterAttribute').value;
            const studio = document.getElementById('filterStudio').value;
            const schoolId = document.getElementById('filterSchool').value;
            const gradeMode = document.querySelector('input[name="gradeMode"]:checked').value;

            if (schoolId) {{
                // 学校単位
                const key = gradeMode === 'each' ? `school_${{schoolId}}_grade` : `school_${{schoolId}}_all`;
                currentData = allSchoolData[key];
                document.getElementById('gradeOptionGroup').style.display = 'flex';
            }} else if (attr) {{
                // 属性単位
                const key = `attr_${{attr}}`;
                currentData = allAttributeData[key];
                document.getElementById('gradeOptionGroup').style.display = 'none';
            }} else {{
                alert('属性または学校を選択してください');
                return;
            }}

            if (currentData) {{
                renderChart();
            }} else {{
                alert('データが見つかりませんでした');
            }}
        }}

        function renderChart() {{
            if (!currentData) return;

            const showPrevYear = document.getElementById('showPrevYear').checked;
            const showExpected = document.getElementById('showExpected').checked;

            // タイトル更新
            const title = currentData.school_name || `${{currentData.attribute}}（${{currentData.school_count}}校平均）`;
            document.getElementById('chartTitle').textContent = title;
            document.getElementById('chartInfo').textContent = currentData.attribute ? `属性: ${{currentData.attribute}}` : '';

            // データセット構築
            const datasets = [];
            const annotations = {{}};
            let allDates = [];

            if (currentData.by_grade && typeof currentData.current_year === 'object' && !Array.isArray(currentData.current_year)) {{
                // 学年別
                const colors = ['#667eea', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];
                let colorIdx = 0;

                for (const [grade, data] of Object.entries(currentData.current_year)) {{
                    if (data.dates && data.dates.length > 0) {{
                        datasets.push({{
                            label: `${{grade}}（今年度）`,
                            data: data.dates.map((d, i) => ({{ x: d, y: data.rates[i] }})),
                            borderColor: colors[colorIdx % colors.length],
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.3,
                            pointRadius: 4
                        }});
                        allDates = allDates.concat(data.dates);
                    }}

                    // 前年度
                    if (showPrevYear && currentData.prev_year && currentData.prev_year[grade]) {{
                        const prevData = currentData.prev_year[grade];
                        if (prevData.dates && prevData.dates.length > 0) {{
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
                    }}
                    colorIdx++;
                }}
            }} else {{
                // 全学年まとめ or 属性
                const current = currentData.current_year;
                if (current && current.dates && current.dates.length > 0) {{
                    datasets.push({{
                        label: '今年度',
                        data: current.dates.map((d, i) => ({{ x: d, y: current.rates[i] }})),
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 5
                    }});
                    allDates = allDates.concat(current.dates);
                }}

                // 前年度
                if (showPrevYear && currentData.prev_year) {{
                    const prev = currentData.prev_year;
                    if (prev.dates && prev.dates.length > 0) {{
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

                // 期待値（属性平均）
                if (showExpected && currentData.expected && currentData.expected.current_year) {{
                    const exp = currentData.expected.current_year;
                    if (exp.dates && exp.dates.length > 0) {{
                        datasets.push({{
                            label: '期待値（属性平均）',
                            data: exp.dates.map((d, i) => ({{ x: d, y: exp.rates[i] }})),
                            borderColor: '#aaa',
                            backgroundColor: 'transparent',
                            borderWidth: 1,
                            borderDash: [2, 4],
                            tension: 0.3,
                            pointRadius: 0
                        }});
                    }}
                }}
            }}

            // イベントアノテーション
            if (currentData.events && currentData.events.length > 0) {{
                currentData.events.forEach((evt, idx) => {{
                    if (evt.date && allDates.includes(evt.date)) {{
                        annotations[`event_${{idx}}`] = {{
                            type: 'line',
                            xMin: evt.date,
                            xMax: evt.date,
                            borderColor: 'rgba(239, 68, 68, 0.5)',
                            borderWidth: 2,
                            borderDash: [3, 3],
                            label: {{
                                display: true,
                                content: evt.name.substring(0, 15),
                                position: 'start',
                                backgroundColor: 'rgba(239, 68, 68, 0.8)',
                                color: 'white',
                                font: {{ size: 10 }}
                            }}
                        }};
                    }}
                }});
            }}

            // チャート描画
            const ctx = document.getElementById('memberRateChart').getContext('2d');

            if (chart) {{
                chart.destroy();
            }}

            chart = new Chart(ctx, {{
                type: 'line',
                data: {{ datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{
                        intersect: false,
                        mode: 'index'
                    }},
                    plugins: {{
                        legend: {{
                            display: true,
                            position: 'top'
                        }},
                        annotation: {{
                            annotations: annotations
                        }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    return `${{context.dataset.label}}: ${{context.parsed.y}}%`;
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            type: 'category',
                            title: {{
                                display: true,
                                text: '日付'
                            }}
                        }},
                        y: {{
                            min: 0,
                            max: 100,
                            title: {{
                                display: true,
                                text: '会員率 (%)'
                            }},
                            ticks: {{
                                callback: function(value) {{
                                    return value + '%';
                                }}
                            }}
                        }}
                    }}
                }}
            }});

            // テーブル表示
            renderTable();
        }}

        function renderTable() {{
            if (!currentData) return;

            const tableSection = document.getElementById('tableSection');
            const thead = document.querySelector('#dataTable thead');
            const tbody = document.querySelector('#dataTable tbody');

            tableSection.style.display = 'block';
            thead.innerHTML = '';
            tbody.innerHTML = '';

            if (currentData.by_grade && typeof currentData.current_year === 'object') {{
                // 学年別テーブル
                const grades = Object.keys(currentData.current_year);
                const headerRow = document.createElement('tr');
                headerRow.innerHTML = '<th>日付</th><th>年度</th>' + grades.map(g => `<th>${{g}}</th>`).join('');
                thead.appendChild(headerRow);

                // 今年度
                const firstGrade = grades[0];
                if (currentData.current_year[firstGrade] && currentData.current_year[firstGrade].dates) {{
                    currentData.current_year[firstGrade].dates.forEach((date, i) => {{
                        const row = document.createElement('tr');
                        let cells = `<td>${{date}}</td><td>今年度</td>`;
                        grades.forEach(g => {{
                            const rate = currentData.current_year[g]?.rates?.[i] ?? '-';
                            cells += `<td>${{rate}}%</td>`;
                        }});
                        row.innerHTML = cells;
                        tbody.appendChild(row);
                    }});
                }}
            }} else {{
                // 全学年まとめ
                const headerRow = document.createElement('tr');
                headerRow.innerHTML = '<th>日付</th><th>年度</th><th>会員率</th><th>期待値</th>';
                thead.appendChild(headerRow);

                // 今年度
                const current = currentData.current_year;
                const expCurrent = currentData.expected?.current_year;
                if (current && current.dates) {{
                    current.dates.forEach((date, i) => {{
                        const row = document.createElement('tr');
                        const exp = expCurrent?.rates?.[i] ?? '-';
                        row.innerHTML = `<td>${{date}}</td><td>今年度</td><td>${{current.rates[i]}}%</td><td>${{exp}}%</td>`;
                        tbody.appendChild(row);
                    }});
                }}

                // 前年度
                const prev = currentData.prev_year;
                const expPrev = currentData.expected?.prev_year;
                if (prev && prev.dates) {{
                    prev.dates.forEach((date, i) => {{
                        const row = document.createElement('tr');
                        const exp = expPrev?.rates?.[i] ?? '-';
                        row.innerHTML = `<td>${{date}}</td><td>前年度</td><td>${{prev.rates[i]}}%</td><td>${{exp}}%</td>`;
                        tbody.appendChild(row);
                    }});
                }}
            }}
        }}

        function exportCSV() {{
            if (!currentData) {{
                alert('先にデータを検索してください');
                return;
            }}

            let csvContent = '';
            const title = currentData.school_name || currentData.attribute;

            if (currentData.by_grade && typeof currentData.current_year === 'object') {{
                // 学年別
                const grades = Object.keys(currentData.current_year);
                csvContent += '日付,年度,' + grades.join(',') + '\\n';

                const firstGrade = grades[0];
                if (currentData.current_year[firstGrade]?.dates) {{
                    currentData.current_year[firstGrade].dates.forEach((date, i) => {{
                        let row = `${{date}},今年度`;
                        grades.forEach(g => {{
                            row += ',' + (currentData.current_year[g]?.rates?.[i] ?? '');
                        }});
                        csvContent += row + '\\n';
                    }});
                }}

                if (currentData.prev_year && currentData.prev_year[firstGrade]?.dates) {{
                    currentData.prev_year[firstGrade].dates.forEach((date, i) => {{
                        let row = `${{date}},前年度`;
                        grades.forEach(g => {{
                            row += ',' + (currentData.prev_year[g]?.rates?.[i] ?? '');
                        }});
                        csvContent += row + '\\n';
                    }});
                }}
            }} else {{
                // 全学年まとめ
                csvContent += '日付,年度,会員率,期待値\\n';

                const current = currentData.current_year;
                const expCurrent = currentData.expected?.current_year;
                if (current?.dates) {{
                    current.dates.forEach((date, i) => {{
                        csvContent += `${{date}},今年度,${{current.rates[i]}},${{expCurrent?.rates?.[i] ?? ''}}\\n`;
                    }});
                }}

                const prev = currentData.prev_year;
                const expPrev = currentData.expected?.prev_year;
                if (prev?.dates) {{
                    prev.dates.forEach((date, i) => {{
                        csvContent += `${{date}},前年度,${{prev.rates[i]}},${{expPrev?.rates?.[i] ?? ''}}\\n`;
                    }});
                }}
            }}

            // ダウンロード
            const blob = new Blob(['\\uFEFF' + csvContent], {{ type: 'text/csv;charset=utf-8;' }});
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `会員率推移_${{title}}_${{new Date().toISOString().slice(0, 10)}}.csv`;
            link.click();
        }}

        // オプション変更時に再描画
        document.getElementById('showPrevYear').addEventListener('change', renderChart);
        document.getElementById('showExpected').addEventListener('change', renderChart);
        document.querySelectorAll('input[name="gradeMode"]').forEach(el => {{
            el.addEventListener('change', search);
        }});
    </script>
</body>
</html>
'''

    # ファイル出力
    if output_path is None:
        output_path = Path(__file__).parent / "member_rate_chart.html"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


def generate_options(items):
    """selectタグのoption生成"""
    return '\n'.join([f'<option value="{item}">{item}</option>' for item in items])


if __name__ == '__main__':
    import sys
    output = sys.argv[1] if len(sys.argv) > 1 else None
    path = generate_member_rate_page(output_path=output)
    print(f"会員率推移グラフページを生成しました: {path}")
