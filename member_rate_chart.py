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


def get_member_rate_trend_by_school(school_id, by_grade=False, target_fy=None, db_path=None):
    """
    学校単位の会員率推移を取得

    会員率は報告書のスナップショット日ごとに蓄積されているため、
    指定年度（4月〜翌3月）のスナップショット日のデータを時系列で表示する。

    Args:
        school_id: 学校ID
        by_grade: True=学年別, False=全学年まとめ
        target_fy: 対象年度（例: 2024 = 2024年4月〜2025年3月）。Noneの場合は全期間
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

    # 年度フィルタの日付範囲を計算
    date_filter = ""
    date_params = []
    if target_fy:
        start_date = f"{target_fy}-04-01"
        end_date = f"{target_fy + 1}-03-31"
        date_filter = " AND m.snapshot_date >= ? AND m.snapshot_date <= ?"
        date_params = [start_date, end_date]

    # イベント開始日を取得（アノテーション用）
    if target_fy:
        cursor.execute('''
            SELECT event_name, start_date, fiscal_year
            FROM events
            WHERE school_id = ? AND fiscal_year = ? AND start_date IS NOT NULL
            ORDER BY start_date
        ''', (school_id, target_fy))
    else:
        cursor.execute('''
            SELECT event_name, start_date, fiscal_year
            FROM events
            WHERE school_id = ? AND start_date IS NOT NULL
            ORDER BY start_date
        ''', (school_id,))
    events = [{'name': row[0], 'date': str(row[1]), 'year': row[2]} for row in cursor.fetchall()]

    if by_grade:
        # 学年別データ - スナップショット日を時系列で表示
        query = f'''
            SELECT
                m.snapshot_date,
                m.fiscal_year,
                m.grade_category,
                m.grade_name,
                SUM(m.student_count) as students,
                SUM(m.member_count) as members
            FROM member_rates m
            WHERE m.school_id = ?{date_filter}
            GROUP BY m.snapshot_date, m.fiscal_year, m.grade_category, m.grade_name
            ORDER BY m.snapshot_date, m.grade_category
        '''
        cursor.execute(query, (school_id, *date_params))

        # 学年ごとにグループ化
        grade_data = defaultdict(lambda: {'dates': [], 'rates': []})
        for row in cursor.fetchall():
            snapshot_date, fiscal_year, grade_cat, grade_name, students, members = row
            rate = members / students if students > 0 else 0

            key = grade_name or grade_cat or '不明'
            grade_data[key]['dates'].append(str(snapshot_date))
            grade_data[key]['rates'].append(round(rate * 100, 1))

        result = {
            'school_name': school_name,
            'attribute': attribute,
            'by_grade': True,
            'current_year': dict(grade_data),
            'prev_year': {},
            'events': events,
            'fiscal_year': target_fy
        }

    else:
        # 全学年まとめ
        query = f'''
            SELECT
                m.snapshot_date,
                SUM(m.student_count) as students,
                SUM(m.member_count) as members
            FROM member_rates m
            WHERE m.school_id = ?{date_filter}
            GROUP BY m.snapshot_date
            ORDER BY m.snapshot_date
        '''
        cursor.execute(query, (school_id, *date_params))

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
            'current_year': all_data,
            'prev_year': {'dates': [], 'rates': []},
            'events': events,
            'fiscal_year': target_fy
        }

    # 期待値（属性平均）を取得
    if attribute:
        result['expected'] = get_attribute_average_all_dates(attribute, cursor, target_fy)
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


def get_attribute_average_all_dates(attribute, cursor, target_fy=None):
    """属性の平均会員率推移を取得（年度フィルタ対応版）"""
    date_filter = ""
    date_params = [attribute]
    if target_fy:
        start_date = f"{target_fy}-04-01"
        end_date = f"{target_fy + 1}-03-31"
        date_filter = " AND m.snapshot_date >= ? AND m.snapshot_date <= ?"
        date_params = [attribute, start_date, end_date]

    query = f'''
        SELECT
            m.snapshot_date,
            SUM(m.student_count) as students,
            SUM(m.member_count) as members
        FROM member_rates m
        JOIN schools s ON m.school_id = s.id
        WHERE s.attribute = ?{date_filter}
        GROUP BY m.snapshot_date
        ORDER BY m.snapshot_date
    '''
    cursor.execute(query, date_params)

    all_data = {'dates': [], 'rates': []}

    for row in cursor.fetchall():
        snapshot_date, students, members = row
        rate = members / students if students > 0 else 0
        all_data['dates'].append(str(snapshot_date))
        all_data['rates'].append(round(rate * 100, 1))

    return {'current_year': all_data, 'prev_year': {'dates': [], 'rates': []}}


def get_member_rate_trend_by_attribute(attribute, studio=None, target_fy=None, db_path=None):
    """
    属性単位の会員率推移を取得

    指定年度（4月〜翌3月）のスナップショット日のデータを時系列で表示する。

    Args:
        attribute: 属性（幼稚園、小学校など）
        studio: 写真館名（オプション、絞り込み用）
        target_fy: 対象年度（例: 2024 = 2024年4月〜2025年3月）。Noneの場合は全期間
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # クエリ条件
    conditions = ['s.attribute = ?']
    params = [attribute]

    if studio:
        conditions.append('s.studio_name = ?')
        params.append(studio)

    # 年度フィルタ
    if target_fy:
        start_date = f"{target_fy}-04-01"
        end_date = f"{target_fy + 1}-03-31"
        conditions.append('m.snapshot_date >= ?')
        conditions.append('m.snapshot_date <= ?')
        params.extend([start_date, end_date])

    where_clause = ' AND '.join(conditions)

    # 対象学校数
    cursor.execute(f'''
        SELECT COUNT(DISTINCT s.id)
        FROM schools s
        WHERE s.attribute = ?{' AND s.studio_name = ?' if studio else ''}
    ''', [attribute, studio] if studio else [attribute])
    school_count = cursor.fetchone()[0]

    # 会員率推移
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

    # 全体平均（期待値として使用）
    overall_conditions = []
    overall_params = []
    if target_fy:
        overall_conditions.append('m.snapshot_date >= ?')
        overall_conditions.append('m.snapshot_date <= ?')
        overall_params = [start_date, end_date]

    overall_where = ' WHERE ' + ' AND '.join(overall_conditions) if overall_conditions else ''

    cursor.execute(f'''
        SELECT
            m.snapshot_date,
            SUM(m.student_count) as students,
            SUM(m.member_count) as members
        FROM member_rates m
        {overall_where}
        GROUP BY m.snapshot_date
        ORDER BY m.snapshot_date
    ''', overall_params)

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
        'current_year': all_data,
        'prev_year': {'dates': [], 'rates': []},
        'expected': {'current_year': overall_data, 'prev_year': {'dates': [], 'rates': []}},
        'events': [],
        'fiscal_year': target_fy
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


