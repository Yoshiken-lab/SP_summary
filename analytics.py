#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上分析システム - 分析ロジック

蓄積されたデータから各種分析を行う
"""

from datetime import datetime, timedelta
from collections import defaultdict
from database import get_connection


def get_latest_report_id(cursor):
    """最新の報告書IDを取得"""
    cursor.execute('SELECT id, report_date FROM reports ORDER BY report_date DESC LIMIT 1')
    row = cursor.fetchone()
    return row[0] if row else None, row[1] if row else None


def get_current_fiscal_year():
    """現在の年度を取得（4月始まり）"""
    today = datetime.now()
    if today.month >= 4:
        return today.year
    return today.year - 1


# ============================================
# 分析1: 季節性分析
# ============================================
def analyze_seasonality(cursor):
    """
    季節性分析: 月ごとの売上パターンを過去データから分析

    Returns:
        dict: {月: {'avg_sales': 平均売上, 'avg_yoy': 平均昨年比, 'trend': 傾向}}
    """
    query = '''
        SELECT
            month,
            fiscal_year,
            AVG(total_sales) as avg_sales,
            AVG(yoy_rate) as avg_yoy
        FROM monthly_summary
        WHERE total_sales > 0
        GROUP BY month, fiscal_year
        ORDER BY fiscal_year, month
    '''

    cursor.execute(query)

    # 月ごとに集計
    monthly_data = defaultdict(list)
    for row in cursor.fetchall():
        month, fiscal_year, avg_sales, avg_yoy = row
        monthly_data[month].append({
            'fiscal_year': fiscal_year,
            'sales': avg_sales,
            'yoy': avg_yoy
        })

    # 各月の統計を計算
    results = {}
    for month in range(1, 13):
        data = monthly_data.get(month, [])
        if not data:
            continue

        avg_sales = sum(d['sales'] for d in data) / len(data)
        yoy_values = [d['yoy'] for d in data if d['yoy'] is not None]
        avg_yoy = sum(yoy_values) / len(yoy_values) if yoy_values else None

        # トレンド判定
        if avg_yoy is not None:
            if avg_yoy >= 1.1:
                trend = 'growing'
            elif avg_yoy >= 0.95:
                trend = 'stable'
            else:
                trend = 'declining'
        else:
            trend = 'unknown'

        results[month] = {
            'avg_sales': avg_sales,
            'avg_yoy': avg_yoy,
            'trend': trend,
            'data_points': len(data)
        }

    return results


# ============================================
# 分析2: 異常検知（急に売上が消えた学校）
# ============================================
def detect_anomalies(cursor, threshold_ratio=0.3):
    """
    異常検知: 急激な売上変動を検出

    直近の報告で売上が急減した学校を検出
    """
    latest_report_id, _ = get_latest_report_id(cursor)
    current_fy = get_current_fiscal_year()

    # 過去3回分の報告書を取得
    cursor.execute('''
        SELECT id, report_date FROM reports
        ORDER BY report_date DESC LIMIT 3
    ''')
    recent_reports = cursor.fetchall()

    if len(recent_reports) < 2:
        return []

    latest_id = recent_reports[0][0]
    prev_id = recent_reports[1][0]

    # 学校ごとの売上を比較
    query = '''
        SELECT
            s.id,
            s.school_name,
            s.attribute,
            s.studio_name,
            COALESCE(curr.total_sales, 0) as current_sales,
            COALESCE(prev.total_sales, 0) as prev_sales
        FROM schools s
        LEFT JOIN (
            SELECT school_id, SUM(sales) as total_sales
            FROM school_sales
            WHERE report_id = ?
            GROUP BY school_id
        ) curr ON curr.school_id = s.id
        LEFT JOIN (
            SELECT school_id, SUM(sales) as total_sales
            FROM school_sales
            WHERE report_id = ?
            GROUP BY school_id
        ) prev ON prev.school_id = s.id
        WHERE prev.total_sales > 50000  -- ある程度の売上がある学校のみ
          AND (
              curr.total_sales IS NULL
              OR curr.total_sales < prev.total_sales * ?
          )
        ORDER BY prev.total_sales DESC
        LIMIT 20
    '''

    cursor.execute(query, (latest_id, prev_id, threshold_ratio))

    results = []
    for row in cursor.fetchall():
        change_rate = (row[4] - row[5]) / row[5] if row[5] > 0 else -1
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio_name': row[3] or '',
            'current_sales': row[4],
            'prev_sales': row[5],
            'change_rate': change_rate,
            'severity': 'critical' if row[4] == 0 else 'warning'
        })

    return results


# ============================================
# 分析3: 会員率時系列トレンド
# ============================================
def analyze_member_rate_trends(cursor, consecutive_months=3):
    """
    時系列トレンド: 会員率が連続して低下している学校を検出
    """
    # 報告書の日付順に取得
    cursor.execute('''
        SELECT id, report_date FROM reports
        ORDER BY report_date
    ''')
    reports = cursor.fetchall()

    if len(reports) < consecutive_months:
        return []

    # 学校ごとの会員率推移を取得
    query = '''
        SELECT
            s.id as school_id,
            s.school_name,
            s.attribute,
            s.studio_name,
            r.report_date,
            SUM(m.student_count) as students,
            SUM(m.member_count) as members,
            CASE WHEN SUM(m.student_count) > 0
                 THEN CAST(SUM(m.member_count) AS FLOAT) / SUM(m.student_count)
                 ELSE 0 END as rate
        FROM member_rates m
        JOIN schools s ON m.school_id = s.id
        JOIN reports r ON m.report_id = r.id
        WHERE m.student_count > 0
        GROUP BY s.id, s.school_name, s.attribute, s.studio_name, r.report_date
        ORDER BY s.school_name, r.report_date
    '''

    cursor.execute(query)
    rows = cursor.fetchall()

    # 学校ごとにグループ化
    school_trends = defaultdict(list)
    for row in rows:
        school_trends[row[0]].append({
            'school_name': row[1],
            'attribute': row[2],
            'studio_name': row[3],
            'report_date': row[4],
            'students': row[5],
            'members': row[6],
            'rate': row[7]
        })

    # 連続低下を検出
    results = []
    for school_id, trend_data in school_trends.items():
        if len(trend_data) < consecutive_months:
            continue

        # 直近N回分をチェック
        recent = trend_data[-consecutive_months:]
        declining = True
        for i in range(1, len(recent)):
            if recent[i]['rate'] >= recent[i-1]['rate']:
                declining = False
                break

        if declining:
            first = recent[0]
            last = recent[-1]
            rate_change = last['rate'] - first['rate']

            results.append({
                'school_id': school_id,
                'school_name': first['school_name'],
                'attribute': first['attribute'] or '',
                'studio_name': first['studio_name'] or '',
                'start_rate': first['rate'],
                'current_rate': last['rate'],
                'rate_change': rate_change,
                'months': consecutive_months,
                'trend_data': [{'date': d['report_date'], 'rate': d['rate']} for d in recent]
            })

    # 変化量で降順ソート
    results.sort(key=lambda x: x['rate_change'])
    return results[:30]


# ============================================
# 分析4: 写真館別ランキング推移
# ============================================
def analyze_studio_rankings(cursor):
    """
    写真館別ランキング: 各写真館の売上と推移を分析
    """
    latest_report_id, _ = get_latest_report_id(cursor)
    current_fy = get_current_fiscal_year()
    prev_fy = current_fy - 1

    query = '''
        SELECT
            s.studio_name,
            SUM(CASE WHEN sys.fiscal_year = ? THEN sys.total_sales ELSE 0 END) as current_sales,
            SUM(CASE WHEN sys.fiscal_year = ? THEN sys.total_sales ELSE 0 END) as prev_sales,
            COUNT(DISTINCT CASE WHEN sys.fiscal_year = ? THEN s.id END) as current_schools,
            COUNT(DISTINCT CASE WHEN sys.fiscal_year = ? THEN s.id END) as prev_schools
        FROM school_yearly_sales sys
        JOIN schools s ON sys.school_id = s.id
        WHERE sys.report_id = ?
        GROUP BY s.studio_name
        HAVING current_sales > 0 OR prev_sales > 0
        ORDER BY current_sales DESC
    '''

    cursor.execute(query, (current_fy, prev_fy, current_fy, prev_fy, latest_report_id))

    results = []
    rank = 1
    for row in cursor.fetchall():
        change_rate = (row[1] - row[2]) / row[2] if row[2] > 0 else 0
        results.append({
            'rank': rank,
            'studio_name': row[0] or '不明',
            'current_sales': row[1],
            'prev_sales': row[2],
            'change_rate': change_rate,
            'current_schools': row[3],
            'prev_schools': row[4]
        })
        rank += 1

    return results


# ============================================
# 分析5: 属性別傾向
# ============================================
def analyze_by_attribute(cursor):
    """
    属性別傾向: 幼稚園・小学校・中学校など属性ごとの傾向を分析
    """
    latest_report_id, _ = get_latest_report_id(cursor)
    current_fy = get_current_fiscal_year()
    prev_fy = current_fy - 1

    query = '''
        SELECT
            s.attribute,
            COUNT(DISTINCT s.id) as school_count,
            SUM(CASE WHEN sys.fiscal_year = ? THEN sys.total_sales ELSE 0 END) as current_sales,
            SUM(CASE WHEN sys.fiscal_year = ? THEN sys.total_sales ELSE 0 END) as prev_sales,
            AVG(CASE WHEN m.fiscal_year = ? AND m.student_count > 0
                     THEN CAST(m.member_count AS FLOAT) / m.student_count
                     ELSE NULL END) as avg_member_rate
        FROM schools s
        LEFT JOIN school_yearly_sales sys ON sys.school_id = s.id AND sys.report_id = ?
        LEFT JOIN member_rates m ON m.school_id = s.id AND m.report_id = ?
        WHERE s.attribute IS NOT NULL AND s.attribute != ''
        GROUP BY s.attribute
        ORDER BY current_sales DESC
    '''

    cursor.execute(query, (current_fy, prev_fy, current_fy, latest_report_id, latest_report_id))

    results = []
    for row in cursor.fetchall():
        change_rate = (row[2] - row[3]) / row[3] if row[3] > 0 else 0
        results.append({
            'attribute': row[0],
            'school_count': row[1],
            'current_sales': row[2],
            'prev_sales': row[3],
            'change_rate': change_rate,
            'avg_member_rate': row[4]
        })

    return results


# ============================================
# 分析6: イベント開始からの経過日数 vs 会員率（学校別成長カーブ）
# ============================================
def analyze_growth_curves(cursor):
    """
    成長カーブ分析: イベント開始からの経過日数と会員率の関係

    学校別・属性別の標準成長パターンを算出し、
    現在のイベントが順調かどうかを判定
    """
    latest_report_id, report_date = get_latest_report_id(cursor)
    if not latest_report_id:
        return {'curves': {}, 'evaluations': []}

    if isinstance(report_date, str):
        report_date = datetime.strptime(report_date, '%Y-%m-%d').date()

    # 過去のイベントデータから成長カーブを算出
    # （イベント開始日と、その時点での会員率を紐付ける）
    query = '''
        SELECT
            s.id as school_id,
            s.school_name,
            s.attribute,
            e.event_name,
            e.start_date,
            r.report_date,
            SUM(m.student_count) as students,
            SUM(m.member_count) as members,
            CASE WHEN SUM(m.student_count) > 0
                 THEN CAST(SUM(m.member_count) AS FLOAT) / SUM(m.student_count)
                 ELSE 0 END as rate
        FROM events e
        JOIN schools s ON e.school_id = s.id
        JOIN member_rates m ON m.school_id = s.id
        JOIN reports r ON m.report_id = r.id
        WHERE e.start_date IS NOT NULL
          AND m.student_count > 0
        GROUP BY s.id, s.school_name, s.attribute, e.event_name, e.start_date, r.report_date
        ORDER BY s.school_name, e.start_date, r.report_date
    '''

    cursor.execute(query)
    rows = cursor.fetchall()

    # 経過日数ごとの会員率を集計（属性別）
    attribute_curves = defaultdict(lambda: defaultdict(list))
    school_curves = defaultdict(lambda: defaultdict(list))

    for row in rows:
        school_id, school_name, attribute, event_name, start_date, rpt_date, students, members, rate = row

        if start_date is None:
            continue

        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(rpt_date, str):
            rpt_date = datetime.strptime(rpt_date, '%Y-%m-%d').date()

        days_elapsed = (rpt_date - start_date).days

        if 0 <= days_elapsed <= 90:  # 90日以内のデータのみ
            # 週単位でグループ化
            week = days_elapsed // 7
            if attribute:
                attribute_curves[attribute][week].append(rate)
            school_curves[school_id][week].append(rate)

    # 属性別の標準カーブを計算
    standard_curves = {}
    for attr, weeks in attribute_curves.items():
        curve = {}
        for week, rates in weeks.items():
            if rates:
                curve[week] = sum(rates) / len(rates)
        standard_curves[attr] = curve

    # 現在進行中のイベントを評価
    current_fy = get_current_fiscal_year()

    query2 = '''
        SELECT
            s.id,
            s.school_name,
            s.attribute,
            e.event_name,
            e.start_date,
            SUM(m.student_count) as students,
            SUM(m.member_count) as members,
            CASE WHEN SUM(m.student_count) > 0
                 THEN CAST(SUM(m.member_count) AS FLOAT) / SUM(m.student_count)
                 ELSE 0 END as current_rate
        FROM events e
        JOIN schools s ON e.school_id = s.id
        LEFT JOIN member_rates m ON m.school_id = s.id AND m.report_id = ?
        WHERE e.fiscal_year = ?
          AND e.start_date IS NOT NULL
          AND e.start_date <= ?
        GROUP BY s.id, s.school_name, s.attribute, e.event_name, e.start_date
        HAVING students > 0
    '''

    cursor.execute(query2, (latest_report_id, current_fy, report_date))

    evaluations = []
    for row in cursor.fetchall():
        school_id, school_name, attribute, event_name, start_date, students, members, current_rate = row

        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()

        days_elapsed = (report_date - start_date).days
        week = days_elapsed // 7

        # 期待値を取得（学校固有 → 属性別 → 全体平均の順で探す）
        expected_rate = None

        # 1. 学校固有のカーブ
        if school_id in school_curves and week in school_curves[school_id]:
            expected_rate = sum(school_curves[school_id][week]) / len(school_curves[school_id][week])

        # 2. 属性別カーブ
        if expected_rate is None and attribute in standard_curves and week in standard_curves[attribute]:
            expected_rate = standard_curves[attribute][week]

        # 3. 全体平均
        if expected_rate is None:
            all_rates = []
            for attr_curve in standard_curves.values():
                if week in attr_curve:
                    all_rates.append(attr_curve[week])
            if all_rates:
                expected_rate = sum(all_rates) / len(all_rates)

        if expected_rate is not None:
            gap = current_rate - expected_rate
            if gap < -0.1:
                status = 'behind'
            elif gap > 0.1:
                status = 'ahead'
            else:
                status = 'on_track'
        else:
            gap = None
            status = 'no_data'

        evaluations.append({
            'school_id': school_id,
            'school_name': school_name,
            'attribute': attribute or '',
            'event_name': event_name,
            'start_date': start_date,
            'days_elapsed': days_elapsed,
            'current_rate': current_rate,
            'expected_rate': expected_rate,
            'gap': gap,
            'status': status
        })

    # 遅れているものを優先
    evaluations.sort(key=lambda x: (x['gap'] if x['gap'] is not None else 0))

    return {
        'curves': standard_curves,
        'evaluations': evaluations[:30]
    }


def get_all_analytics(db_path=None):
    """全分析を実行"""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    analytics = {
        'seasonality': analyze_seasonality(cursor),
        'anomalies': detect_anomalies(cursor),
        'member_rate_trends': analyze_member_rate_trends(cursor),
        'studio_rankings': analyze_studio_rankings(cursor),
        'by_attribute': analyze_by_attribute(cursor),
        'growth_curves': analyze_growth_curves(cursor),
    }

    conn.close()
    return analytics


if __name__ == '__main__':
    analytics = get_all_analytics()

    output = []
    output.append("=" * 60)
    output.append("分析結果")
    output.append("=" * 60)

    # 季節性
    output.append("\n【季節性分析】")
    for month, data in sorted(analytics['seasonality'].items()):
        trend_emoji = {'growing': '↑', 'stable': '→', 'declining': '↓'}.get(data['trend'], '?')
        output.append(f"  {month:2}月: 平均売上 ¥{data['avg_sales']:,.0f} | 昨年比 {data['avg_yoy']*100:.1f}% {trend_emoji}" if data['avg_yoy'] else f"  {month:2}月: 平均売上 ¥{data['avg_sales']:,.0f}")

    # 異常検知
    output.append("\n【異常検知（売上急減）】")
    for item in analytics['anomalies'][:5]:
        output.append(f"  {item['school_name']} | {item['prev_sales']:,.0f} → {item['current_sales']:,.0f}")

    # 会員率トレンド
    output.append("\n【会員率連続低下】")
    for item in analytics['member_rate_trends'][:5]:
        output.append(f"  {item['school_name']} | {item['start_rate']*100:.1f}% → {item['current_rate']*100:.1f}%")

    # 写真館ランキング
    output.append("\n【写真館ランキングTOP5】")
    for item in analytics['studio_rankings'][:5]:
        output.append(f"  {item['rank']}. {item['studio_name']} | ¥{item['current_sales']:,.0f} ({item['change_rate']*100:+.1f}%)")

    # 属性別
    output.append("\n【属性別傾向】")
    for item in analytics['by_attribute']:
        rate_str = f"{item['avg_member_rate']*100:.1f}%" if item['avg_member_rate'] else 'N/A'
        output.append(f"  {item['attribute']}: {item['school_count']}校 | ¥{item['current_sales']:,.0f} | 会員率{rate_str}")

    # 成長カーブ
    output.append("\n【成長カーブ評価（遅れている学校）】")
    for item in analytics['growth_curves']['evaluations'][:5]:
        if item['status'] == 'behind':
            output.append(f"  {item['school_name']} | 現在{item['current_rate']*100:.1f}% (期待{item['expected_rate']*100:.1f}%)")

    with open('analytics_result.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))

    print("analytics_result.txt に保存しました")
