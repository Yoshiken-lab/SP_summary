#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上分析システム - データベース管理 (V2)
再構築版: シンプルで保守性の高いスキーマ
"""

import sqlite3
from pathlib import Path
from datetime import datetime

# デフォルトのDBパス
DEFAULT_DB_PATH = Path(__file__).parent / 'schoolphoto_v2.db'


def get_connection(db_path=None):
    """データベース接続を取得"""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    conn = sqlite3.connect(
        str(db_path),
        timeout=30.0,
        check_same_thread=False
    )
    
    # WALモード有効化（並行アクセス対応）
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA foreign_keys = ON')  # 外部キー制約有効化
    
    return conn


def init_database(db_path=None):
    """データベースを初期化（全テーブル作成）"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # 1. reports (報告書管理)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            report_date DATE NOT NULL UNIQUE,
            imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. schools_master (学校マスタ)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schools_master (
            school_id INTEGER PRIMARY KEY,
            logical_school_id INTEGER NOT NULL,
            school_name TEXT NOT NULL,
            base_school_name TEXT NOT NULL,
            fiscal_year INTEGER,
            region TEXT,
            attribute TEXT,
            studio TEXT,
            manager TEXT,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_schools_logical ON schools_master(logical_school_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_schools_base_name ON schools_master(base_school_name)')
    
    # 3. monthly_totals (月次全体売上)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monthly_totals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            fiscal_year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            total_sales REAL,
            direct_sales REAL,
            studio_sales REAL,
            school_count INTEGER,
            budget REAL,
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
            UNIQUE(report_id, fiscal_year, month)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_monthly_totals_fy ON monthly_totals(fiscal_year, month)')
    
    # 4. manager_monthly_sales (担当者別月次売上)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS manager_monthly_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            fiscal_year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            manager TEXT NOT NULL,
            sales REAL NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
            UNIQUE(report_id, fiscal_year, month, manager)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_manager_sales_fy ON manager_monthly_sales(fiscal_year, month)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_manager_sales_manager ON manager_monthly_sales(manager)')
    
    # 5. branch_monthly_sales (事業所別月次売上)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS branch_monthly_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            fiscal_year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            branch_name TEXT NOT NULL,
            sales REAL NOT NULL,
            budget REAL,
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
            UNIQUE(report_id, fiscal_year, month, branch_name)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_branch_sales_fy ON branch_monthly_sales(fiscal_year, month)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_branch_sales_branch ON branch_monthly_sales(branch_name)')
    
    # 6. school_monthly_sales (学校別月次売上)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS school_monthly_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            fiscal_year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            school_id INTEGER NOT NULL,
            manager TEXT,
            studio TEXT,
            sales REAL NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
            FOREIGN KEY (school_id) REFERENCES schools_master(school_id),
            UNIQUE(report_id, fiscal_year, month, school_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_school_sales_fy ON school_monthly_sales(fiscal_year, month)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_school_sales_school ON school_monthly_sales(school_id)')
    
    # 7. event_sales (イベント別売上)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            fiscal_year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            branch TEXT,
            school_id INTEGER NOT NULL,
            event_name TEXT NOT NULL,
            event_date DATE,
            sales REAL NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
            FOREIGN KEY (school_id) REFERENCES schools_master(school_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_sales_fy ON event_sales(fiscal_year, month)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_sales_school ON event_sales(school_id)')
    
    # 8. member_rates (会員率スナップショット)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS member_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            snapshot_date DATE NOT NULL,
            school_id INTEGER NOT NULL,
            grade TEXT NOT NULL,
            member_rate REAL,
            total_students INTEGER,
            member_count INTEGER,
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
            FOREIGN KEY (school_id) REFERENCES schools_master(school_id),
            UNIQUE(report_id, school_id, grade)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_member_rates_school ON member_rates(school_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_member_rates_date ON member_rates(snapshot_date)')
    
    # 9. manager_aliases (担当者名マッピング)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS manager_aliases (
            alias TEXT PRIMARY KEY,
            canonical_name TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    
    print(f"データベースを初期化しました: {db_path or DEFAULT_DB_PATH}")


def normalize_manager_name(manager_name, conn=None):
    """担当者名を正規化（manager_aliasesテーブルを使用）"""
    if not manager_name:
        return manager_name
    
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
    
    cursor = conn.cursor()
    cursor.execute('SELECT canonical_name FROM manager_aliases WHERE alias = ?', (manager_name,))
    row = cursor.fetchone()
    
    if close_conn:
        conn.close()
    
    return row[0] if row else manager_name


# ============================================
# 条件別集計機能
# ============================================

def get_current_fiscal_year():
    """現在の年度を取得（4月始まり）"""
    now = datetime.now()
    return now.year if now.month >= 4 else now.year - 1


def get_latest_report_id(conn):
    """最新のレポートIDを取得"""
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(id) FROM reports')
    row = cursor.fetchone()
    return row[0] if row else None


def get_rapid_growth_schools(db_path=None, target_fy=None):
    """
    売上好調校を取得

    前年比で30%以上の売上成長を見せている学校

    Args:
        db_path: データベースパス
        target_fy: 対象年度（Noneの場合は現在年度）

    Returns:
        list: [{school_id, school_name, attribute, branch, studio, current_sales, prev_sales, growth_rate}, ...]
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    current_fy = target_fy if target_fy else get_current_fiscal_year()
    prev_fy = current_fy - 1

    # event_dateベースで年度の範囲を計算（4月始まり）
    current_fy_start = f'{current_fy}-04-01'
    current_fy_end = f'{current_fy + 1}-04-01'
    prev_fy_start = f'{prev_fy}-04-01'
    prev_fy_end = f'{prev_fy + 1}-04-01'

    # event_salesから売上を集計（重複除外 + event_dateベース）
    query = '''
        WITH current_sales AS (
            -- 重複レコードを除外: event_date + event_name の組み合わせでユニーク化
            SELECT
                school_id,
                COALESCE(SUM(sales), 0) as total_sales
            FROM event_sales
            WHERE report_id = ? AND event_date >= ? AND event_date < ?
            GROUP BY school_id
        ),
        prev_sales AS (
            -- 重複レコードを除外: event_date + event_name の組み合わせでユニーク化
            SELECT
                school_id,
                COALESCE(SUM(sales), 0) as total_sales
            FROM event_sales
            WHERE report_id = ? AND event_date >= ? AND event_date < ?
            GROUP BY school_id
        )
        SELECT
            s.school_id,
            s.school_name,
            s.attribute,
            s.region,
            s.studio,
            s.manager,
            s.region,
            COALESCE(curr.total_sales, 0) as current_sales,
            COALESCE(prev.total_sales, 0) as prev_sales,
            (COALESCE(curr.total_sales, 0) - prev.total_sales) / prev.total_sales as growth_rate
        FROM schools_master s
        JOIN current_sales curr ON curr.school_id = s.school_id
        JOIN prev_sales prev ON prev.school_id = s.school_id
        WHERE prev.total_sales > 10000  -- 最低売上を設定
          AND (COALESCE(curr.total_sales, 0) - prev.total_sales) / prev.total_sales >= 0.3
        ORDER BY growth_rate DESC
    '''

    report_id = get_latest_report_id(conn)
    if not report_id:
        conn.close()
        return []

    cursor.execute(query, (report_id, current_fy_start, current_fy_end, report_id, prev_fy_start, prev_fy_end))
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'region': row[3] or '',
            'studio': row[4] or '',
            'manager': row[5] or '',
            'region': row[6] or '',
            'current_sales': row[7],
            'prev_sales': row[8],
            'growth_rate': row[9]
        })
    
    conn.close()
    return results


def get_new_schools(db_path=None, target_fy=None, target_month=None):
    """
    新規開始校を取得（指定年度に売上があり、前年度に売上がない学校）

    Args:
        db_path: データベースパス
        target_fy: 対象年度（Noneの場合は現在年度）
        target_month: 対象月（Noneの場合は全月）

    Returns:
        list: [{school_id, school_name, attribute, branch, studio, first_event_date, current_sales, prev_sales, growth_rate}, ...]
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    current_fy = target_fy if target_fy else get_current_fiscal_year()

    # event_dateベースで年度の範囲を計算（4月始まり）
    current_fy_start = f'{current_fy}-04-01'
    current_fy_end = f'{current_fy + 1}-04-01'

    report_id = get_latest_report_id(conn)
    if not report_id:
        conn.close()
        return []

    query = f'''
        WITH first_events AS (
            -- 各学校の初回イベント日を取得（重複除外済み）
            SELECT
                school_id,
                MIN(event_date) as first_event_date
            FROM event_sales
            WHERE report_id = ?
            GROUP BY school_id
        ),
        current_sales AS (
            -- 重複レコードを除外: event_date + event_name の組み合わせでユニーク化
            SELECT
                school_id,
                COALESCE(SUM(sales), 0) as total_sales
            FROM event_sales
            WHERE report_id = ? AND event_date >= ? AND event_date < ?
            GROUP BY school_id
        )
        SELECT
            s.school_id,
            s.school_name,
            s.attribute,
            s.region,
            s.studio,
            s.manager,
            s.region,
            fe.first_event_date,
            COALESCE(curr.total_sales, 0) as current_sales,
            0 as prev_sales
        FROM first_events fe
        JOIN schools_master s ON s.school_id = fe.school_id
        LEFT JOIN current_sales curr ON curr.school_id = fe.school_id
        WHERE fe.first_event_date >= ? AND fe.first_event_date < ?
        ORDER BY COALESCE(curr.total_sales, 0) DESC
    '''

    # パラメータ: report_id (first), report_id, cur_start, cur_end (current), cur_start, cur_end (where)
    params = [report_id, report_id, current_fy_start, current_fy_end, current_fy_start, current_fy_end]

    cursor.execute(query, params)
    
    results = []
    for row in cursor.fetchall():
        # 日付フォーマット：YYYY年MM月DD日
        first_date = row[7]
        if first_date:
            try:
                date_obj = datetime.strptime(first_date, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%Y-%m-%d')
            except:
                formatted_date = first_date
        else:
            formatted_date = ''
            
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'region': row[3] or '',
            'studio': row[4] or '',
            'manager': row[5] or '',
            'region': row[6] or '',
            'first_event_date': formatted_date,
            'current_sales': row[8],
            'prev_sales': row[9],
            'growth_rate': 1.0  # 新規なので100%（便宜上）
        })
    
    conn.close()
    return results


def get_no_events_schools(db_path=None, target_fy=None, target_month=None):
    """
    今年度未実施校を取得（前年度売上があり、今年度売上がない学校）

    Args:
        db_path: データベースパス
        target_fy: 対象年度（Noneの場合は現在年度）
        target_month: 対象月（Noneの場合は全月）- 互換性のために残しているが未使用

    Returns:
        list: [{school_id, school_name, attribute, branch, studio, prev_event_count, current_sales, prev_sales, growth_rate}, ...]
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    current_fy = target_fy if target_fy else get_current_fiscal_year()
    prev_fy = current_fy - 1

    # event_dateベースで年度の範囲を計算（4月始まり）
    current_fy_start = f'{current_fy}-04-01'
    current_fy_end = f'{current_fy + 1}-04-01'
    prev_fy_start = f'{prev_fy}-04-01'
    prev_fy_end = f'{prev_fy + 1}-04-01'

    report_id = get_latest_report_id(conn)
    if not report_id:
        conn.close()
        return []

    query = f'''
        WITH current_events AS (
            -- 今年度のユニークイベント数（重複除外）
            SELECT
                school_id,
                COUNT(DISTINCT event_date || event_name) as event_count
            FROM event_sales
            WHERE report_id = ? AND event_date >= ? AND event_date < ?
            GROUP BY school_id
        ),
        prev_events AS (
            -- 前年度のユニークイベント数（重複除外）
            SELECT
                school_id,
                COUNT(DISTINCT event_date || event_name) as event_count
            FROM event_sales
            WHERE report_id = ? AND event_date >= ? AND event_date < ?
            GROUP BY school_id
        ),
        prev_sales AS (
            -- 前年度売上（重複除外）
            SELECT
                school_id,
                COALESCE(SUM(sales), 0) as total_sales
            FROM event_sales
            WHERE report_id = ? AND event_date >= ? AND event_date < ?
            GROUP BY school_id
        )
        SELECT
            s.school_id,
            s.school_name,
            s.attribute,
            s.region,
            s.studio,
            s.manager,
            s.region,
            COALESCE(pe.event_count, 0) as prev_event_count,
            0 as current_sales,
            COALESCE(prev.total_sales, 0) as prev_sales,
            -1.0 as growth_rate  -- 未実施なので -100%
        FROM schools_master s
        JOIN prev_events pe ON pe.school_id = s.school_id
        LEFT JOIN current_events ce ON ce.school_id = s.school_id
        LEFT JOIN prev_sales prev ON prev.school_id = s.school_id
        WHERE pe.event_count > 0
          AND (ce.event_count IS NULL OR ce.event_count = 0)
        ORDER BY COALESCE(prev.total_sales, 0) DESC
    '''

    # パラメータ構築
    query_params = [
        report_id, current_fy_start, current_fy_end,  # current_events用
        report_id, prev_fy_start, prev_fy_end,        # prev_events用
        report_id, prev_fy_start, prev_fy_end         # prev_sales用
    ]

    cursor.execute(query, query_params)
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'region': row[3] or '',
            'studio': row[4] or '',
            'manager': row[5] or '',
            'region': row[6] or '',
            'prev_event_count': row[7],
            'current_sales': row[8],
            'prev_sales': row[9],
            'growth_rate': row[10]
        })
    
    conn.close()
    return results


def get_declining_schools(db_path=None, target_fy=None, member_rate_threshold=0.5, sales_decline_threshold=0.1):
    """
    会員率・売上低下校を取得

    Args:
        db_path: データベースパス
        target_fy: 対象年度
        member_rate_threshold: 会員率の閾値（これより低い学校を取得）
        sales_decline_threshold: 売上減少率の閾値（これより減少幅が大きい学校を取得。正の値で指定）
                                 例: 0.1 なら -10% 以下（減少率10%以上）
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    current_fy = target_fy if target_fy else get_current_fiscal_year()
    prev_fy = current_fy - 1

    # event_dateベースで年度の範囲を計算（4月始まり）
    current_fy_start = f'{current_fy}-04-01'
    current_fy_end = f'{current_fy + 1}-04-01'
    prev_fy_start = f'{prev_fy}-04-01'
    prev_fy_end = f'{prev_fy + 1}-04-01'

    report_id = get_latest_report_id(conn)
    if not report_id:
        conn.close()
        return []

    # 最新の会員率スナップショットを取得(grade='全学年')
    # event_salesから売上を集計（event_dateベースで年度判定）

    query = f'''
        WITH current_sales AS (
            -- 重複レコードを除外: event_date + event_name の組み合わせでユニーク化
            SELECT
                school_id,
                COALESCE(SUM(sales), 0) as total_sales
            FROM event_sales
            WHERE report_id = ? AND event_date >= ? AND event_date < ?
            GROUP BY school_id
        ),
        prev_sales AS (
            -- 重複レコードを除外: event_date + event_name の組み合わせでユニーク化
            SELECT
                school_id,
                COALESCE(SUM(sales), 0) as total_sales
            FROM event_sales
            WHERE report_id = ? AND event_date >= ? AND event_date < ?
            GROUP BY school_id
        ),
        latest_rates AS (
            -- 各学校の最新snapshot_dateを取得し、そのsnapshotの最新report_idからデータを取得
            SELECT 
                m.school_id,
                ROUND(
                    CASE 
                        WHEN COALESCE(SUM(m.total_students), 0) > 0 
                        THEN CAST(COALESCE(SUM(m.member_count), 0) AS REAL) / SUM(m.total_students) * 100
                        ELSE 0 
                    END,
                    1
                ) as member_rate
            FROM member_rates m
            JOIN (
                SELECT 
                    m2.school_id,
                    m2.snapshot_date,
                    MAX(m2.report_id) as latest_report
                FROM member_rates m2
                JOIN (
                    SELECT school_id, MAX(snapshot_date) as max_snapshot
                    FROM member_rates
                    GROUP BY school_id
                ) latest_snap ON m2.school_id = latest_snap.school_id 
                    AND m2.snapshot_date = latest_snap.max_snapshot
                GROUP BY m2.school_id, m2.snapshot_date
            ) ls ON m.school_id = ls.school_id 
                AND m.snapshot_date = ls.snapshot_date 
                AND m.report_id = ls.latest_report
            WHERE m.grade != '全学年' AND m.total_students > 0
            GROUP BY m.school_id
        )
        SELECT
            s.school_id,
            s.school_name,
            s.attribute,
            s.studio,
            s.manager,
            s.region,
            COALESCE(curr.total_sales, 0) as current_sales,
            COALESCE(prev.total_sales, 0) as prev_sales,
            (COALESCE(curr.total_sales, 0) - prev.total_sales) / prev.total_sales as growth_rate,
            COALESCE(r.member_rate, 0) as member_rate
        FROM schools_master s
        JOIN current_sales curr ON curr.school_id = s.school_id
        JOIN prev_sales prev ON prev.school_id = s.school_id
        LEFT JOIN latest_rates r ON r.school_id = s.school_id
        WHERE prev.total_sales > 0
        ORDER BY (COALESCE(curr.total_sales, 0) - prev.total_sales) / prev.total_sales ASC
    '''
    
    # SQL側ではフィルタしない（JavaScript側で全フィルタリングを行う）
    # パラメータ: 今年度開始日, 今年度終了日, 前年度開始日, 前年度終了日
    # 修正: report_id, cur_start, cur_end, report_id, prev_start, prev_end
    params = [report_id, current_fy_start, current_fy_end, report_id, prev_fy_start, prev_fy_end]
    
    cursor.execute(query, params)
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio': row[3] or '',
            'manager': row[4] or '',
            'region': row[5] or '',
            'current_sales': row[6],
            'prev_sales': row[7],
            'growth_rate': row[8],
            'member_rate': row[9]
        })
    
    conn.close()
    return results


def get_events_for_date_filter(db_path=None, years_back=3):
    """
    イベント開始日別売上分析用の全イベントデータを取得する
    直近N年分を取得
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    current_fy = get_current_fiscal_year()
    start_fy = current_fy - years_back + 1
    
    report_id = get_latest_report_id(conn)
    if not report_id:
        conn.close()
        return []
    
    query = f'''
        WITH latest_rates AS (
            -- 最新の会員率（全学年合算の平均的な率を算出）
            SELECT 
                school_id,
                ROUND(
                    CASE 
                        WHEN COALESCE(SUM(total_students), 0) > 0 
                        THEN CAST(COALESCE(SUM(member_count), 0) AS REAL) / SUM(total_students) * 100
                        ELSE 0 
                    END,
                    1
                ) as member_rate
            FROM member_rates
            WHERE report_id = ?
            GROUP BY school_id
        ),
        -- イベントごとに集計（分割入金を合算）
        daily_events AS (
            SELECT
                report_id,
                fiscal_year,
                school_id,
                event_date,
                event_name,
                SUM(sales) as sales
            FROM event_sales
            WHERE report_id = ? AND fiscal_year >= ?
            GROUP BY report_id, fiscal_year, school_id, event_date, event_name
        )
        SELECT
            e.fiscal_year,
            strftime('%Y', e.event_date) as year,
            strftime('%m', e.event_date) as month,
            strftime('%d', e.event_date) as day,
            e.event_date,
            s.school_name,
            s.attribute,
            s.region,
            s.studio,
            e.event_name,
            e.sales,
            mr.member_rate
        FROM daily_events e
        JOIN schools_master s ON e.school_id = s.school_id
        LEFT JOIN latest_rates mr ON s.school_id = mr.school_id
        ORDER BY e.event_date ASC
    '''
    
    cursor.execute(query, (report_id, report_id, start_fy))
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'fiscal_year': row[0],
            'year': row[1],
            'month': row[2],
            'day': row[3],
            'event_date': row[4],
            'school_name': row[5],
            'attribute': row[6],
            'region': row[7],
            'studio': row[8],
            'event_name': row[9],
            'sales': row[10],
            'member_rate': row[11] if row[11] is not None else 0.0
        })
    
    conn.close()
    return results


def get_all_schools(db_path=None):
    """
    全学校の一覧を取得（フィルター用）
    
    Args:
        db_path: データベースパス
    
    Returns:
        list: [{school_id, school_name, attribute, region, studio}, ...]
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    query = '''
        SELECT DISTINCT
            school_id,
            school_name,
            attribute,
            region,
            studio
        FROM schools_master
        ORDER BY school_name
    '''
    
    cursor.execute(query)
    schools = []
    for row in cursor.fetchall():
        schools.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'region': row[3] or '',
            'studio': row[4] or ''
        })
    
    conn.close()
    return schools


