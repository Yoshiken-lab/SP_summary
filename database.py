#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上分析システム - データベース定義

SQLiteを使用してExcelから取り込んだデータを蓄積・管理する
"""

import sqlite3
from pathlib import Path
from datetime import datetime

# デフォルトのDBパス
DEFAULT_DB_PATH = Path(__file__).parent / "schoolphoto.db"


def get_connection(db_path=None):
    """データベース接続を取得"""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 辞書形式でアクセス可能に
    return conn


def init_database(db_path=None):
    """データベースを初期化（テーブル作成）"""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # ========================================
    # 1. 報告書メタ情報
    # ========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            report_date DATE NOT NULL,           -- 報告書の日付（ファイル名から抽出）
            imported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(file_name)
        )
    ''')

    # ========================================
    # 2. 月別サマリー
    # ========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monthly_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            fiscal_year INTEGER NOT NULL,        -- 年度（2024, 2025など）
            month INTEGER NOT NULL,              -- 月（1-12）
            total_sales REAL,                    -- 総売上額
            direct_sales REAL,                   -- 直取引売上
            studio_school_sales REAL,            -- 写真館・学校売上
            school_count INTEGER,                -- イベント実施学校数
            budget REAL,                         -- 予算
            budget_rate REAL,                    -- 予算比
            yoy_rate REAL,                       -- 昨年比
            FOREIGN KEY (report_id) REFERENCES reports(id),
            UNIQUE(report_id, fiscal_year, month)
        )
    ''')

    # ========================================
    # 3. 学校マスタ
    # ========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_name TEXT NOT NULL,
            attribute TEXT,                      -- 属性（幼稚園、小学校、中学校など）
            studio_name TEXT,                    -- 写真館名
            manager TEXT,                        -- 担当者
            region TEXT,                         -- 事業所/地域
            UNIQUE(school_name)
        )
    ''')

    # ========================================
    # 3-1. 学校外部IDマッピング（元データの学校IDと統合後IDの紐付け）
    # ========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS school_external_ids (
            external_id INTEGER PRIMARY KEY,     -- 元データの学校ID
            school_id INTEGER NOT NULL,          -- 統合後の内部ID
            original_name TEXT,                  -- 元の学校名（トリミング前）
            FOREIGN KEY (school_id) REFERENCES schools(id)
        )
    ''')

    # ========================================
    # 4. 学校別月別売上
    # ========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS school_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            school_id INTEGER NOT NULL,
            fiscal_year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            sales REAL NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports(id),
            FOREIGN KEY (school_id) REFERENCES schools(id),
            UNIQUE(school_id, fiscal_year, month)
        )
    ''')

    # ========================================
    # 5. イベント情報
    # ========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_id INTEGER NOT NULL,
            event_name TEXT NOT NULL,
            start_date DATE,                     -- イベント開始日
            fiscal_year INTEGER NOT NULL,        -- 年度
            FOREIGN KEY (school_id) REFERENCES schools(id),
            UNIQUE(school_id, event_name)
        )
    ''')

    # ========================================
    # 6. イベント別月別売上
    # ========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            fiscal_year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            sales REAL NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports(id),
            FOREIGN KEY (event_id) REFERENCES events(id),
            UNIQUE(event_id, fiscal_year, month)
        )
    ''')

    # ========================================
    # 7. 会員率（スナップショット）
    # ========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS member_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            school_id INTEGER NOT NULL,
            fiscal_year INTEGER NOT NULL,
            grade_category TEXT,                 -- 学年カテゴリ（〇年後卒業の学年）
            grade_name TEXT,                     -- 学年名（年長組、1年生など）
            student_count INTEGER,               -- 生徒数
            member_count INTEGER,                -- 有効会員登録数
            member_rate REAL,                    -- 会員率（計算値）
            snapshot_date DATE,                  -- スナップショット日（報告書の日付）
            FOREIGN KEY (report_id) REFERENCES reports(id),
            FOREIGN KEY (school_id) REFERENCES schools(id)
        )
    ''')

    # ========================================
    # 8. 学校別年度売上集計（比較用）
    # ========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS school_yearly_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            school_id INTEGER NOT NULL,
            fiscal_year INTEGER NOT NULL,
            total_sales REAL NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports(id),
            FOREIGN KEY (school_id) REFERENCES schools(id),
            UNIQUE(report_id, school_id, fiscal_year)
        )
    ''')

    # ========================================
    # 9. 担当者名変換マッピング
    # ========================================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS salesman_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_name TEXT NOT NULL,              -- 変換元の担当者名
            to_name TEXT NOT NULL,                -- 変換先の担当者名
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(from_name)
        )
    ''')

    # ========================================
    # インデックス作成
    # ========================================
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_school_external_ids_school ON school_external_ids(school_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_school_sales_school ON school_sales(school_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_school_sales_year ON school_sales(fiscal_year)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_school ON events(school_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_year ON events(fiscal_year)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_member_rates_school ON member_rates(school_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_member_rates_date ON member_rates(snapshot_date)')

    conn.commit()
    conn.close()

    print(f"データベースを初期化しました: {db_path or DEFAULT_DB_PATH}")


def normalize_school_name(school_name):
    """
    学校名を正規化（年度表記を除去して統合可能な形にする）

    対応パターン:
    - 末尾: 「宇都宮市立豊郷北小学校（2024年度）」→「宇都宮市立豊郷北小学校」
    - 先頭: 「2024年度 おおたけ幼稚園」→「おおたけ幼稚園」
    - 先頭(スペースなし): 「2024年度もりや幼稚園」→「もりや幼稚園」
    """
    import re
    if not school_name:
        return school_name

    normalized = school_name.strip()

    # 末尾の「（○○○○年度）」を除去（全角・半角括弧対応）
    normalized = re.sub(r'[（(]\d{4}年度[）)]$', '', normalized)

    # 先頭の「○○○○年度 」または「○○○○年度」を除去
    normalized = re.sub(r'^\d{4}年度\s*', '', normalized)

    return normalized.strip()


def get_or_create_school(cursor, school_name, external_id=None, attribute=None, studio_name=None, manager=None, region=None):
    """
    学校を取得または作成し、IDを返す

    Args:
        cursor: DBカーソル
        school_name: 学校名（トリミング前の元の名前）
        external_id: 元データの学校ID（あれば優先的に使用）
        attribute: 属性（幼稚園、小学校など）
        studio_name: 写真館名
        manager: 担当者
        region: 事業所/地域

    Returns:
        統合後の内部学校ID
    """
    # 学校名を正規化（年度表記を除去）
    original_name = school_name
    normalized_name = normalize_school_name(school_name)

    # 1. external_idが指定されている場合、まずexternal_idで検索
    if external_id is not None:
        cursor.execute('SELECT school_id FROM school_external_ids WHERE external_id = ?', (external_id,))
        row = cursor.fetchone()
        if row:
            school_id = row[0]
            # 属性情報を更新（external_idが大きい方が最新なので、常に上書きチェック）
            _update_school_if_newer(cursor, school_id, external_id, attribute, studio_name, manager, region)
            return school_id

    # 2. 正規化した学校名で既存レコードを検索
    cursor.execute('SELECT id FROM schools WHERE school_name = ?', (normalized_name,))
    row = cursor.fetchone()

    if row:
        school_id = row[0]
        # external_idが指定されていれば、マッピングを登録
        if external_id is not None:
            _register_external_id(cursor, external_id, school_id, original_name)
            # 属性情報を更新（external_idが大きい方が最新）
            _update_school_if_newer(cursor, school_id, external_id, attribute, studio_name, manager, region)
        else:
            # external_idなしの場合は従来通り上書き
            _update_school_attributes(cursor, school_id, attribute, studio_name, manager, region)
        return school_id
    else:
        # 新規作成
        cursor.execute('''
            INSERT INTO schools (school_name, attribute, studio_name, manager, region)
            VALUES (?, ?, ?, ?, ?)
        ''', (normalized_name, attribute, studio_name, manager, region))
        school_id = cursor.lastrowid

        # external_idが指定されていれば、マッピングを登録
        if external_id is not None:
            _register_external_id(cursor, external_id, school_id, original_name)

        return school_id


def _register_external_id(cursor, external_id, school_id, original_name):
    """外部IDと内部IDのマッピングを登録"""
    cursor.execute('''
        INSERT OR IGNORE INTO school_external_ids (external_id, school_id, original_name)
        VALUES (?, ?, ?)
    ''', (external_id, school_id, original_name))


def _update_school_if_newer(cursor, school_id, new_external_id, attribute, studio_name, manager, region):
    """
    新しいexternal_idのデータで学校情報を更新するか判定
    external_idが大きい方が最新と判断
    """
    # 現在のschool_idに紐づく最大のexternal_idを取得
    cursor.execute('''
        SELECT MAX(external_id) FROM school_external_ids WHERE school_id = ?
    ''', (school_id,))
    row = cursor.fetchone()
    max_external_id = row[0] if row and row[0] else 0

    # 新しいexternal_idが最大値以上なら更新
    if new_external_id >= max_external_id:
        _update_school_attributes(cursor, school_id, attribute, studio_name, manager, region)


def _update_school_attributes(cursor, school_id, attribute, studio_name, manager, region):
    """学校の属性情報を更新（NULL以外の値で上書き）"""
    updates = []
    params = []
    if attribute:
        updates.append('attribute = ?')
        params.append(attribute)
    if studio_name:
        updates.append('studio_name = ?')
        params.append(studio_name)
    if manager:
        updates.append('manager = ?')
        params.append(manager)
    if region:
        updates.append('region = ?')
        params.append(region)

    if updates:
        params.append(school_id)
        cursor.execute(f'UPDATE schools SET {", ".join(updates)} WHERE id = ?', params)


def get_or_create_event(cursor, school_id, event_name, start_date=None, fiscal_year=None):
    """イベントを取得または作成し、IDを返す"""
    cursor.execute('SELECT id FROM events WHERE school_id = ? AND event_name = ?',
                   (school_id, event_name))
    row = cursor.fetchone()

    if row:
        event_id = row[0]
        # 開始日を更新
        if start_date:
            cursor.execute('UPDATE events SET start_date = ? WHERE id = ?', (start_date, event_id))
        return event_id
    else:
        cursor.execute('''
            INSERT INTO events (school_id, event_name, start_date, fiscal_year)
            VALUES (?, ?, ?, ?)
        ''', (school_id, event_name, start_date, fiscal_year))
        return cursor.lastrowid


# ========================================
# 担当者名変換関連
# ========================================

def get_salesman_aliases(db_path=None):
    """全ての担当者名変換マッピングを取得"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT id, from_name, to_name, created_at FROM salesman_aliases ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_salesman_alias_map(db_path=None):
    """担当者名変換マッピングを辞書形式で取得（from_name -> to_name）"""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT from_name, to_name FROM salesman_aliases')
    rows = cursor.fetchall()
    conn.close()
    return {row['from_name']: row['to_name'] for row in rows}


