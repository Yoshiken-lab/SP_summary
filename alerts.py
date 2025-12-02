#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上分析システム - アラート検出

蓄積されたデータから各種アラートを検出する
"""

from datetime import datetime, timedelta
from database import get_connection


class AlertConfig:
    """アラート閾値の設定"""
    # 会員率
    MEMBER_RATE_WARNING = 0.5       # 会員率50%未満で警告
    MEMBER_RATE_DANGER = 0.3        # 会員率30%未満で危険

    # 売上
    YOY_DECLINE_WARNING = -0.2      # 前年比20%減で警告
    YOY_DECLINE_DANGER = -0.3       # 前年比30%減で危険

    # 新規イベント会員率（開始後日数）
    NEW_EVENT_DAYS = 7              # イベント開始から7日
    NEW_EVENT_MIN_RATE = 0.3        # 期待される最低会員率30%

    # 表示件数
    TOP_N = 30


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


def alert_no_events_this_year(cursor, config=AlertConfig):
    """
    アラート1: 今年度未実施（前年実施あり）

    前年度にイベントを実施していたが、今年度はまだ実施していない学校
    """
    current_fy = get_current_fiscal_year()
    prev_fy = current_fy - 1

    query = '''
        SELECT
            s.id as school_id,
            s.school_name,
            s.attribute,
            s.studio_name,
            s.manager,
            COUNT(DISTINCT e_prev.id) as prev_year_events,
            COALESCE(SUM(es_prev.sales), 0) as prev_year_sales
        FROM schools s
        -- 前年度にイベントがある
        INNER JOIN events e_prev ON e_prev.school_id = s.id AND e_prev.fiscal_year = ?
        LEFT JOIN event_sales es_prev ON es_prev.event_id = e_prev.id
        -- 今年度にイベントがない
        WHERE NOT EXISTS (
            SELECT 1 FROM events e_curr
            WHERE e_curr.school_id = s.id AND e_curr.fiscal_year = ?
        )
        GROUP BY s.id, s.school_name, s.attribute, s.studio_name, s.manager
        HAVING prev_year_sales > 0
        ORDER BY prev_year_sales DESC
        LIMIT ?
    '''

    cursor.execute(query, (prev_fy, current_fy, config.TOP_N))
    results = []

    for row in cursor.fetchall():
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio_name': row[3] or '',
            'manager': row[4] or '',
            'prev_year_events': row[5],
            'prev_year_sales': row[6],
            'level': 'danger',
            'message': f'前年度{row[5]}件のイベント実施、売上¥{row[6]:,.0f}'
        })

    return results


def alert_new_event_low_registration(cursor, config=AlertConfig):
    """
    アラート2: 直近開始イベントで会員率が低い

    イベント開始から1週間程度経過しているのに、会員登録率が伸びていない学校
    """
    latest_report_id, report_date = get_latest_report_id(cursor)
    if not latest_report_id:
        return []

    # 報告書の日付を基準に1週間前〜当日に開始したイベントを抽出
    if isinstance(report_date, str):
        report_date = datetime.strptime(report_date, '%Y-%m-%d').date()

    week_ago = report_date - timedelta(days=config.NEW_EVENT_DAYS)

    query = '''
        SELECT
            s.id as school_id,
            s.school_name,
            s.attribute,
            s.studio_name,
            e.event_name,
            e.start_date,
            COALESCE(school_mr.total_students, 0) as total_students,
            COALESCE(school_mr.total_members, 0) as total_members,
            CASE
                WHEN COALESCE(school_mr.total_students, 0) > 0
                THEN CAST(school_mr.total_members AS FLOAT) / school_mr.total_students
                ELSE 0
            END as member_rate
        FROM events e
        JOIN schools s ON e.school_id = s.id
        LEFT JOIN (
            SELECT
                school_id,
                SUM(student_count) as total_students,
                SUM(member_count) as total_members
            FROM member_rates
            WHERE report_id = ?
            GROUP BY school_id
        ) school_mr ON school_mr.school_id = s.id
        WHERE e.start_date BETWEEN ? AND ?
          AND e.start_date IS NOT NULL
        ORDER BY member_rate ASC
        LIMIT ?
    '''

    cursor.execute(query, (latest_report_id, week_ago, report_date, config.TOP_N * 2))
    results = []

    for row in cursor.fetchall():
        member_rate = row[8]
        if member_rate < config.NEW_EVENT_MIN_RATE:
            days_since_start = (report_date - datetime.strptime(str(row[5]), '%Y-%m-%d').date()).days if row[5] else 0

            level = 'danger' if member_rate < config.MEMBER_RATE_DANGER else 'warning'
            results.append({
                'school_id': row[0],
                'school_name': row[1],
                'attribute': row[2] or '',
                'studio_name': row[3] or '',
                'event_name': row[4],
                'start_date': row[5],
                'days_since_start': days_since_start,
                'total_students': row[6],
                'total_members': row[7],
                'member_rate': member_rate,
                'level': level,
                'message': f'開始から{days_since_start}日経過、会員率{member_rate*100:.1f}%'
            })

    return results[:config.TOP_N]


def alert_member_rate_decline(cursor, config=AlertConfig):
    """
    アラート3: 前年比で会員率50%未満 かつ 売上20%以上減少

    前年度と比較して、会員率が大幅に低下し、売上も減少している学校
    """
    latest_report_id, _ = get_latest_report_id(cursor)
    current_fy = get_current_fiscal_year()
    prev_fy = current_fy - 1

    query = '''
        WITH current_member AS (
            SELECT
                school_id,
                SUM(student_count) as students,
                SUM(member_count) as members,
                CASE WHEN SUM(student_count) > 0
                     THEN CAST(SUM(member_count) AS FLOAT) / SUM(student_count)
                     ELSE 0 END as rate
            FROM member_rates
            WHERE report_id = ? AND fiscal_year = ?
            GROUP BY school_id
        ),
        current_sales AS (
            SELECT school_id, total_sales
            FROM school_yearly_sales
            WHERE report_id = ? AND fiscal_year = ?
        ),
        prev_sales AS (
            SELECT school_id, total_sales
            FROM school_yearly_sales
            WHERE report_id = ? AND fiscal_year = ?
        )
        SELECT
            s.id,
            s.school_name,
            s.attribute,
            s.studio_name,
            s.manager,
            cm.rate as current_rate,
            COALESCE(cs.total_sales, 0) as current_sales,
            COALESCE(ps.total_sales, 0) as prev_sales,
            CASE WHEN COALESCE(ps.total_sales, 0) > 0
                 THEN (COALESCE(cs.total_sales, 0) - ps.total_sales) / ps.total_sales
                 ELSE 0 END as sales_change
        FROM schools s
        JOIN current_member cm ON cm.school_id = s.id
        LEFT JOIN current_sales cs ON cs.school_id = s.id
        LEFT JOIN prev_sales ps ON ps.school_id = s.id
        WHERE cm.rate < ?
          AND COALESCE(ps.total_sales, 0) > 0
          AND (COALESCE(cs.total_sales, 0) - ps.total_sales) / ps.total_sales < ?
        ORDER BY cm.rate ASC, sales_change ASC
        LIMIT ?
    '''

    cursor.execute(query, (
        latest_report_id, current_fy,
        latest_report_id, current_fy,
        latest_report_id, prev_fy,
        config.MEMBER_RATE_WARNING,
        config.YOY_DECLINE_WARNING,
        config.TOP_N
    ))

    results = []
    for row in cursor.fetchall():
        level = 'danger' if row[5] < config.MEMBER_RATE_DANGER or row[8] < config.YOY_DECLINE_DANGER else 'warning'
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio_name': row[3] or '',
            'manager': row[4] or '',
            'member_rate': row[5],
            'current_sales': row[6],
            'prev_sales': row[7],
            'sales_change': row[8],
            'level': level,
            'message': f'会員率{row[5]*100:.1f}%、売上{row[8]*100:+.1f}%'
        })

    return results


def alert_new_schools(cursor, config=AlertConfig):
    """
    アラート4: 新規開始校

    前年度に実績がなく、今年度から新規でイベントを開始した学校
    """
    current_fy = get_current_fiscal_year()
    prev_fy = current_fy - 1

    query = '''
        SELECT
            s.id,
            s.school_name,
            s.attribute,
            s.studio_name,
            s.manager,
            COUNT(DISTINCT e.id) as event_count,
            MIN(e.start_date) as first_event_date,
            COALESCE(SUM(es.sales), 0) as total_sales
        FROM schools s
        JOIN events e ON e.school_id = s.id AND e.fiscal_year = ?
        LEFT JOIN event_sales es ON es.event_id = e.id
        WHERE NOT EXISTS (
            SELECT 1 FROM events e_prev
            WHERE e_prev.school_id = s.id AND e_prev.fiscal_year = ?
        )
        GROUP BY s.id, s.school_name, s.attribute, s.studio_name, s.manager
        ORDER BY first_event_date DESC, total_sales DESC
        LIMIT ?
    '''

    cursor.execute(query, (current_fy, prev_fy, config.TOP_N))

    results = []
    for row in cursor.fetchall():
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio_name': row[3] or '',
            'manager': row[4] or '',
            'event_count': row[5],
            'first_event_date': row[6],
            'total_sales': row[7],
            'level': 'info',
            'message': f'今年度{row[5]}件のイベント、売上¥{row[7]:,.0f}'
        })

    return results


def alert_studio_performance_decline(cursor, config=AlertConfig):
    """
    アラート5: 写真館別パフォーマンス低下

    担当校全体で見たときに、前年比で売上が大幅に落ちている写真館
    """
    latest_report_id, _ = get_latest_report_id(cursor)
    current_fy = get_current_fiscal_year()
    prev_fy = current_fy - 1

    query = '''
        WITH studio_sales AS (
            SELECT
                s.studio_name,
                sys.fiscal_year,
                SUM(sys.total_sales) as total_sales,
                COUNT(DISTINCT s.id) as school_count
            FROM school_yearly_sales sys
            JOIN schools s ON sys.school_id = s.id
            WHERE sys.report_id = ?
            GROUP BY s.studio_name, sys.fiscal_year
        )
        SELECT
            curr.studio_name,
            curr.total_sales as current_sales,
            curr.school_count as current_schools,
            prev.total_sales as prev_sales,
            prev.school_count as prev_schools,
            CASE WHEN prev.total_sales > 0
                 THEN (curr.total_sales - prev.total_sales) / prev.total_sales
                 ELSE 0 END as change_rate
        FROM studio_sales curr
        LEFT JOIN studio_sales prev ON curr.studio_name = prev.studio_name AND prev.fiscal_year = ?
        WHERE curr.fiscal_year = ?
          AND prev.total_sales > 0
          AND (curr.total_sales - prev.total_sales) / prev.total_sales < ?
        ORDER BY change_rate ASC
        LIMIT ?
    '''

    cursor.execute(query, (
        latest_report_id,
        prev_fy,
        current_fy,
        config.YOY_DECLINE_WARNING,
        config.TOP_N
    ))

    results = []
    for row in cursor.fetchall():
        level = 'danger' if row[5] < config.YOY_DECLINE_DANGER else 'warning'
        results.append({
            'studio_name': row[0] or '不明',
            'current_sales': row[1],
            'current_schools': row[2],
            'prev_sales': row[3],
            'prev_schools': row[4],
            'change_rate': row[5],
            'level': level,
            'message': f'売上{row[5]*100:+.1f}%（{row[2]}校担当）'
        })

    return results


def alert_rapid_growth_schools(cursor, config=AlertConfig):
    """
    アラート6: 急成長校

    前年比で150%以上の売上成長を見せている学校（成功事例）
    """
    latest_report_id, _ = get_latest_report_id(cursor)
    current_fy = get_current_fiscal_year()
    prev_fy = current_fy - 1

    query = '''
        SELECT
            s.id,
            s.school_name,
            s.attribute,
            s.studio_name,
            s.manager,
            curr.total_sales as current_sales,
            prev.total_sales as prev_sales,
            (curr.total_sales - prev.total_sales) / prev.total_sales as growth_rate
        FROM schools s
        JOIN school_yearly_sales curr ON curr.school_id = s.id
            AND curr.report_id = ? AND curr.fiscal_year = ?
        JOIN school_yearly_sales prev ON prev.school_id = s.id
            AND prev.report_id = ? AND prev.fiscal_year = ?
        WHERE prev.total_sales > 10000  -- 最低売上を設定
          AND (curr.total_sales - prev.total_sales) / prev.total_sales >= 0.5
        ORDER BY growth_rate DESC
        LIMIT ?
    '''

    cursor.execute(query, (
        latest_report_id, current_fy,
        latest_report_id, prev_fy,
        config.TOP_N
    ))

    results = []
    for row in cursor.fetchall():
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio_name': row[3] or '',
            'manager': row[4] or '',
            'current_sales': row[5],
            'prev_sales': row[6],
            'growth_rate': row[7],
            'level': 'success',
            'message': f'売上{row[7]*100:+.1f}%成長！'
        })

    return results


def get_all_alerts(db_path=None):
    """全アラートを取得"""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    alerts = {
        'no_events_this_year': alert_no_events_this_year(cursor),
        'new_event_low_registration': alert_new_event_low_registration(cursor),
        'member_rate_decline': alert_member_rate_decline(cursor),
        'new_schools': alert_new_schools(cursor),
        'studio_performance_decline': alert_studio_performance_decline(cursor),
        'rapid_growth': alert_rapid_growth_schools(cursor),
    }

    conn.close()
    return alerts


if __name__ == '__main__':
    alerts = get_all_alerts()

    output = []
    output.append("=" * 60)
    output.append("アラート検出結果")
    output.append("=" * 60)

    for alert_type, items in alerts.items():
        output.append(f"\n【{alert_type}】: {len(items)}件")
        for i, item in enumerate(items[:5]):
            output.append(f"  {i+1}. {item.get('school_name', item.get('studio_name', '?'))} - {item.get('message', '')}")

    with open('alerts_result.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))

    print("alerts_result.txt に保存しました")
