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

    # 販売開始後イベント会員率（開始後日数）
    NEW_EVENT_DAYS = 14             # イベント開始から2週間
    NEW_EVENT_MIN_RATE = 0.3        # 期待される最低会員率30%

    # 表示件数（ページネーション用）
    PAGE_SIZE = 30


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
    全件取得（件数制限なし）
    """
    current_fy = get_current_fiscal_year()
    prev_fy = current_fy - 1

    query = '''
        SELECT
            s.id as school_id,
            s.school_name,
            s.attribute,
            s.studio_name,
            s.region,
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
        GROUP BY s.id, s.school_name, s.attribute, s.studio_name, s.region, s.manager
        HAVING prev_year_sales > 0
        ORDER BY prev_year_sales DESC
    '''

    cursor.execute(query, (prev_fy, current_fy))
    results = []

    for row in cursor.fetchall():
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio_name': row[3] or '',
            'region': row[4] or '',
            'manager': row[5] or '',
            'prev_year_events': row[6],
            'prev_year_sales': row[7],
            'level': 'danger',
            'message': f'前年度{row[6]}件のイベント実施、売上¥{row[7]:,.0f}'
        })

    return results


def alert_new_event_low_registration(cursor, config=AlertConfig):
    """
    イベント開始日別会員率

    全てのイベントを開始日と共に一覧表示（日付で絞り込んで使用）
    売上データも含めて取得
    """
    latest_report_id, report_date = get_latest_report_id(cursor)
    if not latest_report_id:
        return []

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
            END as member_rate,
            COALESCE(es.sales, 0) as total_sales
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
        LEFT JOIN (
            SELECT event_id, SUM(sales) as sales
            FROM event_sales
            GROUP BY event_id
        ) es ON es.event_id = e.id
        WHERE e.start_date IS NOT NULL
        ORDER BY e.start_date DESC, s.school_name ASC
    '''

    cursor.execute(query, (latest_report_id,))
    results = []

    for row in cursor.fetchall():
        member_rate = row[8]
        total_sales = row[9]

        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio_name': row[3] or '',
            'event_name': row[4],
            'start_date': row[5],
            'total_students': row[6],
            'total_members': row[7],
            'member_rate': member_rate,
            'total_sales': total_sales,
            'level': 'info',
            'message': f'会員率{member_rate*100:.1f}%、売上¥{total_sales:,.0f}'
        })

    return results


def alert_member_rate_decline(cursor, config=AlertConfig, member_rate_threshold=None, sales_decline_threshold=None):
    """
    アラート3: 会員率・売上低下

    会員率と売上低下の両方の基準で絞り込み可能
    全件取得（件数制限なし）

    Args:
        cursor: DBカーソル
        config: アラート設定
        member_rate_threshold: 会員率の閾値（例: 0.5 = 50%未満）。Noneの場合はフィルタなし
        sales_decline_threshold: 売上低下の閾値（例: -0.2 = 20%以上減少）。Noneの場合はフィルタなし
    """
    latest_report_id, _ = get_latest_report_id(cursor)
    current_fy = get_current_fiscal_year()
    prev_fy = current_fy - 1

    # デフォルト値の設定
    if member_rate_threshold is None:
        member_rate_threshold = 1.0  # 100%（実質フィルタなし）
    if sales_decline_threshold is None:
        sales_decline_threshold = 0.0  # 0%（実質フィルタなし）

    # event_salesから売上を集計（school_yearly_salesにデータがない場合に対応）
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
            -- event_salesから今年度の売上を集計
            SELECT
                e.school_id,
                COALESCE(SUM(es.sales), 0) as total_sales
            FROM events e
            LEFT JOIN event_sales es ON es.event_id = e.id
            WHERE e.fiscal_year = ?
            GROUP BY e.school_id
        ),
        prev_sales AS (
            -- event_salesから前年度の売上を集計
            SELECT
                e.school_id,
                COALESCE(SUM(es.sales), 0) as total_sales
            FROM events e
            LEFT JOIN event_sales es ON es.event_id = e.id
            WHERE e.fiscal_year = ?
            GROUP BY e.school_id
        )
        SELECT
            s.id,
            s.school_name,
            s.attribute,
            s.studio_name,
            s.region,
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
    '''

    cursor.execute(query, (
        latest_report_id, current_fy,
        current_fy,
        prev_fy,
        member_rate_threshold,
        sales_decline_threshold
    ))

    results = []
    for row in cursor.fetchall():
        level = 'danger' if row[6] < config.MEMBER_RATE_DANGER or row[9] < config.YOY_DECLINE_DANGER else 'warning'
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio_name': row[3] or '',
            'region': row[4] or '',
            'manager': row[5] or '',
            'member_rate': row[6],
            'current_sales': row[7],
            'prev_sales': row[8],
            'sales_change': row[9],
            'level': level,
            'message': f'会員率{row[6]*100:.1f}%、売上{row[9]*100:+.1f}%'
        })

    return results


def alert_new_schools(cursor, config=AlertConfig, target_fy=None, target_month=None):
    """
    アラート4: 新規開始校

    指定した年度・月に初めてイベントを開始した学校
    全件取得（件数制限なし）

    Args:
        cursor: DBカーソル
        config: アラート設定
        target_fy: 対象年度。Noneの場合は現在年度
        target_month: 対象月（1-12）。Noneの場合は全月
    """
    current_fy = target_fy if target_fy else get_current_fiscal_year()
    prev_fy = current_fy - 1

    # 月指定がある場合
    if target_month:
        # 指定月に開始したイベントを持つ新規校を取得
        query = '''
            SELECT
                s.id,
                s.school_name,
                s.attribute,
                s.studio_name,
                s.region,
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
            AND strftime('%m', e.start_date) = ?
            GROUP BY s.id, s.school_name, s.attribute, s.studio_name, s.region, s.manager
            ORDER BY first_event_date DESC, total_sales DESC
        '''
        cursor.execute(query, (current_fy, prev_fy, f'{target_month:02d}'))
    else:
        query = '''
            SELECT
                s.id,
                s.school_name,
                s.attribute,
                s.studio_name,
                s.region,
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
            GROUP BY s.id, s.school_name, s.attribute, s.studio_name, s.region, s.manager
            ORDER BY first_event_date DESC, total_sales DESC
        '''
        cursor.execute(query, (current_fy, prev_fy))

    results = []
    for row in cursor.fetchall():
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio_name': row[3] or '',
            'region': row[4] or '',
            'manager': row[5] or '',
            'event_count': row[6],
            'first_event_date': row[7],
            'total_sales': row[8],
            'level': 'info',
            'message': f'{current_fy}年度{row[6]}件のイベント、売上¥{row[8]:,.0f}'
        })

    return results


def alert_studio_performance_decline(cursor, config=AlertConfig):
    """
    アラート5: 写真館別パフォーマンス低下

    担当校全体で見たときに、前年比で売上が20%以上落ちている写真館
    全件取得（件数制限なし）
    """
    # school_yearly_salesにデータがある最新の年度を取得
    cursor.execute('SELECT MAX(fiscal_year) FROM school_yearly_sales')
    max_fy = cursor.fetchone()[0]
    if not max_fy:
        return []

    current_fy = max_fy
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
            GROUP BY s.studio_name, sys.fiscal_year
        ),
        studio_region AS (
            SELECT studio_name, region
            FROM schools
            WHERE id IN (
                SELECT MAX(id) FROM schools GROUP BY studio_name
            )
        )
        SELECT
            curr.studio_name,
            curr.total_sales as current_sales,
            curr.school_count as current_schools,
            prev.total_sales as prev_sales,
            prev.school_count as prev_schools,
            CASE WHEN prev.total_sales > 0
                 THEN (curr.total_sales - prev.total_sales) / prev.total_sales
                 ELSE 0 END as change_rate,
            sr.region
        FROM studio_sales curr
        LEFT JOIN studio_sales prev ON curr.studio_name = prev.studio_name AND prev.fiscal_year = ?
        LEFT JOIN studio_region sr ON curr.studio_name = sr.studio_name
        WHERE curr.fiscal_year = ?
          AND prev.total_sales > 0
          AND (curr.total_sales - prev.total_sales) / prev.total_sales < ?
        ORDER BY change_rate ASC
    '''

    cursor.execute(query, (
        prev_fy,
        current_fy,
        config.YOY_DECLINE_WARNING
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
            'region': row[6],
            'level': level,
            'message': f'売上{row[5]*100:+.1f}%（{row[2]}校担当）'
        })

    return results


def alert_rapid_growth_schools(cursor, config=AlertConfig):
    """
    アラート6: 急成長校

    前年比で150%以上の売上成長を見せている学校（成功事例）
    全件取得（件数制限なし）
    """
    latest_report_id, _ = get_latest_report_id(cursor)
    current_fy = get_current_fiscal_year()
    prev_fy = current_fy - 1

    # event_salesから売上を集計（school_yearly_salesにデータがない場合に対応）
    query = '''
        WITH current_sales AS (
            SELECT
                e.school_id,
                COALESCE(SUM(es.sales), 0) as total_sales
            FROM events e
            LEFT JOIN event_sales es ON es.event_id = e.id
            WHERE e.fiscal_year = ?
            GROUP BY e.school_id
        ),
        prev_sales AS (
            SELECT
                e.school_id,
                COALESCE(SUM(es.sales), 0) as total_sales
            FROM events e
            LEFT JOIN event_sales es ON es.event_id = e.id
            WHERE e.fiscal_year = ?
            GROUP BY e.school_id
        )
        SELECT
            s.id,
            s.school_name,
            s.attribute,
            s.studio_name,
            s.region,
            s.manager,
            COALESCE(curr.total_sales, 0) as current_sales,
            COALESCE(prev.total_sales, 0) as prev_sales,
            (COALESCE(curr.total_sales, 0) - prev.total_sales) / prev.total_sales as growth_rate
        FROM schools s
        JOIN current_sales curr ON curr.school_id = s.id
        JOIN prev_sales prev ON prev.school_id = s.id
        WHERE prev.total_sales > 10000  -- 最低売上を設定
          AND (COALESCE(curr.total_sales, 0) - prev.total_sales) / prev.total_sales >= 0.5
        ORDER BY growth_rate DESC
    '''

    cursor.execute(query, (current_fy, prev_fy))

    results = []
    for row in cursor.fetchall():
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio_name': row[3] or '',
            'region': row[4] or '',
            'manager': row[5] or '',
            'current_sales': row[6],
            'prev_sales': row[7],
            'growth_rate': row[8],
            'level': 'success',
            'message': f'売上{row[8]*100:+.1f}%成長！'
        })

    return results


def get_yearly_events_comparison(cursor, school_id, left_year, right_year, month=None):
    """
    年度別イベント比較（タイミング分析）

    指定した学校の2つの年度のイベントを比較
    """
    query = '''
        SELECT
            e.id,
            e.event_name,
            e.start_date,
            e.fiscal_year,
            strftime('%m', e.start_date) as month,
            COALESCE(es_sum.total_sales, 0) as sales
        FROM events e
        LEFT JOIN (
            SELECT event_id, SUM(sales) as total_sales
            FROM event_sales
            GROUP BY event_id
        ) es_sum ON es_sum.event_id = e.id
        WHERE e.school_id = ?
          AND e.fiscal_year IN (?, ?)
          AND e.start_date IS NOT NULL
    '''
    params = [school_id, left_year, right_year]

    if month:
        query += ' AND strftime("%m", e.start_date) = ?'
        params.append(f'{int(month):02d}')

    query += ' ORDER BY e.start_date ASC'

    cursor.execute(query, params)

    results = {'left': [], 'right': [], 'school_info': None}

    # 学校情報を取得
    cursor.execute('SELECT school_name, attribute, studio_name FROM schools WHERE id = ?', (school_id,))
    school_row = cursor.fetchone()
    if school_row:
        results['school_info'] = {
            'school_name': school_row[0],
            'attribute': school_row[1] or '',
            'studio_name': school_row[2] or ''
        }

    cursor.execute(query, params)
    for row in cursor.fetchall():
        event_data = {
            'event_id': row[0],
            'event_name': row[1],
            'start_date': row[2],
            'fiscal_year': row[3],
            'month': row[4],
            'sales': row[5]
        }
        if row[3] == left_year:
            results['left'].append(event_data)
        else:
            results['right'].append(event_data)

    return results


def get_member_rate_trend_improved(cursor, target_fy=None):
    """
    会員率トレンド（前年より改善した学校）

    前年度と比較して会員率が改善した学校を取得
    member_ratesテーブルでデータがある最新2年度を比較
    """
    # member_ratesでデータがある年度を取得
    cursor.execute('SELECT DISTINCT fiscal_year FROM member_rates ORDER BY fiscal_year DESC LIMIT 2')
    years = [row[0] for row in cursor.fetchall()]

    if len(years) < 2:
        return []  # 2年分のデータがない

    current_fy = years[0]
    prev_fy = years[1]

    # 各年度の最新report_idを取得
    cursor.execute('''
        SELECT fiscal_year, MAX(report_id) as latest_report_id
        FROM member_rates
        WHERE fiscal_year IN (?, ?)
        GROUP BY fiscal_year
    ''', (current_fy, prev_fy))

    report_ids = {row[0]: row[1] for row in cursor.fetchall()}
    curr_report_id = report_ids.get(current_fy)
    prev_report_id = report_ids.get(prev_fy)

    if not curr_report_id or not prev_report_id:
        return []

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
        prev_member AS (
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
        )
        SELECT
            s.id,
            s.school_name,
            s.attribute,
            s.studio_name,
            s.region,
            cm.rate as current_rate,
            pm.rate as prev_rate,
            cm.rate - pm.rate as improvement
        FROM schools s
        JOIN current_member cm ON cm.school_id = s.id
        JOIN prev_member pm ON pm.school_id = s.id
        WHERE cm.rate > pm.rate
          AND pm.rate > 0
        ORDER BY improvement DESC
    '''

    cursor.execute(query, (curr_report_id, current_fy, prev_report_id, prev_fy))
    results = []

    for row in cursor.fetchall():
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio_name': row[3] or '',
            'branch_name': row[4] or '',
            'current_rate': row[5],
            'prev_rate': row[6],
            'improvement': row[7],
            'level': 'success',
            'message': f'会員率{row[7]*100:+.1f}%改善'
        })

    return results


def get_sales_unit_price_analysis(cursor, target_fy=None):
    """
    売上単価分析

    会員あたり売上単価を計算し、属性平均と比較
    """
    if target_fy is None:
        target_fy = get_current_fiscal_year()

    latest_report_id, _ = get_latest_report_id(cursor)
    if not latest_report_id:
        return []

    # まず属性別の平均単価を計算
    attr_avg_query = '''
        WITH school_data AS (
            SELECT
                s.id as school_id,
                s.attribute,
                COALESCE(SUM(es.sales), 0) as total_sales,
                COALESCE(mr.total_members, 0) as total_members
            FROM schools s
            LEFT JOIN events e ON e.school_id = s.id AND e.fiscal_year = ?
            LEFT JOIN (
                SELECT event_id, SUM(sales) as sales
                FROM event_sales
                GROUP BY event_id
            ) es ON es.event_id = e.id
            LEFT JOIN (
                SELECT school_id, SUM(member_count) as total_members
                FROM member_rates
                WHERE report_id = ? AND fiscal_year = ?
                GROUP BY school_id
            ) mr ON mr.school_id = s.id
            GROUP BY s.id, s.attribute
        )
        SELECT
            attribute,
            AVG(CASE WHEN total_members > 0 THEN total_sales / total_members ELSE 0 END) as avg_unit_price
        FROM school_data
        WHERE total_members > 0
        GROUP BY attribute
    '''

    cursor.execute(attr_avg_query, (target_fy, latest_report_id, target_fy))
    attr_averages = {row[0]: row[1] for row in cursor.fetchall()}

    # 学校ごとのデータを取得
    query = '''
        SELECT
            s.id,
            s.school_name,
            s.attribute,
            s.studio_name,
            s.region,
            COALESCE(mr.total_members, 0) as total_members,
            COALESCE(mr.total_students, 0) as total_students,
            COALESCE(sales.total_sales, 0) as total_sales,
            CASE WHEN COALESCE(mr.total_students, 0) > 0
                 THEN CAST(mr.total_members AS FLOAT) / mr.total_students
                 ELSE 0 END as member_rate
        FROM schools s
        LEFT JOIN (
            SELECT school_id, SUM(member_count) as total_members, SUM(student_count) as total_students
            FROM member_rates
            WHERE report_id = ? AND fiscal_year = ?
            GROUP BY school_id
        ) mr ON mr.school_id = s.id
        LEFT JOIN (
            SELECT e.school_id, SUM(es.sales) as total_sales
            FROM events e
            LEFT JOIN (
                SELECT event_id, SUM(sales) as sales
                FROM event_sales
                GROUP BY event_id
            ) es ON es.event_id = e.id
            WHERE e.fiscal_year = ?
            GROUP BY e.school_id
        ) sales ON sales.school_id = s.id
        WHERE mr.total_members > 0
        ORDER BY s.school_name
    '''

    cursor.execute(query, (latest_report_id, target_fy, target_fy))
    results = []

    for row in cursor.fetchall():
        total_members = row[5]
        total_sales = row[7]
        member_rate = row[8]
        unit_price = total_sales / total_members if total_members > 0 else 0
        attribute = row[2] or ''
        attr_avg = attr_averages.get(attribute, 0)
        diff = unit_price - attr_avg

        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': attribute,
            'studio_name': row[3] or '',
            'branch_name': row[4] or '',
            'total_members': total_members,
            'total_students': row[6],
            'total_sales': total_sales,
            'member_rate': member_rate,
            'unit_price': unit_price,
            'attr_avg': attr_avg,
            'diff': diff,
            'level': 'success' if diff > 0 else 'warning',
            'message': f'単価¥{unit_price:,.0f}（属性平均比{diff:+,.0f}）'
        })

    return results


def get_schools_for_filter(cursor):
    """フィルタ用の学校リストを取得"""
    cursor.execute('SELECT id, school_name, attribute, studio_name, region FROM schools ORDER BY school_name')
    return [{'id': row[0], 'school_name': row[1], 'attribute': row[2] or '', 'studio_name': row[3] or '', 'branch_name': row[4] or ''} for row in cursor.fetchall()]


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
        'member_rate_trend_improved': get_member_rate_trend_improved(cursor),
        'sales_unit_price': get_sales_unit_price_analysis(cursor),
        'schools_for_filter': get_schools_for_filter(cursor),
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