def add_salesman_alias(from_name, to_name, db_path=None):
    """
    担当者名変換マッピングを追加し、既存データも自動でマイグレーション

    Args:
        from_name: 変換元の担当者名
        to_name: 変換先の担当者名
        db_path: DBパス（省略時はデフォルト）

    Returns:
        dict: 処理結果 {success: bool, migrated_count: int, message: str}
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    try:
        # マッピングを追加
        cursor.execute('''
            INSERT INTO salesman_aliases (from_name, to_name)
            VALUES (?, ?)
        ''', (from_name, to_name))

        # 既存データをマイグレーション（schoolsテーブルのmanagerを更新）
        cursor.execute('''
            UPDATE schools SET manager = ? WHERE manager = ?
        ''', (to_name, from_name))
        migrated_count = cursor.rowcount

        conn.commit()
        return {
            'success': True,
            'migrated_count': migrated_count,
            'message': f'マッピングを追加しました。{migrated_count}件の既存データを更新しました。'
        }
    except Exception as e:
        conn.rollback()
        return {
            'success': False,
            'migrated_count': 0,
            'message': f'エラー: {str(e)}'
        }
    finally:
        conn.close()


def delete_salesman_alias(alias_id, db_path=None):
    """
    担当者名変換マッピングを削除

    Args:
        alias_id: 削除するマッピングのID
        db_path: DBパス（省略時はデフォルト）

    Returns:
        dict: 処理結果 {success: bool, message: str}
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute('DELETE FROM salesman_aliases WHERE id = ?', (alias_id,))
        if cursor.rowcount == 0:
            return {
                'success': False,
                'message': '指定されたマッピングが見つかりません'
            }
        conn.commit()
        return {
            'success': True,
            'message': 'マッピングを削除しました'
        }
    except Exception as e:
        conn.rollback()
        return {
            'success': False,
            'message': f'エラー: {str(e)}'
        }
    finally:
        conn.close()


def apply_salesman_alias(manager_name, db_path=None):
    """
    担当者名に変換マッピングを適用

    Args:
        manager_name: 元の担当者名
        db_path: DBパス（省略時はデフォルト）

    Returns:
        str: 変換後の担当者名（マッピングがなければ元の名前をそのまま返す）
    """
    if not manager_name:
        return manager_name

    alias_map = get_salesman_alias_map(db_path)
    return alias_map.get(manager_name, manager_name)


if __name__ == '__main__':
    # 直接実行時はDB初期化
    init_database()