def get_yearly_event_comparison(db_path=None, school_id=None, year1=None, year2=None):
    """
    指定学校の2つの年度のイベント一覧を取得して比較
    
    Args:
        db_path: データベースパス
        school_id: 学校ID
        year1: 比較年度1
        year2: 比較年度2
    
    Returns:
        dict: {
            'year1_events': [{event_name, event_date, sales, publish_date}, ...],
            'year2_events': [...],
            'year1_total': 合計売上,
            'year2_total': 合計売上,
            'school_info': {school_name, attribute, region, studio}
        }
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    if not school_id:
        conn.close()
        return {
            'year1_events': [],
            'year2_events': [],
            'year1_total': 0,
            'year2_total': 0,
            'school_info': {}
        }
    
    current_fy = year1 if year1 else get_current_fiscal_year()
    compare_fy = year2 if year2 else current_fy - 1
    
    report_id = get_latest_report_id(conn)
    if not report_id:
        conn.close()
        return {
            'year1_events': [],
            'year2_events': [],
            'year1_total': 0,
            'year2_total': 0,
            'school_info': {}
        }
    
    # 学校情報取得
    cursor.execute('''
        SELECT school_name, attribute, region, studio
        FROM schools_master
        WHERE school_id = ?
    ''', (school_id,))
    
    school_row = cursor.fetchone()
    school_info = {
        'school_name': school_row[0] if school_row else '',
        'attribute': school_row[1] if school_row else '',
        'region': school_row[2] if school_row else '',
        'studio': school_row[3] if school_row else ''
    }
    
    # 年度1のイベント取得
    query = '''
        SELECT 
            event_name,
            event_date,
            SUM(sales) as sales
        FROM event_sales
        WHERE school_id = ? AND fiscal_year = ? AND report_id = ?
        GROUP BY event_name, event_date
        ORDER BY event_date ASC
    '''
    
    cursor.execute(query, (school_id, current_fy, report_id))
    year1_events = []
    year1_total = 0
    
    for row in cursor.fetchall():
        event_date = row[1]
        # 公開日をフォーマット (YYYY-MM-DD -> MM月DD日)
        if event_date:
            try:
                date_obj = datetime.strptime(event_date, '%Y-%m-%d')
                publish_date = f"{date_obj.month}月{date_obj.day}日"
            except:
                publish_date = event_date
        else:
            publish_date = ''
        
        year1_events.append({
            'event_name': row[0],
            'event_date': event_date,
            'sales': row[2],
            'publish_date': publish_date
        })
        year1_total += row[2]
    
    # 年度2のイベント取得
    cursor.execute(query, (school_id, compare_fy, report_id))
    year2_events = []
    year2_total = 0
    
    for row in cursor.fetchall():
        event_date = row[1]
        if event_date:
            try:
                date_obj = datetime.strptime(event_date, '%Y-%m-%d')
                publish_date = f"{date_obj.month}月{date_obj.day}日"
            except:
                publish_date = event_date
        else:
            publish_date = ''
        
        year2_events.append({
            'event_name': row[0],
            'event_date': event_date,
            'sales': row[2],
            'publish_date': publish_date
        })
        year2_total += row[2]
    
    conn.close()
    
    return {
        'year1_events': year1_events,
        'year2_events': year2_events,
        'year1_total': year1_total,
        'year2_total': year2_total,
        'school_info': school_info
    }


def get_improved_member_rate_schools(db_path=None, target_fy=None):
    """
    会員率改善校を取得（前年度と比較して会員率が向上している学校）
    
    Args:
        db_path: データベースパス
        target_fy: 対象年度（Noneの場合は現在年度）
    
    Returns:
        list: [{school_id, school_name, attribute, studio, manager, region, 
               current_rate, prev_rate, improvement_point, current_sales}, ...]
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    current_fy = target_fy if target_fy else get_current_fiscal_year()
    prev_fy = current_fy - 1
    
    report_id = get_latest_report_id(conn)
    if not report_id:
        conn.close()
        return []

    # 今年度の売上も表示したいので取得しておく
    # 会員率の計算ロジック:
    # member_ratesテーブルから、対象年度と前年度それぞれの「最新スナップショット」を特定し、
    # その時点での全学年合計の会員率を算出する。

    query = '''
        WITH fiscal_snapshots AS (
            SELECT 
                school_id,
                snapshot_date,
                (CASE 
                    WHEN CAST(strftime('%m', snapshot_date) AS INTEGER) >= 4 
                    THEN CAST(strftime('%Y', snapshot_date) AS INTEGER)
                    ELSE CAST(strftime('%Y', snapshot_date) AS INTEGER) - 1
                END) as fiscal_year
            FROM member_rates
            GROUP BY school_id, snapshot_date
        ),
        latest_snapshots AS (
            SELECT
                school_id,
                fiscal_year,
                MAX(snapshot_date) as max_date
            FROM fiscal_snapshots
            WHERE fiscal_year IN (?, ?)
            GROUP BY school_id, fiscal_year
        ),
        calculated_rates AS (
            SELECT
                ls.school_id,
                ls.fiscal_year,
                CAST(SUM(m.member_count) AS REAL) / NULLIF(SUM(m.total_students), 0) * 100 as rate
            FROM member_rates m
            JOIN latest_snapshots ls ON m.school_id = ls.school_id AND m.snapshot_date = ls.max_date
            WHERE m.grade != '全学年' AND m.total_students > 0
            GROUP BY ls.school_id, ls.fiscal_year
        ),
        current_sales AS (
            SELECT
                school_id,
                COALESCE(SUM(sales), 0) as sales
            FROM event_sales
            WHERE fiscal_year = ?
            GROUP BY school_id
        )
        SELECT
            s.school_id,
            s.school_name,
            s.attribute,
            s.studio,
            s.manager,
            s.region,
            COALESCE(curr.rate, 0) as current_rate,
            COALESCE(prev.rate, 0) as prev_rate,
            COALESCE(curr.rate, 0) - COALESCE(prev.rate, 0) as improvement,
            COALESCE(cs.sales, 0) as current_sales
        FROM schools_master s
        JOIN calculated_rates curr ON s.school_id = curr.school_id AND curr.fiscal_year = ?
        JOIN calculated_rates prev ON s.school_id = prev.school_id AND prev.fiscal_year = ?
        LEFT JOIN current_sales cs ON s.school_id = cs.school_id
        WHERE (COALESCE(curr.rate, 0) - COALESCE(prev.rate, 0)) > 0
        ORDER BY improvement DESC
    '''
    
    # パラメータ: current_fy, prev_fy (latest_snapshots用), current_fy (sales用), current_fy, prev_fy (join用)
    params = [current_fy, prev_fy, current_fy, current_fy, prev_fy]
    
    cursor.execute(query, params)
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio': row[3] or '',
            'manager': row[4] or '',
            'region': row[5] or '',
            'current_rate': row[6],
            'prev_rate': row[7],
            'improvement_point': row[8],
            'current_sales': row[9]
        })
    
    conn.close()
    return results


