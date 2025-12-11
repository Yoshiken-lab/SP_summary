# スクールフォト 売上集計システム

SP_sales_ver1.1の集計機能とダッシュボードを統合したWebアプリケーションです。

## 機能

- **ファイルアップロード**: 売上CSV、会員CSV、担当者マスタXLSXを読み込み
- **売上集計**: 全体、事業所別、担当者別、イベント別の売上を集計
- **会員率計算**: 学校ごとの会員率を計算
- **Excel出力**: 集計結果をExcelファイルで出力
- **DB保存**: 既存のダッシュボードシステムと連携
- **ダッシュボード公開**: HTMLダッシュボードを自動生成・公開

## インストール

### 1. 依存パッケージのインストール

```bash
cd app
pip install -r requirements.txt
```

### 2. フロントエンドのビルド（オプション）

```bash
cd frontend
npm install
npm run build
```

## 起動方法

### 簡単起動（Windows）

`start.bat` をダブルクリックするだけで起動できます。

### コマンドラインから起動

```bash
# デフォルト（ポート8080）
python run.py

# ポート指定
python run.py --port 9000

# デバッグモード
python run.py --debug
```

### 環境変数で設定

```bash
set PORT=9000
set HOST=0.0.0.0
python run.py
```

## 開発モード

フロントエンドをホットリロードで開発する場合：

```bash
# start_dev.bat を実行するか、以下を実行

# ターミナル1: Flask API
python run.py --port 8080 --debug

# ターミナル2: Vite開発サーバー
cd frontend
npm run dev
```

## ディレクトリ構成

```
app/
├── run.py                 # 起動スクリプト
├── config.py              # 設定ファイル
├── requirements.txt       # Python依存パッケージ
├── start.bat              # Windows起動スクリプト
├── start_dev.bat          # 開発用起動スクリプト
│
├── backend/               # Flask API
│   ├── api.py             # APIエンドポイント
│   ├── aggregator/        # 集計ロジック
│   │   ├── sales.py       # 売上集計
│   │   ├── summary.py     # 全体集計
│   │   ├── accounts.py    # 会員率計算
│   │   └── excel_output.py# Excel出力
│   └── services/          # サービス層
│       ├── file_handler.py# ファイル処理
│       └── db_service.py  # DB操作
│
└── frontend/              # Vue.js フロントエンド
    ├── src/
    │   ├── App.vue        # メインコンポーネント
    │   └── style.css      # スタイル
    ├── package.json
    └── vite.config.js
```

## API仕様

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/health` | ヘルスチェック |
| POST | `/api/upload` | ファイルアップロード |
| POST | `/api/aggregate` | 集計実行 |
| GET | `/api/download/{session_id}` | Excelダウンロード |
| POST | `/api/save-db` | DB保存 |
| POST | `/api/publish` | ダッシュボード公開 |
| GET | `/api/config` | 設定取得 |

## 設定

`config.py` で以下の設定が可能です：

- `PORT`: サーバーポート（デフォルト: 8080）
- `HOST`: ホストアドレス（デフォルト: 127.0.0.1）
- `OUTPUT_DIR`: Excel出力先（デフォルト: ~/Downloads）
- `PUBLISH_PATH`: ダッシュボード公開先

## トラブルシューティング

### ポートが使用中の場合

```bash
python run.py --port 9000
```

### 文字化けが発生する場合

CSVファイルのエンコーディングがCP932（Shift_JIS）であることを確認してください。

### ファイルアップロードエラー

- ファイルサイズが16MB以下であることを確認
- ファイル形式（CSV/XLSX）が正しいことを確認
