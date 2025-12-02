#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上分析ダッシュボード生成スクリプト

使い方:
    python schoolphoto_dashboard.py <売上報告書.xlsx>
    
出力:
    同じフォルダに「売上分析ダッシュボード_YYYYMMDD.html」を生成
"""

import pandas as pd
import numpy as np
import sys
import os
import re
from datetime import datetime
from pathlib import Path


# ============================================
# 設定（必要に応じて変更）
# ============================================
class Config:
    # アラート閾値
    MEMBER_RATE_WARNING = 0.5      # 会員率50%未満で警告
    MEMBER_RATE_DANGER = 0.3       # 会員率30%未満で危険
    YOY_DECLINE_WARNING = -0.2     # 前年比20%減で警告
    YOY_DECLINE_DANGER = -0.3      # 前年比30%減で危険
    BUDGET_WARNING = 0.8           # 予算達成率80%未満で警告
    
    # 表示件数
    TOP_N_ALERTS = 20              # アラート表示件数


# ============================================
# データ読み込み関数
# ============================================
def load_sales_summary(xlsx):
    """売上シートから月別サマリーを読み込み"""
    df = pd.read_excel(xlsx, sheet_name='売上', header=None)
    
    result = {'2025': {}, '2024': {}, '2023': {}}
    
    # 2025年度データ（行3-12付近）
    for i, row in df.iterrows():
        if pd.notna(row[1]) and '2025年度' in str(row[1]):
            # ヘッダー行を探す
            header_row = i + 1
            data_start = i + 2
            break
    
    # 月のカラム位置を取得
    header = df.iloc[header_row]
    months_2025 = []
    for col_idx, val in enumerate(header):
        if pd.notna(val) and '月' in str(val):
            months_2025.append((col_idx, str(val).replace('月', '')))
    
    # 各指標を取得
    for i in range(data_start, data_start + 10):
        row = df.iloc[i]
        label = str(row[1]) if pd.notna(row[1]) else ''
        
        if '総売上額' in label and '内' not in label:
            result['2025']['総売上額'] = {m[1]: row[m[0]] for m in months_2025 if pd.notna(row[m[0]])}
        elif '直取引' in label:
            result['2025']['直取引'] = {m[1]: row[m[0]] for m in months_2025 if pd.notna(row[m[0]])}
        elif '写真館・学校' in label:
            result['2025']['写真館・学校'] = {m[1]: row[m[0]] for m in months_2025 if pd.notna(row[m[0]])}
        elif 'イベント実施学校数' in label:
            result['2025']['実施学校数'] = {m[1]: row[m[0]] for m in months_2025 if pd.notna(row[m[0]])}
        elif '予算比' in label:
            result['2025']['予算比'] = {m[1]: row[m[0]] for m in months_2025 if pd.notna(row[m[0]])}
        elif '昨年比' in label:
            result['2025']['昨年比'] = {m[1]: row[m[0]] for m in months_2025 if pd.notna(row[m[0]])}
        elif '予算' == label.strip():
            result['2025']['予算'] = {m[1]: row[m[0]] for m in months_2025 if pd.notna(row[m[0]])}
    
    # 2024年度データも同様に取得
    for i, row in df.iterrows():
        if pd.notna(row[1]) and '2024年度' in str(row[1]):
            header_row = i + 1
            data_start = i + 2
            break
    
    header = df.iloc[header_row]
    months_2024 = []
    for col_idx, val in enumerate(header):
        if pd.notna(val) and '月' in str(val):
            months_2024.append((col_idx, str(val).replace('月', '')))
    
    for i in range(data_start, min(data_start + 10, len(df))):
        row = df.iloc[i]
        label = str(row[1]) if pd.notna(row[1]) else ''
        
        if '総売上額' in label and '内' not in label:
            result['2024']['総売上額'] = {m[1]: row[m[0]] for m in months_2024 if pd.notna(row[m[0]])}
    
    return result


def load_member_rates(xlsx):
    """会員率シートから学校別会員率を読み込み"""
    df = pd.read_excel(xlsx, sheet_name='会員率', header=None)
    
    # ヘッダー行を探す
    for i, row in df.iterrows():
        if pd.notna(row[1]) and '学校ID' in str(row[1]):
            header_row = i
            break
    
    # データ部分を抽出
    df_data = df.iloc[header_row + 1:].copy()
    df_data.columns = df.iloc[header_row]
    df_data = df_data.reset_index(drop=True)
    
    # カラム名を正規化
    col_map = {}
    for col in df_data.columns:
        if pd.isna(col):
            continue
        col_str = str(col)
        if '学校ID' in col_str:
            col_map[col] = '学校ID'
        elif '学校名' in col_str:
            col_map[col] = '学校名'
        elif '属性' in col_str:
            col_map[col] = '属性'
        elif '写真館' in col_str:
            col_map[col] = '写真館名'
        elif '生徒数' in col_str:
            col_map[col] = '生徒数'
        elif '有効会員' in col_str:
            col_map[col] = '会員数'
        elif '会員率' in col_str:
            col_map[col] = '会員率'
        elif '学年' in col_str and 'お子様' in col_str:
            col_map[col] = '学年'
    
    df_data = df_data.rename(columns=col_map)
    
    # 必要なカラムのみ抽出
    needed_cols = ['学校ID', '学校名', '属性', '写真館名', '生徒数', '会員数', '会員率', '学年']
    available_cols = [c for c in needed_cols if c in df_data.columns]
    df_data = df_data[available_cols].copy()
    
    # 数値変換
    for col in ['生徒数', '会員数', '会員率']:
        if col in df_data.columns:
            df_data[col] = pd.to_numeric(df_data[col], errors='coerce')
    
    # 生徒数0以外を対象に、学校単位で集計
    df_valid = df_data[df_data['生徒数'] > 0].copy()
    
    school_summary = df_valid.groupby(['学校名', '属性', '写真館名']).agg({
        '生徒数': 'sum',
        '会員数': 'sum'
    }).reset_index()
    school_summary['会員率'] = school_summary['会員数'] / school_summary['生徒数']
    
    return school_summary


def load_school_sales_2025(xlsx):
    """学校別（2025年度）シートから売上を読み込み"""
    df = pd.read_excel(xlsx, sheet_name='学校別（2025年度）', header=None)
    
    # ヘッダー行を探す
    for i, row in df.iterrows():
        if pd.notna(row[1]) and '担当者' in str(row[1]):
            header_row = i
            break
    
    df_data = df.iloc[header_row + 1:].copy()
    df_data.columns = df.iloc[header_row]
    df_data = df_data.reset_index(drop=True)
    
    # カラム名を正規化
    col_map = {}
    month_cols = []
    for col in df_data.columns:
        if pd.isna(col):
            continue
        col_str = str(col)
        if '担当者' in col_str:
            col_map[col] = '担当者'
        elif '写真館' in col_str:
            col_map[col] = '写真館'
        elif '学校名' in col_str:
            col_map[col] = '学校名'
        elif '総計' in col_str:
            col_map[col] = '総計'
        elif '月分' in col_str:
            # 2025年4月分 → 4月
            month = re.search(r'(\d+)月', col_str)
            if month:
                new_name = f'{month.group(1)}月'
                col_map[col] = new_name
                month_cols.append(new_name)
    
    df_data = df_data.rename(columns=col_map)
    
    # 総計を数値に
    if '総計' in df_data.columns:
        df_data['総計'] = pd.to_numeric(df_data['総計'], errors='coerce')
    
    # NaN行を除去
    df_data = df_data.dropna(subset=['学校名'])
    
    return df_data, month_cols


def load_school_comparison(xlsx):
    """学校別売り上げ比較シートを読み込み"""
    df = pd.read_excel(xlsx, sheet_name='学校別売り上げ比較', header=None)
    
    # ヘッダー行を探す
    for i, row in df.iterrows():
        if pd.notna(row[1]) and '担当者' in str(row[1]):
            header_row = i
            break
    
    df_data = df.iloc[header_row + 1:].copy()
    df_data.columns = df.iloc[header_row]
    df_data = df_data.reset_index(drop=True)
    
    # カラム名を正規化
    col_map = {}
    for col in df_data.columns:
        if pd.isna(col):
            continue
        col_str = str(col)
        if '担当者' in col_str:
            col_map[col] = '担当者'
        elif '写真館' in col_str:
            col_map[col] = '写真館'
        elif '学校名' in col_str:
            col_map[col] = '学校名'
        elif '2024' in col_str:
            col_map[col] = '2024年度売上'
        elif '2023' in col_str:
            col_map[col] = '2023年度売上'
        elif '差額' in col_str:
            col_map[col] = '差額'
    
    df_data = df_data.rename(columns=col_map)
    
    # 数値変換
    for col in ['2024年度売上', '2023年度売上', '差額']:
        if col in df_data.columns:
            df_data[col] = pd.to_numeric(df_data[col], errors='coerce')
    
    df_data = df_data.dropna(subset=['学校名'])
    
    return df_data


# ============================================
# 分析関数
# ============================================
def analyze_alerts(member_df, school_2025_df, comparison_df, config=Config):
    """各種アラートを検出"""
    alerts = {
        'member_rate_low': [],      # 会員率低い
        'yoy_decline': [],          # 前年比大幅減
        'no_sales_2025': [],        # 2025年度売上ゼロ
    }
    
    # 1. 会員率アラート
    if member_df is not None and len(member_df) > 0:
        low_rate = member_df[member_df['会員率'] < config.MEMBER_RATE_WARNING].copy()
        low_rate = low_rate.sort_values('会員率')
        for _, row in low_rate.head(config.TOP_N_ALERTS).iterrows():
            level = 'danger' if row['会員率'] < config.MEMBER_RATE_DANGER else 'warning'
            alerts['member_rate_low'].append({
                '学校名': row['学校名'],
                '属性': row.get('属性', ''),
                '会員率': row['会員率'],
                '生徒数': row['生徒数'],
                '会員数': row['会員数'],
                'level': level
            })
    
    # 2. 前年比大幅減アラート
    if comparison_df is not None and len(comparison_df) > 0:
        comp = comparison_df.copy()
        comp = comp[(comp['2024年度売上'] > 0) | (comp['2023年度売上'] > 0)]
        comp['変化率'] = comp['差額'] / comp['2023年度売上'].replace(0, np.nan)
        decline = comp[comp['変化率'] < config.YOY_DECLINE_WARNING].copy()
        decline = decline.sort_values('変化率')
        for _, row in decline.head(config.TOP_N_ALERTS).iterrows():
            level = 'danger' if row['変化率'] < config.YOY_DECLINE_DANGER else 'warning'
            alerts['yoy_decline'].append({
                '学校名': row['学校名'],
                '担当者': row.get('担当者', ''),
                '2024年度売上': row['2024年度売上'],
                '2023年度売上': row['2023年度売上'],
                '差額': row['差額'],
                '変化率': row['変化率'],
                'level': level
            })
    
    # 3. 2025年度売上ゼロ（前年実績ありの学校）
    if school_2025_df is not None and comparison_df is not None:
        zero_2025 = school_2025_df[school_2025_df['総計'] == 0]['学校名'].tolist()
        had_sales_2024 = comparison_df[comparison_df['2024年度売上'] > 0]['学校名'].tolist()
        no_sales_schools = set(zero_2025) & set(had_sales_2024)
        
        for school in list(no_sales_schools)[:config.TOP_N_ALERTS]:
            info = comparison_df[comparison_df['学校名'] == school].iloc[0]
            alerts['no_sales_2025'].append({
                '学校名': school,
                '担当者': info.get('担当者', ''),
                '2024年度売上': info['2024年度売上'],
                'level': 'danger'
            })
    
    return alerts


# ============================================
# HTML生成関数
# ============================================
def generate_html(sales_summary, member_df, school_2025_df, comparison_df, alerts, report_date, config=Config):
    """HTMLダッシュボードを生成"""
    
    # 2025年度サマリー計算
    sales_2025 = sales_summary.get('2025', {})
    total_sales = sum(sales_2025.get('総売上額', {}).values()) if sales_2025.get('総売上額') else 0
    total_budget = sum(sales_2025.get('予算', {}).values()) if sales_2025.get('予算') else 0
    avg_budget_rate = np.mean(list(sales_2025.get('予算比', {}).values())) if sales_2025.get('予算比') else 0
    avg_yoy_rate = np.mean(list(sales_2025.get('昨年比', {}).values())) if sales_2025.get('昨年比') else 0
    
    # 月別データ（グラフ用）
    months_order = ['4', '5', '6', '7', '8', '9', '10', '11', '12', '1', '2', '3']
    sales_by_month = sales_2025.get('総売上額', {})
    budget_by_month = sales_2025.get('予算', {})
    yoy_by_month = sales_2025.get('昨年比', {})
    
    months_data = []
    sales_data = []
    budget_data = []
    yoy_data = []
    
    for m in months_order:
        if m in sales_by_month:
            months_data.append(f'{m}月')
            sales_data.append(sales_by_month[m])
            budget_data.append(budget_by_month.get(m, 0))
            yoy_data.append(yoy_by_month.get(m, 0) * 100 if m in yoy_by_month else None)
    
    # アラート件数
    alert_counts = {
        'member': len(alerts['member_rate_low']),
        'yoy': len(alerts['yoy_decline']),
        'no_sales': len(alerts['no_sales_2025'])
    }
    total_alerts = sum(alert_counts.values())
    
    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>スクールフォト売上分析ダッシュボード - {report_date}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', 'Hiragino Sans', 'Meiryo', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            border-radius: 16px;
            padding: 24px 32px;
            margin-bottom: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            font-size: 28px;
            color: #1a1a2e;
            margin-bottom: 8px;
        }}
        .header .date {{
            color: #666;
            font-size: 14px;
        }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .card-title {{
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .card-value {{
            font-size: 32px;
            font-weight: 700;
            color: #1a1a2e;
        }}
        .card-value.success {{ color: #10b981; }}
        .card-value.warning {{ color: #f59e0b; }}
        .card-value.danger {{ color: #ef4444; }}
        .card-sub {{
            font-size: 13px;
            color: #888;
            margin-top: 8px;
        }}
        .chart-section {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }}
        @media (max-width: 1024px) {{
            .chart-section {{
                grid-template-columns: 1fr;
            }}
        }}
        .chart-card {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        .chart-card h3 {{
            font-size: 18px;
            color: #1a1a2e;
            margin-bottom: 20px;
        }}
        .alert-section {{
            margin-bottom: 24px;
        }}
        .alert-tabs {{
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
        }}
        .alert-tab {{
            padding: 12px 24px;
            border-radius: 8px;
            background: rgba(255,255,255,0.2);
            color: white;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.3s;
            border: none;
        }}
        .alert-tab:hover, .alert-tab.active {{
            background: white;
            color: #1a1a2e;
        }}
        .alert-tab .badge {{
            background: #ef4444;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            margin-left: 8px;
        }}
        .alert-content {{
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            display: none;
        }}
        .alert-content.active {{
            display: block;
        }}
        .alert-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .alert-table th {{
            text-align: left;
            padding: 12px;
            background: #f8fafc;
            border-bottom: 2px solid #e2e8f0;
            font-weight: 600;
            color: #475569;
        }}
        .alert-table td {{
            padding: 12px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .alert-table tr:hover {{
            background: #f8fafc;
        }}
        .status-badge {{
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }}
        .status-badge.danger {{
            background: #fef2f2;
            color: #dc2626;
        }}
        .status-badge.warning {{
            background: #fffbeb;
            color: #d97706;
        }}
        .percent {{
            font-weight: 600;
        }}
        .percent.negative {{ color: #ef4444; }}
        .percent.positive {{ color: #10b981; }}
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
            <h1>📊 スクールフォト売上分析ダッシュボード</h1>
            <p class="date">レポート日: {report_date} | データ期間: 2025年度</p>
        </div>
        
        <div class="summary-cards">
            <div class="card">
                <div class="card-title">2025年度 累計売上</div>
                <div class="card-value">¥{total_sales:,.0f}</div>
                <div class="card-sub">予算 ¥{total_budget:,.0f}</div>
            </div>
            <div class="card">
                <div class="card-title">平均予算達成率</div>
                <div class="card-value {'success' if avg_budget_rate >= 1 else 'warning' if avg_budget_rate >= 0.8 else 'danger'}">{avg_budget_rate*100:.1f}%</div>
                <div class="card-sub">目標: 100%</div>
            </div>
            <div class="card">
                <div class="card-title">平均昨年比</div>
                <div class="card-value {'success' if avg_yoy_rate >= 1 else 'warning' if avg_yoy_rate >= 0.8 else 'danger'}">{avg_yoy_rate*100:.1f}%</div>
                <div class="card-sub">{'↑ 成長' if avg_yoy_rate >= 1 else '↓ 減少'}</div>
            </div>
            <div class="card">
                <div class="card-title">要対応アラート</div>
                <div class="card-value {'danger' if total_alerts > 10 else 'warning' if total_alerts > 0 else 'success'}">{total_alerts}件</div>
                <div class="card-sub">会員率:{alert_counts['member']} / 売上減:{alert_counts['yoy']} / 未販売:{alert_counts['no_sales']}</div>
            </div>
        </div>
        
        <div class="chart-section">
            <div class="chart-card">
                <h3>📈 月別売上推移（2025年度）</h3>
                <canvas id="salesChart"></canvas>
            </div>
            <div class="chart-card">
                <h3>📊 昨年比推移</h3>
                <canvas id="yoyChart"></canvas>
            </div>
        </div>
        
        <div class="alert-section">
            <div class="alert-tabs">
                <button class="alert-tab active" onclick="showAlert('member')">
                    会員率低下 <span class="badge">{alert_counts['member']}</span>
                </button>
                <button class="alert-tab" onclick="showAlert('yoy')">
                    売上大幅減 <span class="badge">{alert_counts['yoy']}</span>
                </button>
                <button class="alert-tab" onclick="showAlert('nosales')">
                    2025年度未販売 <span class="badge">{alert_counts['no_sales']}</span>
                </button>
            </div>
            
            <div id="alert-member" class="alert-content active">
                <table class="alert-table">
                    <thead>
                        <tr>
                            <th>学校名</th>
                            <th>属性</th>
                            <th>生徒数</th>
                            <th>会員数</th>
                            <th>会員率</th>
                            <th>状態</th>
                        </tr>
                    </thead>
                    <tbody>
'''
    
    # 会員率アラートテーブル
    for alert in alerts['member_rate_low']:
        status_class = alert['level']
        status_text = '危険' if status_class == 'danger' else '警告'
        html += f'''
                        <tr>
                            <td>{alert['学校名']}</td>
                            <td>{alert['属性']}</td>
                            <td>{alert['生徒数']:.0f}</td>
                            <td>{alert['会員数']:.0f}</td>
                            <td class="percent negative">{alert['会員率']*100:.1f}%</td>
                            <td><span class="status-badge {status_class}">{status_text}</span></td>
                        </tr>
'''
    
    if not alerts['member_rate_low']:
        html += '<tr><td colspan="6" style="text-align:center;color:#888;padding:40px;">アラートはありません 🎉</td></tr>'
    
    html += '''
                    </tbody>
                </table>
            </div>
            
            <div id="alert-yoy" class="alert-content">
                <table class="alert-table">
                    <thead>
                        <tr>
                            <th>学校名</th>
                            <th>担当者</th>
                            <th>2024年度売上</th>
                            <th>2023年度売上</th>
                            <th>差額</th>
                            <th>変化率</th>
                            <th>状態</th>
                        </tr>
                    </thead>
                    <tbody>
'''
    
    # 売上減少アラートテーブル
    for alert in alerts['yoy_decline']:
        status_class = alert['level']
        status_text = '危険' if status_class == 'danger' else '警告'
        html += f'''
                        <tr>
                            <td>{alert['学校名']}</td>
                            <td>{alert['担当者']}</td>
                            <td>¥{alert['2024年度売上']:,.0f}</td>
                            <td>¥{alert['2023年度売上']:,.0f}</td>
                            <td class="percent negative">¥{alert['差額']:,.0f}</td>
                            <td class="percent negative">{alert['変化率']*100:.1f}%</td>
                            <td><span class="status-badge {status_class}">{status_text}</span></td>
                        </tr>
'''
    
    if not alerts['yoy_decline']:
        html += '<tr><td colspan="7" style="text-align:center;color:#888;padding:40px;">アラートはありません 🎉</td></tr>'
    
    html += '''
                    </tbody>
                </table>
            </div>
            
            <div id="alert-nosales" class="alert-content">
                <table class="alert-table">
                    <thead>
                        <tr>
                            <th>学校名</th>
                            <th>担当者</th>
                            <th>2024年度売上</th>
                            <th>状態</th>
                        </tr>
                    </thead>
                    <tbody>
'''
    
    # 未販売アラートテーブル
    for alert in alerts['no_sales_2025']:
        html += f'''
                        <tr>
                            <td>{alert['学校名']}</td>
                            <td>{alert['担当者']}</td>
                            <td>¥{alert['2024年度売上']:,.0f}</td>
                            <td><span class="status-badge danger">要確認</span></td>
                        </tr>
'''
    
    if not alerts['no_sales_2025']:
        html += '<tr><td colspan="4" style="text-align:center;color:#888;padding:40px;">アラートはありません 🎉</td></tr>'
    
    html += f'''
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="footer">
            Generated by スクールフォト売上分析ツール | {datetime.now().strftime('%Y-%m-%d %H:%M')}
        </div>
    </div>
    
    <script>
        // タブ切り替え
        function showAlert(type) {{
            document.querySelectorAll('.alert-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.alert-tab').forEach(el => el.classList.remove('active'));
            document.getElementById('alert-' + type).classList.add('active');
            event.target.classList.add('active');
        }}
        
        // 売上グラフ
        const salesCtx = document.getElementById('salesChart').getContext('2d');
        new Chart(salesCtx, {{
            type: 'bar',
            data: {{
                labels: {months_data},
                datasets: [
                    {{
                        label: '売上',
                        data: {sales_data},
                        backgroundColor: 'rgba(102, 126, 234, 0.8)',
                        borderRadius: 8
                    }},
                    {{
                        label: '予算',
                        data: {budget_data},
                        backgroundColor: 'rgba(200, 200, 200, 0.5)',
                        borderRadius: 8
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ position: 'top' }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            callback: function(value) {{
                                return '¥' + (value / 1000000).toFixed(1) + 'M';
                            }}
                        }}
                    }}
                }}
            }}
        }});
        
        // 昨年比グラフ
        const yoyCtx = document.getElementById('yoyChart').getContext('2d');
        new Chart(yoyCtx, {{
            type: 'line',
            data: {{
                labels: {months_data},
                datasets: [{{
                    label: '昨年比 (%)',
                    data: {[y if y else 'null' for y in yoy_data]},
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ display: false }},
                    annotation: {{
                        annotations: {{
                            line1: {{
                                type: 'line',
                                yMin: 100,
                                yMax: 100,
                                borderColor: '#10b981',
                                borderWidth: 2,
                                borderDash: [5, 5]
                            }}
                        }}
                    }}
                }},
                scales: {{
                    y: {{
                        min: 60,
                        max: 120,
                        ticks: {{
                            callback: function(value) {{
                                return value + '%';
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
'''
    
    return html


# ============================================
# メイン処理
# ============================================
def main():
    if len(sys.argv) < 2:
        print("使い方: python schoolphoto_dashboard.py <売上報告書.xlsx>")
        print("例: python schoolphoto_dashboard.py スクールフォト売り上げ報告書_20251201.xlsx")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"エラー: ファイルが見つかりません: {input_file}")
        sys.exit(1)
    
    print(f"📂 ファイル読み込み中: {input_file}")
    
    # レポート日付をファイル名から抽出
    match = re.search(r'(\d{8})', input_file)
    if match:
        date_str = match.group(1)
        report_date = f"{date_str[:4]}年{date_str[4:6]}月{date_str[6:8]}日"
    else:
        report_date = datetime.now().strftime('%Y年%m月%d日')
    
    # データ読み込み
    xlsx = pd.ExcelFile(input_file)
    
    print("📊 データ解析中...")
    sales_summary = load_sales_summary(xlsx)
    member_df = load_member_rates(xlsx)
    school_2025_df, _ = load_school_sales_2025(xlsx)
    comparison_df = load_school_comparison(xlsx)
    
    print("🔍 アラート検出中...")
    alerts = analyze_alerts(member_df, school_2025_df, comparison_df)
    
    print("📝 HTMLダッシュボード生成中...")
    html = generate_html(sales_summary, member_df, school_2025_df, comparison_df, alerts, report_date)
    
    # 出力ファイル名
    output_file = f"売上分析ダッシュボード_{match.group(1) if match else datetime.now().strftime('%Y%m%d')}.html"
    # 出力先ディレクトリ（環境変数で指定可能、デフォルトは入力ファイルと同じ場所）
    output_dir = os.environ.get('OUTPUT_DIR', os.path.dirname(input_file) or '.')
    output_path = os.path.join(output_dir, output_file)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ 完了！ダッシュボードを生成しました:")
    print(f"   {output_path}")
    
    # サマリー表示
    print(f"\n📋 サマリー:")
    print(f"   - 会員率警告: {len(alerts['member_rate_low'])}校")
    print(f"   - 売上減少警告: {len(alerts['yoy_decline'])}校")
    print(f"   - 2025年度未販売: {len(alerts['no_sales_2025'])}校")


if __name__ == '__main__':
    main()
