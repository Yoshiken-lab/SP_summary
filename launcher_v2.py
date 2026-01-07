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
        self.pages['monthly'] = PlaceholderPage(self.content_area, "月次集計", "CSVデータから売上を集計し、Excel報告書を作成します")
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


def main():
    app = MainApp()
    app.run()

if __name__ == '__main__':
    main()
