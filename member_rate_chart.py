#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上分析システム - 会員率推移グラフデータ

会員率の推移データを取得し、グラフ用にフォーマットする
"""

import json
from datetime import datetime
from collections import defaultdict
from database import get_connection

# 事業所名の統合マッピング（キー → 値 に統合）
BRANCH_MAPPING = {
    '栃木': '鹿沼',  # 栃木を鹿沼に統合
}


def normalize_branch(branch_name):
    """事業所名を正規化（マッピングがあれば変換）"""
    if branch_name is None:
        return None
    return BRANCH_MAPPING.get(branch_name, branch_name)


def get_filter_options(db_path=None):
    """フィルター用の選択肢を取得"""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 属性一覧
    cursor.execute('''
        SELECT DISTINCT attribute FROM schools
        WHERE attribute IS NOT NULL AND attribute != ''
        ORDER BY attribute
    ''')
    attributes = [row[0] for row in cursor.fetchall()]

    # 写真館一覧
    cursor.execute('''
        SELECT DISTINCT studio_name FROM schools
        WHERE studio_name IS NOT NULL AND studio_name != ''
        ORDER BY studio_name
    ''')
    studios = [row[0] for row in cursor.fetchall()]

    # 学校一覧（属性・写真館付き）
    cursor.execute('''
        SELECT id, school_name, attribute, studio_name
        FROM schools
        ORDER BY school_name
    ''')
    schools = [{'id': row[0], 'name': row[1], 'attribute': row[2], 'studio': row[3]}
               for row in cursor.fetchall()]

    conn.close()

    return {
        'attributes': attributes,
        'studios': studios,
        'schools': schools
    }


def get_member_rate_trend_by_school(school_id, by_grade=False, db_path=None):
    """
    学校単位の会員率推移を取得

    会員率は報告書のスナップショット日ごとに蓄積されているため、
    全てのスナップショット日のデータを時系列で表示する。

    Args:
        school_id: 学校ID
        by_grade: True=学年別, False=全学年まとめ
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 学校情報
    cursor.execute('SELECT school_name, attribute FROM schools WHERE id = ?', (school_id,))
    school_info = cursor.fetchone()
    if not school_info:
        conn.close()
        return None

    school_name, attribute = school_info

    # イベント開始日を取得（アノテーション用）
    cursor.execute('''
        SELECT event_name, start_date, fiscal_year
        FROM events
        WHERE school_id = ? AND start_date IS NOT NULL
        ORDER BY start_date
    ''', (school_id,))
    events = [{'name': row[0], 'date': str(row[1]), 'year': row[2]} for row in cursor.fetchall()]

    if by_grade:
        # 学年別データ - 全てのスナップショット日を時系列で表示
        query = '''
            SELECT
                m.snapshot_date,
                m.fiscal_year,
                m.grade_category,
                m.grade_name,
                SUM(m.student_count) as students,
                SUM(m.member_count) as members
            FROM member_rates m
            WHERE m.school_id = ?
            GROUP BY m.snapshot_date, m.fiscal_year, m.grade_category, m.grade_name
            ORDER BY m.snapshot_date, m.grade_category
        '''
        cursor.execute(query, (school_id,))

        # 学年ごとにグループ化（年度を跨いで全てのデータを表示）
        grade_data = defaultdict(lambda: {'dates': [], 'rates': []})
        for row in cursor.fetchall():
            snapshot_date, fiscal_year, grade_cat, grade_name, students, members = row
            rate = members / students if students > 0 else 0

            key = grade_name or grade_cat or '不明'
            grade_data[key]['dates'].append(str(snapshot_date))
            grade_data[key]['rates'].append(round(rate * 100, 1))

        # 全データを current_year に入れる（時系列表示用）
        # prev_year は空にする（会員率は年度比較ではなく推移を見るため）
        result = {
            'school_name': school_name,
            'attribute': attribute,
            'by_grade': True,
            'current_year': dict(grade_data),
            'prev_year': {},  # 会員率推移では前年度比較は不要
            'events': events
        }

    else:
        # 全学年まとめ - 全てのスナップショット日を時系列で表示
        query = '''
            SELECT
                m.snapshot_date,
                SUM(m.student_count) as students,
                SUM(m.member_count) as members
            FROM member_rates m
            WHERE m.school_id = ?
            GROUP BY m.snapshot_date
            ORDER BY m.snapshot_date
        '''
        cursor.execute(query, (school_id,))

        all_data = {'dates': [], 'rates': []}

        for row in cursor.fetchall():
            snapshot_date, students, members = row
            rate = members / students if students > 0 else 0
            all_data['dates'].append(str(snapshot_date))
            all_data['rates'].append(round(rate * 100, 1))

        result = {
            'school_name': school_name,
            'attribute': attribute,
            'by_grade': False,
            'current_year': all_data,  # 全ての日付データを時系列表示
            'prev_year': {'dates': [], 'rates': []},  # 会員率推移では前年度比較は不要
            'events': events
        }

    # 期待値（属性平均）を取得
    if attribute:
        result['expected'] = get_attribute_average_all_dates(attribute, cursor)
    else:
        result['expected'] = None

    conn.close()
    return result


