#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上集計システム - ランチャー V2 (Modern UI)

Hybrid Proデザインのサーバー起動・停止管理アプリケーション
モダンなフラットデザインを採用
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

# カラーパレット (Modern)
COLORS = {
    'bg_main': '#F3F4F6',      # 背景色（薄いグレー）
    'bg_card': '#FFFFFF',      # カード背景（白）
    'text_primary': '#111827', # メインテキスト
    'text_secondary': '#6B7280', # サブテキスト
    'primary': '#2563EB',      # メインカラー（青）
    'primary_hover': '#1D4ED8',
    'danger': '#EF4444',       # 危険色（赤）
    'danger_hover': '#DC2626',
    'success': '#10B981',      # 成功色（緑）
    'border': '#E5E7EB',       # ボーダー色
    'log_bg': '#1F2937',       # ログ背景（ダーク）
    'log_fg': '#D1D5DB'        # ログ文字
}

# デフォルト設定
DEFAULT_CONFIG = {
    'api_port': 8080,
    'dashboard_port': 8000,
}

# 高DPI対応（Windows）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


class ModernButton(tk.Button):
    """モダンなフラットボタン"""
    def __init__(self, master, **kwargs):
        self.btn_type = kwargs.pop('btn_type', 'primary')
        self.default_bg = COLORS.get(self.btn_type, COLORS['primary'])
        self.hover_bg = COLORS.get(f'{self.btn_type}_hover', self.default_bg)
        
        super().__init__(
            master,
            relief='flat',
            borderwidth=0,
            cursor='hand2',
            font=('Segoe UI', 9, 'bold'),
            fg='white',
            bg=self.default_bg,
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
        # Merge kwargs into cnf
        cnf = {**cnf, **kwargs}
        
        if 'state' in cnf:
            if cnf['state'] == 'disabled':
                self['bg'] = '#9CA3AF'
                self['cursor'] = 'arrow'
            else:
                self['bg'] = self.default_bg
                self['cursor'] = 'hand2'
        super().configure(cnf)


class ServerLauncher:
    """サーバーランチャー Modern UI"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title('スクールフォト売上管理システム')
        self.root.geometry('780x650')
        self.root.configure(bg=COLORS['bg_main'])
        
        # アイコン設定（もしあれば）
        # icon_path = BASE_DIR / 'icon.ico'
        # if icon_path.exists():
        #     self.root.iconbitmap(str(icon_path))

        # プロセス管理
        self.api_process = None
        self.dashboard_process = None
        self.api_running = False
        self.dashboard_running = False

        # 設定読み込み
        self.config = self._load_config()

        # UI構築
        self._setup_ui()
        self._center_window()

        # 閉じるボタンの処理
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _load_config(self):
        """設定ファイルの読み込み"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()

    def _save_config(self):
        """設定ファイルの保存"""
        try:
            self.config['api_port'] = int(self.api_port_var.get())
            self.config['dashboard_port'] = int(self.dashboard_port_var.get())
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._log(f'設定保存エラー: {e}')

    def _setup_ui(self):
        """UIをセットアップ"""
        # メインコンテナ（余白用）
        container = tk.Frame(self.root, bg=COLORS['bg_main'])
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        # ヘッダー
        self._create_header(container)

        # カードエリア
        cards_frame = tk.Frame(container, bg=COLORS['bg_main'])
        cards_frame.pack(fill=tk.X, pady=(0, 20))
        cards_frame.grid_columnconfigure(0, weight=1)
        cards_frame.grid_columnconfigure(1, weight=1)

        # APIサーバーカード
        self._create_card(
            cards_frame, 
            column=0, 
            title='管理APIサーバー', 
            icon='🛠',
            is_api=True
        )

        # 公開サーバーカード
        self._create_card(
            cards_frame, 
            column=1, 
            title='公開ダッシュボード', 
            icon='🌐',
            is_api=False
        )

        # ログパネル
        self._create_log_panel(container)

    def _create_header(self, parent):
        """ヘッダー作成"""
        header_frame = tk.Frame(parent, bg=COLORS['bg_main'])
        header_frame.pack(fill=tk.X, pady=(0, 25))

        title = tk.Label(
            header_frame,
            text='スクールフォト売上管理システム',
            font=('Segoe UI', 20, 'bold'),
            bg=COLORS['bg_main'],
            fg=COLORS['text_primary']
        )
        title.pack(side=tk.LEFT)
        
        subtitle = tk.Label(
            header_frame,
            text='v2.0',
            font=('Segoe UI', 10),
            bg=COLORS['bg_main'],
            fg=COLORS['text_secondary']
        )
        subtitle.pack(side=tk.LEFT, padx=(10, 0), anchor='sw', pady=(0, 5))

    def _create_card(self, parent, column, title, icon, is_api):
        """カードコンポーネント作成"""
        # カードのフレーム（白背景、少し影っぽくボーダー）
        card = tk.Frame(parent, bg=COLORS['bg_card'], padx=20, pady=20)
        card.grid(row=0, column=column, padx=10, sticky='ew')
        
        # 枠線（擬似的な影）
        # tk.Frameにはshadowがないので、configureでreliefなどは指定せずフラットにする
        
        # タイトル行
        title_frame = tk.Frame(card, bg=COLORS['bg_card'])
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(
            title_frame, text=icon, font=('Segoe UI', 16),
            bg=COLORS['bg_card']
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Label(
            title_frame, text=title, font=('Segoe UI', 14, 'bold'),
            bg=COLORS['bg_card'], fg=COLORS['text_primary']
        ).pack(side=tk.LEFT)

        # ステータス表示
        status_frame = tk.Frame(card, bg=COLORS['bg_card'])
        status_frame.pack(fill=tk.X, pady=(0, 20))
        
        # ステータスバッジ部分
        status_canvas = tk.Canvas(
            status_frame, width=100, height=30, 
            bg=COLORS['bg_card'], highlightthickness=0
        )
        status_canvas.pack(anchor='center')
        
        # 状態ラベル（後で更新するために属性として保持）
        status_label = tk.Label(
            status_frame, text='停止中', font=('Segoe UI', 12, 'bold'),
            bg=COLORS['bg_card'], fg=COLORS['text_secondary']
        )
        status_label.pack(anchor='center', pady=(5, 0))

        # 設定行
        config_frame = tk.Frame(card, bg=COLORS['bg_card'])
        config_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(
            config_frame, text='ポート', font=('Segoe UI', 9, 'bold'),
            bg=COLORS['bg_card'], fg=COLORS['text_secondary']
        ).pack(side=tk.LEFT)
        
        port_var = tk.StringVar(value=str(self.config['api_port'] if is_api else self.config['dashboard_port']))
        
        # カスタムエントリー
        entry_frame = tk.Frame(config_frame, bg=COLORS['border'], padx=1, pady=1)
        entry_frame.pack(side=tk.LEFT, padx=(10, 0))
        
        port_entry = tk.Entry(
            entry_frame, textvariable=port_var, width=8,
            font=('Consolas', 11), bd=0, relief='flat'
        )
        port_entry.pack(padx=5, pady=3)

        # アクションボタン
        btn_frame = tk.Frame(card, bg=COLORS['bg_card'])
        btn_frame.pack(fill=tk.X)
        
        start_btn = ModernButton(
            btn_frame, text='サーバー起動', btn_type='primary',
            command=self._start_api if is_api else self._start_dashboard
        )
        start_btn.pack(fill=tk.X, pady=(0, 10))
        
        stop_btn = ModernButton(
            btn_frame, text='サーバー停止', btn_type='danger',
            command=self._stop_api if is_api else self._stop_dashboard,
            state=tk.DISABLED
        )
        stop_btn.pack(fill=tk.X)

        # 参照を保存
        if is_api:
            self.api_port_var = port_var
            self.api_status_canvas = status_canvas
            self.api_status_label = status_label
            self.api_start_btn = start_btn
            self.api_stop_btn = stop_btn
            self._draw_status_pill(status_canvas, False)
        else:
            self.dashboard_port_var = port_var
            self.dashboard_status_canvas = status_canvas
            self.dashboard_status_label = status_label
            self.dashboard_start_btn = start_btn
            self.dashboard_stop_btn = stop_btn
            self._draw_status_pill(status_canvas, False)

    def _create_log_panel(self, parent):
        """ログパネル作成"""
        # ヘッダー
        log_header = tk.Frame(parent, bg=COLORS['bg_main'])
        log_header.pack(fill=tk.X, pady=(10, 5))
        
        tk.Label(
            log_header, text='システムログ', font=('Segoe UI', 10, 'bold'),
            bg=COLORS['bg_main'], fg=COLORS['text_secondary']
        ).pack(side=tk.LEFT)

        # ログ本文
        self.log_text = scrolledtext.ScrolledText(
            parent, height=8, font=('Consolas', 9),
            bg=COLORS['log_bg'], fg=COLORS['log_fg'],
            bd=0, highlightthickness=0
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _center_window(self):
        """ウィンドウを画面中央に配置"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def _draw_status_pill(self, canvas, is_running):
        """状態を示すカプセル（Pill）を描画"""
        canvas.delete('all')
        color = COLORS['success'] if is_running else '#9CA3AF'
        text_color = 'white'
        
        # 角丸背景
        # tkinter canvas doesn't have good round rect, using oval+rect approximation or just rect
        # 簡易的に円を描画
        w = 100
        h = 30
        
        # 枠
        canvas.create_rectangle(0, 0, w, h, fill='', outline='') # clear
        
        # 状態のカプセル (背景)
        fill_col = color + '20' # 透過っぽい色...はTkinter無理なので、背景白前提で薄い色を作るべきだが、
        # ここではシンプルに円を描く
        
        r = 6
        canvas.create_oval(w/2 - r, h/2 - r, w/2 + r, h/2 + r, fill=color, outline='')

    def _log(self, message):
        """ログを追加"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f'[{timestamp}] {message}\n')
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _start_api(self):
        """APIサーバーを起動"""
        if self.api_running: return
        try:
            port = int(self.api_port_var.get())
        except ValueError:
            messagebox.showerror('エラー', 'ポート番号は数値で入力してください')
            return

        self._save_config()
        self._log(f'管理APIサーバーを起動中... (ポート: {port})')

        def run_server():
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
                self.api_running = True
                self.root.after(0, self._update_api_ui_running)
                self._log(f'管理APIサーバー起動完了: http://127.0.0.1:{port}')

                for line in self.api_process.stdout:
                    self.root.after(0, lambda l=line: self._log(f'[API] {l.strip()}'))

            except Exception as e:
                self.root.after(0, lambda: self._log(f'API起動エラー: {e}'))
                self.root.after(0, self._update_api_ui_stopped)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

    def _stop_api(self):
        """APIサーバーを停止"""
        if not self.api_running: return
        self._log('管理APIサーバーを停止中...')
        try:
            if self.api_process:
                self.api_process.terminate()
                self.api_process = None
        except Exception:
            pass
        self.api_running = False
        self._update_api_ui_stopped()
        self._log('管理APIサーバー停止完了')

    def _start_dashboard(self):
        """公開サーバーを起動"""
        if self.dashboard_running: return
        try:
            port = int(self.dashboard_port_var.get())
        except ValueError:
            messagebox.showerror('エラー', 'ポート番号は数値で入力してください')
            return

        self._save_config()
        self._log(f'公開ダッシュボードを起動中... (ポート: {port})')

        def run_server():
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
                self.dashboard_running = True
                self.root.after(0, self._update_dashboard_ui_running)
                self._log(f'公開ダッシュボード起動完了: http://localhost:{port}')

                for line in self.dashboard_process.stdout:
                    self.root.after(0, lambda l=line: self._log(f'[Web] {l.strip()}'))

            except Exception as e:
                self.root.after(0, lambda: self._log(f'公開サーバー起動エラー: {e}'))
                self.root.after(0, self._update_dashboard_ui_stopped)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

    def _stop_dashboard(self):
        """公開サーバーを停止"""
        if not self.dashboard_running: return
        self._log('公開ダッシュボードを停止中...')
        try:
            if self.dashboard_process:
                self.dashboard_process.terminate()
                self.dashboard_process = None
        except Exception:
            pass
        self.dashboard_running = False
        self._update_dashboard_ui_stopped()
        self._log('公開ダッシュボード停止完了')

    def _update_api_ui_running(self):
        self._draw_status_pill(self.api_status_canvas, True)
        self.api_status_label.config(text='起動中', fg=COLORS['success'])
        self.api_start_btn.config(state=tk.DISABLED)
        self.api_stop_btn.config(state=tk.NORMAL)

    def _update_api_ui_stopped(self):
        self._draw_status_pill(self.api_status_canvas, False)
        self.api_status_label.config(text='停止中', fg=COLORS['text_secondary'])
        self.api_start_btn.config(state=tk.NORMAL)
        self.api_stop_btn.config(state=tk.DISABLED)

    def _update_dashboard_ui_running(self):
        self._draw_status_pill(self.dashboard_status_canvas, True)
        self.dashboard_status_label.config(text='起動中', fg=COLORS['success'])
        self.dashboard_start_btn.config(state=tk.DISABLED)
        self.dashboard_stop_btn.config(state=tk.NORMAL)

    def _update_dashboard_ui_stopped(self):
        self._draw_status_pill(self.dashboard_status_canvas, False)
        self.dashboard_status_label.config(text='停止中', fg=COLORS['text_secondary'])
        self.dashboard_start_btn.config(state=tk.NORMAL)
        self.dashboard_stop_btn.config(state=tk.DISABLED)

    def _on_closing(self):
        if self.api_running or self.dashboard_running:
            if messagebox.askyesno('終了確認', 'サーバーが実行中です。\n停止してから終了しますか？'):
                if self.api_running: self._stop_api()
                if self.dashboard_running: self._stop_dashboard()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        self._log('Launcher V2 (Modern UI) Ready')
        self.root.mainloop()


def main():
    app = ServerLauncher()
    app.run()


if __name__ == '__main__':
    main()
