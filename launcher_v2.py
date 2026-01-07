#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上集計システム - ランチャー V2 (Hybrid Pro)

Hybrid Proデザインのサーバー起動・停止管理アプリケーション
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

# パス設定
BASE_DIR = Path(__file__).parent
APP_DIR = BASE_DIR / 'app'
CONFIG_FILE = BASE_DIR / 'launcher_config.json'

# デフォルト設定
DEFAULT_CONFIG = {
    'api_port': 8080,
    'dashboard_port': 8000,
}


class ServerLauncher:
    """サーバーランチャー Hybrid Pro"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title('スクールフォト 売上集計システム - Launcher V2')
        self.root.geometry('700x600')
        self.root.resizable(False, False)

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
        # スタイル設定
        style = ttk.Style()
        style.theme_use('clam')

        # メインフレーム
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ヘッダー
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))

        title_label = ttk.Label(
            header_frame,
            text='School Photo System',
            font=('Meiryo', 18, 'bold'),
        )
        title_label.pack(side=tk.LEFT)

        # カードエリア
        cards_frame = ttk.Frame(main_frame)
        cards_frame.pack(fill=tk.BOTH, pady=10)

        # APIサーバーカード
        self._create_api_card(cards_frame)

        # 公開サーバーカード
        self._create_dashboard_card(cards_frame)

        # ログパネル
        self._create_log_panel(main_frame)

    def _create_api_card(self, parent):
        """APIサーバーカード作成"""
        card = ttk.LabelFrame(parent, text='API Server', padding=15)
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # ステータス
        status_frame = ttk.Frame(card)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.api_status_indicator = tk.Canvas(
            status_frame, width=12, height=12, highlightthickness=0
        )
        self.api_status_indicator.pack(side=tk.LEFT, padx=(0, 8))
        self._draw_status_indicator(self.api_status_indicator, False)

        self.api_status_label = ttk.Label(
            status_frame, text='Offline', font=('Meiryo', 10, 'bold')
        )
        self.api_status_label.pack(side=tk.LEFT)

        # ポート設定
        port_frame = ttk.Frame(card)
        port_frame.pack(fill=tk.X, pady=10)

        ttk.Label(port_frame, text='Port:', font=('Meiryo', 9)).pack(side=tk.LEFT, padx=(0, 5))
        self.api_port_var = tk.StringVar(value=str(self.config['api_port']))
        api_port_entry = ttk.Entry(port_frame, textvariable=self.api_port_var, width=8, font=('Consolas', 10))
        api_port_entry.pack(side=tk.LEFT)

        # ボタン
        btn_frame = ttk.Frame(card)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.api_start_btn = ttk.Button(
            btn_frame, text='起動', command=self._start_api, width=10
        )
        self.api_start_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.api_stop_btn = ttk.Button(
            btn_frame, text='停止', command=self._stop_api, width=10, state=tk.DISABLED
        )
        self.api_stop_btn.pack(side=tk.LEFT)

    def _create_dashboard_card(self, parent):
        """公開サーバーカード作成"""
        card = ttk.LabelFrame(parent, text='Public Dashboard', padding=15)
        card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ステータス
        status_frame = ttk.Frame(card)
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.dashboard_status_indicator = tk.Canvas(
            status_frame, width=12, height=12, highlightthickness=0
        )
        self.dashboard_status_indicator.pack(side=tk.LEFT, padx=(0, 8))
        self._draw_status_indicator(self.dashboard_status_indicator, False)

        self.dashboard_status_label = ttk.Label(
            status_frame, text='Offline', font=('Meiryo', 10, 'bold')
        )
        self.dashboard_status_label.pack(side=tk.LEFT)

        # ポート設定
        port_frame = ttk.Frame(card)
        port_frame.pack(fill=tk.X, pady=10)

        ttk.Label(port_frame, text='Port:', font=('Meiryo', 9)).pack(side=tk.LEFT, padx=(0, 5))
        self.dashboard_port_var = tk.StringVar(value=str(self.config['dashboard_port']))
        dashboard_port_entry = ttk.Entry(port_frame, textvariable=self.dashboard_port_var, width=8, font=('Consolas', 10))
        dashboard_port_entry.pack(side=tk.LEFT)

        # ボタン
        btn_frame = ttk.Frame(card)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.dashboard_start_btn = ttk.Button(
            btn_frame, text='起動', command=self._start_dashboard, width=10
        )
        self.dashboard_start_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.dashboard_stop_btn = ttk.Button(
            btn_frame, text='停止', command=self._stop_dashboard, width=10, state=tk.DISABLED
        )
        self.dashboard_stop_btn.pack(side=tk.LEFT)

    def _create_log_panel(self, parent):
        """ログパネル作成"""
        log_frame = ttk.LabelFrame(parent, text='System Log', padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(20, 0))

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=10, font=('Consolas', 8), state=tk.DISABLED, wrap=tk.WORD
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

    def _draw_status_indicator(self, canvas, is_running):
        """ステータスインジケーターを描画"""
        canvas.delete('all')
        color = '#10b981' if is_running else '#ef4444'
        canvas.create_oval(2, 2, 10, 10, fill=color, outline='')

    def _log(self, message):
        """ログを追加"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f'[{timestamp}] {message}\n')
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _start_api(self):
        """APIサーバーを起動"""
        if self.api_running:
            return

        try:
            port = int(self.api_port_var.get())
        except ValueError:
            messagebox.showerror('エラー', 'ポート番号は数値で入力してください')
            return

        self._save_config()
        self._log(f'APIサーバーを起動中... (ポート: {port})')

        def run_server():
            try:
                script_path = APP_DIR / 'run.py'
                self.api_process = subprocess.Popen(
                    [sys.executable, str(script_path), '--port', str(port)],
                    cwd=str(APP_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                self.api_running = True
                self.root.after(0, self._update_api_ui_running)
                self._log(f'APIサーバー起動完了: http://127.0.0.1:{port}')

                # ログ読み込み
                for line in self.api_process.stdout:
                    self.root.after(0, lambda l=line: self._log(f'[API] {l.strip()}'))

            except Exception as e:
                self.root.after(0, lambda: self._log(f'APIサーバー起動エラー: {e}'))
                self.root.after(0, self._update_api_ui_stopped)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

    def _stop_api(self):
        """APIサーバーを停止"""
        if not self.api_running:
            return

        self._log('APIサーバーを停止中...')
        try:
            if self.api_process:
                self.api_process.terminate()
                self.api_process.wait(timeout=5)
                self.api_process = None
        except Exception as e:
            self._log(f'停止エラー: {e}')
            if self.api_process:
                self.api_process.kill()
                self.api_process = None

        self.api_running = False
        self._update_api_ui_stopped()
        self._log('APIサーバー停止完了')

    def _start_dashboard(self):
        """公開サーバーを起動"""
        if self.dashboard_running:
            return

        try:
            port = int(self.dashboard_port_var.get())
        except ValueError:
            messagebox.showerror('エラー', 'ポート番号は数値で入力してください')
            return

        self._save_config()
        self._log(f'公開サーバーを起動中... (ポート: {port})')

        def run_server():
            try:
                script_path = APP_DIR / 'simple_server.py'
                self.dashboard_process = subprocess.Popen(
                    [sys.executable, str(script_path), '--port', str(port)],
                    cwd=str(APP_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                self.dashboard_running = True
                self.root.after(0, self._update_dashboard_ui_running)
                self._log(f'公開サーバー起動完了: http://localhost:{port}')

                # ログ読み込み
                for line in self.dashboard_process.stdout:
                    self.root.after(0, lambda l=line: self._log(f'[Dashboard] {l.strip()}'))

            except Exception as e:
                self.root.after(0, lambda: self._log(f'公開サーバー起動エラー: {e}'))
                self.root.after(0, self._update_dashboard_ui_stopped)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

    def _stop_dashboard(self):
        """公開サーバーを停止"""
        if not self.dashboard_running:
            return

        self._log('公開サーバーを停止中...')
        try:
            if self.dashboard_process:
                self.dashboard_process.terminate()
                self.dashboard_process.wait(timeout=5)
                self.dashboard_process = None
        except Exception as e:
            self._log(f'停止エラー: {e}')
            if self.dashboard_process:
                self.dashboard_process.kill()
                self.dashboard_process = None

        self.dashboard_running = False
        self._update_dashboard_ui_stopped()
        self._log('公開サーバー停止完了')

    def _update_api_ui_running(self):
        """API UI更新: 実行中"""
        self._draw_status_indicator(self.api_status_indicator, True)
        self.api_status_label.config(text='Online', foreground='#10b981')
        self.api_start_btn.config(state=tk.DISABLED)
        self.api_stop_btn.config(state=tk.NORMAL)

    def _update_api_ui_stopped(self):
        """API UI更新: 停止中"""
        self._draw_status_indicator(self.api_status_indicator, False)
        self.api_status_label.config(text='Offline', foreground='#ef4444')
        self.api_start_btn.config(state=tk.NORMAL)
        self.api_stop_btn.config(state=tk.DISABLED)

    def _update_dashboard_ui_running(self):
        """公開サーバー UI更新: 実行中"""
        self._draw_status_indicator(self.dashboard_status_indicator, True)
        self.dashboard_status_label.config(text='Online', foreground='#10b981')
        self.dashboard_start_btn.config(state=tk.DISABLED)
        self.dashboard_stop_btn.config(state=tk.NORMAL)

    def _update_dashboard_ui_stopped(self):
        """公開サーバー UI更新: 停止中"""
        self._draw_status_indicator(self.dashboard_status_indicator, False)
        self.dashboard_status_label.config(text='Offline', foreground='#ef4444')
        self.dashboard_start_btn.config(state=tk.NORMAL)
        self.dashboard_stop_btn.config(state=tk.DISABLED)

    def _on_closing(self):
        """ウィンドウを閉じる時の処理"""
        if self.api_running or self.dashboard_running:
            if messagebox.askyesno(
                '確認',
                'サーバーが実行中です。\n停止してから終了しますか？'
            ):
                if self.api_running:
                    self._stop_api()
                if self.dashboard_running:
                    self._stop_dashboard()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        """アプリケーションを実行"""
        self._log('Launcher V2 起動完了')
        self.root.mainloop()


def main():
    app = ServerLauncher()
    app.run()


if __name__ == '__main__':
    main()