def get_attribute_average(attribute, cursor):
    """属性の平均会員率推移を取得（旧バージョン・互換性のため残す）"""
    query = '''
        SELECT
            r.report_date,
            m.fiscal_year,
            SUM(m.student_count) as students,
            SUM(m.member_count) as members
        FROM member_rates m
        JOIN reports r ON m.report_id = r.id
        JOIN schools s ON m.school_id = s.id
        WHERE s.attribute = ?
        GROUP BY r.report_date, m.fiscal_year
        ORDER BY r.report_date
    '''
    cursor.execute(query, (attribute,))

    current_year = {'dates': [], 'rates': []}
    prev_year = {'dates': [], 'rates': []}

    rows = cursor.fetchall()
    if rows:
        years = set(row[1] for row in rows if row[1])
        current_fy = max(years) if years else None
        prev_fy = current_fy - 1 if current_fy else None

        for row in rows:
            report_date, fiscal_year, students, members = row
            rate = members / students if students > 0 else 0

            if fiscal_year == current_fy:
                current_year['dates'].append(str(report_date))
                current_year['rates'].append(round(rate * 100, 1))
            elif fiscal_year == prev_fy:
                prev_year['dates'].append(str(report_date))
                prev_year['rates'].append(round(rate * 100, 1))

    return {'current_year': current_year, 'prev_year': prev_year}


def get_attribute_average_all_dates(attribute, cursor):
    """属性の平均会員率推移を取得（全スナップショット日表示版）"""
    query = '''
        SELECT
            m.snapshot_date,
            SUM(m.student_count) as students,
            SUM(m.member_count) as members
        FROM member_rates m
        JOIN schools s ON m.school_id = s.id
        WHERE s.attribute = ?
        GROUP BY m.snapshot_date
        ORDER BY m.snapshot_date
    '''
    cursor.execute(query, (attribute,))

    all_data = {'dates': [], 'rates': []}

    for row in cursor.fetchall():
        snapshot_date, students, members = row
        rate = members / students if students > 0 else 0
        all_data['dates'].append(str(snapshot_date))
        all_data['rates'].append(round(rate * 100, 1))

    return {'current_year': all_data, 'prev_year': {'dates': [], 'rates': []}}