def get_sales_trend_by_school(school_id, target_fy=None, db_path=None):
    """
    学校単位の売上推移を取得

    月別の売上データを累計で表示する（4月から順に積み上げ）。

    Args:
        school_id: 学校ID
        target_fy: 対象年度（指定しない場合は最新年度）
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

    # 月別売上を取得（年度別）
    cursor.execute('''
        SELECT
            ss.fiscal_year,
            ss.month,
            ss.sales
        FROM school_sales ss
        WHERE ss.school_id = ?
        ORDER BY ss.fiscal_year,
                 CASE WHEN ss.month >= 4 THEN ss.month - 4 ELSE ss.month + 8 END
    ''', (school_id,))

    # 年度別にデータを整理
    yearly_data = {}
    for row in cursor.fetchall():
        fiscal_year, month, sales = row
        if fiscal_year not in yearly_data:
            yearly_data[fiscal_year] = []
        yearly_data[fiscal_year].append({
            'month': month,
            'sales': sales or 0
        })

    # 対象年度と前年度を特定
    years = sorted(yearly_data.keys(), reverse=True)
    if target_fy and target_fy in yearly_data:
        current_fy = target_fy
    else:
        current_fy = years[0] if years else None
    prev_fy = current_fy - 1 if current_fy and current_fy - 1 in yearly_data else None

    # 累計売上を計算（月順に積み上げ）
    def build_cumulative_data(data_list):
        """月別データを累計に変換"""
        dates = []
        sales = []
        cumulative = 0
        for item in data_list:
            cumulative += item['sales']
            dates.append(f"{item['month']}月")
            sales.append(cumulative)
        return {'dates': dates, 'sales': sales}

    current_year = build_cumulative_data(yearly_data.get(current_fy, [])) if current_fy else {'dates': [], 'sales': []}
    prev_year = build_cumulative_data(yearly_data.get(prev_fy, [])) if prev_fy else {'dates': [], 'sales': []}

    # 累計売上を取得
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
        'yoy': yoy,
        'fiscal_year': current_fy
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


def get_sales_trend_by_studio(studio_name, target_fy=None, db_path=None):
    """
    写真館単位の売上推移を取得

    月別の売上データを累計で表示する（4月から順に積み上げ）。

    Args:
        studio_name: 写真館名
        target_fy: 対象年度（指定しない場合は最新年度）
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 対象学校数
    cursor.execute('SELECT COUNT(*) FROM schools WHERE studio_name = ?', (studio_name,))
    school_count = cursor.fetchone()[0]

    # 月別売上を取得（年度・月別に集計）
    cursor.execute('''
        SELECT
            ss.fiscal_year,
            ss.month,
            SUM(ss.sales) as total_sales
        FROM school_sales ss
        JOIN schools s ON ss.school_id = s.id
        WHERE s.studio_name = ?
        GROUP BY ss.fiscal_year, ss.month
        ORDER BY ss.fiscal_year,
                 CASE WHEN ss.month >= 4 THEN ss.month - 4 ELSE ss.month + 8 END
    ''', (studio_name,))

    # 年度別にデータを整理
    yearly_data = {}
    for row in cursor.fetchall():
        fiscal_year, month, total_sales = row
        if fiscal_year not in yearly_data:
            yearly_data[fiscal_year] = []
        yearly_data[fiscal_year].append({
            'month': month,
            'sales': total_sales or 0
        })

    # 対象年度と前年度を特定
    years = sorted(yearly_data.keys(), reverse=True)
    if target_fy and target_fy in yearly_data:
        current_fy = target_fy
    else:
        current_fy = years[0] if years else None
    prev_fy = current_fy - 1 if current_fy and current_fy - 1 in yearly_data else None

    # 累計売上を計算（月順に積み上げ）
    def build_cumulative_data(data_list):
        """月別データを累計に変換"""
        dates = []
        sales = []
        cumulative = 0
        for item in data_list:
            cumulative += item['sales']
            dates.append(f"{item['month']}月")
            sales.append(cumulative)
        return {'dates': dates, 'sales': sales}

    current_year = build_cumulative_data(yearly_data.get(current_fy, [])) if current_fy else {'dates': [], 'sales': []}
    prev_year = build_cumulative_data(yearly_data.get(prev_fy, [])) if prev_fy else {'dates': [], 'sales': []}

    # 累計売上を取得
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
        'yoy': yoy,
        'fiscal_year': current_fy
    }


