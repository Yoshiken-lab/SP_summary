#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
スクールフォト売上集計システム - ランチャー

サーバーの起動・停止をGUIで行うためのアプリケーション
"""

import sys
import os
import subprocess
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# 実行ファイルのディレクトリを基準にする
if getattr(sys, 'frozen', False):
    # exe実行時
    BASE_DIR = Path(sys.executable).parent
else:
    # 通常のPython実行時
    BASE_DIR = Path(__file__).parent

# サーバー設定
SERVER_HOST = '127.0.0.1'
DEFAULT_PORT = 8089
PORT_OPTIONS = [8080, 8089, 8888, 3000, 5000]


class ServerLauncher:
    """サーバーランチャーGUI"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title('スクールフォト 売上集計システム')
        self.root.geometry('400x380')
        self.root.resizable(False, False)

        # アイコン設定（あれば）
        icon_path = BASE_DIR / 'icon.ico'
        if icon_path.exists():
            self.root.iconbitmap(str(icon_path))

        self.server_process = None
        self.is_running = False
        self.current_port = DEFAULT_PORT

        self._setup_ui()
        self._center_window()

        # 閉じるボタンの処理
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_ui(self):
        """UIをセットアップ"""
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # タイトル
        title_label = ttk.Label(
            main_frame,
            text='スクールフォト\n売上集計システム',
            font=('Meiryo', 16, 'bold'),
            justify=tk.CENTER
        )
        title_label.pack(pady=(0, 20))

        # ステータス表示
        self.status_frame = ttk.Frame(main_frame)
        self.status_frame.pack(fill=tk.X, pady=10)

        self.status_indicator = tk.Canvas(
            self.status_frame, width=16, height=16,
            highlightthickness=0
        )
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 8))
        self._draw_status_indicator(False)

        self.status_label = ttk.Label(
            self.status_frame,
            text='サーバー停止中',
            font=('Meiryo', 10)
        )
        self.status_label.pack(side=tk.LEFT)

        # ポート選択
        port_frame = ttk.Frame(main_frame)
        port_frame.pack(fill=tk.X, pady=10)

        port_label = ttk.Label(
            port_frame,
            text='ポート:',
            font=('Meiryo', 10)
        )
        port_label.pack(side=tk.LEFT, padx=(0, 8))

        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.port_combo = ttk.Combobox(
            port_frame,
            textvariable=self.port_var,
            values=[str(p) for p in PORT_OPTIONS],
            width=8,
            font=('Consolas', 10)
        )
        self.port_combo.pack(side=tk.LEFT)
        self.port_combo.bind('<<ComboboxSelected>>', self._on_port_change)
        self.port_combo.bind('<Return>', self._on_port_change)
        self.port_combo.bind('<FocusOut>', self._on_port_change)

        # URL表示
        self.url_frame = ttk.Frame(main_frame)
        self.url_frame.pack(fill=tk.X, pady=5)

        self.url_label = ttk.Label(
            self.url_frame,
            text=f'URL: http://{SERVER_HOST}:{self.current_port}',
            font=('Consolas', 9),
            foreground='gray'
        )
        self.url_label.pack()

        # ボタンフレーム
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        # スタイル設定
        style = ttk.Style()
        style.configure('Start.TButton', font=('Meiryo', 11))
        style.configure('Stop.TButton', font=('Meiryo', 11))
        style.configure('Open.TButton', font=('Meiryo', 10))

        # 起動ボタン
        self.start_btn = ttk.Button(
            button_frame,
            text='▶ サーバー起動',
            style='Start.TButton',
            command=self._start_server,
            width=15
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        # 停止ボタン
        self.stop_btn = ttk.Button(
            button_frame,
            text='■ サーバー停止',
            style='Stop.TButton',
            command=self._stop_server,
            width=15,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # ブラウザで開くボタン
        self.open_btn = ttk.Button(
            main_frame,
            text='🌐 ブラウザで開く',
            style='Open.TButton',
            command=self._open_browser,
            state=tk.DISABLED
        )
        self.open_btn.pack(pady=10)

        # ログ表示エリア
        log_frame = ttk.LabelFrame(main_frame, text='ログ', padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.log_text = tk.Text(
            log_frame, height=4, font=('Consolas', 8),
            state=tk.DISABLED, wrap=tk.WORD
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

    def _draw_status_indicator(self, is_running):
        """ステータスインジケーターを描画"""
        self.status_indicator.delete('all')
        color = '#10b981' if is_running else '#ef4444'
        self.status_indicator.create_oval(2, 2, 14, 14, fill=color, outline='')

    def _on_port_change(self, event=None):
        """ポート変更時の処理"""
        try:
            port = int(self.port_var.get())
            if 1024 <= port <= 65535:
                self.current_port = port
                self._update_url_display()
            else:
                messagebox.showwarning('警告', 'ポートは1024〜65535の範囲で指定してください')
                self.port_var.set(str(self.current_port))
        except ValueError:
            messagebox.showwarning('警告', 'ポートは数値で入力してください')
            self.port_var.set(str(self.current_port))

    def _update_url_display(self):
        """URL表示を更新"""
        url = f'http://{SERVER_HOST}:{self.current_port}'
        self.url_label.config(text=f'URL: {url}')

    def _log(self, message):
        """ログを追加"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f'{message}\n')
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _start_server(self):
        """サーバーを起動"""
        if self.is_running:
            return

        # 起動中はポート変更を無効化
        self.port_combo.config(state=tk.DISABLED)
        self._log(f'サーバーを起動中... (ポート: {self.current_port})')

        def run_server():
            try:
                # run_server.pyを実行
                server_script = BASE_DIR / 'run_server.py'
                port_arg = ['--port', str(self.current_port)]

                # Python実行パスを決定
                if getattr(sys, 'frozen', False):
                    # exe実行時
                    os.chdir(str(BASE_DIR))
                    sys.path.insert(0, str(BASE_DIR))

                    # サーバーを別プロセスで起動
                    self.server_process = subprocess.Popen(
                        [sys.executable, str(server_script)] + port_arg,
                        cwd=str(BASE_DIR),
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                else:
                    # 開発時
                    self.server_process = subprocess.Popen(
                        [sys.executable, str(server_script)] + port_arg,
                        cwd=str(BASE_DIR)
                    )

                self.is_running = True
                self.root.after(0, self._update_ui_running)
                server_url = f'http://{SERVER_HOST}:{self.current_port}'
                self._log(f'サーバー起動完了: {server_url}')

            except Exception as e:
                self.root.after(0, lambda: self._log(f'エラー: {e}'))
                self.root.after(0, self._update_ui_stopped)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

    def _stop_server(self):
        """サーバーを停止"""
        if not self.is_running:
            return

        self._log('サーバーを停止中...')

        try:
            if self.server_process:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
                self.server_process = None
        except Exception as e:
            self._log(f'停止エラー: {e}')
            if self.server_process:
                self.server_process.kill()
                self.server_process = None

        self.is_running = False
        self._update_ui_stopped()
        self._log('サーバー停止完了')

    def _update_ui_running(self):
        """UI更新: サーバー実行中"""
        self._draw_status_indicator(True)
        self.status_label.config(text='サーバー実行中')
        self.url_label.config(foreground='#2563eb')
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.open_btn.config(state=tk.NORMAL)

    def _update_ui_stopped(self):
        """UI更新: サーバー停止中"""
        self._draw_status_indicator(False)
        self.status_label.config(text='サーバー停止中')
        self.url_label.config(foreground='gray')
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.open_btn.config(state=tk.DISABLED)
        self.port_combo.config(state='readonly')

    def _open_browser(self):
        """ブラウザでアプリを開く"""
        server_url = f'http://{SERVER_HOST}:{self.current_port}'
        webbrowser.open(server_url)

    def _on_closing(self):
        """ウィンドウを閉じる時の処理"""
        if self.is_running:
            if messagebox.askyesno(
                '確認',
                'サーバーが実行中です。\n停止してから終了しますか？'
            ):
                self._stop_server()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        """アプリケーションを実行"""
        self.root.mainloop()


def main():
    app = ServerLauncher()
    app.run()


if __name__ == '__main__':
    main()
