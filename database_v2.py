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
    
    report_id = get_latest_report_id(conn)
    if not report_id:
        conn.close()
        return []

    # event_salesから売上を集計
    query = '''
        WITH current_sales AS (
            SELECT
                school_id,
                COALESCE(SUM(sales), 0) as total_sales
            FROM event_sales
            WHERE fiscal_year = ? AND report_id = ?
            GROUP BY school_id
        ),
        prev_sales AS (
            SELECT
                school_id,
                COALESCE(SUM(sales), 0) as total_sales
            FROM event_sales
            WHERE fiscal_year = ? AND report_id = ?
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
    
    cursor.execute(query, (current_fy, report_id, prev_fy, report_id))
    
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
    prev_fy = current_fy - 1
    
    report_id = get_latest_report_id(conn)
    if not report_id:
        conn.close()
        return []

    # 月指定がある場合の条件
    month_condition = "AND month = ?" if target_month else ""
    
    # パラメータ構築
    params = [current_fy, report_id]
    if target_month:
        params.append(target_month)
    # 前年度のパラメータ
    # params.extend([prev_fy, report_id]) # This line is removed as the logic changes

    query = f'''
        WITH first_events AS (
            SELECT
                school_id,
                MIN(event_date) as first_event_date
            FROM event_sales
            GROUP BY school_id
        ),
        current_sales AS (
            SELECT
                school_id,
                COALESCE(SUM(sales), 0) as total_sales
            FROM event_sales
            WHERE fiscal_year = ? AND report_id = ? {month_condition}
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
        WHERE (
            -- 初回イベント日が対象年度内（4月1日～翌年3月31日）
            (strftime('%Y', fe.first_event_date) = CAST(? AS TEXT) AND strftime('%m', fe.first_event_date) >= '04')
            OR
            (strftime('%Y', fe.first_event_date) = CAST(? + 1 AS TEXT) AND strftime('%m', fe.first_event_date) <= '03')
        )
        ORDER BY COALESCE(curr.total_sales, 0) DESC
    '''
    
    # パラメータ: current_fy, report_id, [target_month], current_fy, current_fy
    params = [current_fy, report_id]
    if target_month:
        params.append(target_month)
    params.extend([current_fy, current_fy])
    
    cursor.execute(query, params)
    
    results = []
    for row in cursor.fetchall():
        # 日付フォーマット：YYYY年MM月DD日
        first_date = row[7]
        if first_date:
            try:
                date_obj = datetime.strptime(first_date, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%Y年%m月%d日')
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
        target_month: 対象月（Noneの場合は全月）
    
    Returns:
        list: [{school_id, school_name, attribute, branch, studio, prev_event_count, current_sales, prev_sales, growth_rate}, ...]
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    current_fy = target_fy if target_fy else get_current_fiscal_year()
    prev_fy = current_fy - 1
    
    report_id = get_latest_report_id(conn)
    if not report_id:
        conn.close()
        return []

    # 月指定がある場合はフィルタリング条件を追加
    month_condition = "AND month <= ?" if target_month else ""
    params = [target_month] if target_month else []

    query = f'''
        WITH current_events AS (
            SELECT
                school_id,
                COUNT(*) as event_count
            FROM event_sales
            WHERE fiscal_year = ? AND report_id = ? {month_condition}
            GROUP BY school_id
        ),
        prev_events AS (
            SELECT
                school_id,
                COUNT(*) as event_count
            FROM event_sales
            WHERE fiscal_year = ? AND report_id = ? {month_condition}
            GROUP BY school_id
        ),
        prev_sales AS (
            SELECT
                school_id,
                COALESCE(SUM(sales), 0) as total_sales
            FROM event_sales
            WHERE fiscal_year = ? AND report_id = ? {month_condition}
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
    
    query_params = [current_fy, report_id] + params + [prev_fy, report_id] + params + [prev_fy, report_id] + params
    
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
    
    report_id = get_latest_report_id(conn)
    if not report_id:
        conn.close()
        return []

    # 最新の会員率スナップショットを取得(grade='全学年')
    # event_salesから売上を集計
    
    query = f'''
        WITH current_sales AS (
            SELECT
                school_id,
                COALESCE(SUM(sales), 0) as total_sales
            FROM event_sales
            WHERE fiscal_year = ?
            GROUP BY school_id
        ),
        prev_sales AS (
            SELECT
                school_id,
                COALESCE(SUM(sales), 0) as total_sales
            FROM event_sales
            WHERE fiscal_year = ?
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
    params = [current_fy, prev_fy]
    
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


if __name__ == '__main__':
    # テスト実行: データベース初期化
    init_database()