def get_monthly_sales_by_branch(db_path=None, target_years=None):
    """
    事業所別の月別売上を取得（マッピングによる統合対応・年度別）

    Args:
        db_path: データベースパス
        target_years: 対象年度のリスト（例: [2024, 2025]）。Noneの場合は現在年度のみ

    Returns:
        branches: 事業所ごとの月別売上（年度別）
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

    # 対象年度が指定されていない場合は現在年度のみ
    if target_years is None:
        target_years = [current_fy]

    # 事業所一覧を取得し、マッピング適用後の一意なリストを作成
    cursor.execute('''
        SELECT DISTINCT region FROM schools
        WHERE region IS NOT NULL AND region != ''
        ORDER BY region
    ''')
    raw_branches = [row[0] for row in cursor.fetchall()]

    # マッピング適用後の事業所リスト（重複排除）
    normalized_branches = list(dict.fromkeys([normalize_branch(b) for b in raw_branches]))

    # 年度別のデータを格納
    result_by_year = {}

    for year in target_years:
        result = {}
        prev_fy = year - 1

        for branch in normalized_branches:
            # マッピングで統合される事業所を取得（例：鹿沼 → [鹿沼, 栃木]）
            source_branches = [b for b in raw_branches if normalize_branch(b) == branch]

            # 対象年度の月別売上（統合対象の事業所を合算）
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
            ''', (*source_branches, year))

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

            # 予算は全体の予算から按分（簡易実装）
            budget_data = {}

            result[branch] = {
                'current': current_data,
                'prev': prev_data,
                'budget': budget_data
            }

        result_by_year[year] = result

    conn.close()

    return {
        'branches': normalized_branches,
        'data_by_year': result_by_year,
        'current_fiscal_year': current_fy
    }


def get_monthly_sales_by_person(db_path=None, target_years=None):
    """
    担当者別の月別売上を取得（年度別）

    Args:
        db_path: データベースパス
        target_years: 対象年度のリスト（例: [2024, 2025]）。Noneの場合は現在年度のみ

    Returns:
        persons: 担当者ごとの月別売上（年度別）
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

    # 対象年度が指定されていない場合は現在年度のみ
    if target_years is None:
        target_years = [current_fy]

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

    # 年度別のデータを格納
    result_by_year = {}

    for year in target_years:
        result = {}
        prev_fy = year - 1

        for person in persons:
            # 対象年度の月別売上
            cursor.execute('''
                SELECT
                    ss.month,
                    SUM(ss.sales) as total_sales
                FROM school_sales ss
                JOIN schools s ON ss.school_id = s.id
                WHERE s.manager = ? AND ss.fiscal_year = ?
                GROUP BY ss.month
                ORDER BY CASE WHEN ss.month >= 4 THEN ss.month - 4 ELSE ss.month + 8 END
            ''', (person, year))

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

        result_by_year[year] = result

    conn.close()

    return {
        'persons': persons,
        'data_by_year': result_by_year,
        'person_branches': person_branches,
        'current_fiscal_year': current_fy
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
