#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上管理システム - Desktop App (Dark Sidebar)

従来のランチャー機能に加え、WEBアプリの機能を統合するための
メインデスクトップアプリケーション。
"""

import sys
import os
import subprocess
import threading
import json
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
from datetime import datetime
import ctypes

# パス設定
BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / 'app'
CONFIG_FILE = BASE_DIR / 'launcher_config.json'

# 高DPI対応（Windows）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# カラーパレット (Dark Sidebar Theme)
COLORS = {
    'bg_sidebar': '#111827',   # サイドバー背景（かなり暗い）
    'bg_main': '#1F2937',      # メインエリア背景（暗いグレー）
    'bg_card': '#374151',      # カード背景（少し明るいグレー）
    'text_primary': '#F9FAFB', # メインテキスト（白に近い）
    'text_secondary': '#9CA3AF', # サブテキスト（グレー）
    'accent': '#3B82F6',       # アクセントカラー（青）
    'accent_hover': '#2563EB',
    'danger': '#EF4444',       # 赤
    'danger_hover': '#DC2626',
    'success': '#10B981',      # 緑
    'border': '#4B5563',       # 枠線
    'sidebar_active': '#374151', # サイドバー選択中
    'log_bg': '#111827',       # ログ背景
    'log_fg': '#D1D5DB'        # ログ文字
}

# デフォルト設定
DEFAULT_CONFIG = {
    'api_port': 8080,
    'dashboard_port': 8000,
}

class ModernButton(tk.Button):
    """モダンなフラットボタン"""
    def __init__(self, master, **kwargs):
        self.btn_type = kwargs.pop('btn_type', 'primary')
        self.default_bg = kwargs.pop('bg', COLORS['accent'])
        if self.btn_type == 'danger':
            self.default_bg = COLORS['danger']
            self.hover_bg = COLORS['danger_hover']
        else:
            self.hover_bg = COLORS['accent_hover']
        
        # 初期状態の設定
        state = kwargs.get('state', 'normal')
        current_bg = self.default_bg if state != 'disabled' else '#6B7280'
        
        super().__init__(
            master,
            relief='flat',
            borderwidth=0,
            cursor='hand2' if state != 'disabled' else 'arrow',
            font=('Segoe UI', 9, 'bold'),
            fg='white',
            bg=current_bg,
            activebackground=self.hover_bg,
            activeforeground='white',
            **kwargs
        )
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

    def _on_enter(self, e):
        if self['state'] != 'disabled':
            self['bg'] = self.hover_bg

    def _on_leave(self, e):
        if self['state'] != 'disabled':
            self['bg'] = self.default_bg
            
    def configure(self, cnf=None, **kwargs):
        if cnf is None:
            cnf = {}
        cnf = {**cnf, **kwargs}
        if 'state' in cnf:
            if cnf['state'] == 'disabled':
                self['bg'] = '#6B7280'
                self['cursor'] = 'arrow'
            else:
                self['bg'] = self.default_bg
                self['cursor'] = 'hand2'
        super().configure(cnf)

class SidebarButton(tk.Button):
    """サイドバー用ナビゲーションボタン"""
    def __init__(self, master, text, icon, command, is_active=False):
        self.default_bg = COLORS['bg_sidebar']
        self.active_bg = COLORS['sidebar_active']
        self.hover_bg = '#1F2937'
        self.is_active = is_active
        
        super().__init__(
            master,
            text=f"  {icon}  {text}",
            font=('Segoe UI', 10),
            fg=COLORS['text_primary'] if is_active else COLORS['text_secondary'],
            bg=self.active_bg if is_active else self.default_bg,
            relief='flat',
            bd=0,
            anchor='w',
            padx=20,
            cursor='hand2',
            activebackground=self.active_bg,
            activeforeground=COLORS['text_primary'],
            command=command
        )
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

    def _on_enter(self, e):
        if not self.is_active:
            self['bg'] = self.hover_bg
            self['fg'] = COLORS['text_primary']

    def _on_leave(self, e):
        if not self.is_active:
            self['bg'] = self.default_bg
            self['fg'] = COLORS['text_secondary']

    def set_active(self, active):
        self.is_active = active
        if active:
            self['bg'] = self.active_bg
            self['fg'] = COLORS['text_primary']
            self['font'] = ('Segoe UI', 10, 'bold')
        else:
            self['bg'] = self.default_bg
            self['fg'] = COLORS['text_secondary']
            self['font'] = ('Segoe UI', 10)


class MainApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('SP ADMIN PRO - スクールフォト売上管理')
        self.root.geometry('1000x700')
        self.root.configure(bg=COLORS['bg_main'])

        # プロセス管理 (サーバータブで使用)
        self.server_manager = ServerManager(self)
        
        # メインレイアウト
        self._setup_layout()
        
        # 閉じる処理
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # 初期表示
        self.show_page('server')

    def _setup_layout(self):
        # 1. サイドバー (左側)
        self.sidebar = tk.Frame(self.root, bg=COLORS['bg_sidebar'], width=250)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False) # 幅を固定

        # ロゴエリア
        logo_frame = tk.Frame(self.sidebar, bg=COLORS['bg_sidebar'], height=80)
        logo_frame.pack(fill=tk.X)
        logo_frame.pack_propagate(False)
        
        tk.Label(
            logo_frame, 
            text="SP ADMIN PRO", 
            font=('Segoe UI', 16, 'bold'),
            fg=COLORS['accent'],
            bg=COLORS['bg_sidebar']
        ).pack(side=tk.LEFT, padx=20, pady=25)

        # メニューボタンエリア
        self.menu_buttons = {}
        menu_items = [
            ('server', 'サーバー管理', '⚙'),
            ('monthly', '月次集計', '📅'),
            ('cumulative', '累積集計', '📈'),
            ('results', '実績反映', '⚡'),
            ('database', 'データベース確認', '💾'),
        ]

        for key, text, icon in menu_items:
            btn = SidebarButton(
                self.sidebar, 
                text, 
                icon, 
                lambda k=key: self.show_page(k)
            )
            btn.pack(fill=tk.X, pady=2)
            self.menu_buttons[key] = btn

        # フッター (バージョン情報など)
        footer_label = tk.Label(
            self.sidebar,
            text="v2.1.0",
            font=('Segoe UI', 8),
            fg=COLORS['text_secondary'],
            bg=COLORS['bg_sidebar']
        )
        footer_label.pack(side=tk.BOTTOM, pady=20)

        # 2. メインコンテンツエリア (右側)
        self.content_area = tk.Frame(self.root, bg=COLORS['bg_main'])
        self.content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ページ保持用辞書
        self.pages = {}
        
        # 各ページの初期化
        self.pages['server'] = ServerControlPage(self.content_area, self.server_manager)
        self.pages['monthly'] = MonthlyAggregationPage(self.content_area)
        self.pages['cumulative'] = PlaceholderPage(self.content_area, "累積集計", "過去のデータを統合して全体の傾向を分析します")
        self.pages['results'] = PlaceholderPage(self.content_area, "実績反映", "確定した売上データをシステムのマスタに反映させます")
        self.pages['database'] = PlaceholderPage(self.content_area, "データベース確認", "登録されているテーブルやレコードを直接確認します")

    def show_page(self, page_key):
        # メニューボタンの見た目更新
        for key, btn in self.menu_buttons.items():
            btn.set_active(key == page_key)
            
        # ページの切り替え
        for key, page in self.pages.items():
            if key == page_key:
                page.pack(fill=tk.BOTH, expand=True)
            else:
                page.pack_forget()

    def _on_closing(self):
        if self.server_manager.is_any_running():
            if messagebox.askyesno('終了確認', 'サーバーが実行中です。\n停止してから終了しますか？'):
                self.server_manager.stop_all()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        self.root.mainloop()


class ServerManager:
    """サーバープロセスの管理ロジック"""
    def __init__(self, app):
        self.app = app
        self.api_process = None
        self.dashboard_process = None
        self.config = self._load_config()
        self.log_callback = None # ログ出力先 (Page側でセット)

    def _load_config(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()

    def save_config(self, api_port, dashboard_port):
        self.config['api_port'] = api_port
        self.config['dashboard_port'] = dashboard_port
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def is_any_running(self):
        return (self.api_process is not None) or (self.dashboard_process is not None)

    def start_api(self, port, on_start, on_stop):
        if self.api_process: return
        
        def run():
            try:
                script_path = APP_DIR / 'run.py'
                self.api_process = subprocess.Popen(
                    [sys.executable, str(script_path), '--port', str(port)],
                    cwd=str(APP_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                self.app.root.after(0, on_start)
                self.log(f'管理APIサーバー起動完了: http://127.0.0.1:{port}')
                
                for line in self.api_process.stdout:
                    self.app.root.after(0, lambda l=line: self.log(f'[API] {l.strip()}'))
            except Exception as e:
                self.app.root.after(0, lambda: self.log(f'API起動エラー: {e}'))
                self.app.root.after(0, on_stop)

        threading.Thread(target=run, daemon=True).start()

    def stop_api(self):
        if self.api_process:
            self.api_process.terminate()
            self.api_process = None
            self.log('APIサーバー停止')

    def start_dashboard(self, port, on_start, on_stop):
        if self.dashboard_process: return
        
        def run():
            try:
                script_path = APP_DIR / 'simple_server.py'
                self.dashboard_process = subprocess.Popen(
                    [sys.executable, str(script_path), '--port', str(port)],
                    cwd=str(APP_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                self.app.root.after(0, on_start)
                self.log(f'公開ダッシュボード起動完了: http://localhost:{port}')
                
                for line in self.dashboard_process.stdout:
                    self.app.root.after(0, lambda l=line: self.log(f'[Web] {l.strip()}'))
            except Exception as e:
                self.app.root.after(0, lambda: self.log(f'Dashboard起動エラー: {e}'))
                self.app.root.after(0, on_stop)

        threading.Thread(target=run, daemon=True).start()

    def stop_dashboard(self):
        if self.dashboard_process:
            self.dashboard_process.terminate()
            self.dashboard_process = None
            self.log('Dashboardサーバー停止')

    def stop_all(self):
        self.stop_api()
        self.stop_dashboard()


class ServerControlPage(tk.Frame):
    """サーバー管理ページ (旧ランチャー機能)"""
    def __init__(self, parent, manager):
        super().__init__(parent, bg=COLORS['bg_main'])
        self.manager = manager
        
        # ログコールバックの登録
        self.manager.log_callback = self._log_to_widget

        # ヘッダー
        tk.Label(self, text="サーバー管理", font=('Segoe UI', 18, 'bold'), 
                 fg=COLORS['text_primary'], bg=COLORS['bg_main']).pack(anchor='w', padx=30, pady=(30, 20))

        # コンテンツエリア
        container = tk.Frame(self, bg=COLORS['bg_main'])
        container.pack(fill=tk.BOTH, expand=True, padx=30)
        
        # カード配置
        cards_frame = tk.Frame(container, bg=COLORS['bg_main'])
        cards_frame.pack(fill=tk.X)
        cards_frame.grid_columnconfigure(0, weight=1)
        cards_frame.grid_columnconfigure(1, weight=1)

        # APIカード
        self._create_card(cards_frame, 0, "管理APIサーバー", "🛠", True)
        # Dashboardカード
        self._create_card(cards_frame, 1, "公開ダッシュボード", "🌐", False)

        # ログエリア
        log_frame = tk.Frame(container, bg=COLORS['bg_main'])
        log_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        tk.Label(log_frame, text="システムログ", font=('Segoe UI', 10, 'bold'),
                 fg=COLORS['text_secondary'], bg=COLORS['bg_main']).pack(anchor='w', pady=(0, 5))
                 
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=10, font=('Consolas', 9),
            bg=COLORS['log_bg'], fg=COLORS['log_fg'],
            bd=0, highlightthickness=0
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _create_card(self, parent, col, title, icon, is_api):
        card = tk.Frame(parent, bg=COLORS['bg_card'], padx=20, pady=20)
        card.grid(row=0, column=col, padx=10 if col==1 else (0, 10), sticky='ew')
        
        # タイトル
        header = tk.Frame(card, bg=COLORS['bg_card'])
        header.pack(fill=tk.X, pady=(0, 15))
        tk.Label(header, text=icon, font=('Segoe UI', 16), bg=COLORS['bg_card'], fg='white').pack(side=tk.LEFT, padx=(0,10))
        tk.Label(header, text=title, font=('Segoe UI', 14, 'bold'), bg=COLORS['bg_card'], fg='white').pack(side=tk.LEFT)

        # ステータス
        status_var = tk.StringVar(value="停止中")
        status_lbl = tk.Label(card, textvariable=status_var, font=('Segoe UI', 11), bg=COLORS['bg_card'], fg=COLORS['text_secondary'])
        status_lbl.pack(pady=(0, 15))

        # ポート設定
        conf_frame = tk.Frame(card, bg=COLORS['bg_card'])
        conf_frame.pack(fill=tk.X, pady=(0, 15))
        tk.Label(conf_frame, text="ポート", bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(side=tk.LEFT)
        port_var = tk.StringVar(value=str(self.manager.config['api_port'] if is_api else self.manager.config['dashboard_port']))
        tk.Entry(conf_frame, textvariable=port_var, width=6, bg=COLORS['bg_main'], fg='white', relief='flat', insertbackground='white').pack(side=tk.LEFT, padx=10)

        # コントロール
        btn_frame = tk.Frame(card, bg=COLORS['bg_card'])
        btn_frame.pack(fill=tk.X)
        
        start_btn = ModernButton(btn_frame, text="起動", btn_type="primary")
        start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        stop_btn = ModernButton(btn_frame, text="停止", btn_type="danger", state="disabled")
        stop_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # アクション設定
        def on_start_click():
            try:
                p = int(port_var.get())
                self.manager.save_config(
                    p if is_api else self.manager.config['api_port'],
                    p if not is_api else self.manager.config['dashboard_port']
                )
                if is_api:
                    self.manager.start_api(p, lambda: update_ui(True), lambda: update_ui(False))
                else:
                    self.manager.start_dashboard(p, lambda: update_ui(True), lambda: update_ui(False))
            except ValueError:
                messagebox.showerror("エラー", "ポート番号を確認してください")

        def on_stop_click():
            if is_api:
                self.manager.stop_api()
            else:
                self.manager.stop_dashboard()
            update_ui(False)

        def update_ui(running):
            if running:
                status_var.set("起動中")
                status_lbl.config(fg=COLORS['success'])
                start_btn.config(state="disabled")
                stop_btn.config(state="normal")
            else:
                status_var.set("停止中")
                status_lbl.config(fg=COLORS['text_secondary'])
                start_btn.config(state="normal")
                stop_btn.config(state="disabled")

        start_btn.config(command=on_start_click)
        stop_btn.config(command=on_stop_click)


    def _log_to_widget(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f'[{timestamp}] {message}\n')
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)


class PlaceholderPage(tk.Frame):
    """未実装機能のプレースホルダーページ"""
    def __init__(self, parent, title, description):
        super().__init__(parent, bg=COLORS['bg_main'])
        
        tk.Label(self, text=title, font=('Segoe UI', 24, 'bold'), 
                 fg=COLORS['text_primary'], bg=COLORS['bg_main']).pack(anchor='center', pady=(150, 20))
        
        tk.Label(self, text=description, font=('Segoe UI', 12),
                 fg=COLORS['text_secondary'], bg=COLORS['bg_main']).pack(anchor='center')
        
        tk.Label(self, text="この機能は現在開発中です", font=('Segoe UI', 10),
                 fg=COLORS['accent'], bg=COLORS['bg_main']).pack(anchor='center', pady=30)


class MonthlyAggregationPage(tk.Frame):
    """月次集計ページ"""
    def __init__(self, parent):
        super().__init__(parent, bg=COLORS['bg_main'])
        
        # 状態管理
        self.files = {
            'sales': None,
            'accounts': None,
            'master': None
        }
        self.is_processing = False
        
        # UI構築
        self._create_header()
        self._create_main_layout()

    def _create_header(self):
        """ヘッダー作成"""
        header = tk.Frame(self, bg=COLORS['bg_main'])
        header.pack(fill=tk.X, padx=30, pady=(30, 20))
        
        tk.Label(
            header, text="月次集計", font=('Segoe UI', 18, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_main']
        ).pack(anchor='w')
        
        tk.Label(
            header, text="CSVデータから売上を集計し、Excel報告書を作成します",
            font=('Segoe UI', 10), fg=COLORS['text_secondary'], bg=COLORS['bg_main']
        ).pack(anchor='w', pady=(5, 0))

    def _create_main_layout(self):
        """メインレイアウト作成"""
        container = tk.Frame(self, bg=COLORS['bg_main'])
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 30))
        
        # 左右2カラムレイアウト
        # 左側: ファイル選択（60%）
        left_frame = tk.Frame(container, bg=COLORS['bg_main'])
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))
        
        # 右側: 期間選択 + 実行（40%）
        right_frame = tk.Frame(container, bg=COLORS['bg_main'])
        right_frame.pack(side=tk.LEFT, fill=tk.Y, ipadx=150)
        
        self._create_file_upload_section(left_frame)
        self._create_period_section(right_frame)

    def _create_file_upload_section(self, parent):
        """ファイルアップロードセクション作成"""
        # STEP 1ヘッダー
        header_frame = tk.Frame(parent, bg=COLORS['bg_card'], padx=20, pady=15)
        header_frame.pack(fill=tk.X)
        
        step_badge = tk.Label(
            header_frame, text="STEP 1", font=('Consolas', 8, 'bold'),
            fg=COLORS['accent'], bg='#1E3A5F', padx=8, pady=2
        )
        step_badge.pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(
            header_frame, text="ファイル選択", font=('Segoe UI', 11, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT)
        
        # ファイル選択エリア
        files_container = tk.Frame(parent, bg=COLORS['bg_card'], padx=20, pady=20)
        files_container.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        
        # 3つのファイル選択UI
        self._create_file_select_row(files_container, "売上データ (CSV)", "📊", "sales", "*.csv")
        self._create_file_select_row(files_container, "会員データ (CSV)", "👥", "accounts", "*.csv")
        self._create_file_select_row(files_container, "担当者マスタ (XLSX)", "📋", "master", "*.xlsx")

    def _create_file_select_row(self, parent, label_text, icon, file_key, file_filter):
        """ファイル選択行を作成（ドロップゾーンスタイル）"""
        row_frame = tk.Frame(parent, bg=COLORS['bg_card'])
        row_frame.pack(fill=tk.X, pady=(0, 20))
        
        # ラベル + アイコン
        label_frame = tk.Frame(row_frame, bg=COLORS['bg_card'])
        label_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(
            label_frame, text=icon, font=('Segoe UI', 14),
            bg=COLORS['bg_card']
        ).pack(side=tk.LEFT, padx=(0, 8))
        
        tk.Label(
            label_frame, text=label_text, font=('Segoe UI', 10, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT)
        
        # チェックマーク（選択済みの場合）
        check_label = tk.Label(
            label_frame, text="✓", font=('Segoe UI', 12, 'bold'),
            fg=COLORS['success'], bg=COLORS['bg_card']
        )
        
        # ドロップゾーン（破線ボーダー + クラウドアイコン）
        drop_zone = tk.Frame(row_frame, bg=COLORS['bg_main'], highlightthickness=2, 
                             highlightbackground=COLORS['border'], highlightcolor=COLORS['border'])
        drop_zone.pack(fill=tk.X, ipady=30)
        
        # 内部コンテンツフレーム（クリック可能にするため）
        content_frame = tk.Frame(drop_zone, bg=COLORS['bg_main'], cursor='hand2')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # クラウドアイコン
        cloud_label = tk.Label(
            content_frame, text="☁", font=('Segoe UI', 32),
            fg=COLORS['text_secondary'], bg=COLORS['bg_main']
        )
        cloud_label.pack(pady=(0, 5))
        
        # プレースホルダーテキスト / ファイル名
        file_name_label = tk.Label(
            content_frame, text="ファイルをドラッグ&ドロップ",
            font=('Segoe UI', 9), fg=COLORS['text_secondary'],
            bg=COLORS['bg_main']
        )
        file_name_label.pack()
        
        # クリックイベントをバインド（ドロップゾーン全体をクリック可能に）
        def on_click(event=None):
            self._select_file(file_key, file_name_label, cloud_label, check_label, file_filter)
        
        drop_zone.bind('<Button-1>', on_click)
        content_frame.bind('<Button-1>', on_click)
        cloud_label.bind('<Button-1>', on_click)
        file_name_label.bind('<Button-1>', on_click)
        
        # ホバーエフェクト
        def on_enter(event):
            drop_zone.config(highlightbackground=COLORS['accent'], highlightcolor=COLORS['accent'])
            content_frame.config(bg='#2a3142')
            cloud_label.config(bg='#2a3142', fg=COLORS['accent'])
            file_name_label.config(bg='#2a3142')
        
        def on_leave(event):
            drop_zone.config(highlightbackground=COLORS['border'], highlightcolor=COLORS['border'])
            content_frame.config(bg=COLORS['bg_main'])
            cloud_label.config(bg=COLORS['bg_main'], fg=COLORS['text_secondary'])
            file_name_label.config(bg=COLORS['bg_main'])
        
        drop_zone.bind('<Enter>', on_enter)
        drop_zone.bind('<Leave>', on_leave)
        content_frame.bind('<Enter>', on_enter)
        content_frame.bind('<Leave>', on_leave)
        
        # 参照を保存
        setattr(self, f'{file_key}_name_label', file_name_label)
        setattr(self, f'{file_key}_cloud_label', cloud_label)
        setattr(self, f'{file_key}_check', check_label)

    def _create_period_section(self, parent):
        """期間選択セクション作成"""
        # STEP 2カード
        card = tk.Frame(parent, bg=COLORS['bg_card'], padx=20, pady=20)
        card.pack(fill=tk.X)
        
        # ヘッダー
        header_frame = tk.Frame(card, bg=COLORS['bg_card'])
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        step_badge = tk.Label(
            header_frame, text="STEP 2", font=('Consolas', 8, 'bold'),
            fg=COLORS['accent'], bg='#1E3A5F', padx=8, pady=2
        )
        step_badge.pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(
            header_frame, text="対象期間", font=('Segoe UI', 11, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT)
        
        # 年度選択
        year_frame = tk.Frame(card, bg=COLORS['bg_card'])
        year_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(
            year_frame, text="年度", font=('Segoe UI', 9, 'bold'),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card']
        ).pack(anchor='w', pady=(0, 5))
        
        # 年度のリスト（過去5年分）
        current_year = datetime.now().year
        current_month = datetime.now().month
        fiscal_year = current_year if current_month >= 4 else current_year - 1
        years = [str(y) + "年度" for y in range(fiscal_year - 4, fiscal_year + 2)]
        
        self.year_var = tk.StringVar(value=str(fiscal_year) + "年度")
        year_combo = ttk.Combobox(
            year_frame, textvariable=self.year_var, values=years,
            state='readonly', font=('Segoe UI', 10)
        )
        year_combo.pack(fill=tk.X)
        
        # 月選択
        month_frame = tk.Frame(card, bg=COLORS['bg_card'])
        month_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(
            month_frame, text="月", font=('Segoe UI', 9, 'bold'),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card']
        ).pack(anchor='w', pady=(0, 5))
        
        months = [str(m) + "月" for m in range(1, 13)]
        self.month_var = tk.StringVar(value=str(current_month) + "月")
        month_combo = ttk.Combobox(
            month_frame, textvariable=self.month_var, values=months,
            state='readonly', font=('Segoe UI', 10)
        )
        month_combo.pack(fill=tk.X)
        
        # 実行ボタン
        self.execute_btn = ModernButton(
            card, text="集計を実行", btn_type='primary',
            command=self._execute_aggregation,
            state='disabled'
        )
        self.execute_btn.pack(fill=tk.X, pady=(10, 0))

    def _select_file(self, file_key, file_name_label, cloud_label, check_label, file_filter):
        """ファイル選択ダイアログ"""
        from tkinter import filedialog
        
        filetypes = []
        if file_filter == "*.csv":
            filetypes = [("CSVファイル", "*.csv"), ("すべてのファイル", "*.*")]
        elif file_filter == "*.xlsx":
            filetypes = [("Excelファイル", "*.xlsx"), ("すべてのファイル", "*.*")]
        
        filename = filedialog.askopenfilename(
            title=f"{file_key}ファイルを選択",
            filetypes=filetypes
        )
        
        if filename:
            self.files[file_key] = filename
            # ファイル名のみ表示
            file_name_label.config(text=Path(filename).name, fg=COLORS['accent'])
            # クラウドアイコンを小さく、色を変更
            cloud_label.config(text="📄", font=('Segoe UI', 24))
            # チェックマーク表示
            check_label.pack(side=tk.RIGHT)
            self._check_can_execute()

    def _check_can_execute(self):
        """実行ボタンの活性化チェック"""
        if all(self.files.values()) and not self.is_processing:
            self.execute_btn.config(state='normal')
        else:
            self.execute_btn.config(state='disabled')

    def _execute_aggregation(self):
        """集計実行"""
        # TODO: 次のステップで実装
        messagebox.showinfo("開発中", "集計機能は次のステップで実装します")


def main():
    app = MainApp()
    app.run()

if __name__ == '__main__':
    main()
