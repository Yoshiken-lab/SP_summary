# スクールフォト 売上集計システム - ユーザーマニュアル

## 目次
1. [システム概要](#システム概要)
2. [起動方法](#起動方法)
3. [WEBアプリケーション操作方法](#webアプリケーション操作方法)
4. [データベース操作](#データベース操作)
5. [トラブルシューティング](#トラブルシューティング)

---

## システム概要

### 主な機能
1. **月次集計** - CSVデータから月次報告書（Excel）を作成
2. **累積集計** - 複数の月次報告書から年度累積報告書を作成
3. **実績反映** - 報告書をデータベースに反映し、ダッシュボードを自動生成
4. **データベース確認** - 保存されたデータの検索・CSV出力

### 技術構成
- **フロントエンド**: Vue.js 3 + Vite (ポート: 5173)
- **バックエンド**: Flask (ポート: 8081)
- **データベース**: SQLite (`schoolphoto_v2.db`)
- **ダッシュボード**: 静的HTML (Plotly.js使用)

---

## 起動方法

### 前提条件
- Python 3.8以上
- Node.js 16以上
- 必要なパッケージがインストール済み

### 1. バックエンド（Flask）の起動

```powershell
# プロジェクトルートに移動
cd C:\Users\admin\Documents\06-Python\SP_summary

# Flaskサーバーを起動（8081ポート）
cd app
python run.py --port 8081
```

**正常起動時のログ:**
```
============================================================
  スクールフォト 売上集計システム
============================================================
  サーバー起動中...
  URL: http://127.0.0.1:8081

  停止するには Ctrl+C を押してください
============================================================
```

### 2. フロントエンド（Vue）の起動

**新しいターミナルを開いて:**

```powershell
# フロントエンドディレクトリに移動
cd C:\Users\admin\Documents\06-Python\SP_summary\app\frontend

# 開発サーバーを起動
npm run dev
```

**正常起動時のログ:**
```
VITE v4.x.x  ready in xxx ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

### 3. ブラウザでアクセス

```
http://localhost:5173/
```

---

## WEBアプリケーション操作方法

### 月次集計

#### 機能概要
CSVファイル（売上・口座振替）とXLSXファイル（価格マスタ）から月次報告書を作成します。

#### 操作手順

1. **STEP 1: ファイル選択**
   - **売上CSVファイル**: ドラッグ&ドロップまたはクリックして選択
   - **口座振替CSVファイル**: 同様に選択
   - **価格マスタXLSXファイル**: 同様に選択

2. **STEP 2: 対象期間の設定**
   - **会計年度**: プルダウンから選択
   - **会計月**: プルダウンから選択

3. **集計を実行**
   - 「集計を実行」ボタンをクリック
   - 進捗が表示されます
   - 完了後、自動的にExcelファイルがダウンロードされます

#### 生成されるファイル
```
SP_月次集計_YYYY年M月.xlsx
```

**ファイルの場所**: ブラウザのダウンロードフォルダ

---

### 累積集計

#### 機能概要
複数の月次報告書から年度の累積報告書を作成します。

#### 操作手順

1. **STEP 1: 月次集計ファイルを追加**
   - 複数の月次報告書（ExcelファイルをドラッグSP_月次集計_*.xlsx`）をドラッグ&ドロップ

2. **STEP 2: 追加されたファイルを確認**
   - ファイルごとに対象年月（例: 2024年4月）を選択
   - 不要なファイルは「削除」ボタンで除外

3. **STEP 3: 既存の累積ファイル（オプション）**
   - 既に作成済みの累積ファイルがある場合、アップロード可能
   - 空欄でもOK

4. **集計を実行**
   - 「累積集計を実行」ボタンをクリック
   - 完了後、Excelファイルが自動ダウンロード

#### 生成されるファイル
```
SP_年度累計_YYYY.xlsx
```

**対象年度の計算**: 選択した月から自動判定（4月〜翌年3月）

---

### 実績反映

#### 機能概要
作成した報告書をデータベースに保存し、ダッシュボードを自動生成します。

#### 操作手順

##### STEP 1: データ反映

1. **報告書のアップロード**
   - 月次報告書または累積報告書をドラップ&ドロップ
   - 複数ファイル同時アップロード可能

2. **実績を反映**
   - 「実績を反映 (N件)」ボタンをクリック
   - 重複データがある場合、確認ダイアログが表示されます
   - 「はい」を選択すると上書き保存されます

3. **完了確認**
   - 処理完了後、以下の統計が表示されます:
     - 学校別売上データ: XX件
     - 月別サマリーデータ: XX件
     - イベント別売上データ: XX件

##### STEP 2: 担当者設定（オプション）

**担当者名の変換**
- 同一人物で担当者名が異なる場合の変換ルールを設定
- 例: 「佐藤」→「佐藤（邦）」

**学校担当者の変更**
- 特定の学校・期間の担当者を変更
- 既存の売上データも自動更新されます

##### STEP 3: ダッシュボード公開

実績反映後、**自動的にダッシュボードが生成**されます。

**確認事項:**
- 最終生成日時
- ファイルパス
- 生成状態（成功/失敗）

**操作:**
1. **プレビュー**: ダッシュボードをブラウザで表示
2. **社内サーバーに公開**: 指定のサーバーにアップロード（設定が必要）

---

### データベース確認

#### 機能概要
データベースに保存された各種データを検索・確認・CSV出力できます。

#### 操作手順

1. **STEP 1: 確認するデータを選択**
   - 月別サマリー
   - 学校別売上
   - イベント別売上
   - 会員率

2. **STEP 2: 検索条件**
   - 年度
   - 月
   - 事業所
   - 担当者
   - 学校名（部分一致）
   - イベント開始日（イベント別売上のみ）

3. **検索**
   - 「検索」ボタンをクリック
   - 結果が表示されます（50件/ページ）

4. **CSVダウンロード**
   - 「CSVダウンロード」ボタンで全件出力
   - 現在の検索条件が適用されます

---

## データベース操作

### データベースファイル

**メインDB:**
```
C:\Users\admin\Documents\06-Python\SP_summary\schoolphoto_v2.db
```

### バックアップの取得

#### 手動バックアップ（推奨）

**方法1: ファイルコピー**

```powershell
# プロジェクトルートに移動
cd C:\Users\admin\Documents\06-Python\SP_summary

# 日付付きバックアップを作成
$date = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item schoolphoto_v2.db "schoolphoto_v2_backup_$date.db"
```

**バックアップファイル例:**
```
schoolphoto_v2_backup_20260106_120000.db
```

**方法2: SQLiteコマンド使用**

```powershell
# SQLite3がインストールされている場合
sqlite3 schoolphoto_v2.db ".backup 'schoolphoto_v2_backup.db'"
```

#### 定期バックアップ（自動化）

**Windows タスクスケジューラを使用:**

1. バックアップスクリプトを作成 (`backup_db.ps1`):

```powershell
# backup_db.ps1
$date = Get-Date -Format "yyyyMMdd"
$source = "C:\Users\admin\Documents\06-Python\SP_summary\schoolphoto_v2.db"
$backup_dir = "C:\Users\admin\Documents\06-Python\SP_summary\backups"
$destination = "$backup_dir\schoolphoto_v2_backup_$date.db"

# バックアップディレクトリを作成（存在しない場合）
if (-not (Test-Path $backup_dir)) {
    New-Item -ItemType Directory -Path $backup_dir
}

# バックアップ実行
Copy-Item $source $destination -Force

# 30日前のバックアップを削除
$limit = (Get-Date).AddDays(-30)
Get-ChildItem $backup_dir -Filter "schoolphoto_v2_backup_*.db" | 
    Where-Object { $_.LastWriteTime -lt $limit } | 
    Remove-Item
```

2. タスクスケジューラで毎日実行するように設定

---

### バックアップからの復元

#### 注意事項
⚠️ **復元前に必ず現在のDBをバックアップしてください**

#### 手順

```powershell
# 1. 現在のDBをバックアップ
cd C:\Users\admin\Documents\06-Python\SP_summary
$date = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item schoolphoto_v2.db "schoolphoto_v2_before_restore_$date.db"

# 2. Flaskサーバーを停止（Ctrl+C）

# 3. バックアップファイルから復元
Copy-Item schoolphoto_v2_backup_YYYYMMDD_HHMMSS.db schoolphoto_v2.db -Force

# 4. Flaskサーバーを再起動
cd app
python run.py --port 8081
```

---

### データの完全消去

#### ⚠️ 重要な警告
- **この操作は取り消しできません**
- 必ず事前にバックアップを取得してください

#### 方法1: 特定テーブルのデータ削除

```powershell
# SQLite3を使用
sqlite3 schoolphoto_v2.db

# SQLiteプロンプトで実行
DELETE FROM school_sales;
DELETE FROM monthly_summary;
DELETE FROM event_sales;
DELETE FROM member_rates;

# 変更を保存して終了
.quit
```

#### 方法2: データベース全体の再作成

```powershell
# 1. バックアップ作成
Copy-Item schoolphoto_v2.db schoolphoto_v2_backup_before_reset.db

# 2. 既存DBを削除
Remove-Item schoolphoto_v2.db

# 3. Flaskサーバーを起動（自動的に新しいDBが作成されます）
cd app
python run.py --port 8081
```

---

### データのエクスポート

#### CSV形式でエクスポート

**WEBアプリから:**
1. 「データベース確認」メニューを開く
2. 検索条件を設定
3. 「CSVダウンロード」ボタンをクリック

**SQLiteコマンドから:**

```powershell
sqlite3 schoolphoto_v2.db

# CSVモードに切り替え
.mode csv
.headers on

# 出力先を指定
.output school_sales_export.csv
SELECT * FROM school_sales;
.output stdout

.quit
```

---

### データのインポート

#### 報告書からのインポート

**WEBアプリから:**
1. 「実績反映」メニューを開く
2. 報告書（Excel）をアップロード
3. 「実績を反映」をクリック

**コマンドラインから:**

```powershell
cd C:\Users\admin\Documents\06-Python\SP_summary

# 単一ファイルのインポート
python -c "from importer_v2 import import_excel_v2; import_excel_v2('報告書.xlsx', 'schoolphoto_v2.db')"
```

---

## トラブルシューティング

### 起動時のエラー

#### エラー: `Port 8081 is already in use`

**原因**: 既に別のFlaskサーバーが起動している

**解決方法:**
```powershell
# プロセスを確認
Get-Process | Where-Object {$_.ProcessName -like "*python*"}

# プロセスを終了
Stop-Process -Name python -Force

# サーバーを再起動
cd app
python run.py --port 8081
```

#### エラー: `ECONNREFUSED 127.0.0.1:8081`

**原因**: フロントエンドが起動しているが、バックエンドが起動していない

**解決方法:**
1. Flaskサーバー（8081ポート）が起動しているか確認
2. 起動していない場合、上記の「バックエンドの起動」手順を実行

---

### 集計処理のエラー

#### エラー: `ファイル形式が正しくありません`

**原因**: CSVファイルのエンコーディングまたは形式が不正

**解決方法:**
- CSVファイルを`Shift-JIS`エンコーディングで保存
- 列名が正しいか確認（売上CSV: `撮影番号`, `学校名`, `撮影日` など）

#### エラー: `担当者マスタ不一致`

**原因**: エクセル上の担当者名とCSVの担当者名が一致しない

**解決方法:**
1. 「実績反映」→「担当者設定」→「担当者名の変換」で変換ルールを追加
2. または、Excelファイルの列名を確認・修正

---

### ダッシュボード生成のエラー

#### ダッシュボードが生成されない

**確認事項:**
1. Flaskサーバーのコンソールログを確認
2. データベースにデータが存在するか確認:
   ```powershell
   sqlite3 schoolphoto_v2.db
   SELECT COUNT(*) FROM school_sales;
   .quit
   ```

**手動でダッシュボードを再生成:**
```powershell
cd C:\Users\admin\Documents\06-Python\SP_summary
python dashboard_v2.py
```

---

### データベース破損

#### 症状
- `database disk image is malformed` エラー
- データが正しく表示されない

#### 解決方法

**方法1: SQLite整合性チェック**
```powershell
sqlite3 schoolphoto_v2.db "PRAGMA integrity_check;"
```

**方法2: バックアップから復元**
上記の「バックアップからの復元」手順を参照

**方法3: ダンプ＆リストア**
```powershell
# データをダンプ
sqlite3 schoolphoto_v2.db .dump > backup.sql

# 新しいDBを作成しリストア
sqlite3 schoolphoto_v2_new.db < backup.sql

# 古いDBをリネーム
Move-Item schoolphoto_v2.db schoolphoto_v2_corrupted.db
Move-Item schoolphoto_v2_new.db schoolphoto_v2.db
```

---

## 付録

### よく使うSQLクエリ

#### データ件数の確認
```sql
-- 各テーブルのレコード数
SELECT 'school_sales' AS table_name, COUNT(*) AS count FROM school_sales
UNION ALL
SELECT 'monthly_summary', COUNT(*) FROM monthly_summary
UNION ALL
SELECT 'event_sales', COUNT(*) FROM event_sales
UNION ALL
SELECT 'member_rates', COUNT(*) FROM member_rates;
```

#### 最新のデータ確認
```sql
-- 最新の報告書ID
SELECT MAX(report_id) FROM reports;

-- 最新の月次データ
SELECT * FROM monthly_summary 
ORDER BY fiscal_year DESC, month DESC 
LIMIT 10;
```

#### 特定年度のデータ削除
```sql
-- 2023年度のデータを削除
DELETE FROM school_sales WHERE fiscal_year = 2023;
DELETE FROM monthly_summary WHERE fiscal_year = 2023;
DELETE FROM event_sales WHERE fiscal_year = 2023;
```

---

### システム要件

#### 推奨スペック
- **OS**: Windows 10/11
- **CPU**: 2コア以上
- **メモリ**: 4GB以上
- **ストレージ**: 500MB以上の空き容量

#### 必要なソフトウェア
- Python 3.8以上
- Node.js 16以上
- SQLite3（オプション、コマンドライン操作用）

---

### お問い合わせ

システムに関する質問やバグ報告は、開発担当者までご連絡ください。

**作成日**: 2026年1月6日  
**バージョン**: 1.0