def get_member_rate_trend_by_attribute(attribute, studio=None, db_path=None):
    """
    属性単位の会員率推移を取得

    全てのスナップショット日のデータを時系列で表示する。

    Args:
        attribute: 属性（幼稚園、小学校など）
        studio: 写真館名（オプション、絞り込み用）
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # クエリ条件
    conditions = ['s.attribute = ?']
    params = [attribute]

    if studio:
        conditions.append('s.studio_name = ?')
        params.append(studio)

    where_clause = ' AND '.join(conditions)

    # 対象学校数
    cursor.execute(f'''
        SELECT COUNT(DISTINCT s.id)
        FROM schools s
        WHERE {where_clause}
    ''', params)
    school_count = cursor.fetchone()[0]

    # 会員率推移（全スナップショット日を時系列表示）
    query = f'''
        SELECT
            m.snapshot_date,
            SUM(m.student_count) as students,
            SUM(m.member_count) as members
        FROM member_rates m
        JOIN schools s ON m.school_id = s.id
        WHERE {where_clause}
        GROUP BY m.snapshot_date
        ORDER BY m.snapshot_date
    '''
    cursor.execute(query, params)

    all_data = {'dates': [], 'rates': []}

    for row in cursor.fetchall():
        snapshot_date, students, members = row
        rate = members / students if students > 0 else 0
        all_data['dates'].append(str(snapshot_date))
        all_data['rates'].append(round(rate * 100, 1))

    # 全体平均（期待値として使用）- 全スナップショット日
    cursor.execute('''
        SELECT
            m.snapshot_date,
            SUM(m.student_count) as students,
            SUM(m.member_count) as members
        FROM member_rates m
        GROUP BY m.snapshot_date
        ORDER BY m.snapshot_date
    ''')

    overall_data = {'dates': [], 'rates': []}

    for row in cursor.fetchall():
        snapshot_date, students, members = row
        rate = members / students if students > 0 else 0
        overall_data['dates'].append(str(snapshot_date))
        overall_data['rates'].append(round(rate * 100, 1))

    conn.close()

    return {
        'attribute': attribute,
        'studio': studio,
        'school_count': school_count,
        'by_grade': False,
        'current_year': all_data,  # 全スナップショット日のデータ
        'prev_year': {'dates': [], 'rates': []},  # 会員率推移では前年度比較は不要
        'expected': {'current_year': overall_data, 'prev_year': {'dates': [], 'rates': []}},
        'events': []  # 属性単位ではイベントなし
    }


def export_to_csv(data, filename):
    """データをCSV形式でエクスポート"""
    import csv

    rows = []

    if data.get('by_grade') and isinstance(data.get('current_year'), dict):
        # 学年別データ
        header = ['日付', '年度']
        grades = list(data['current_year'].keys())
        header.extend([f'{g}_会員率' for g in grades])

        # 今年度
        if grades and data['current_year'].get(grades[0], {}).get('dates'):
            for i, date in enumerate(data['current_year'][grades[0]]['dates']):
                row = [date, '今年度']
                for g in grades:
                    rates = data['current_year'].get(g, {}).get('rates', [])
                    row.append(rates[i] if i < len(rates) else '')
                rows.append(row)

        # 前年度
        if grades and data['prev_year'].get(grades[0], {}).get('dates'):
            for i, date in enumerate(data['prev_year'][grades[0]]['dates']):
                row = [date, '前年度']
                for g in grades:
                    rates = data['prev_year'].get(g, {}).get('rates', [])
                    row.append(rates[i] if i < len(rates) else '')
                rows.append(row)

    else:
        # 全学年まとめ or 属性データ
        header = ['日付', '年度', '会員率', '期待値']

        # 今年度
        current = data.get('current_year', {})
        expected_current = data.get('expected', {}).get('current_year', {})

        for i, date in enumerate(current.get('dates', [])):
            rate = current['rates'][i] if i < len(current.get('rates', [])) else ''
            exp = expected_current.get('rates', [])[i] if i < len(expected_current.get('rates', [])) else ''
            rows.append([date, '今年度', rate, exp])

        # 前年度
        prev = data.get('prev_year', {})
        expected_prev = data.get('expected', {}).get('prev_year', {})

        for i, date in enumerate(prev.get('dates', [])):
            rate = prev['rates'][i] if i < len(prev.get('rates', [])) else ''
            exp = expected_prev.get('rates', [])[i] if i < len(expected_prev.get('rates', [])) else ''
            rows.append([date, '前年度', rate, exp])

    # CSV書き出し
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    return filename


def get_sales_filter_options(db_path=None):
    """売上推移グラフ用のフィルター選択肢を取得"""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 事業所一覧（regionカラム）
    cursor.execute('''
        SELECT DISTINCT region FROM schools
        WHERE region IS NOT NULL AND region != ''
        ORDER BY region
    ''')
    branches = [row[0] for row in cursor.fetchall()]

    # 写真館一覧
    cursor.execute('''
        SELECT DISTINCT studio_name FROM schools
        WHERE studio_name IS NOT NULL AND studio_name != ''
        ORDER BY studio_name
    ''')
    studios = [row[0] for row in cursor.fetchall()]

    # 担当者一覧（managerカラム）
    cursor.execute('''
        SELECT DISTINCT manager FROM schools
        WHERE manager IS NOT NULL AND manager != ''
        ORDER BY manager
    ''')
    persons = [row[0] for row in cursor.fetchall()]

    # 学校一覧（事業所・写真館・担当者付き）
    cursor.execute('''
        SELECT id, school_name, region, studio_name, manager
        FROM schools
        ORDER BY school_name
    ''')
    schools = [{'id': row[0], 'name': row[1], 'branch': row[2], 'studio': row[3], 'person': row[4]}
               for row in cursor.fetchall()]

    conn.close()

    return {
        'branches': branches,
        'studios': studios,
        'persons': persons,
        'schools': schools
    }


def get_sales_trend_by_school(school_id, db_path=None):
    """
    学校単位の売上推移を取得

    Args:
        school_id: 学校ID
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 学校情報
    cursor.execute('SELECT school_name, studio_name FROM schools WHERE id = ?', (school_id,))
    school_info = cursor.fetchone()
    if not school_info:
        conn.close()
        return None

    school_name, studio_name = school_info

    # 売上推移（レポート日ごとに累計売上を集計）
    cursor.execute('''
        SELECT
            r.report_date,
            ss.fiscal_year,
            SUM(ss.sales) as total_sales
        FROM school_sales ss
        JOIN reports r ON ss.report_id = r.id
        WHERE ss.school_id = ?
        GROUP BY r.report_date, ss.fiscal_year
        ORDER BY r.report_date
    ''', (school_id,))

    current_year = {'dates': [], 'sales': []}
    prev_year = {'dates': [], 'sales': []}

    rows = cursor.fetchall()
    if rows:
        years = set(row[1] for row in rows if row[1])
        current_fy = max(years) if years else None
        prev_fy = current_fy - 1 if current_fy else None

        for row in rows:
            report_date, fiscal_year, total_sales = row
            if fiscal_year == current_fy:
                current_year['dates'].append(str(report_date))
                current_year['sales'].append(total_sales or 0)
            elif fiscal_year == prev_fy:
                prev_year['dates'].append(str(report_date))
                prev_year['sales'].append(total_sales or 0)

    # 最新の累計売上を取得
    current_total = current_year['sales'][-1] if current_year['sales'] else 0
    prev_total = prev_year['sales'][-1] if prev_year['sales'] else 0
    yoy = current_total / prev_total if prev_total > 0 else 0

    conn.close()

    return {
        'school_name': school_name,
        'studio_name': studio_name,
        'current_year': current_year,
        'prev_year': prev_year,
        'current_total': current_total,
        'prev_total': prev_total,
        'yoy': yoy
    }