def get_sales_unit_price_analysis(db_path=None, target_fy=None):
    """
    イベント平均単価（1イベントあたりの売上）が高い学校を取得
    会員データと属性平均との比較も含む
    
    Args:
        db_path: データベースパス
        target_fy: 対象年度（Noneの場合は現在年度）
    
    Returns:
        list: [{school_id, school_name, attribute, studio, manager, region, 
               total_sales, event_count, avg_price, member_count, member_rate,
               attr_avg_price, price_ratio}, ...]
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    current_fy = target_fy if target_fy else get_current_fiscal_year()
    
    report_id = get_latest_report_id(conn)
    if not report_id:
        conn.close()
        return []
    
    # イベントデータと会員データを結合して取得
    # 会員データは grade != '全学年' の合計を使用（'全学年'データが存在しない場合に対応）
    query = '''
        WITH latest_snapshot AS (
            SELECT 
                school_id, 
                MAX(snapshot_date) as max_snapshot
            FROM member_rates
            GROUP BY school_id
        ),
        latest_member_counts AS (
            SELECT 
                m.school_id,
                COALESCE(SUM(m.member_count), 0) as member_count,
                 CASE 
                    WHEN SUM(m.total_students) > 0 THEN CAST(SUM(m.member_count) AS REAL) / SUM(m.total_students) * 100
                    ELSE 0 
                END as member_rate
            FROM member_rates m
            JOIN latest_snapshot ls ON m.school_id = ls.school_id AND m.snapshot_date = ls.max_snapshot
            WHERE m.grade != '全学年'
            GROUP BY m.school_id
        )
        SELECT
            s.school_id,
            s.school_name,
            s.attribute,
            s.studio,
            s.manager,
            s.region,
            COALESCE(SUM(e.sales), 0) as total_sales,
            COUNT(DISTINCT e.event_name || COALESCE(e.event_date, '')) as event_count,
            CASE 
                WHEN COUNT(DISTINCT e.event_name || COALESCE(e.event_date, '')) > 0 
                THEN CAST(SUM(e.sales) AS REAL) / COUNT(DISTINCT e.event_name || COALESCE(e.event_date, ''))
                ELSE 0 
            END as avg_price,
            COALESCE(lmc.member_count, 0) as member_count,
            COALESCE(lmc.member_rate, 0) as member_rate
        FROM schools_master s
        JOIN event_sales e ON s.school_id = e.school_id
        LEFT JOIN latest_member_counts lmc ON s.school_id = lmc.school_id
        WHERE e.fiscal_year = ? AND e.report_id = ?
        GROUP BY s.school_id, s.school_name, s.attribute, s.studio, s.manager, s.region
        HAVING event_count > 0
        ORDER BY avg_price DESC
    '''
    
    cursor.execute(query, (current_fy, report_id))
    
    results = []
    attr_totals = {}  # 属性ごとの集計用
    
    raw_rows = cursor.fetchall()
    
    # 1回目ループ: 平均計算のための集計
    for row in raw_rows:
        attribute = row[2] or 'その他'
        sales = row[6]
        count = row[7]
        
        if attribute not in attr_totals:
            attr_totals[attribute] = {'sales': 0, 'count': 0}
        
        attr_totals[attribute]['sales'] += sales
        attr_totals[attribute]['count'] += count

    # 2回目ループ: データ整形と平均比の計算
    for row in raw_rows:
        attribute = row[2] or 'その他'
        avg_price = row[8]
        
        # 属性平均単価の計算
        attr_avg_price = 0
        if attribute in attr_totals and attr_totals[attribute]['count'] > 0:
            attr_avg_price = attr_totals[attribute]['sales'] / attr_totals[attribute]['count']
            
        # 平均比の計算
        price_ratio = 0
        if attr_avg_price > 0:
            price_ratio = (avg_price / attr_avg_price) * 100
            
        results.append({
            'school_id': row[0],
            'school_name': row[1],
            'attribute': row[2] or '',
            'studio': row[3] or '',
            'manager': row[4] or '',
            'region': row[5] or '',
            'total_sales': row[6],
            'event_count': row[7],
            'avg_price': avg_price,
            'member_count': row[9],
            'member_rate': row[10],
            'attr_avg_price': attr_avg_price,
            'price_ratio': price_ratio
        })
    
    conn.close()
    return results


def get_studio_decline_analysis(db_path=None, target_fy=None):
    """
    写真館別の売上低下分析
    
    Returns:
        list: 写真館ごとの売上情報
            - studio: 写真館名
            - region: 事業所
            - current_sales: 今年度売上
            - prev_sales: 前年度売上
            - school_count: 担当校数
            - change_rate: 変化率 (今年度/前年度 - 1)
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    # 最新のreport_idを取得
    report_id = get_latest_report_id(conn)
    if not report_id:
        conn.close()
        return []
    
    # 年度指定がない場合は最新年度
    if target_fy is None:
        cursor.execute('SELECT MAX(fiscal_year) FROM event_sales WHERE report_id = ?', (report_id,))
        result = cursor.fetchone()
        target_fy = result[0] if result and result[0] else datetime.now().year
    
    prev_fy = target_fy - 1
    
    # 今年度の写真館別集計
    # 写真館名でユニークにするため、regionは結合し、集計単位をstudioのみにする
    # 売上は「発生ベース」で集計するため、event_sales（イベント年度）ではなくschool_monthly_sales（計上年度）を使用
    query = '''
        WITH current_year AS (
            SELECT 
                s.studio,
                GROUP_CONCAT(DISTINCT s.region) as region,
                COUNT(DISTINCT s.school_id) as school_count,
                COALESCE(SUM(sms.sales), 0) as current_sales
            FROM schools_master s
            LEFT JOIN school_monthly_sales sms ON s.school_id = sms.school_id 
                AND sms.fiscal_year = ? AND sms.report_id = ?
            WHERE s.studio IS NOT NULL AND s.studio != ''
            GROUP BY s.studio
        ),
        prev_year AS (
            SELECT 
                s.studio,
                COALESCE(SUM(sms.sales), 0) as prev_sales
            FROM schools_master s
            LEFT JOIN school_monthly_sales sms ON s.school_id = sms.school_id 
                AND sms.fiscal_year = ? AND sms.report_id = ?
            WHERE s.studio IS NOT NULL AND s.studio != ''
            GROUP BY s.studio
        )
        SELECT 
            c.studio,
            '', -- attribute placeholder (no longer used)
            c.region,
            c.current_sales,
            COALESCE(p.prev_sales, 0) as prev_sales,
            c.school_count,
            CASE 
                WHEN p.prev_sales > 0 THEN ((c.current_sales - p.prev_sales) * 1.0 / p.prev_sales)
                ELSE 0
            END as change_rate
        FROM current_year c
        LEFT JOIN prev_year p ON c.studio = p.studio
        ORDER BY change_rate ASC
    '''
    
    cursor.execute(query, (target_fy, report_id, prev_fy, report_id))
    
    results = []
    for row in cursor.fetchall():
        results.append({
            'studio': row[0] or '',
            'attribute': row[1] or '',
            'region': row[2] or '',
            'current_sales': row[3] or 0,
            'prev_sales': row[4] or 0,
            'school_count': row[5] or 0,
            'change_rate': row[6] or 0
        })
    
    conn.close()
    return results



if __name__ == '__main__':
    # テスト実行: データベース初期化
    init_database()
