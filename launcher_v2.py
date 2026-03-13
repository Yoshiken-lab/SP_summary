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
import socket
import time
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import webbrowser
from pathlib import Path
from datetime import datetime
import ctypes
import shutil
from importer_v2 import import_excel_v2
from dashboard_v2 import generate_dashboard
import database_v2
from database_inspection_page import DatabaseInspectionPage

# バックエンドモジュールをインポート
sys.path.insert(0, str(Path(__file__).parent / 'app' / 'backend'))
from aggregator import SalesAggregator, AccountsCalculator, ExcelExporter, SchoolMasterMismatchError, CumulativeAggregator
from services import FileHandler

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TKDND_AVAILABLE = True
except ImportError:
    TKDND_AVAILABLE = False
    TkinterDnD = None

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
    'warning': '#F59E0B',      # オレンジ
    'success': '#10B981',      # 緑
    'border': '#4B5563',       # 枠線
    'sidebar_active': '#374151', # サイドバー選択中
    'log_bg': '#111827',       # ログ背景
    'log_fg': '#D1D5DB'        # ログ文字
}

# デフォルト設定
DEFAULT_CONFIG = {
    'api_host': '127.0.0.1',
    'api_port': 8080,
    'dashboard_host': '0.0.0.0',
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
        
        # kwargsからfontを取り出す（指定がなければデフォルト）
        font = kwargs.pop('font', ('Meiryo', 9, 'bold'))
        
        super().__init__(
            master,
            relief='flat',
            borderwidth=0,
            cursor='hand2' if state != 'disabled' else 'arrow',
            font=font,
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
        
        # btn_type handling
        if 'btn_type' in cnf:
            btn_type = cnf.pop('btn_type')
            if btn_type == 'danger':
                self.default_bg = COLORS['danger']
                self.hover_bg = COLORS['danger_hover']
            elif btn_type == 'secondary':
                self.default_bg = COLORS.get('secondary', '#6B7280') # Fallback if undefined
                self.hover_bg = COLORS.get('secondary_hover', '#4B5563')
            else:
                self.default_bg = COLORS['accent']
                self.hover_bg = COLORS['accent_hover']
            
            cnf['activebackground'] = self.hover_bg
        
        # Call super configure
        super().configure(cnf)
        
        # Update appearance based on state
        current_state = cnf.get('state', self['state'])
        if current_state == 'disabled':
            super().configure(bg='#4B5563', fg='#000000', cursor='arrow')
        else:
            super().configure(bg=self.default_bg, fg='white', cursor='hand2')
    
    # configはconfigureのエイリアス
    config = configure

class ModernDropdown(tk.Frame):
    """モダンなドロップダウンウィジェット"""
    def __init__(self, master, values, default_value="", width=None, **kwargs):
        super().__init__(master, bg=COLORS['bg_main'], **kwargs)
        
        self.values = values
        self.current_value = tk.StringVar(value=default_value)
        
        # ドロップダウンボタン
        button_config = {
            'textvariable': self.current_value,
            'font': ('Meiryo', 10),
            'fg': COLORS['text_primary'],
            'bg': COLORS['bg_main'],
            'relief': 'flat',
            'bd': 0,
            'anchor': 'w',
            'padx': 10,
            'cursor': 'hand2',
            'command': self._toggle_menu
        }
        
        # width指定があれば適用（ピクセル単位）
        if width:
            button_config['width'] = width
        
        self.button = tk.Button(self, **button_config)
        
        # ボタンに枠線を追加（クリック可能とわかりやすく）
        self.button.config(
            highlightthickness=1,
            highlightbackground=COLORS['border'],
            highlightcolor=COLORS['border']
        )
        self.button.pack(fill=tk.BOTH, expand=True, ipady=8)
        
        # ドロップダウンアイコン（Frameの子として配置し、buttonの上に重ねる）
        arrow_label = tk.Label(
            self, text="▼", font=('Meiryo', 8),
            fg=COLORS['text_secondary'], bg=COLORS['bg_main']
        )
        arrow_label.place(relx=1.0, rely=0.5, anchor='e', x=-10)
        
        # 矢印をクリックしてもボタンが反応するように
        arrow_label.bind('<Button-1>', lambda e: self._toggle_menu())
        
        # ホバーエフェクト（矢印の後に追加）
        def on_enter(e):
            self.button.config(highlightbackground=COLORS['accent'], highlightcolor=COLORS['accent'])
        
        def on_leave(e):
            self.button.config(highlightbackground=COLORS['border'], highlightcolor=COLORS['border'])
        
        self.button.bind('<Enter>', on_enter)
        self.button.bind('<Leave>', on_leave)
        arrow_label.bind('<Enter>', on_enter)
        arrow_label.bind('<Leave>', on_leave)
        
        self.menu = None
        self.menu_visible = False
    
    def _toggle_menu(self):
        if self.menu_visible:
            self._hide_menu()
        else:
            self._show_menu()
    
    def _show_menu(self):
        # メニューを作成
        self.menu = tk.Toplevel(self)
        self.menu.wm_overrideredirect(True)
        self.menu.config(bg=COLORS['bg_card'])
        
        # 位置を計算
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        # メニューの高さを計算（各アイテムx30px程度、最大300px）
        menu_height = min(len(self.values) * 35, 300)
        self.menu.geometry(f"{self.winfo_width()}x{menu_height}+{x}+{y}")
        
        # スクロール可能なキャンバス
        canvas = tk.Canvas(self.menu, bg=COLORS['bg_card'], highlightthickness=0)
        scrollbar = tk.Scrollbar(self.menu, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLORS['bg_card'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 選択肢を追加
        for value in self.values:
            # シンプルなButton（横幅いっぱいに広げる）
            item = tk.Button(
                scrollable_frame, text=value, font=('Meiryo', 10),
                fg=COLORS['text_primary'], bg=COLORS['bg_card'],
                relief='flat', bd=0, anchor='w',
                cursor='hand2', padx=10,
                command=lambda v=value: self._select(v)
            )
            # fill='x'ではなくfill='both'で高さも確保
            item.pack(fill='both', ipady=5)
            
            # ホバーエフェクト
            def on_enter(e, btn=item):
                btn.config(bg=COLORS['sidebar_active'])
            def on_leave(e, btn=item):
                btn.config(bg=COLORS['bg_card'])
            
            item.bind('<Enter>', on_enter)
            item.bind('<Leave>', on_leave)
        
        # キャンバスとスクロールバーを配置
        canvas.pack(side="left", fill="both", expand=True)
        if len(self.values) * 35 > 300:  # スクロールが必要な場合のみ表示
            scrollbar.pack(side="right", fill="y")
        
        # マウスホイールでスクロール
        def on_mousewheel(event):
            try:
                # ウィジェットが存在するかチェック
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                # エラーが発生した場合は無視
                pass
        
        # Canvasとscrollable_frameの両方にバインド
        canvas.bind("<MouseWheel>", on_mousewheel)
        scrollable_frame.bind("<MouseWheel>", on_mousewheel)
        
        # マウスがメニュー内にある間だけホイールを有効化
        def bind_wheel(e):
            canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        def unbind_wheel(e):
            canvas.unbind_all("<MouseWheel>")
        
        self.menu.bind('<Enter>', bind_wheel)
        self.menu.bind('<Leave>', unbind_wheel)
        
        self.menu_visible = True
        self.menu.bind('<FocusOut>', lambda e: self._hide_menu())
        self.menu.focus_set()
    
    def _hide_menu(self):
        if self.menu:
            try:
                # マウスホイールイベントをアンバインド（常に実行）
                self.unbind_all("<MouseWheel>")
                self.menu.destroy()
            except tk.TclError:
                # エラーが発生しても続行
                pass
            finally:
                self.menu = None
        self.menu_visible = False
    
    def _select(self, value):
        self.current_value.set(value)
        self._hide_menu()
    
    def get(self):
        return self.current_value.get()



class ModernDialog(tk.Toplevel):
    """モダンなカスタムダイアログ"""
    def __init__(self, parent, title, message, type='info', detail=None):
        super().__init__(parent)
        self.result = False
        
        # ウィンドウ設定
        self.overrideredirect(True)  # タイトルバーを非表示
        self.config(bg=COLORS['bg_card'])
        self.attributes('-topmost', True)
        
        # 枠線（ボーダー）を作成するためのメインフレーム
        self.main_frame = tk.Frame(
            self, bg=COLORS['bg_card'], 
            highlightthickness=1, 
            highlightbackground=COLORS['border'],
            highlightcolor=COLORS['border']
        )
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ドラッグ移動機能用データ
        self._drag_data = {"x": 0, "y": 0}
        
        # タイトルバー作成
        self._create_title_bar(title)
        
        # コンテンツエリア
        self._create_content(message, type, detail)
        
        # ボタンエリア
        self._create_buttons(type)
        
        # 位置調整（親ウィンドウの中央）
        self._center_window(parent)
        
        # モーダル化
        self.transient(parent)
        self.grab_set()
        
        # アニメーション（フェードイン）
        self.attributes('-alpha', 0.0)
        self._fade_in()
        
        # 最前面へ
        self.lift()
        self.focus_force()
        
    def _center_window(self, parent):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        
        # 固定サイズ（幅500px）
        target_width = 500
        target_height = max(height, 220)
        
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (target_width // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (target_height // 2)
        
        self.geometry(f"{target_width}x{target_height}+{x}+{y}")

    def _fade_in(self):
        """フェードインアニメーション"""
        alpha = self.attributes('-alpha')
        if alpha < 1.0:
            alpha += 0.1
            self.attributes('-alpha', alpha)
            self.after(20, self._fade_in)

    def _create_title_bar(self, title):
        title_bar = tk.Frame(self.main_frame, bg=COLORS['bg_main'], height=35)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)
        
        # タイトルテキスト
        tk.Label(
            title_bar, text=title, font=('Meiryo', 10, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_main']
        ).pack(side=tk.LEFT, padx=15)
        
        # 閉じるボタン（×）
        close_btn = tk.Label(
            title_bar, text="✕", font=('Meiryo', 10),
            fg=COLORS['text_secondary'], bg=COLORS['bg_main'],
            cursor='hand2', padx=15
        )
        close_btn.pack(side=tk.RIGHT, fill=tk.Y)
        close_btn.bind('<Button-1>', lambda e: self.destroy())
        close_btn.bind('<Enter>', lambda e: close_btn.config(bg='#ef4444', fg='white'))
        close_btn.bind('<Leave>', lambda e: close_btn.config(bg=COLORS['bg_main'], fg=COLORS['text_secondary']))
        
        # ドラッグイベントバインド
        title_bar.bind('<Button-1>', self._start_move)
        title_bar.bind('<B1-Motion>', self._on_move)
        
    def _start_move(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_move(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        x = self.winfo_x() + dx
        y = self.winfo_y() + dy
        self.geometry(f"+{x}+{y}")

    def _create_content(self, message, type, detail):
        content = tk.Frame(self.main_frame, bg=COLORS['bg_card'])
        content.pack(fill=tk.BOTH, expand=True, padx=25, pady=25)
        
        # アイコン選択
        icon_char = "ℹ"
        icon_color = COLORS['accent']
        if type == 'error':
            icon_char = "✕"
            icon_color = '#ef4444' # Red
        elif type == 'success':
            icon_char = "✓"
            icon_color = '#10b981' # Green
        elif type == 'confirm':
            icon_char = "?"
            icon_color = '#f59e0b' # Orange
        elif type == 'warning':
            icon_char = "⚠"
            icon_color = COLORS['warning']  # Orange/Yellow
            
        icon_frame = tk.Frame(content, bg=COLORS['bg_card'])
        icon_frame.pack(side=tk.LEFT, anchor='n', padx=(0, 20))
        
        tk.Label(
            icon_frame, text=icon_char, font=('Meiryo', 32),
            fg=icon_color, bg=COLORS['bg_card']
        ).pack()
        
        # メッセージエリア
        msg_frame = tk.Frame(content, bg=COLORS['bg_card'])
        msg_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(
            msg_frame, text=message, font=('Meiryo', 11),
            fg=COLORS['text_primary'], bg=COLORS['bg_card'],
            justify='left', wraplength=380
        ).pack(anchor='w', pady=(5, 0))
        
        if detail:
            detail_bg = COLORS['bg_main']
            detail_frame = tk.Frame(msg_frame, bg=detail_bg, padx=10, pady=10)
            detail_frame.pack(fill=tk.X, pady=(10, 0))
            
            # ディレクトリパスの場合はリンクのように見せる
            is_path = ':\\' in detail or '/' in detail
            fg_color = COLORS['accent'] if is_path else COLORS['text_secondary']
            cursor = 'hand2' if is_path else ''
            
            detail_label = tk.Label(
                detail_frame, text=detail, font=('Meiryo', 9) if is_path else ('Meiryo', 9),
                fg=fg_color, bg=detail_bg,
                justify='left', wraplength=360, cursor=cursor
            )
            detail_label.pack(anchor='w')
            
            if is_path:
                detail_label.bind('<Button-1>', lambda e: os.startfile(detail) if os.path.exists(detail) else None)

    def _create_buttons(self, type):
        btn_frame = tk.Frame(self.main_frame, bg=COLORS['bg_card'])
        btn_frame.pack(fill=tk.X, padx=25, pady=(0, 25))
        
        # 右寄せのためのスペーサー
        tk.Frame(btn_frame, bg=COLORS['bg_card']).pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        if type == 'confirm':
             # キャンセル/いいえボタン
            no_btn = ModernButton(
                btn_frame, text="いいえ", btn_type='secondary',
                command=self.destroy, width=15
            )
            no_btn.pack(side=tk.RIGHT, padx=(10, 0))
            
            # OK/はいボタン
            yes_btn = ModernButton(
                btn_frame, text="はい", btn_type='primary',
                command=self._on_yes, width=15
            )
            yes_btn.pack(side=tk.RIGHT)
            
        else: # info, error, success
            ok_btn = ModernButton(
                btn_frame, text="OK", btn_type='primary',
                command=self.destroy, width=15
            )
            ok_btn.pack(side=tk.RIGHT)

    def _on_yes(self):
        self.result = True
        self.destroy()

    @classmethod
    def show_info(cls, parent, title, message, detail=None):
        dialog = cls(parent, title, message, 'info', detail)
        parent.wait_window(dialog)
        return True
        
    @classmethod
    def show_error(cls, parent, title, message, detail=None):
        dialog = cls(parent, title, message, 'error', detail)
        parent.wait_window(dialog)
        return True
        
    @classmethod
    def show_success(cls, parent, title, message, detail=None):
        dialog = cls(parent, title, message, 'success', detail)
        parent.wait_window(dialog)
        return True

    @classmethod
    def show_warning(cls, parent, title, message, detail=None):
        """警告ダイアログを表示"""
        dialog = cls(parent, title, message, 'warning', detail)
        parent.wait_window(dialog)
        return True

    @classmethod
    def ask_yes_no(cls, parent, title, message, detail=None):
        dialog = cls(parent, title, message, 'confirm', detail)
        parent.wait_window(dialog)
        return dialog.result

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
            font=('Meiryo', 13),
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
            self['font'] = ('Meiryo', 13, 'bold')
        else:
            self['bg'] = self.default_bg
            self['fg'] = COLORS['text_secondary']
            self['font'] = ('Meiryo', 13)


class MainApp:
    def __init__(self):
        # tkinterdnd2が利用可能ならDnD対応版を使用
        if TKDND_AVAILABLE:
            self.root = TkinterDnD.Tk()
        else:
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
            font=('Meiryo', 16, 'bold'),
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
            font=('Meiryo', 8),
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
        self.pages['cumulative'] = CumulativeAggregationPage(self.content_area)
        self.pages['results'] = PerformanceReflectionPage(self.content_area, self.server_manager)
        self.pages['database'] = DatabaseInspectionPage(self.content_area, ModernButton, ModernDropdown)

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
        self.dashboard_dir = APP_DIR / 'public_dashboards'
        self.config = self._load_config()
        self.log_callback = None # ログ出力先 (Page側でセット)

    def _load_config(self):
        config = DEFAULT_CONFIG.copy()
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        config.update(loaded)
            except Exception:
                pass
        config['api_host'] = self._normalize_host(
            config.get('api_host'),
            DEFAULT_CONFIG['api_host']
        )
        config['dashboard_host'] = self._normalize_host(
            config.get('dashboard_host'),
            DEFAULT_CONFIG['dashboard_host']
        )
        return config

    def _normalize_host(self, value, fallback):
        host = str(value).strip() if value is not None else ''
        return host if host else fallback

    def _resolve_access_host(self, bind_host):
        host = self._normalize_host(bind_host, DEFAULT_CONFIG['dashboard_host'])
        if host in ('0.0.0.0', '::', ''):
            return self.get_local_ip()
        if host == 'localhost':
            return '127.0.0.1'
        return host

    def get_dashboard_access_url(self):
        bind_host = self.config.get('dashboard_host', DEFAULT_CONFIG['dashboard_host'])
        access_host = self._resolve_access_host(bind_host)
        port = self.config.get('dashboard_port', DEFAULT_CONFIG['dashboard_port'])
        return f'http://{access_host}:{port}'

    def get_dashboard_local_url(self):
        port = self.config.get('dashboard_port', DEFAULT_CONFIG['dashboard_port'])
        return f'http://127.0.0.1:{port}'

    def _resolve_probe_host(self, bind_host):
        host = self._normalize_host(bind_host, DEFAULT_CONFIG['dashboard_host'])
        if host in ('', '0.0.0.0', '::', 'localhost'):
            return '127.0.0.1'
        return host

    def _wait_for_server_ready(self, process, bind_host, port, timeout_sec=6.0):
        probe_host = self._resolve_probe_host(bind_host)
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if process.poll() is not None:
                return False
            try:
                with socket.create_connection((probe_host, int(port)), timeout=0.5):
                    return True
            except OSError:
                time.sleep(0.1)
        return False

    def save_config(self, api_port=None, dashboard_port=None, api_host=None, dashboard_host=None):
        if api_port is not None:
            self.config['api_port'] = int(api_port)
        if dashboard_port is not None:
            self.config['dashboard_port'] = int(dashboard_port)
        if api_host is not None:
            self.config['api_host'] = self._normalize_host(api_host, DEFAULT_CONFIG['api_host'])
        if dashboard_host is not None:
            self.config['dashboard_host'] = self._normalize_host(
                dashboard_host,
                DEFAULT_CONFIG['dashboard_host']
            )
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

    def _is_process_running(self, process):
        return (process is not None) and (process.poll() is None)

    def is_any_running(self):
        return self._is_process_running(self.api_process) or self._is_process_running(self.dashboard_process)

    def start_api(self, port, on_start, on_stop, host=None):
        if self._is_process_running(self.api_process):
            self.log('APIサーバーは既に起動中です')
            return
        self.api_process = None
        
        def run():
            try:
                bind_host = self._normalize_host(
                    host if host is not None else self.config.get('api_host'),
                    DEFAULT_CONFIG['api_host']
                )
                script_path = APP_DIR / 'run.py'
                process = subprocess.Popen(
                    [sys.executable, str(script_path), '--host', bind_host, '--port', str(port)],
                    cwd=str(APP_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                self.api_process = process
                if not self._wait_for_server_ready(process, bind_host, port):
                    self.log(f'API起動失敗: {bind_host}:{port} で待ち受けできませんでした')
                    if process.poll() is None:
                        process.terminate()
                    self.api_process = None
                    self.app.root.after(0, on_stop)
                    return
                self.app.root.after(0, on_start)
                access_host = self._resolve_access_host(bind_host)
                self.log(f'管理APIサーバー起動完了: http://{access_host}:{port}')
                
                for line in process.stdout:
                    self.app.root.after(0, lambda l=line: self.log(f'[API] {l.strip()}'))
                exit_code = process.poll()
                if self.api_process is process:
                    self.api_process = None
                self.app.root.after(0, lambda c=exit_code: self.log(f'APIサーバープロセス終了 (code={c})'))
                self.app.root.after(0, on_stop)
            except Exception as e:
                self.app.root.after(0, lambda: self.log(f'API起動エラー: {e}'))
                self.app.root.after(0, on_stop)

        threading.Thread(target=run, daemon=True).start()

    def stop_api(self):
        if self.api_process:
            if self.api_process.poll() is None:
                self.api_process.terminate()
            self.api_process = None
            self.log('APIサーバー停止')

    def start_dashboard(self, port, on_start, on_stop, host=None):
        if self._is_process_running(self.dashboard_process):
            self.log('Dashboardサーバーは既に起動中です')
            return
        self.dashboard_process = None
        
        def run():
            try:
                bind_host = self._normalize_host(
                    host if host is not None else self.config.get('dashboard_host'),
                    DEFAULT_CONFIG['dashboard_host']
                )
                script_path = APP_DIR / 'simple_server.py'
                process = subprocess.Popen(
                    [sys.executable, str(script_path), '--host', bind_host, '--port', str(port)],
                    cwd=str(APP_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                self.dashboard_process = process
                if not self._wait_for_server_ready(process, bind_host, port):
                    self.log(f'Dashboard起動失敗: {bind_host}:{port} で待ち受けできませんでした')
                    if process.poll() is None:
                        process.terminate()
                    self.dashboard_process = None
                    self.app.root.after(0, on_stop)
                    return
                self.app.root.after(0, on_start)
                access_host = self._resolve_access_host(bind_host)
                self.log(f'公開ダッシュボード起動完了: http://{access_host}:{port}')
                if access_host != '127.0.0.1':
                    self.log(f'ローカルアクセスURL: http://127.0.0.1:{port}')
                
                for line in process.stdout:
                    self.app.root.after(0, lambda l=line: self.log(f'[Web] {l.strip()}'))
                exit_code = process.poll()
                if self.dashboard_process is process:
                    self.dashboard_process = None
                self.app.root.after(0, lambda c=exit_code: self.log(f'Dashboardサーバープロセス終了 (code={c})'))
                self.app.root.after(0, on_stop)
            except Exception as e:
                self.app.root.after(0, lambda: self.log(f'Dashboard起動エラー: {e}'))
                self.app.root.after(0, on_stop)

        threading.Thread(target=run, daemon=True).start()

    def stop_dashboard(self):
        if self.dashboard_process:
            if self.dashboard_process.poll() is None:
                self.dashboard_process.terminate()
            self.dashboard_process = None
            self.log('Dashboardサーバー停止')

    def stop_all(self):
        self.stop_api()
        self.stop_dashboard()

    def is_dashboard_running(self):
        return self._is_process_running(self.dashboard_process)

    def get_local_ip(self):
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # 実際に接続はしないが、ルーティング情報を参照して自己IPを取得
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
            except Exception:
                ip = '127.0.0.1'
            finally:
                s.close()
            return ip
        except Exception:
            return '127.0.0.1'


class ServerControlPage(tk.Frame):
    """サーバー管理ページ (旧ランチャー機能)"""
    def __init__(self, parent, manager):
        super().__init__(parent, bg=COLORS['bg_main'])
        self.manager = manager
        
        # ログコールバックの登録
        self.manager.log_callback = self._log_to_widget

        # ヘッダー
        tk.Label(self, text="サーバー管理", font=('Meiryo', 18, 'bold'), 
                 fg=COLORS['text_primary'], bg=COLORS['bg_main']).pack(anchor='w', padx=30, pady=(30, 20))

        # コンテンツエリア
        container = tk.Frame(self, bg=COLORS['bg_main'])
        container.pack(fill=tk.BOTH, expand=True, padx=30)
        
        # コントロールパネルの作成
        self._create_dashboard_panel(container)

        # ログエリア
        log_frame = tk.Frame(container, bg=COLORS['bg_main'])
        log_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        label_row = tk.Frame(log_frame, bg=COLORS['bg_main'])
        label_row.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(label_row, text="システムログ", font=('Meiryo', 10, 'bold'),
                 fg=COLORS['text_secondary'], bg=COLORS['bg_main']).pack(side=tk.LEFT)
                 
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=12, font=('Consolas', 9),
            bg=COLORS['log_bg'], fg=COLORS['log_fg'],
            bd=1, relief='flat', highlightthickness=1,
            highlightbackground=COLORS['border']
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _create_dashboard_panel(self, parent):
        """ダッシュボード管理パネル（新デザイン）"""
        self.dashboard_card = tk.Frame(parent, bg=COLORS['bg_card'], padx=25, pady=25,
                                     highlightthickness=2, highlightbackground=COLORS['border'])
        self.dashboard_card.pack(fill=tk.X)
        
        # --- ヘッダー行 (タイトル + ステータス) ---
        header_row = tk.Frame(self.dashboard_card, bg=COLORS['bg_card'])
        header_row.pack(fill=tk.X, pady=(0, 20))
        
        # 左側: アイコンとタイトル
        title_box = tk.Frame(header_row, bg=COLORS['bg_card'])
        title_box.pack(side=tk.LEFT)
        
        tk.Label(title_box, text="🌐", font=('Meiryo', 20), 
                 fg=COLORS['accent'], bg=COLORS['bg_card']).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(title_box, text="公開ダッシュボード", font=('Meiryo', 16, 'bold'),
                 fg=COLORS['text_primary'], bg=COLORS['bg_card']).pack(side=tk.LEFT)
        
        # 右側: ステータスバッジ
        self.status_badge = tk.Label(header_row, text="● 停止中", font=('Meiryo', 12, 'bold'),
                                     fg=COLORS['warning'], bg=COLORS['bg_main'],
                                     padx=15, pady=5)
        self.status_badge.pack(side=tk.RIGHT)
        
        # --- 仕切り線 ---
        tk.Frame(self.dashboard_card, bg=COLORS['border'], height=1).pack(fill=tk.X, pady=(0, 20))
        
        # --- コントロール行 ---
        control_row = tk.Frame(self.dashboard_card, bg=COLORS['bg_card'])
        control_row.pack(fill=tk.X)
        
        # ホスト設定
        host_frame = tk.Frame(control_row, bg=COLORS['bg_card'])
        host_frame.pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(host_frame, text="バインドホスト", font=('Meiryo', 9),
                 fg=COLORS['text_secondary'], bg=COLORS['bg_card']).pack(anchor='w', pady=(0, 2))

        self.host_var = tk.StringVar(
            value=self.manager.config.get('dashboard_host', DEFAULT_CONFIG['dashboard_host'])
        )
        self.host_entry = tk.Entry(
            host_frame, textvariable=self.host_var, width=16,
            font=('Consolas', 11), bg=COLORS['bg_main'], fg='white',
            relief='flat', insertbackground='white', justify='left'
        )
        self.host_entry.pack(ipady=3)

        # ポート設定
        port_frame = tk.Frame(control_row, bg=COLORS['bg_card'])
        port_frame.pack(side=tk.LEFT)
        
        tk.Label(port_frame, text="ポート番号", font=('Meiryo', 9),
                 fg=COLORS['text_secondary'], bg=COLORS['bg_card']).pack(anchor='w', pady=(0, 2))
                 
        self.port_var = tk.StringVar(value=str(self.manager.config['dashboard_port']))
        
        # 数字のみ入力可能にする検証関数
        vcmd = (self.register(self._validate_port), '%P')
        
        self.port_entry = tk.Entry(
            port_frame, textvariable=self.port_var, width=10, 
            font=('Consolas', 11), bg=COLORS['bg_main'], fg='white',
            relief='flat', insertbackground='white', justify='center',
            validate='key', validatecommand=vcmd
        )
        self.port_entry.pack(ipady=3)
        
        # URL表示（起動時のみ有効化）
        self.url_frame = tk.Frame(control_row, bg=COLORS['bg_card'])
        self.url_frame.pack(side=tk.LEFT, padx=(30, 0), fill=tk.Y)
        
        tk.Label(self.url_frame, text="アクセスURL", font=('Meiryo', 9),
                 fg=COLORS['text_secondary'], bg=COLORS['bg_card']).pack(anchor='w', pady=(0, 2))
                 
        self.url_link = tk.Label(
            self.url_frame, text="running...", font=('Consolas', 11, 'underline'),
            fg=COLORS['accent'], bg=COLORS['bg_card'], cursor='hand2'
        )
        self.url_link.pack(anchor='w')
        self.url_link.bind('<Button-1>', lambda e: webbrowser.open(self.url_link.cget("text")))
        
        # アクションボタン（右寄せ）
        btn_box = tk.Frame(control_row, bg=COLORS['bg_card'])
        btn_box.pack(side=tk.RIGHT, anchor='s')
        
        self.start_btn = ModernButton(
            btn_box, text="サーバー起動", btn_type="primary", width=14,
            command=self._on_start_click
        )
        self.start_btn.pack(side=tk.LEFT)
        
        self.stop_btn = ModernButton(
            btn_box, text="停止", btn_type="danger", width=10,
            command=self._on_stop_click, state="disabled"
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # 初期表示更新
        self._update_ui(self.manager.is_dashboard_running())

    def _validate_port(self, value):
        """ポート番号の検証（数字のみ、空文字もOK）"""
        if value == "":
            return True
        try:
            int(value)
            return True
        except ValueError:
            return False

    def _on_start_click(self):
        try:
            host = self.host_var.get().strip()
            port = int(self.port_var.get())
            if not host:
                raise ValueError("host")
            self.manager.save_config(dashboard_port=port, dashboard_host=host)
            self.manager.start_dashboard(
                port, 
                lambda: self._update_ui(True), 
                lambda: self._update_ui(False),
                host=host
            )
        except ValueError:
            ModernDialog.show_error(self, "エラー", "ホストとポート番号を正しく入力してください")

    def _on_stop_click(self):
        self.manager.stop_dashboard()
        self._update_ui(False)

    def _update_ui(self, running):
        if running:
            # 起動中スタイル
            self.status_badge.config(text="● 起動中", fg=COLORS['success'], bg='#064E3B') # Dark Green BG
            self.dashboard_card.config(highlightbackground=COLORS['success'])
            
            url = self.manager.get_dashboard_access_url()
            self.url_link.config(text=url, state='normal')
            self.url_frame.pack(side=tk.LEFT, padx=(30, 0), fill=tk.Y) # 表示
            
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.host_entry.config(state="disabled")
            self.port_entry.config(state="disabled")  # ポート入力を無効化
        else:
            # 停止中スタイル
            self.status_badge.config(text="● 停止中", fg=COLORS['warning'], bg=COLORS['bg_main'])
            self.dashboard_card.config(highlightbackground=COLORS['warning'])
            
            self.url_frame.pack_forget() # URL非表示
            
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.host_entry.config(state="normal")
            self.port_entry.config(state="normal")  # ポート入力を有効化


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
        
        tk.Label(self, text=title, font=('Meiryo', 24, 'bold'), 
                 fg=COLORS['text_primary'], bg=COLORS['bg_main']).pack(anchor='center', pady=(150, 20))
        
        tk.Label(self, text=description, font=('Meiryo', 12),
                 fg=COLORS['text_secondary'], bg=COLORS['bg_main']).pack(anchor='center')
        
        tk.Label(self, text="この機能は現在開発中です", font=('Meiryo', 10),
                 fg=COLORS['accent'], bg=COLORS['bg_main']).pack(anchor='center', pady=30)


class CumulativeAggregationPage(tk.Frame):
    """累積集計ページ"""
    def __init__(self, parent):
        super().__init__(parent, bg=COLORS['bg_main'])
        
        # 状態管理
        self.cumulative_files = []  # ファイル情報リスト
        self.existing_file_path = None  # 既存ファイルパス（オプション）
        self.is_processing = False
        
        # UI構築
        self._create_header()
        self._create_main_layout()
    
    def _create_header(self):
        """ヘッダー作成"""
        header = tk.Frame(self, bg=COLORS['bg_main'])
        header.pack(fill=tk.X, padx=30, pady=(30, 20))
        
        tk.Label(
            header, text="累積集計", font=('Meiryo', 18, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_main']
        ).pack(anchor='w')
        
        tk.Label(
            header, text="複数の月次集計ファイルを元に、年度の累積報告書を作成します",
            font=('Meiryo', 10), fg=COLORS['text_secondary'], bg=COLORS['bg_main']
        ).pack(anchor='w', pady=(5, 0))
    
    def _create_main_layout(self):
        """メインレイアウト作成"""
        # スクロール可能なコンテナ
        container = tk.Frame(self, bg=COLORS['bg_main'])
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 30))
        
        # Custom Scrollbar Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Dark.Vertical.TScrollbar",
            background=COLORS['bg_card'],
            troughcolor=COLORS['bg_main'],
            bordercolor=COLORS['bg_main'],
            arrowcolor=COLORS['text_secondary'],
            relief='flat')
            
        # Canvasを作成（スクロールバーなし）
        canvas = tk.Canvas(container, bg=COLORS['bg_main'], highlightthickness=0)
        
        # スクロール可能なフレーム
        self.content_area = tk.Frame(canvas, bg=COLORS['bg_main'])
        
        # Canvasのサイズ変更時にウィンドウ幅を更新
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        
        self.content_area.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_window = canvas.create_window((0, 0), window=self.content_area, anchor="nw")
        canvas.bind('<Configure>', on_canvas_configure)
        
        canvas.pack(side="left", fill="both", expand=True)
        
        # マウスホイールイベントはファイルリストなどの個別要素に任せるため、全体スクロールは無効化
        self.canvas = canvas
        # def on_mousewheel(event):
        #     canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        # self.bind('<Enter>', lambda e: canvas.bind_all("<MouseWheel>", on_mousewheel))
        # self.bind('<Leave>', lambda e: canvas.unbind_all("<MouseWheel>"))
        
        # STEP 1: ファイル追加
        self._create_file_drop_section()
        
        # STEP 2: ファイルリストはSTEP 1の下に動的に追加される
        self.file_list_frame = None
        
        # STEP 3: 既存ファイル選択 + 実行ボタン
        self.control_section_frame = None
        self._create_control_section()
    
    def _create_control_section(self):
        """STEP 3: 既存ファイル選択と実行ボタン"""
        self.control_section_frame = tk.Frame(self.content_area, bg=COLORS['bg_card'], padx=20, pady=20)
        self.control_section_frame.pack(fill=tk.X, pady=(0, 20))
        
        # ヘッダー
        header_frame = tk.Frame(self.control_section_frame, bg=COLORS['bg_card'])
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        step_badge = tk.Label(
            header_frame, text="STEP 2", font=('Meiryo', 9, 'bold'),
            fg=COLORS['accent'], bg='#1E3A5F', padx=8, pady=2
        )
        step_badge.pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(
            header_frame, text="既存ファイル（オプション）", font=('Meiryo', 12, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT)
        
        # 説明テキスト
        tk.Label(
            self.control_section_frame, text="既存のファイルに追記・上書きする場合に選択",
            font=('Meiryo', 9), fg=COLORS['text_secondary'], bg=COLORS['bg_card']
        ).pack(anchor='w', pady=(0, 10))
        
        # ファイル選択ボタン
        btn_frame = tk.Frame(self.control_section_frame, bg=COLORS['bg_card'])
        btn_frame.pack(fill=tk.X, pady=(0, 20))
        
        select_existing_btn = ModernButton(
            btn_frame, text="📂 ファイルを選択", btn_type='secondary',
            command=self._select_existing_file,
            font=('Meiryo', 10),
            width=25  # 固定幅に変更
        )
        select_existing_btn.pack(side=tk.LEFT)
        
        # 選択されたファイル表示
        self.existing_file_label = tk.Label(
            self.control_section_frame, text="",
            font=('Meiryo', 9), fg=COLORS['text_secondary'], bg=COLORS['bg_card'],
            wraplength=500, justify='left'
        )
        self.existing_file_label.pack(anchor='w', pady=(5, 20))
        
        # 実行ボタン
        self.execute_btn = ModernButton(
            self.control_section_frame, text="累積集計を実行", btn_type='primary',
            font=('Meiryo', 12),
            command=self._execute_cumulative,
            state='disabled',
            width=30  # 固定幅に変更
        )
        # self.execute_btn.pack(anchor='w')
    
    def _select_existing_file(self):
        """既存ファイル選択ダイアログ"""
        from tkinter import filedialog
        
        filename = filedialog.askopenfilename(
            title="既存の累積ファイルを選択",
            filetypes=[("Excelファイル", "*.xlsx"), ("すべてのファイル", "*.*")]
        )
        
        if filename:
            self.existing_file_path = filename
            display_name = Path(filename).name
            self.existing_file_label.config(
                text=f"選択済み: {display_name}",
                fg=COLORS['accent']
            )
        
    def _check_can_execute(self):
        """実行ボタンの有効化チェック"""
        # 全てのファイルに年月が設定されているか確認
        can_execute = (
            len(self.cumulative_files) > 0 and
            all(f['year'] is not None and f['month'] is not None for f in self.cumulative_files) and
            not self.is_processing
        )
        
        if can_execute:
            self.execute_btn.config(state='normal')
            self.execute_btn.pack(anchor='w')
        else:
            self.execute_btn.config(state='disabled')
            self.execute_btn.pack_forget()
    
    def _execute_cumulative(self):
        """累積集計実行"""
        if self.is_processing:
            return
        
        # 進捗モーダル表示
        self._show_progress_modal()
        
        # 別スレッドで実行
        self.is_processing = True
        self.execute_btn.config(state='disabled')
        
        thread = threading.Thread(target=self._run_cumulative_process, daemon=True)
        thread.start()
    
    def _run_cumulative_process(self):
        """累積集計処理（別スレッド）"""
        try:
            # ファイルを年月順にソート
            sorted_files = sorted(self.cumulative_files, key=lambda x: (x['year'], x['month']))
            
            # 出力先とパラメータの準備
            output_dir = Path.home() / 'Downloads'
            existing_path = Path(self.existing_file_path) if self.existing_file_path else None
            
            # 年度計算（最初のファイルから）
            first_file = sorted_files[0]
            fiscal_year = first_file['year'] if first_file['month'] >= 4 else first_file['year'] - 1
            
            total = len(sorted_files)
            output_path = None
            processed_months = []
            
            # 各ファイルを順番に処理
            for i, file_info in enumerate(sorted_files):
                # 進捗更新
                progress_msg = f"{file_info['year']}年{file_info['month']}月 処理中... ({i+1}/{total})"
                self.after(0, lambda msg=progress_msg: self._update_progress_label(msg))
                
                # 2件目以降は、前回の出力を既存ファイルとして使用
                if i > 0 and output_path:
                    existing_path = Path(output_path)
                
                # CumulativeAggregator実行
                aggregator = CumulativeAggregator(
                    input_path=Path(file_info['file_path']),
                    output_dir=output_dir,
                    year=file_info['year'],
                    month=file_info['month'],
                    fiscal_year=fiscal_year,
                    existing_file_path=existing_path
                )
                result = aggregator.process()
                
                output_path = result['outputPath']
                processed_months.append(f"{file_info['year']}年{file_info['month']}月")
            
            # 完了
            final_result = {
                'fiscalYear': fiscal_year,
                'processedCount': total,
                'processedMonths': '、'.join(processed_months),
                'outputPath': output_path
            }
            
            self.after(0, lambda: self._hide_progress_modal())
            self.after(0, lambda r=final_result: self._show_cumulative_result(r))
            
        except Exception as e:
            self.after(0, lambda: self._hide_progress_modal())
            self.after(0, lambda: ModernDialog.show_error(
                self, 'エラー', f'累積集計中にエラーが発生しました', detail=str(e)
            ))
        finally:
            self.is_processing = False
            self.after(0, lambda: self.execute_btn.config(state='normal'))
    
    def _show_progress_modal(self):
        """集計中モーダルを表示"""
        self.progress_window = tk.Toplevel(self)
        self.progress_window.title("累積集計")
        self.progress_window.geometry("550x250")
        self.progress_window.overrideredirect(True)
        self.progress_window.config(bg=COLORS['bg_card'])
        self.progress_window.attributes('-topmost', True)
        
        # 枠線
        container = tk.Frame(
            self.progress_window, bg=COLORS['bg_card'],
            highlightthickness=1, highlightbackground=COLORS['border'], highlightcolor=COLORS['border']
        )
        container.pack(fill=tk.BOTH, expand=True)
        
        # 中央に配置
        self.progress_window.update_idletasks()
        x = (self.progress_window.winfo_screenwidth() // 2) - 275
        y = (self.progress_window.winfo_screenheight() // 2) - 125
        self.progress_window.geometry(f"+{x}+{y}")
        
        # コンテンツ
        frame = tk.Frame(container, bg=COLORS['bg_card'], padx=30, pady=30)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # スピナー的なアイコン
        tk.Label(
            frame, text="⏳", font=('Meiryo', 32),
            fg=COLORS['accent'], bg=COLORS['bg_card']
        ).pack(pady=(0, 15))
        
        tk.Label(
            frame, text="累積集計中...", font=('Meiryo', 14, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        ).pack(pady=(0, 10))
        
        self.progress_label = tk.Label(
            frame, text="準備中...", font=('Meiryo', 10),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card'], justify='center',
            wraplength=480
        )
        self.progress_label.pack()
        
        self.progress_window.transient(self.winfo_toplevel())
        self.progress_window.grab_set()
        
        # 最前面へ
        self.progress_window.lift()
        self.progress_window.focus_force()
    
    def _update_progress_label(self, message):
        """進捗ラベル更新"""
        if hasattr(self, 'progress_label') and self.progress_label.winfo_exists():
            self.progress_label.config(text=message)
    
    def _hide_progress_modal(self):
        """モーダルを閉じる"""
        if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
            self.progress_window.destroy()
    
    def _show_cumulative_result(self, result):
        """累積集計完了ダイアログ"""
        message = f"累積集計が完了しました！\n対象年度: {result['fiscalYear']}年度\n処理ファイル数: {result['processedCount']}件"
        detail = f"追記月: {result['processedMonths']}\n保存先:\n{result['outputPath']}"
        
        ModernDialog.show_success(
            self,
            '累積集計完了',
            message,
            detail=detail
        )
        
        self._reset_form()
    
    def _reset_form(self):
        """フォームをリセット"""
        self.cumulative_files = []
        self.existing_file_path = None
        self.existing_file_label.config(text="")
        self.execute_btn.config(state='disabled')
        
        # 年度ラベルをリセット
        if hasattr(self, 'fiscal_year_label'):
            delattr(self, 'fiscal_year_label')
        
        # ファイルリストを更新（空にする）
        self._update_file_list()
    
    def _create_file_drop_section(self):
        """STEP 1: ファイル選択と一覧（横並びレイアウト）"""
        card = tk.Frame(self.content_area, bg=COLORS['bg_card'], padx=20, pady=20)
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # ヘッダー
        header_frame = tk.Frame(card, bg=COLORS['bg_card'])
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        step_badge = tk.Label(
            header_frame, text="STEP 1", font=('Meiryo', 9, 'bold'),
            fg=COLORS['accent'], bg='#1E3A5F', padx=8, pady=2
        )
        step_badge.pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(
            header_frame, text="ファイル選択と対象年月設定", font=('Meiryo', 12, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT)
        
        # コンテンツエリア（横2列）
        content_container = tk.Frame(card, bg=COLORS['bg_card'])
        content_container.pack(fill=tk.BOTH, expand=True)
        
        # 左側: ドロップゾーン（幅を固定または比率を設定）
        self.drop_zone_frame = tk.Frame(content_container, bg=COLORS['bg_card'], width=450, height=400)
        self.drop_zone_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))
        self.drop_zone_frame.pack_propagate(False) # サイズ固定
        
        # ドロップゾーン
        drop_zone = tk.Frame(self.drop_zone_frame, bg=COLORS['bg_main'], height=200, highlightthickness=2,
                           highlightbackground=COLORS['border'], highlightcolor=COLORS['border'])
        drop_zone.pack(side=tk.TOP, fill=tk.X, expand=False)
        drop_zone.pack_propagate(False)
        
        content_frame = tk.Frame(drop_zone, bg=COLORS['bg_main'], cursor='hand2')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
        
        # アイコン
        tk.Label(
            content_frame, text="📁", font=('Meiryo', 24),
            fg=COLORS['text_secondary'], bg=COLORS['bg_main']
        ).pack(pady=(0, 8))
        
        # テキスト
        tk.Label(
            content_frame, text="ファイルをドラッグ&ドロップ（複数可）",
            font=('Meiryo', 11), fg=COLORS['text_primary'], bg=COLORS['bg_main']
        ).pack()
        
        tk.Label(
            content_frame, text="または クリックしてファイルを選択",
            font=('Meiryo', 9), fg=COLORS['text_secondary'], bg=COLORS['bg_main']
        ).pack(pady=(5, 0))
        
        # イベントバインディング（クリックとドラッグ＆ドロップ）
        def on_click(event):
            self._select_files()
        
        drop_zone.bind('<Button-1>', on_click)
        content_frame.bind('<Button-1>', on_click)
        
        # ホバーエフェクト
        def on_enter(event):
            drop_zone.config(highlightbackground=COLORS['accent'], highlightcolor=COLORS['accent'])
            content_frame.config(bg='#2a3142')
        
        def on_leave(event):
            drop_zone.config(highlightbackground=COLORS['border'], highlightcolor=COLORS['border'])
            content_frame.config(bg=COLORS['bg_main'])
        
        drop_zone.bind('<Enter>', on_enter)
        drop_zone.bind('<Leave>', on_leave)
        content_frame.bind('<Enter>', on_enter)
        content_frame.bind('<Leave>', on_leave)
        
        # ドラッグ&ドロップ（TkinterDnD利用可能なら）
        if TKDND_AVAILABLE:
            def on_drop(event):
                files = self.winfo_toplevel().tk.splitlist(event.data)
                xlsx_files = [f for f in files if f.lower().endswith('.xlsx')]
                if xlsx_files:
                    self._add_files(xlsx_files)
            
            drop_zone.drop_target_register(DND_FILES)
            drop_zone.dnd_bind('<<Drop>>', on_drop)
            content_frame.drop_target_register(DND_FILES)
            content_frame.dnd_bind('<<Drop>>', on_drop)
        
        # 右側: ファイルリストエリア（初期状態では非表示）
        self.file_list_container = tk.Frame(content_container, bg=COLORS['bg_card'])
        # ファイルが追加されたときに pack(side=tk.LEFT) で表示される
    
    def _select_files(self):
        """ファイル選択ダイアログ（複数選択）"""
        from tkinter import filedialog
        
        filenames = filedialog.askopenfilenames(
            title="月次集計ファイルを選択（複数可）",
            filetypes=[("Excelファイル", "*.xlsx"), ("すべてのファイル", "*.*")]
        )
        
        if filenames:
            self._add_files(list(filenames))
    
    def _add_files(self, file_paths):
        """ファイルをリストに追加"""
        for file_path in file_paths:
            # 重複チェック
            if not any(f['file_path'] == file_path for f in self.cumulative_files):
                self.cumulative_files.append({
                    'file_path': file_path,
                    'year': None,
                    'month': None,
                    'display_name': Path(file_path).name
                })
        
        self._update_file_list()
        self._check_can_execute()  # 実行ボタンの有効化チェック
    
    def _update_file_list(self):
        """ファイルリスト表示を更新"""
        # 既存のリストフレームを削除
        if self.file_list_frame:
            self.file_list_frame.destroy()
        
        if not self.cumulative_files:
            self._check_can_execute()  # ファイルがない場合もチェック
            # ファイルリストコンテナを非表示
            if hasattr(self, 'file_list_container'):
                self.file_list_container.pack_forget()
            return
        
        # ファイルリストコンテナを表示
        if hasattr(self, 'file_list_container'):
            self.file_list_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # ファイルリストフレームをコンテナ内に作成
        self.file_list_frame = tk.Frame(self.file_list_container, bg=COLORS['bg_card'])
        self.file_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # テーブルヘッダー（固定幅Frame戦略で完全整列）
        table_header = tk.Frame(self.file_list_frame, bg=COLORS['bg_main'], padx=10, pady=8)
        table_header.pack(fill=tk.X)
        
        # 右側のカラムから順に配置 (pack side=RIGHT) - Frameで幅固定
        
        # 操作カラム（80px固定）スクロールバー削除に伴い余白調整
        action_col = tk.Frame(table_header, bg=COLORS['bg_main'], width=80, height=30)
        action_col.pack(side=tk.RIGHT, padx=(5, 0)) # 右余白を0に戻す
        action_col.pack_propagate(False)
        
        tk.Label(
            action_col, text="操作", font=('Meiryo', 9, 'bold'),
            fg=COLORS['text_secondary'], bg=COLORS['bg_main'], anchor='center'
        ).pack(expand=True, fill=tk.BOTH)
        
        # 対象月カラム（100px固定）
        month_col = tk.Frame(table_header, bg=COLORS['bg_main'], width=100, height=30)
        month_col.pack(side=tk.RIGHT, padx=(5, 5))
        month_col.pack_propagate(False)
        
        tk.Label(
            month_col, text="対象月", font=('Meiryo', 9, 'bold'),
            fg=COLORS['text_secondary'], bg=COLORS['bg_main'], anchor='center'
        ).pack(expand=True, fill=tk.BOTH)
        
        # 対象年カラム（120px固定）
        year_col = tk.Frame(table_header, bg=COLORS['bg_main'], width=120, height=30)
        year_col.pack(side=tk.RIGHT, padx=(10, 5))
        year_col.pack_propagate(False)
        
        tk.Label(
            year_col, text="対象年", font=('Meiryo', 9, 'bold'),
            fg=COLORS['text_secondary'], bg=COLORS['bg_main'], anchor='center'
        ).pack(expand=True, fill=tk.BOTH)
        
        # ファイル名カラム（残りのスペースを埋める）
        tk.Label(
            table_header, text="ファイル名", font=('Meiryo', 9, 'bold'),
            fg=COLORS['text_secondary'], bg=COLORS['bg_main'], anchor='w'
        ).pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        
        # ファイル一覧（スクロール可能）
        list_container = tk.Frame(self.file_list_frame, bg=COLORS['bg_card'])
        list_container.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(list_container, bg=COLORS['bg_card'], highlightthickness=0, height=200)
        scrollable_frame = tk.Frame(canvas, bg=COLORS['bg_card'])
        
        # Canvasのサイズ変更時に内部フレームの幅を更新して同期させる
        def on_list_canvas_configure(event):
            canvas.itemconfig(list_window, width=event.width)
            
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        list_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.bind('<Configure>', on_list_canvas_configure)
        
        canvas.pack(side="left", fill="both", expand=True)
        
        # ファイルリストのマウスホイールスクロール
        def on_list_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
        # Canvas上にマウスがある時だけスクロール有効化
        canvas.bind('<Enter>', lambda e: canvas.bind_all("<MouseWheel>", on_list_mousewheel))
        canvas.bind('<Leave>', lambda e: canvas.unbind_all("<MouseWheel>"))
        
        # 各ファイル行を作成
        for i, file_info in enumerate(self.cumulative_files):
            self._create_file_row(scrollable_frame, i, file_info)
        
        # STEP 2（既存ファイル選択）を再配置（ファイルリストの後に表示されるように）
        if self.control_section_frame:
            self.control_section_frame.pack_forget()
            self.control_section_frame.pack(fill=tk.X, pady=(0, 20))
    
    def _create_file_row(self, parent, index, file_info):
        """ファイルリストの1行を作成"""
        row = tk.Frame(parent, bg=COLORS['bg_main'], padx=10, pady=8)
        row.pack(fill=tk.X, pady=2)
        
        # 右側の要素から順に配置 (pack side=RIGHT) - Frameで幅固定
        
        # 削除ボタン（80px固定）
        action_col = tk.Frame(row, bg=COLORS['bg_main'], width=80, height=40)
        action_col.pack(side=tk.RIGHT, padx=(5, 0))
        action_col.pack_propagate(False)
        
        delete_btn = ModernButton(
            action_col, text="削除", btn_type='danger',
            command=lambda i=index: self._remove_file(i),
            font=('Meiryo', 9), width=6
        )
        delete_btn.pack(expand=True)
        
        # 月選択ドロップダウン（100px固定）
        month_col = tk.Frame(row, bg=COLORS['bg_main'], width=100, height=40)
        month_col.pack(side=tk.RIGHT, padx=(5, 5))
        month_col.pack_propagate(False)
        
        month_options = [f"{month}月" for month in range(1, 13)]
        month_default = f"{file_info['month']}月" if file_info['month'] else ""
        month_dropdown = ModernDropdown(month_col, month_options, month_default, width=8)
        month_dropdown.pack(expand=True)
        
        # 年選択ドロップダウン（120px固定）
        year_col = tk.Frame(row, bg=COLORS['bg_main'], width=120, height=40)
        year_col.pack(side=tk.RIGHT, padx=(10, 5))
        year_col.pack_propagate(False)
        
        current_year = datetime.now().year
        year_options = [f"{year}年" for year in range(current_year - 5, current_year + 2)]
        year_default = f"{file_info['year']}年" if file_info['year'] else ""
        year_dropdown = ModernDropdown(year_col, year_options, year_default, width=10)
        year_dropdown.pack(expand=True)
        
        # ファイル名（残りのスペースを埋める）
        tk.Label(
            row, text=file_info['display_name'], font=('Meiryo', 9),
            fg=COLORS['text_primary'], bg=COLORS['bg_main'], anchor='w'
        ).pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)

        # コールバック関数
        def on_year_change(*args):
            val = year_dropdown.current_value.get()
            if val:
                try:
                    self.cumulative_files[index]['year'] = int(val.replace("年", ""))
                    self._update_fiscal_year_display()
                    self._check_can_execute()
                except ValueError:
                    pass

        def on_month_change(*args):
            val = month_dropdown.current_value.get()
            if val:
                try:
                    self.cumulative_files[index]['month'] = int(val.replace("月", ""))
                    self._update_fiscal_year_display()
                    self._check_can_execute()
                except ValueError:
                    pass
        
        # 変数の監視
        year_dropdown.current_value.trace_add("write", on_year_change)
        month_dropdown.current_value.trace_add("write", on_month_change)
    
    def _update_fiscal_year_display(self):
        """年度表示を更新（ファイルリスト下部）"""
        # 年度計算
        fiscal_year = None
        if self.cumulative_files:
            # 年月が設定されている最初のファイルから年度を計算
            for file_info in self.cumulative_files:
                if file_info['year'] and file_info['month']:
                    year = file_info['year']
                    month = file_info['month']
                    fiscal_year = year if month >= 4 else year - 1
                    break
        
        # 既存の年度表示ラベルがあれば更新、なければ作成
        if not hasattr(self, 'fiscal_year_label'):
            if fiscal_year and self.file_list_frame:
                # 年度表示ラベルを作成
                fiscal_year_frame = tk.Frame(self.file_list_frame, bg='#1E3A5F', padx=15, pady=10)
                fiscal_year_frame.pack(fill=tk.X, pady=(10, 0))
                
                self.fiscal_year_label = tk.Label(
                    fiscal_year_frame, text=f"対象年度: {fiscal_year}年度　（出力ファイル: SP_年度累計_{fiscal_year}.xlsx）",
                    font=('Meiryo', 10), fg=COLORS['accent'], bg='#1E3A5F'
                )
                self.fiscal_year_label.pack()
        elif hasattr(self, 'fiscal_year_label'):
            # ウィジェットが既に削除されている可能性があるのでチェック
            try:
                if not self.fiscal_year_label.winfo_exists():
                    # ウィジェットが削除されている場合は属性を削除
                    delattr(self, 'fiscal_year_label')
                    # 再帰的に呼び出して再作成
                    self._update_fiscal_year_display()
                    return
            except tk.TclError:
                # TclErrorが発生した場合も属性を削除
                delattr(self, 'fiscal_year_label')
                self._update_fiscal_year_display()
                return
            
            if fiscal_year:
                self.fiscal_year_label.config(text=f"対象年度: {fiscal_year}年度　（出力ファイル: SP_年度累計_{fiscal_year}.xlsx）")
            else:
                # 年度が計算できなくなった場合はラベルを削除
                if self.fiscal_year_label.winfo_exists():
                    self.fiscal_year_label.master.destroy()
                delattr(self, 'fiscal_year_label')
    
    def _remove_file(self, index):
        """ファイルをリストから削除"""
        if 0 <= index < len(self.cumulative_files):
            self.cumulative_files.pop(index)
            # 年度ラベルをリセット
            if hasattr(self, 'fiscal_year_label'):
                delattr(self, 'fiscal_year_label')
            self._update_file_list()





class PerformanceReflectionPage(tk.Frame):
    """実績反映ページ"""
    def __init__(self, parent, server_manager=None):
        super().__init__(parent, bg=COLORS['bg_main'])
        
        self.server_manager = server_manager
        
        # 状態管理
        self.uploaded_files = [] # リスト: {'path': Path, 'name': str, 'size': str}
        self.is_processing = False
        
        # UI構築
        self._create_header()
        self._create_main_layout()
        
        # ステータス更新開始
        self._update_status()

    def _create_header(self):
        """ページヘッダー作成"""
        header = tk.Frame(self, bg=COLORS['bg_main'], pady=20, padx=30)
        header.pack(fill=tk.X)
        
        tk.Label(
            header, text="実績反映", font=('Meiryo', 18, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_main']
        ).pack(anchor='w')
        
        tk.Label(
            header, text="売上報告書（Excel）を取り込み、データベースとダッシュボードを更新します。",
            font=('Meiryo', 10), fg=COLORS['text_secondary'], bg=COLORS['bg_main']
        ).pack(anchor='w', pady=(5, 0))

    def _create_main_layout(self):
        """メインレイアウト作成 (左右2カラム 5:5)"""
        # メインコンテナ
        main_container = tk.Frame(self, bg=COLORS['bg_main'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        
        # グリッド設定 (5:5) - 左側のコンテンツが増えるため少し広げる
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_columnconfigure(1, weight=1)
        main_container.grid_rowconfigure(0, weight=1)
        
        # 左カラム
        left_col = tk.Frame(main_container, bg=COLORS['bg_main'])
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        
        # 右カラム
        right_col = tk.Frame(main_container, bg=COLORS['bg_main'])
        right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        
        # コンテンツ配置
        self._create_left_panel(left_col)
        self._create_right_panel(right_col)

    def _create_left_panel(self, parent):
        """左パネル (ファイル選択 + 実行)"""
        # タイトル: 売上報告書ファイルを取り込む
        tk.Label(
            parent, text="売上報告書ファイルを取り込む", font=('Meiryo', 12, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_main']
        ).pack(anchor='w', pady=(0, 10))
        
        # ドロップゾーン
        self.drop_zone = tk.Frame(
            parent, bg=COLORS['bg_card'],
            highlightbackground=COLORS['border'], highlightthickness=1
        )
        self.drop_zone.pack(fill=tk.X, expand=False, ipady=20)
        
        # ... (DnD setup omitted as it's handled by update) ...
        # ホバーエフェクト
        def on_enter(e):
            self.drop_zone.config(highlightbackground=COLORS['accent'])
        def on_leave(e):
            self.drop_zone.config(highlightbackground=COLORS['border'])
        self.drop_zone.bind('<Enter>', on_enter)
        self.drop_zone.bind('<Leave>', on_leave)
        
        # DnD設定
        try:
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind('<<Drop>>', self._on_drop)
        except Exception:
            pass
            
        content_frame = tk.Frame(self.drop_zone, bg=COLORS['bg_card'])
        content_frame.pack(expand=True)
        
        tk.Label(
            content_frame, text="📁", font=('Meiryo', 32),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card']
        ).pack(pady=(0, 15))
        
        tk.Label(
            content_frame, text="ここにExcelファイルを\nドラッグ＆ドロップ",
            font=('Meiryo', 14), fg=COLORS['text_secondary'], bg=COLORS['bg_card'],
            justify='center'
        ).pack(pady=(0, 15))
        
        ModernButton(
            content_frame, text="ファイルを選択",
            command=self._select_files, width=20
        ).pack()
        
        # ファイルリスト表示エリア
        self.file_list_frame = tk.Frame(parent, bg=COLORS['bg_main'])
        self.file_list_frame.pack(fill=tk.X, pady=(15, 20)) # 下に余白追加

        # 実績反映を実行ボタン (左カラム最下部配置)
        self._create_execution_panel(parent)

    def _create_right_panel(self, parent):
        """右パネル (ステータス)"""
        # 公開ステータスパネル
        self._create_status_panel(parent)
        
    def _create_execution_panel(self, parent):
        """実行ボタン配置"""
        # タイトル: 実績反映を実行（ファイル選択時に表示）
        self.execution_title = tk.Label(
            parent, text="実績反映を実行", font=('Meiryo', 12, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_main']
        )
        # self.execution_title.pack(anchor='w', pady=(0, 10))  # 初期非表示
        
        self.execute_btn_frame = tk.Frame(parent, bg=COLORS['bg_main'])
        # self.execute_btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.execute_btn = ModernButton(
            self.execute_btn_frame, 
            text="実績反映を実行", 
            command=self._confirm_execution,
            width=25,
            state='disabled'
        )
        self.execute_btn.pack(fill=tk.X, ipady=5)
        
    def _create_status_panel(self, parent):
        """公開ステータスパネル"""
        if not self.server_manager:
            return

        tk.Label(
            parent, text="公開ステータス", font=('Meiryo', 11, 'bold'),
            fg=COLORS['text_secondary'], bg=COLORS['bg_main']
        ).pack(anchor='w', pady=(0, 5))

        self.status_card = tk.Frame(parent, bg=COLORS['bg_card'], padx=15, pady=15,
                                  highlightthickness=1, highlightbackground=COLORS['border'])
        self.status_card.pack(fill=tk.X)
        
        # ステータス表示部
        status_row = tk.Frame(self.status_card, bg=COLORS['bg_card'])
        status_row.pack(fill=tk.X, pady=(0, 10))
        
        self.status_indicator = tk.Label(
            status_row, text="●", font=('Meiryo', 12),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card']
        )
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 5))
        
        self.status_text = tk.Label(
            status_row, text="停止中", font=('Meiryo', 11, 'bold'),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card']
        )
        self.status_text.pack(side=tk.LEFT)
        
        # 最終更新日時
        self.last_updated_label = tk.Label(
            status_row, text="最終更新: --", font=('Meiryo', 9),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card']
        )
        self.last_updated_label.pack(side=tk.RIGHT)

        # URL表示部
        self.url_frame = tk.Frame(self.status_card, bg=COLORS['bg_main'], padx=10, pady=8)
        self.url_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.url_label = tk.Label(
            self.url_frame, text="--", font=('Consolas', 10),
            fg=COLORS['text_secondary'], bg=COLORS['bg_main']
        )
        self.url_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # アクションボタン
        btn_row = tk.Frame(self.status_card, bg=COLORS['bg_card'])
        btn_row.pack(fill=tk.X)
        
        # ブラウザで開く
        self.open_btn = ModernButton(
            btn_row, text="開く", btn_type='secondary', width=8,
            command=self._open_dashboard, state='disabled'
        )
        self.open_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # コピー
        self.copy_btn = ModernButton(
            btn_row, text="URLコピー", btn_type='secondary', width=10,
            command=self._copy_url, state='disabled'
        )
        self.copy_btn.pack(side=tk.LEFT)

    def _update_status(self):
        """ステータス更新ループ"""
        if not self.winfo_exists():
            return
            
        if self.server_manager:
            is_running = self.server_manager.is_dashboard_running()
            url = self.server_manager.get_dashboard_access_url()
            
            # 最終更新日時の取得とデータ有無判定
            last_updated = "未作成"
            has_data = False
            try:
                index_path = self.server_manager.dashboard_dir / "index.html"
                if index_path.exists():
                    mtime = index_path.stat().st_mtime
                    from datetime import datetime
                    dt = datetime.fromtimestamp(mtime)
                    last_updated = f"最終作成: {dt.strftime('%Y/%m/%d %H:%M')}"
                    has_data = True
            except Exception:
                pass
            
            self.last_updated_label.config(text=last_updated)

            if is_running:
                # 公開中 (Green)
                self.status_indicator.config(fg=COLORS['success'])
                self.status_text.config(text="公開中", fg=COLORS['success'])
                self.url_label.config(text=url, fg=COLORS['text_primary'])
                self.open_btn.config(state='normal')
                self.copy_btn.config(state='normal')
                self.status_card.config(highlightbackground=COLORS['success'])
            elif has_data:
                # 停止中・データあり (Orange)
                self.status_indicator.config(fg=COLORS['warning'])
                self.status_text.config(text="公開停止中", fg=COLORS['warning'])
                self.url_label.config(text="(サーバー停止中)", fg=COLORS['text_secondary'])
                self.open_btn.config(state='disabled')
                self.copy_btn.config(state='disabled')
                self.status_card.config(highlightbackground=COLORS['warning'])
            else:
                # 未作成 (Grey)
                self.status_indicator.config(fg=COLORS['text_secondary'])
                self.status_text.config(text="未作成", fg=COLORS['text_secondary'])
                self.url_label.config(text="--", fg=COLORS['text_secondary'])
                self.open_btn.config(state='disabled')
                self.copy_btn.config(state='disabled')
                self.status_card.config(highlightbackground=COLORS['border'])
                
        # 2秒ごとに更新
        self.after(2000, self._update_status)

    def _toggle_dashboard(self):
        """ダッシュボードサーバーの起動/停止切り替え"""
        if not self.server_manager:
            return
            
        is_running = self.server_manager.is_dashboard_running()
        port = self.server_manager.config.get('dashboard_port', 8000)
        host = self.server_manager.config.get('dashboard_host', DEFAULT_CONFIG['dashboard_host'])
        
        if is_running:
            self.server_manager.stop_dashboard()
        else:
            self.server_manager.start_dashboard(
                port,
                lambda: self._update_status(), # on_start
                lambda: self._update_status(),  # on_stop
                host=host
            )
        # 即時更新
        self.after(100, self._update_status)

    def _open_dashboard(self):
        """ブラウザで開く"""
        if self.server_manager:
            webbrowser.open(self.server_manager.get_dashboard_local_url())

    def _copy_url(self):
        """URLをクリップボードにコピー"""
        if self.server_manager:
            url = self.server_manager.get_dashboard_access_url()
            self.clipboard_clear()
            self.clipboard_append(url)
            ModernDialog.show_info(self, "コピー完了", "共有用URLをクリップボードにコピーしました。")

    def _on_drop(self, event):
        """ファイルドロップ時の処理"""
        files = self.tk.splitlist(event.data)
        self._add_files(files)

    def _select_files(self):
        """ファイル選択ダイアログ"""
        files = filedialog.askopenfilenames(
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if files:
            self._add_files(files)

    def _add_files(self, files):
        """ファイルをリストに追加"""
        for f in files:
            path = Path(f)
            if path.suffix.lower() not in ['.xlsx', '.xls']:
                continue
            
            # 重複チェック（リスト内）
            if any(fl['path'] == path for fl in self.uploaded_files):
                continue
            
            size_mb = path.stat().st_size / (1024 * 1024)
            self.uploaded_files.append({
                'path': path,
                'name': path.name,
                'size': f"{size_mb:.1f} MB"
            })
        
        self._update_file_list()

    def _update_file_list(self):
        """ファイルリスト表示更新"""
        # 既存の内容をクリア
        for widget in self.file_list_frame.winfo_children():
            widget.destroy()
            
        if not self.uploaded_files:
            self._check_can_execute()
            return

        # ヘッダー
        header = tk.Frame(self.file_list_frame, bg=COLORS['bg_sidebar'], height=30)
        header.pack(fill=tk.X, pady=(0, 2))
        header.pack_propagate(False)
        
        tk.Label(
            header, text="ファイル名", font=('Meiryo', 9, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_sidebar']
        ).pack(side=tk.LEFT, padx=10)
        


        # ファイル一覧
        for i, file_info in enumerate(self.uploaded_files):
            row = tk.Frame(self.file_list_frame, bg=COLORS['bg_card'], padx=10, pady=8)
            row.pack(fill=tk.X, pady=2)
            
            tk.Label(
                row, text=file_info['name'], font=('Meiryo', 9),
                fg=COLORS['text_primary'], bg=COLORS['bg_card']
            ).pack(side=tk.LEFT)
            
            ModernButton(
                row, text="削除", 
                command=lambda idx=i: self._remove_file(idx),
                width=6, btn_type='danger'
            ).pack(side=tk.RIGHT)

        self._check_can_execute()

    def _remove_file(self, index):
        """ファイルをリストから削除"""
        if 0 <= index < len(self.uploaded_files):
            self.uploaded_files.pop(index)
            self._update_file_list()

    def _check_can_execute(self):
        """実行可能かチェック"""
        if self.uploaded_files:
            self.execute_btn.config(state='normal')
            self.execution_title.pack(anchor='w', pady=(0, 10))  # タイトル表示
            self.execute_btn_frame.pack(fill=tk.X, pady=(5, 0))
        else:
            self.execute_btn.config(state='disabled')
            self.execution_title.pack_forget()  # タイトル非表示
            self.execute_btn_frame.pack_forget()

    def _confirm_execution(self):
        """実行確認"""
        if not self.uploaded_files:
            return
            
        if self.is_processing:
            return
            
        response = ModernDialog.ask_yes_no(
            self,
            "実行確認",
            f"{len(self.uploaded_files)}個のファイルを反映しますか？",
            detail="※この処理は取り消せません。\n※反映には数分かかる場合があります。"
        )
        
        if response:
            self._start_import_process()

    def _start_import_process(self):
        """インポート処理開始（スレッド）"""
        self.is_processing = True
        self.execute_btn.config(state='disabled')
        self._show_progress_modal()
        
        thread = threading.Thread(target=self._run_import_process)
        thread.daemon = True
        thread.start()
    
    def _run_import_process(self):
        """インポート実行（別スレッド）"""
        try:
            success_count = 0
            error_details = []
            total_files = len(self.uploaded_files)
            
            for i, file_info in enumerate(self.uploaded_files):
                file_path = file_info['path']
                
                self._update_progress(f"処理中 ({i+1}/{total_files}):\n{file_info['name']}")
                
                result = import_excel_v2(file_path)
                
                if result['success']:
                    success_count += 1
                else:
                    error_details.append(f"{file_info['name']}: {result.get('error')}")
            
            if success_count > 0:
                self._update_progress("ダッシュボードを更新中...")
                
                public_dir = APP_DIR / 'public_dashboards'
                public_dir.mkdir(exist_ok=True, parents=True)
                
                output_path = generate_dashboard(output_dir=public_dir)
                
                try:
                    shutil.copy(output_path, public_dir / 'index.html')
                except Exception as e:
                    print(f"index.html creation failed: {e}")
                
            self.after(0, lambda: self._handle_completion(success_count, total_files, error_details))
            
        except Exception as e:
            self.after(0, lambda: self._handle_error(str(e)))
            
    def _handle_completion(self, success_count, total_files, error_details):
        """完了時処理"""
        self._hide_progress_modal()
        self.is_processing = False
        
        if success_count == total_files:
            ModernDialog.show_success(
                self,
                "処理完了",
                "すべてのファイルの反映が完了しました！",
                detail="ダッシュボードが更新されました。"
            )
            self.uploaded_files = []
            self._update_file_list()
        else:
            detail_msg = f"成功: {success_count}件\n失敗: {len(error_details)}件\n\nエラー詳細:\n" + "\n".join(error_details)
            ModernDialog.show_warning(
                self,
                "一部完了",
                "一部のファイルでエラーが発生しました。",
                detail=detail_msg
            )
            self._check_can_execute()
            
    def _handle_error(self, error_message):
        """エラー時処理"""
        self._hide_progress_modal()
        self.is_processing = False
        self._check_can_execute()
        
        ModernDialog.show_error(
            self,
            "エラー",
            "予期せぬエラーが発生しました",
            detail=error_message
        )

    def _show_progress_modal(self):
        """進捗モーダル表示"""
        self.progress_window = tk.Toplevel(self)
        self.progress_window.title("処理中")
        self.progress_window.geometry("400x200")
        self.progress_window.overrideredirect(True)
        self.progress_window.config(bg=COLORS['bg_card'])
        self.progress_window.attributes('-topmost', True)
        
        # 中央配置
        self.update_idletasks() # 親ウィンドウのサイズ確定待ち
        try:
            x = self.winfo_rootx() + (self.winfo_width() // 2) - 200
            y = self.winfo_rooty() + (self.winfo_height() // 2) - 100
        except:
             x = (self.winfo_screenwidth() // 2) - 200
             y = (self.winfo_screenheight() // 2) - 100
        self.progress_window.geometry(f"+{x}+{y}")
        
        frame = tk.Frame(
            self.progress_window, bg=COLORS['bg_card'],
            highlightthickness=1, highlightbackground=COLORS['border']
        )
        frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(
            frame, text="⏳", font=('Meiryo', 32),
            bg=COLORS['bg_card'], fg=COLORS['accent']
        ).pack(pady=(30, 10))
        
        tk.Label(
            frame, text="実績データを反映中...", font=('Meiryo', 12, 'bold'),
            bg=COLORS['bg_card'], fg=COLORS['text_primary']
        ).pack()
        
        self.progress_label = tk.Label(
            frame, text="準備中...", font=('Meiryo', 9),
            bg=COLORS['bg_card'], fg=COLORS['text_secondary']
        )
        self.progress_label.pack(pady=(5, 0))

        # モーダル設定（操作ブロック）
        self.progress_window.transient(self.winfo_toplevel())
        self.progress_window.grab_set()
        self.progress_window.lift()
        self.progress_window.focus_force()
        
    def _update_progress(self, message):
        """進捗メッセージ更新"""
        self.after(0, lambda: self.progress_label.config(text=message) if hasattr(self, 'progress_label') else None)
        
    def _hide_progress_modal(self):
        """モーダルを閉じる"""
        if hasattr(self, 'progress_window') and self.progress_window.winfo_exists():
            self.progress_window.destroy()


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
            header, text="月次集計", font=('Meiryo', 18, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_main']
        ).pack(anchor='w')
        
        tk.Label(
            header, text="CSVデータから売上を集計し、Excel報告書を作成します",
            font=('Meiryo', 10), fg=COLORS['text_secondary'], bg=COLORS['bg_main']
        ).pack(anchor='w', pady=(5, 0))

    def _create_main_layout(self):
        """メインレイアウト作成（縦並び）"""
        # コンテンツエリア（上部）
        content_area = tk.Frame(self, bg=COLORS['bg_main'])
        content_area.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 30))
        
        # STEP 1: ファイル選択（横3つ並び）
        self._create_file_upload_section(content_area)
        
        # STEP 2: 期間選択
        self._create_period_section(content_area)
        
        # 実行ボタン（STEP 2の真下、独立）
        button_frame = tk.Frame(content_area, bg=COLORS['bg_main'])
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        self.execute_btn = ModernButton(
            button_frame, text="集計を実行", btn_type='primary',
            font=('Meiryo', 12),
            command=self._execute_aggregation,
            state='disabled'
        )
        # self.execute_btn.pack(fill=tk.X, ipady=12)

    def _create_file_upload_section(self, parent):
        """ファイルアップロードセクション作成（横3つ並び）"""
        # カード全体
        card = tk.Frame(parent, bg=COLORS['bg_card'], padx=20, pady=20)
        card.pack(fill=tk.X, pady=(0, 20))
        
        # STEP 1ヘッダー
        header_frame = tk.Frame(card, bg=COLORS['bg_card'])
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        step_badge = tk.Label(
            header_frame, text="STEP 1", font=('Meiryo', 9, 'bold'),
            fg=COLORS['accent'], bg='#1E3A5F', padx=8, pady=2
        )
        step_badge.pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(
            header_frame, text="ファイル選択", font=('Meiryo', 12, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT)
        
        # ファイル選択エリア（横3つグリッド配置）
        files_grid = tk.Frame(card, bg=COLORS['bg_card'])
        files_grid.pack(fill=tk.X)
        
        # グリッド設定（3列）
        files_grid.columnconfigure(0, weight=1)
        files_grid.columnconfigure(1, weight=1)
        files_grid.columnconfigure(2, weight=1)
        
        # 3つのファイル選択UI（横並び）
        files_data = [
            ("売上データ (CSV)", "📊", "sales", "*.csv", 0),
            ("会員データ (CSV)", "👥", "accounts", "*.csv", 1),
            ("担当者マスタ (XLSX)", "📋", "master", "*.xlsx", 2)
        ]
        
        for label_text, icon, file_key, file_filter, col in files_data:
            self._create_file_select_col(files_grid, label_text, icon, file_key, file_filter, col)

    def _create_file_select_col(self, parent, label_text, icon, file_key, file_filter, col):
        """ファイル選択カラムを作成（グリッド用）"""
        col_frame = tk.Frame(parent, bg=COLORS['bg_card'])
        col_frame.grid(row=0, column=col, padx=10, sticky='nsew')
        
        # ラベル + アイコン
        label_frame = tk.Frame(col_frame, bg=COLORS['bg_card'])
        label_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(
            label_frame, text=icon, font=('Meiryo', 12),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Label(
            label_frame, text=label_text, font=('Meiryo', 10, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT)
        
        # 削除ボタン（ファイル選択後に表示）
        remove_btn = tk.Label(
            label_frame, text="削除", font=('Meiryo', 9),
            fg='white', bg='#991B1B', cursor='hand2', padx=6, pady=2
        )
        remove_btn.bind('<Button-1>', lambda e: self._remove_file(file_key, file_name_label, cloud_label, remove_btn))
        
        # ドロップゾーン（破線ボーダー + クラウドアイコン）
        drop_zone = tk.Frame(col_frame, bg=COLORS['bg_main'], highlightthickness=2, 
                             highlightbackground=COLORS['border'], highlightcolor=COLORS['border'])
        drop_zone.pack(fill=tk.BOTH, expand=True, ipady=40)
        
        # 内部コンテンツフレーム
        content_frame = tk.Frame(drop_zone, bg=COLORS['bg_main'], cursor='hand2')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=20)
        
        # クラウドアイコン
        cloud_label = tk.Label(
            content_frame, text="☁", font=('Meiryo', 28),
            fg=COLORS['text_secondary'], bg=COLORS['bg_main']
        )
        cloud_label.pack(pady=(0, 5))
        
        # プレースホルダーテキスト / ファイル名
        file_name_label = tk.Label(
            content_frame, text="ドラッグ&ドロップ",
            font=('Meiryo', 12), fg=COLORS['text_secondary'],
            bg=COLORS['bg_main'], wraplength=150
        )
        file_name_label.pack()
        
        # クリックイベントをバインド
        def on_click(event=None):
            self._select_file(file_key, file_name_label, cloud_label, remove_btn, file_filter)
        
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
        
        # ドラッグ&ドロップの登録
        if TKDND_AVAILABLE:
            def on_drop(event):
                # ドロップされたファイルパスを取得
                files = self.winfo_toplevel().tk.splitlist(event.data)
                if files:
                    dropped_file = files[0]  # 最初のファイルのみ使用
                    # ファイル形式チェック
                    if file_filter == "*.csv" and not dropped_file.lower().endswith('.csv'):
                        ModernDialog.show_error(self, "エラー", "CSVファイルを選択してください")
                        return
                    elif file_filter == "*.xlsx" and not dropped_file.lower().endswith('.xlsx'):
                        ModernDialog.show_error(self, "エラー", "Excelファイル(.xlsx)を選択してください")
                        return
                    
                    # ファイルを設定
                    self.files[file_key] = dropped_file
                    file_name_label.config(text=Path(dropped_file).name, fg=COLORS['accent'], font=('Meiryo', 12))
                    cloud_label.config(text="📄", font=('Meiryo', 20))
                    remove_btn.pack(side=tk.RIGHT, padx=(5, 0))
                    self._check_can_execute()
            
            # ドロップターゲットとして登録
            drop_zone.drop_target_register(DND_FILES)
            drop_zone.dnd_bind('<<Drop>>', on_drop)
            content_frame.drop_target_register(DND_FILES)
            content_frame.dnd_bind('<<Drop>>', on_drop)
        
        # 参照を保存
        setattr(self, f'{file_key}_name_label', file_name_label)
        setattr(self, f'{file_key}_cloud_label', cloud_label)
        setattr(self, f'{file_key}_remove_btn', remove_btn)

    def _create_period_section(self, parent):
        """期間選択セクション作成（スタイル付きCombobox）"""
        # STEP 2カード
        card = tk.Frame(parent, bg=COLORS['bg_card'], padx=20, pady=20)
        card.pack(fill=tk.X)
        
        # ヘッダー
        header_frame = tk.Frame(card, bg=COLORS['bg_card'])
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        step_badge = tk.Label(
            header_frame, text="STEP 2", font=('Meiryo', 9, 'bold'),
            fg=COLORS['accent'], bg='#1E3A5F', padx=8, pady=2
        )
        step_badge.pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(
            header_frame, text="対象期間", font=('Meiryo', 12, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        ).pack(side=tk.LEFT)
        
        # Comboboxのスタイル設定（よりモダンに）
        style = ttk.Style()
        style.theme_use('clam')
        
        # ドロップダウンリスト（Listbox）のスタイル設定
        # 標準のComboboxでもリスト部分はOS標準色になりがちなので、個別に設定
        self.option_add('*TCombobox*Listbox.background', COLORS['bg_card'])
        self.option_add('*TCombobox*Listbox.foreground', COLORS['text_primary'])
        self.option_add('*TCombobox*Listbox.selectBackground', COLORS['accent'])
        self.option_add('*TCombobox*Listbox.selectForeground', 'white')
        self.option_add('*TCombobox*Listbox.font', ('Meiryo', 10))
        self.option_add('*TCombobox*Listbox.relief', 'flat')
        self.option_add('*TCombobox*Listbox.borderwidth', '0')
        
        # Combobox本体のスタイル（フラットデザイン）
        style.configure('Modern.TCombobox',
            fieldbackground=COLORS['bg_main'],    # 入力欄の背景
            background=COLORS['bg_main'],         # 矢印ボタンの背景
            foreground=COLORS['text_primary'],    # 文字色
            arrowcolor=COLORS['text_secondary'],  # 矢印の色
            bordercolor=COLORS['border'],         # 枠線の色
            lightcolor=COLORS['bg_main'],         # 3D効果除去
            darkcolor=COLORS['bg_main'],          # 3D効果除去
            relief='flat',                        # フラットに
            borderwidth=1,                        # 枠線は細く
            arrowsize=16,                         # 矢印を少し大きく
            padding=5                             # 内部パディングで広さを出す
        )
        
        # 状態によるスタイルの変化
        style.map('Modern.TCombobox',
            fieldbackground=[('readonly', COLORS['bg_main']), ('active', COLORS['sidebar_active'])],
            background=[('active', COLORS['sidebar_active'])], # ホバー時のボタン背景
            arrowcolor=[('active', 'white')],                 # ホバー時の矢印
            bordercolor=[('focus', COLORS['accent'])],         # フォーカス時の枠線
            lightcolor=[('focus', COLORS['accent'])],
            darkcolor=[('focus', COLORS['accent'])]
        )
        
        # 年度・月を横並びで表示
        period_frame = tk.Frame(card, bg=COLORS['bg_card'])
        period_frame.pack(fill=tk.X)
        
        # 年度選択（左半分）
        year_container = tk.Frame(period_frame, bg=COLORS['bg_card'])
        year_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        tk.Label(
            year_container, text="年度", font=('Meiryo', 9, 'bold'),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card']
        ).pack(anchor='w', pady=(0, 5))
        
        current_year = datetime.now().year
        current_month = datetime.now().month
        fiscal_year = current_year if current_month >= 4 else current_year - 1
        years = [f"{y}年度" for y in range(fiscal_year - 4, fiscal_year + 2)]
        
        self.year_var = tk.StringVar(value=f"{fiscal_year}年度")
        year_combo = ttk.Combobox(
            year_container, textvariable=self.year_var, values=years,
            state='readonly', font=('Meiryo', 10),
            style='Modern.TCombobox', cursor='hand2'
        )
        year_combo.pack(fill=tk.X, ipady=5)
        
        # 月選択（右半分）
        month_container = tk.Frame(period_frame, bg=COLORS['bg_card'])
        month_container.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(
            month_container, text="月", font=('Meiryo', 9, 'bold'),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card']
        ).pack(anchor='w', pady=(0, 5))
        
        months = [f"{m}月" for m in range(1, 13)]
        self.month_var = tk.StringVar(value=f"{current_month}月")
        month_combo = ttk.Combobox(
            month_container, textvariable=self.month_var, values=months,
            state='readonly', font=('Meiryo', 10),
            style='Modern.TCombobox', cursor='hand2'
        )
        month_combo.pack(fill=tk.X, ipady=5)

    def _select_file(self, file_key, file_name_label, cloud_label, remove_btn, file_filter):
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
            file_name_label.config(text=Path(filename).name, fg=COLORS['accent'], font=('Meiryo', 12))
            # クラウドアイコンを小さく、色を変更
            cloud_label.config(text="📄", font=('Meiryo', 20))
            # 削除ボタン表示
            remove_btn.pack(side=tk.RIGHT, padx=(5, 0))
            self._check_can_execute()
    
    def _remove_file(self, file_key, file_name_label, cloud_label, remove_btn):
        """選択したファイルを削除"""
        self.files[file_key] = None
        # UI を初期状態に戻す
        file_name_label.config(text="ファイルをドラッグ&ドロップ", fg=COLORS['text_secondary'])
        cloud_label.config(text="☁", font=('Meiryo', 32))
        remove_btn.pack_forget()
        self._check_can_execute()

    def _check_can_execute(self):
        """実行ボタンの活性化チェック"""
        if all(self.files.values()) and not self.is_processing:
            self.execute_btn.config(state='normal')
            self.execute_btn.pack(fill=tk.X, ipady=12)
        else:
            self.execute_btn.config(state='disabled')
            self.execute_btn.pack_forget()

    def _execute_aggregation(self):
        """集計実行"""
        if not all(self.files.values()) or self.is_processing:
            return
        
        # 処理中フラグ
        self.is_processing = True
        self.execute_btn.config(state='disabled')
        
        # 集計中モーダルを表示
        self._show_progress_modal()
        
        # スレッドで実行（UIをブロックしないため）
        thread = threading.Thread(target=self._run_aggregation_process)
        thread.daemon = True
        thread.start()
    
    def _run_aggregation_process(self):
        """集計処理の実行（別スレッド）"""
        try:
            # 集計実行
            result = self._run_direct_aggregation()
            if result:
                # 成功時は結果ダイアログを表示
                output_path = result.get('output_file', '')
                total_sales = result.get('total_sales', 0)
                self.after(0, lambda: self._show_result_dialog(total_sales, output_path))
        
        except SchoolMasterMismatchError as e:
            # マスタ不一致エラー
            schools = e.unmatched_schools
            self.after(0, lambda: [
                self._hide_progress_modal(),
                self._show_master_mismatch_dialog(schools)
            ])
        
        except Exception as e:
            # エラーダイアログを表示
            error_msg = str(e)
            self.after(0, lambda: [
                self._hide_progress_modal(),
                self._show_error_dialog(error_msg)
            ])
        
        finally:
            # 処理完了フラグ
            self.is_processing = False
            self.after(0, lambda: self.execute_btn.config(state='normal' if all(self.files.values()) else 'disabled'))
    
    def _run_direct_aggregation(self):
        """集計実行処理（直接Pythonモジュール呼び出し）"""
        try:
            # 年度・月を抽出
            year_str = self.year_var.get()
            month_str = self.month_var.get()
            
            fiscal_year = int(year_str.replace('年度', ''))
            month = int(month_str.replace('月', ''))
            
            # ファイルハンドラーで読み込み
            upload_dir = Path(__file__).parent / 'temp_uploads'
            upload_dir.mkdir(parents=True, exist_ok=True)
            file_handler = FileHandler(upload_dir)
            
            sales_df = file_handler.read_sales_csv(Path(self.files['sales']))
            accounts_df = file_handler.read_accounts_csv(Path(self.files['accounts']))
            master_df = file_handler.read_master_excel(Path(self.files['master']))
            
            # 集計実行
            aggregator = SalesAggregator(sales_df, master_df)
            result = aggregator.aggregate_all()
            
            # 会員率計算
            accounts_calc = AccountsCalculator(accounts_df)
            accounts_result_df = accounts_calc.calculate()
            
            # Excel出力（ユーザーのDownloadsフォルダ）
            output_dir = Path.home() / 'Downloads'
            output_dir.mkdir(exist_ok=True)
            
            filename = f"SP_SalesResult_{fiscal_year}{month:02d}.xlsx"
            exporter = ExcelExporter(
                result,
                output_dir=output_dir,
                filename=filename,
                accounts_df=accounts_result_df
            )
            output_path = exporter.export()
            
            # 結果を返す
            return {
                'total_sales': result.summary.total_sales,
                'output_file': str(output_path)
            }
        
        except Exception as e:
            raise e
    
    def _show_progress_modal(self):
        """集計中モーダルを表示（カスタムデザイン）"""
        self.progress_window = tk.Toplevel(self)
        self.progress_window.title("月次集計")
        self.progress_window.geometry("550x250")
        self.progress_window.overrideredirect(True)
        self.progress_window.config(bg=COLORS['bg_card'])
        self.progress_window.attributes('-topmost', True)
        
        # 枠線
        container = tk.Frame(
            self.progress_window, bg=COLORS['bg_card'],
            highlightthickness=1, highlightbackground=COLORS['border'], highlightcolor=COLORS['border']
        )
        container.pack(fill=tk.BOTH, expand=True)
        
        # 中央に配置
        self.progress_window.update_idletasks()
        x = (self.progress_window.winfo_screenwidth() // 2) - 275
        y = (self.progress_window.winfo_screenheight() // 2) - 125
        self.progress_window.geometry(f"+{x}+{y}")
        
        # コンテンツ
        frame = tk.Frame(container, bg=COLORS['bg_card'], padx=30, pady=30)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # スピナー的なアイコン
        tk.Label(
            frame, text="⏳", font=('Meiryo', 32),
            fg=COLORS['accent'], bg=COLORS['bg_card']
        ).pack(pady=(0, 15))
        
        tk.Label(
            frame, text="集計中...", font=('Meiryo', 14, 'bold'),
            fg=COLORS['text_primary'], bg=COLORS['bg_card']
        ).pack(pady=(0, 10))
        
        tk.Label(
            frame, text="この処理には時間がかかる場合があります\nしばらくお待ちください", font=('Meiryo', 10),
            fg=COLORS['text_secondary'], bg=COLORS['bg_card'], justify='center',
            wraplength=480
        ).pack()
        
        
        self.progress_window.transient(self)
        self.progress_window.grab_set()
        
        # 最前面へ
        self.progress_window.lift()
        self.progress_window.focus_force()
    
    def _hide_progress_modal(self):
        """集計中モーダルを閉じる"""
        if hasattr(self, 'progress_window') and self.progress_window:
            self.progress_window.destroy()
            self.progress_window = None
    
    def _show_result_dialog(self, total_sales, output_path):
        """集計完了ダイアログを表示"""
        # 進捗モーダルを閉じる
        self._hide_progress_modal()
        
        # 総売上をフォーマット
        sales_str = f'¥{int(total_sales):,}'
        
        # 保存先ディレクトリ
        output_dir = Path(output_path).parent
        
        ModernDialog.show_success(
            self,
            '月次集計完了',
            f'集計が完了しました！\n総売上: {sales_str}',
            detail=f'保存先:\n{output_path}'
        )
        
        self._reset_form()
    
    def _show_master_mismatch_dialog(self, schools):
        """マスタ不一致エラーダイアログを表示"""
        schools_list = '\n'.join([f'  • {school}' for school in schools])
        
        ModernDialog.show_error(
            self,
            '担当者マスタ不一致',
            f'以下の学校が担当者マスタ（XLSX）に登録されていません。\n'
            f'マスタを更新してから、再度集計を実行してください。',
            detail=schools_list
        )
        
        # エラー後はフォームをリセット
        self._reset_form()
    
    def _show_error_dialog(self, message):
        """エラーダイアログを表示"""
        ModernDialog.show_error(self, 'エラー', message)
    
    def _reset_form(self):
        """フォームをリセット"""
        # ファイル選択をクリア
        for file_key in ['sales', 'accounts', 'master']:
            if self.files[file_key]:
                self.files[file_key] = None
                
                # UIをリセット
                name_label = getattr(self, f'{file_key}_name_label')
                cloud_label = getattr(self, f'{file_key}_cloud_label')
                remove_btn = getattr(self, f'{file_key}_remove_btn')
                
                name_label.config(text="ドラッグ&ドロップ", fg=COLORS['text_secondary'], font=('Meiryo', 12))
                cloud_label.config(text="☁", font=('Meiryo', 28))
                remove_btn.pack_forget()
        
        # ボタンを無効化
        self.execute_btn.config(state='disabled')


def main():
    app = MainApp()
    app.run()

if __name__ == '__main__':
    main()