def get_event_sales_by_school(school_id, db_path=None):
    """
    学校単位のイベント別売上を取得

    Args:
        school_id: 学校ID
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 学校情報
    cursor.execute('SELECT school_name FROM schools WHERE id = ?', (school_id,))
    school_info = cursor.fetchone()
    if not school_info:
        conn.close()
        return None

    school_name = school_info[0]

    # イベント別売上を取得（開始日も含める）
    cursor.execute('''
        SELECT
            e.id as event_id,
            e.event_name,
            e.start_date,
            es.fiscal_year,
            SUM(es.sales) as total_sales
        FROM events e
        JOIN event_sales es ON e.id = es.event_id
        WHERE e.school_id = ?
        GROUP BY e.id, e.event_name, e.start_date, es.fiscal_year
        ORDER BY es.fiscal_year DESC, total_sales DESC
    ''', (school_id,))

    events = []
    rows = cursor.fetchall()
    if rows:
        years = set(row[3] for row in rows if row[3])
        current_fy = max(years) if years else None
        prev_fy = current_fy - 1 if current_fy else None

        # 年度別に集計
        current_year_events = []
        prev_year_events = []

        for row in rows:
            event_id, event_name, start_date, fiscal_year, total_sales = row
            event_data = {
                'event_id': event_id,
                'event_name': event_name,
                'start_date': str(start_date) if start_date else None,
                'sales': total_sales or 0
            }
            if fiscal_year == current_fy:
                current_year_events.append(event_data)
            elif fiscal_year == prev_fy:
                prev_year_events.append(event_data)

        events = {
            'current_year': current_year_events,
            'prev_year': prev_year_events
        }

    conn.close()

    return {
        'school_name': school_name,
        'events': events
    }


def get_sales_trend_by_studio(studio_name, db_path=None):
    """
    写真館単位の売上推移を取得

    Args:
        studio_name: 写真館名
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 対象学校数
    cursor.execute('SELECT COUNT(*) FROM schools WHERE studio_name = ?', (studio_name,))
    school_count = cursor.fetchone()[0]

    # 売上推移（レポート日ごとに集計）
    cursor.execute('''
        SELECT
            r.report_date,
            ss.fiscal_year,
            SUM(ss.sales) as total_sales
        FROM school_sales ss
        JOIN reports r ON ss.report_id = r.id
        JOIN schools s ON ss.school_id = s.id
        WHERE s.studio_name = ?
        GROUP BY r.report_date, ss.fiscal_year
        ORDER BY r.report_date
    ''', (studio_name,))

    current_year = {'dates': [], 'sales': []}
    prev_year = {'dates': [], 'sales': []}

    rows = cursor.fetchall()
    if rows:
        years = set(row[1] for row in rows if row[1])
        current_fy = max(years) if years else None
        prev_fy = current_fy - 1 if current_fy else None

        for row in rows:
            report_date, fiscal_year, total_sales = row
            if fiscal_year == current_fy:
                current_year['dates'].append(str(report_date))
                current_year['sales'].append(total_sales or 0)
            elif fiscal_year == prev_fy:
                prev_year['dates'].append(str(report_date))
                prev_year['sales'].append(total_sales or 0)

    # 最新の累計売上を取得
    current_total = current_year['sales'][-1] if current_year['sales'] else 0
    prev_total = prev_year['sales'][-1] if prev_year['sales'] else 0
    yoy = current_total / prev_total if prev_total > 0 else 0

    conn.close()

    return {
        'studio_name': studio_name,
        'school_count': school_count,
        'current_year': current_year,
        'prev_year': prev_year,
        'current_total': current_total,
        'prev_total': prev_total,
        'yoy': yoy
    }


