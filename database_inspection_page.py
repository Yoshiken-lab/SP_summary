#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
データベース確認ページ - 読み取り専用
"""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
from datetime import datetime
import database_v2

# カラーパレット（launcher_v2.pyから参照）
COLORS = {
    'bg_sidebar': '#111827',
    'bg_main': '#1F2937',
    'bg_card': '#374151',
    'text_primary': '#F9FAFB',
    'text_secondary': '#9CA3AF',
    'accent': '#3B82F6',
    'accent_hover': '#2563EB',
    'danger': '#EF4444',
    'danger_hover': '#DC2626',
    'success': '#10B981',
    'warning': '#F59E0B',
    'border': '#4B5563',
    'sidebar_active': '#374151',
    'log_bg': '#111827',
    'log_fg': '#D1D5DB'
}

# ModernButtonとModernDropdownは launcher_v2.py から使用
# インポートは launcher_v2.py 側で行われる


class DatabaseInspectionPage(tk.Frame):
    """データベース確認ページ - 読み取り専用"""
    def __init__(self, parent, ModernButton, ModernDropdown):
        super().__init__(parent, bg=COLORS['bg_main'])
        
        # ボタンとドロップダウンのクラス参照を保存
        self.ModernButton = ModernButton
        self.ModernDropdown = ModernDropdown
        
        # データベースパス
        self.db_path = Path(__file__).parent / 'schoolphoto_v2.db'
        
        # 現在選択中のテーブル
        self.current_table = 'monthly_totals'
        
        # フィルタ条件
        self.filter_year = None
        self.filter_month = None
        
        # ページネーション
        self.current_page = 1
        self.records_per_page = 50
        self.total_records = 0
        
        # UI構築
        self._create_header()
        self._create_statistics_dashboard()
        self._create_table_selection()
        self._create_filter_panel()
        self._create_data_view()
        
        # 初期データ読み込み
        self._update_statistics()
        self._load_table_data()
    
    def _create_header(self):
        """ヘッダー作成"""
        header = tk.Frame(self, bg=COLORS['bg_main'])
        header.pack(fill=tk.X, padx=30, pady=(30, 20))
        
        tk.Label(
            header, text="データベース確認", font=('Meiryo', 18, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_main']
        ).pack(anchor='w')
        
        tk.Label(
            header, text="データベースに登録されている情報を確認します（読み取り専用）",
            font=('Meiryo', 10), fg=COLORS['text_secondary'], bg=COLORS['bg_main']
        ).pack(anchor='w', pady=(5, 0))
    
    def _create_statistics_dashboard(self):
        """統計ダッシュボード作成（4つのカード）"""
        stats_frame = tk.Frame(self, bg=COLORS['bg_main'])
        stats_frame.pack(fill=tk.X, padx=30, pady=(0, 20))
        
        # カードコンテナ
        cards_container = tk.Frame(stats_frame, bg=COLORS['bg_main'])
        cards_container.pack(fill=tk.X)
        cards_container.grid_columnconfigure(0, weight=1)
        cards_container.grid_columnconfigure(1, weight=1)
        cards_container.grid_columnconfigure(2, weight=1)
        cards_container.grid_columnconfigure(3, weight=1)
        
        # カード作成
        self.report_count_label = self._create_stat_card(
            cards_container, 0, "📊", "売上レポート", "0件"
        )
        self.school_count_label = self._create_stat_card(
            cards_container, 1, "🏫", "学校マスタ", "0校"
        )
        self.event_count_label = self._create_stat_card(
            cards_container, 2, "📅", "イベント売上", "0件"
        )
        self.last_update_label = self._create_stat_card(
            cards_container, 3, "🕒", "最終更新", "--"
        )
    
    def _create_stat_card(self, parent, column, icon, title, value):
        """統計カード作成"""
        card = tk.Frame(parent, bg=COLORS['bg_card'], padx=15, pady=15)
        card.grid(row=0, column=column, padx=5, sticky='ew')
        
        # アイコン + タイトル
        header_frame = tk.Frame(card, bg=COLORS['bg_card'])
        header_frame.pack(fill=tk.X)
        
        tk.Label(
            header_frame, text=icon, font=('Meiryo', 16),
            bg=COLORS['bg_card'], fg=COLORS['accent']
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Label(
            header_frame, text=title, font=('Meiryo', 9),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT)
        
        # 値ラベル
        value_label = tk.Label(
            card, text=value, font=('Meiryo', 20, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        )
        value_label.pack(anchor='w', pady=(5, 0))
        
        return value_label
    
    def _create_table_selection(self):
        """STEP 1: テーブル選択タブ"""
        section = tk.Frame(self, bg=COLORS['bg_card'], padx=20, pady=20)
        section.pack(fill=tk.X, padx=30, pady=(0, 15))
        
        # ヘッダー
        header_frame = tk.Frame(section, bg=COLORS['bg_card'])
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        step_badge = tk.Label(
            header_frame, text="STEP 1", font=('Meiryo', 9, 'bold'),
            fg=COLORS['accent'], bg='#1E3A5F', padx=8, pady=2
        )
        step_badge.pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(
            header_frame, text="確認するデータを選択", font=('Meiryo', 12, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT)
        
        # タブボタン
        tabs_frame = tk.Frame(section, bg=COLORS['bg_card'])
        tabs_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.tab_buttons = {}
        tables = [
            ('monthly_totals', '月別マスター'),
            ('school_monthly_sales', '学校別明細'),
            ('event_sales', 'イベント明細'),
            ('member_rates', '会員率')
        ]
        
        for i, (table_id, table_name) in enumerate(tables):
            btn = self.ModernButton(
                tabs_frame, text=table_name,
                btn_type='primary' if i == 0 else 'secondary',
                width=15,
                command=lambda t=table_id: self._select_table(t)
            )
            btn.pack(side=tk.LEFT, padx=(0, 10) if i < len(tables) - 1 else 0)
            self.tab_buttons[table_id] = btn
        
        # 説明テキスト
        self.table_description = tk.Label(
            section, text="→ 月ごとの売上概要", font=('Meiryo', 9),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card']
        )
        self.table_description.pack(anchor='w')
    
    def _create_filter_panel(self):
        """STEP 2: 検索条件パネル"""
        section = tk.Frame(self, bg=COLORS['bg_card'], padx=20, pady=20)
        section.pack(fill=tk.X, padx=30, pady=(0, 15))
        
        # ヘッダー
        header_frame = tk.Frame(section, bg=COLORS['bg_card'])
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        step_badge = tk.Label(
            header_frame, text="STEP 2", font=('Meiryo', 9, 'bold'),
            fg=COLORS['accent'], bg='#1E3A5F', padx=8, pady=2
        )
        step_badge.pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(
            header_frame, text="検索条件", font=('Meiryo', 12, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT)
        
        # フィルタ行
        filter_row = tk.Frame(section, bg=COLORS['bg_card'])
        filter_row.pack(fill=tk.X)
        
        # 年度フィルタ
        tk.Label(
            filter_row, text="年度:", font=('Meiryo', 10),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        # 年度の選択肢（2020-2030）
        year_values = ['すべて'] + [str(y) for y in range(2030, 2019, -1)]
        self.year_filter = self.ModernDropdown(
            filter_row, values=year_values, default_value='すべて', width=120
        )
        self.year_filter.pack(side=tk.LEFT, padx=(0, 20))
        
        # 月フィルタ
        tk.Label(
            filter_row, text="月:", font=('Meiryo', 10),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        # 月の選択肢（1-12）
        month_values = ['すべて'] + [str(m) for m in range(1, 13)]
        self.month_filter = self.ModernDropdown(
            filter_row, values=month_values, default_value='すべて', width=100
        )
        self.month_filter.pack(side=tk.LEFT, padx=(0, 20))
        
        # ボタン
        btn_frame = tk.Frame(filter_row, bg=COLORS['bg_card'])
        btn_frame.pack(side=tk.RIGHT)
        
        self.ModernButton(
            btn_frame, text="条件クリア", btn_type='secondary', width=10,
            command=self._clear_filters
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.ModernButton(
            btn_frame, text="検索", btn_type='primary', width=10,
            command=self._apply_filters
        ).pack(side=tk.LEFT)
    
    def _create_data_view(self):
        """データ表示エリア（Treeview + ページネーション）"""
        view_frame = tk.Frame(self, bg=COLORS['bg_main'])
        view_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 30))
        
        # Treeview
        tree_container = tk.Frame(view_frame, bg=COLORS['bg_card'])
        tree_container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(tree_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeviewスタイル設定 (Hybrid Modern)
        style = ttk.Style()
        style.theme_use('clam')  # カスタマイズしやすいテーマを使用
        
        # Treeview全体のスタイル
        style.configure(
            "Modern.Treeview",
            background=COLORS['bg_main'],
            foreground=COLORS['text_primary'],
            fieldbackground=COLORS['bg_main'],
            borderwidth=0,
            rowheight=30,  # 行間を少し広げて見やすく
            font=('Meiryo', 10)
        )
        
        # ヘッダーのスタイル（フラット & ダーク）
        style.configure(
            "Modern.Treeview.Heading",
            background="#374151",  # 少し明るいグレー
            foreground="#FFFFFF",
            relief="flat",
            font=('Meiryo', 10, 'bold'),
            padding=(10, 5)
        )
        
        # ヘッダーのホバー効果
        style.map(
            "Modern.Treeview.Heading",
            background=[('active', '#4B5563')]
        )
        
        # 選択行のスタイル
        style.map(
            "Modern.Treeview",
            background=[('selected', COLORS['accent'])],
            foreground=[('selected', '#FFFFFF')]
        )
        
        self.tree = ttk.Treeview(
            tree_container,
            yscrollcommand=scrollbar.set,
            selectmode='browse',
            height=15,
            style="Modern.Treeview"
        )
        
        # ストライプ（縞模様）用のタグ設定
        self.tree.tag_configure('odd', background=COLORS['bg_main'])
        self.tree.tag_configure('even', background='#252F3E')  # 少し明るい背景色
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.tree.yview)
        
        # ページネーション
        pagination_frame = tk.Frame(view_frame, bg=COLORS['bg_main'])
        pagination_frame.pack(fill=tk.X, pady=(10, 0))
        
        # ページ情報（左）
        self.page_info_label = tk.Label(
            pagination_frame, text="0件中 0-0件", font=('Meiryo', 9),
            fg=COLORS['text_secondary'], bg=COLORS['bg_main']
        )
        self.page_info_label.pack(side=tk.LEFT)
        
        # ページボタン（右）
        page_buttons = tk.Frame(pagination_frame, bg=COLORS['bg_main'])
        page_buttons.pack(side=tk.RIGHT)
        
        self.ModernButton(
            page_buttons, text="<<", width=3,
            command=lambda: self._change_page('first')
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.ModernButton(
            page_buttons, text="<", width=3,
            command=lambda: self._change_page('prev')
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.page_number_label = tk.Label(
            page_buttons, text="1/1", font=('Meiryo', 10, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_main']
        )
        self.page_number_label.pack(side=tk.LEFT, padx=10)
        
        self.ModernButton(
            page_buttons, text=">", width=3,
            command=lambda: self._change_page('next')
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.ModernButton(
            page_buttons, text=">>", width=3,
            command=lambda: self._change_page('last')
        ).pack(side=tk.LEFT)
    
    # ========================================
    # データ取得・表示メソッド
    # ========================================
    
    def _update_statistics(self):
        """統計情報を更新"""
        try:
            conn = database_v2.get_connection(self.db_path)
            cursor = conn.cursor()
            
            # レポート件数
            cursor.execute('SELECT COUNT(*) FROM reports')
            report_count = cursor.fetchone()[0]
            self.report_count_label.config(text=f"{report_count}件")
            
            # 学校数
            cursor.execute('SELECT COUNT(DISTINCT school_id) FROM schools_master')
            school_count = cursor.fetchone()[0]
            self.school_count_label.config(text=f"{school_count}校")
            
            # イベント件数
            cursor.execute('SELECT COUNT(*) FROM event_sales')
            event_count = cursor.fetchone()[0]
            self.event_count_label.config(text=f"{event_count}件")
            
            # 最終更新
            cursor.execute('SELECT MAX(imported_at) FROM reports')
            last_update = cursor.fetchone()[0]
            if last_update:
                dt = datetime.fromisoformat(last_update)
                self.last_update_label.config(text=dt.strftime('%Y/%m/%d %H:%M'))
            
            conn.close()
        except Exception as e:
            print(f"統計情報取得エラー: {e}")
    
    def _load_table_data(self):
        """テーブルデータを読み込み"""
        try:
            # Treeviewクリア
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # テーブル定義（カラム、クエリ、カラム幅）
            table_configs = {
                'monthly_totals': {
                    'columns': ['ID', '年度', '月', '総売上', '直売上', 'スタジオ売上', '学校数', '予算'],
                    'column_ids': ['id', 'fiscal_year', 'month', 'total_sales', 'direct_sales', 'studio_sales', 'school_count', 'budget'],
                    'widths': [50, 60, 40, 100, 100, 100, 70, 100],
                    'query': '''
                        SELECT id, fiscal_year, month, total_sales, direct_sales, studio_sales, school_count, budget
                        FROM monthly_totals
                        WHERE 1=1
                        {year_filter}
                        {month_filter}
                        ORDER BY fiscal_year DESC, month DESC
                        LIMIT ? OFFSET ?
                    ''',
                    'count_query': 'SELECT COUNT(*) FROM monthly_totals WHERE 1=1 {year_filter} {month_filter}'
                },
                'school_monthly_sales': {
                    'columns': ['ID', '年度', '月', '学校ID', '学校名', '担当者', 'スタジオ', '売上'],
                    'column_ids': ['id', 'fiscal_year', 'month', 'school_id', 'school_name', 'manager', 'studio', 'sales'],
                    'widths': [50, 60, 40, 70, 200, 80, 80, 100],
                    'query': '''
                        SELECT s.id, s.fiscal_year, s.month, s.school_id, 
                               COALESCE(m.school_name, '不明'), s.manager, s.studio, s.sales
                        FROM school_monthly_sales s
                        LEFT JOIN schools_master m ON s.school_id = m.school_id
                        WHERE 1=1
                        {year_filter}
                        {month_filter}
                        ORDER BY s.fiscal_year DESC, s.month DESC, s.sales DESC
                        LIMIT ? OFFSET ?
                    ''',
                    'count_query': 'SELECT COUNT(*) FROM school_monthly_sales WHERE 1=1 {year_filter} {month_filter}'
                },
                'event_sales': {
                    'columns': ['ID', '年度', '月', 'イベント日', '学校名', '支社', 'イベント名', '売上'],
                    'column_ids': ['id', 'fiscal_year', 'month', 'event_date', 'school_name', 'branch', 'event_name', 'sales'],
                    'widths': [50, 60, 40, 90, 200, 80, 150, 100],
                    'query': '''
                        SELECT e.id, e.fiscal_year, e.month, e.event_date,
                               COALESCE(m.school_name, '不明'), e.branch, e.event_name, e.sales
                        FROM event_sales e
                        LEFT JOIN schools_master m ON e.school_id = m.school_id
                        WHERE 1=1
                        {year_filter}
                        {month_filter}
                        ORDER BY e.event_date DESC
                        LIMIT ? OFFSET ?
                    ''',
                    'count_query': 'SELECT COUNT(*) FROM event_sales WHERE 1=1 {year_filter} {month_filter}'
                },
                'member_rates': {
                    'columns': ['ID', '学校ID', '学校名', 'スナップショット日', '学年', '会員率(%)', '総生徒数', '会員数'],
                    'column_ids': ['id', 'school_id', 'school_name', 'snapshot_date', 'grade', 'member_rate', 'total_students', 'member_count'],
                    'widths': [50, 70, 200, 110, 80, 80, 80, 70],
                    'query': '''
                        SELECT r.id, r.school_id, COALESCE(m.school_name, '不明'), 
                               r.snapshot_date, r.grade, r.member_rate, r.total_students, r.member_count
                        FROM member_rates r
                        LEFT JOIN schools_master m ON r.school_id = m.school_id
                        WHERE 1=1
                        ORDER BY r.snapshot_date DESC
                        LIMIT ? OFFSET ?
                    ''',
                    'count_query': 'SELECT COUNT(*) FROM member_rates WHERE 1=1'
                }
            }
            
            config = table_configs.get(self.current_table)
            if not config:
                return
            
            # フィルタ条件構築
            year_filter = f" AND fiscal_year = {self.filter_year}" if self.filter_year else ""
            month_filter = f" AND month = {self.filter_month}" if self.filter_month else ""
            
            # member_ratesテーブルにはfiscal_year/monthカラムがないのでフィルタ無効
            if self.current_table == 'member_rates':
                year_filter = ""
                month_filter = ""
            
            # クエリ準備
            query = config['query'].format(year_filter=year_filter, month_filter=month_filter)
            count_query = config['count_query'].format(year_filter=year_filter, month_filter=month_filter)
            
            # データベース接続
            conn = database_v2.get_connection(self.db_path)
            cursor = conn.cursor()
            
            # 総件数取得
            cursor.execute(count_query)
            self.total_records = cursor.fetchone()[0]
            
            # ページネーション計算
            total_pages = max(1, (self.total_records + self.records_per_page - 1) // self.records_per_page)
            self.current_page = min(self.current_page, total_pages)
            offset = (self.current_page - 1) * self.records_per_page
            
            # データ取得
            cursor.execute(query, (self.records_per_page, offset))
            rows = cursor.fetchall()
            
            conn.close()
            
            # Treeview設定
            self.tree.configure(columns=config['column_ids'], show='headings')
            
            # カラムヘッダー設定
            for i, (col_id, col_name, width) in enumerate(zip(config['column_ids'], config['columns'], config['widths'])):
                self.tree.heading(col_id, text=col_name)
                self.tree.column(col_id, width=width, anchor='w' if i > 0 else 'center')
            
            # データ挿入
            for row in rows:
                # 数値フォーマット
                formatted_row = []
                for i, value in enumerate(row):
                    if value is None:
                        formatted_row.append('')
                    elif isinstance(value, float):
                        formatted_row.append(f"{value:,.0f}")
                    else:
                        formatted_row.append(str(value))
                
                # ストライプ用のタグ設定
                tags = ('even',) if i % 2 == 0 else ('odd',)
                self.tree.insert('', 'end', values=formatted_row, tags=tags)
            
            # ページ情報更新
            start_num = offset + 1 if self.total_records > 0 else 0
            end_num = min(offset + self.records_per_page, self.total_records)
            self.page_info_label.config(text=f"{self.total_records}件中 {start_num}-{end_num}件")
            self.page_number_label.config(text=f"{self.current_page}/{total_pages}")
            
        except Exception as e:
            print(f"データ取得エラー: {e}")
            import traceback
            traceback.print_exc()
    
    def _select_table(self, table_id):
        """テーブル選択"""
        self.current_table = table_id
        
        # ボタンスタイル更新
        for tid, btn in self.tab_buttons.items():
            btn.config(btn_type='primary' if tid == table_id else 'secondary')
        
        # 説明更新
        descriptions = {
            'monthly_totals': '→ 月ごとの売上概要',
            'school_monthly_sales': '→ 学校別の月次売上',
            'event_sales': '→ イベント単位の売上',
            'member_rates': '→ 学校別会員率スナップショット'
        }
        self.table_description.config(text=descriptions.get(table_id, ''))
        
        # データ再読み込み
        self._load_table_data()
    
    def _clear_filters(self):
        """フィルタクリア"""
        self.year_filter._select('すべて')
        self.month_filter._select('すべて')
        self.filter_year = None
        self.filter_month = None
        self._load_table_data()
    
    def _apply_filters(self):
        """フィルタ適用"""
        year = self.year_filter.get()
        month = self.month_filter.get()
        
        self.filter_year = None if year == 'すべて' else int(year)
        self.filter_month = None if month == 'すべて' else int(month)
        
        self.current_page = 1
        self._load_table_data()
    
    def _change_page(self, direction):
        """ページ変更"""
        total_pages = max(1, (self.total_records + self.records_per_page - 1) // self.records_per_page)
        
        if direction == 'first':
            self.current_page = 1
        elif direction == 'last':
            self.current_page = total_pages
        elif direction == 'prev':
            self.current_page = max(1, self.current_page - 1)
        elif direction == 'next':
            self.current_page = min(total_pages, self.current_page + 1)
        
        self._load_table_data()
