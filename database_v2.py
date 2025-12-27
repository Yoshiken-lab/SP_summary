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
    
    # 4. branch_monthly_sales (事業所別月次売上)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS branch_monthly_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            fiscal_year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            branch TEXT NOT NULL,
            sales REAL NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
            UNIQUE(report_id, fiscal_year, month, branch)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_branch_sales_fy ON branch_monthly_sales(fiscal_year, month)')
    
    # 5. manager_monthly_sales (担当者別月次売上)
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


if __name__ == '__main__':
    # テスト実行: データベース初期化
    init_database()