def get_monthly_sales_by_branch(db_path=None):
    """
    事業所別の月別売上を取得（マッピングによる統合対応）

    Returns:
        branches: 事業所ごとの月別売上（今年度/前年度/予算）
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 最新のレポートIDを取得
    cursor.execute('SELECT id, report_date FROM reports ORDER BY report_date DESC LIMIT 1')
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {}
    latest_report_id = row[0]

    # 現在の年度を計算
    from alerts import get_current_fiscal_year
    current_fy = get_current_fiscal_year()
    prev_fy = current_fy - 1

    # 事業所一覧を取得し、マッピング適用後の一意なリストを作成
    cursor.execute('''
        SELECT DISTINCT region FROM schools
        WHERE region IS NOT NULL AND region != ''
        ORDER BY region
    ''')
    raw_branches = [row[0] for row in cursor.fetchall()]

    # マッピング適用後の事業所リスト（重複排除）
    normalized_branches = list(dict.fromkeys([normalize_branch(b) for b in raw_branches]))

    result = {}

    for branch in normalized_branches:
        # マッピングで統合される事業所を取得（例：鹿沼 → [鹿沼, 栃木]）
        source_branches = [b for b in raw_branches if normalize_branch(b) == branch]

        # 今年度の月別売上（統合対象の事業所を合算）
        placeholders = ','.join(['?' for _ in source_branches])
        cursor.execute(f'''
            SELECT
                ss.month,
                SUM(ss.sales) as total_sales
            FROM school_sales ss
            JOIN schools s ON ss.school_id = s.id
            WHERE s.region IN ({placeholders}) AND ss.fiscal_year = ?
            GROUP BY ss.month
            ORDER BY CASE WHEN ss.month >= 4 THEN ss.month - 4 ELSE ss.month + 8 END
        ''', (*source_branches, current_fy))

        current_data = {row[0]: row[1] for row in cursor.fetchall()}

        # 前年度の月別売上
        cursor.execute(f'''
            SELECT
                ss.month,
                SUM(ss.sales) as total_sales
            FROM school_sales ss
            JOIN schools s ON ss.school_id = s.id
            WHERE s.region IN ({placeholders}) AND ss.fiscal_year = ?
            GROUP BY ss.month
            ORDER BY CASE WHEN ss.month >= 4 THEN ss.month - 4 ELSE ss.month + 8 END
        ''', (*source_branches, prev_fy))

        prev_data = {row[0]: row[1] for row in cursor.fetchall()}

        # 予算は全体の予算から按分（簡易実装：月別サマリーから学校数比率で計算）
        # 実際のデータがあれば正確な予算を使う
        # ここでは仮に予算を0として、後で全体の予算から計算
        budget_data = {}

        result[branch] = {
            'current': current_data,
            'prev': prev_data,
            'budget': budget_data
        }

    conn.close()

    return {
        'branches': normalized_branches,
        'data': result,
        'fiscal_year': current_fy
    }


def get_monthly_sales_by_person(db_path=None):
    """
    担当者別の月別売上を取得

    Returns:
        persons: 担当者ごとの月別売上（今年度/前年度）
        person_branches: 担当者と事業所の紐付け
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 最新のレポートIDを取得
    cursor.execute('SELECT id, report_date FROM reports ORDER BY report_date DESC LIMIT 1')
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {}
    latest_report_id = row[0]

    # 現在の年度を計算
    from alerts import get_current_fiscal_year
    current_fy = get_current_fiscal_year()
    prev_fy = current_fy - 1

    # 担当者一覧（事業所情報も取得）
    cursor.execute('''
        SELECT DISTINCT manager, region FROM schools
        WHERE manager IS NOT NULL AND manager != ''
        ORDER BY manager
    ''')
    rows = cursor.fetchall()
    persons = list(set(row[0] for row in rows))
    persons.sort()

    # 担当者と事業所の紐付け（マッピング適用）
    person_branches = {}
    for row in rows:
        person, region = row
        if person not in person_branches:
            person_branches[person] = []
        normalized_region = normalize_branch(region)
        if normalized_region and normalized_region not in person_branches[person]:
            person_branches[person].append(normalized_region)

    result = {}

    for person in persons:
        # 今年度の月別売上
        cursor.execute('''
            SELECT
                ss.month,
                SUM(ss.sales) as total_sales
            FROM school_sales ss
            JOIN schools s ON ss.school_id = s.id
            WHERE s.manager = ? AND ss.fiscal_year = ?
            GROUP BY ss.month
            ORDER BY CASE WHEN ss.month >= 4 THEN ss.month - 4 ELSE ss.month + 8 END
        ''', (person, current_fy))

        current_data = {row[0]: row[1] for row in cursor.fetchall()}

        # 前年度の月別売上
        cursor.execute('''
            SELECT
                ss.month,
                SUM(ss.sales) as total_sales
            FROM school_sales ss
            JOIN schools s ON ss.school_id = s.id
            WHERE s.manager = ? AND ss.fiscal_year = ?
            GROUP BY ss.month
            ORDER BY CASE WHEN ss.month >= 4 THEN ss.month - 4 ELSE ss.month + 8 END
        ''', (person, prev_fy))

        prev_data = {row[0]: row[1] for row in cursor.fetchall()}

        result[person] = {
            'current': current_data,
            'prev': prev_data
        }

    conn.close()

    return {
        'persons': persons,
        'data': result,
        'person_branches': person_branches,
        'fiscal_year': current_fy
    }


if __name__ == '__main__':
    # テスト
    options = get_filter_options()
    print(f"属性: {len(options['attributes'])}種類")
    print(f"写真館: {len(options['studios'])}社")
    print(f"学校: {len(options['schools'])}校")

    # 最初の学校でテスト
    if options['schools']:
        school = options['schools'][0]
        print(f"\nテスト: {school['name']}")
        data = get_member_rate_trend_by_school(school['id'], by_grade=False)
        if data:
            print(f"  今年度データ点数: {len(data['current_year'].get('dates', []))}")
            print(f"  前年度データ点数: {len(data['prev_year'].get('dates', []))}")
