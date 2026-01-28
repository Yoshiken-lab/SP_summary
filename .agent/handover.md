# スクールフォトダッシュボード開発 引き継ぎドキュメント

**最終更新**: 2026-01-05  
**プロジェクト**: スクールフォト売上分析ダッシュボード V2  
**開発者**: Antigravity AI + はるきち

---

## 📋 プロジェクト概要

スクールフォト事業の売上・会員率・イベントデータを可視化・分析するWebダッシュボードシステム。
Excelファイルからデータをインポートし、SQLiteデータベースで管理、HTMLダッシュボードで表示。

### 主要技術スタック
- **バックエンド**: Python 3.x, SQLite3
- **フロントエンド**: HTML, CSS (Vanilla), JavaScript (Vanilla), Chart.js
- **データ処理**: pandas, openpyxl

---

## 📁 主要ファイル構成

### コアファイル

#### `database_v2.py`
- **役割**: データベーススキーマ定義、CRUD操作、集計クエリ
- **重要な関数**:
  - `init_database()`: DB初期化、テーブル作成
  - `get_rapid_growth_schools()`: 売上好調校取得
  - `get_new_schools()`: 新規開始校取得
  - `get_no_events_schools()`: 今年度未実施校取得
  - `get_decline_schools()`: 会員率・売上低下校取得
  - `get_events_for_date_filter()`: イベント開始日別データ取得（過去3年分）

#### `dashboard_v2.py`
- **役割**: HTMLダッシュボード生成
- **主要機能**:
  - 売上サマリーカード表示
  - 月別・事業所別・担当者別グラフ（Chart.js）
  - 学校別分析（会員率推移、売上推移）
  - 条件別集計セクション（売上好調校、新規開始校、未実施校、低下校、イベント開始日別売上）
- **重要な設計**:
  - f-string内でJavaScriptを生成（`{{` `}}`でエスケープ必須）
  - データはPythonでJSON化してJavaScript変数として埋め込み

#### `importer_v2.py`
- **役割**: Excelファイルからデータインポート
- **処理フロー**:
  1. 学校名の正規化（`SCHOOL_NAME_MAPPINGS`）
  2. 年度・月情報の抽出
  3. reports, schools_master, member_rates, event_salesテーブルへ挿入
- **注意点**: 同じ日付のレポートは上書き（DELETE → INSERT）

#### `member_rate_page.py`
- **役割**: 会員率推移グラフの専用ページ生成
- **特徴**: 全学校の会員率を時系列でグラフ化

---

## ✅ 実装済み機能

### フェーズ1: 基本4種類の条件別集計（完了）

#### 1. 売上好調校 (rapid_growth)
- **条件**: 前年同期比+20%以上
- **表示項目**: 学校名、属性、事業所、今年度売上、前年度売上、成長率
- **ソート**: クライアントサイドソート対応

#### 2. 新規開始校 (new_schools)
- **条件**: 今年度に初めてイベントを実施
- **データベース修正**:
  - 初開催日ベースのロジック（`first_event_date`）
  - 日付フォーマット: `YYYY-MM-DD`
- **表示項目**: 学校名、属性、事業所、開始日、今年度売上
- **フィルター**: 年度選択、月選択（1-12月）
- **月フィルター機能**: `first_event_date`の月部分（substring 5-7）で絞り込み

#### 3. 今年度未実施校 (no_events)
- **条件**: 前年度はイベント実施したが今年度は未実施
- **データベース修正**:
  - `event_date`ベースのロジック（今年度のevent_dateが存在しない）
- **表示項目**: 学校名、属性、事業所、前年度イベント数、前年度売上
- **フィルター**: 年度選択

#### 4. 会員率・売上低下校 (decline)
- **条件**: 会員率 < 閾値 AND 売上変化率が指定範囲内
- **表示項目**: 学校名、属性、事業所、会員率、売上変化率、今年度売上、前年度売上
- **フィルター**: 会員率閾値（デフォルト30%）、売上変化率範囲（-10%〜-50%）
- **特徴**: クライアントサイドでのリアルタイムフィルタリング

### フェーズ2: イベント関連分析

#### 5. イベント開始日別売上 (event_sales_by_date) ✅ 完了
- **機能**: 年・月・日を指定してイベントを絞り込み表示
- **データ範囲**: 過去3年分（`years_back=3`）
- **データベース**:
  - 関数: `get_events_for_date_filter()`
  - JOIN: event_sales + schools_master + 会員率（latest_rates CTE）
  - ORDER BY: `event_date ASC`（昇順）
- **UI要素**:
  - 新カテゴリ「イベント関連」（紫色）
  - フィルター: 年（必須）、月（任意）、日（任意）
  - 「に公開したイベントを [表示する]」ボタン
- **表示項目**: 学校名、属性、事業所、イベント名、開始日、会員率、売上
- **カラム幅**: 学校名・イベント名を広く、属性・事業所を狭く調整済み
- **ソート**: クライアントサイドソート対応（YYYY-MM-DD形式認識）
- **初期表示**: 日付昇順（古い日付から表示）

**実装の経緯・トラブルシューティング**:
- セクション幅の問題: `.container`の外に配置→ `max-width: 1600px` + `margin: auto`で統一
- ソート問題: DBから降順で来ていた→ `ORDER BY ASC`に変更
- カラム幅問題: 合計100%超え→ 調整済み（18%+7%+9%+28%+11%+9%+9%+9%）
- padding問題: タイトル・タブがはみ出る→ 30px→20pxに削減

---

## 🚧 未実装機能

### フェーズ2: イベント関連分析（残り）

#### 年度別イベント比較 (yearly_comparison)
- **目的**: 同一イベント名の年度間比較
- **必要な実装**:
  - DB関数: 年度ごとのイベント売上を取得
  - UI: 年度選択フィルター
  - 表示: イベント名、各年度の売上、変化率

### フェーズ3: トレンド・詳細分析

- 写真館別低下 (studio_decline)
- 会員率改善校 (member_rate_trend)
- 売上単価分析 (unit_price)

---

## 🏗️ 重要な設計決定・パターン

### 1. データベース設計

#### テーブル構造
```sql
reports: レポートメタデータ（id, report_date, fiscal_year, month_name）
schools_master: 学校マスタ（school_id, school_name, attribute, region, studio, manager）
member_rates: 会員率データ（report_id, school_id, grade, member_count, total_students）
event_sales: イベント売上（report_id, school_id, event_date, event_name, sales, fiscal_year）
```

#### 年度（fiscal_year）の定義
- 4-3月が同じ年度
- 例: 2024年4月〜2025年3月 → 2024年度

### 2. JavaScript埋め込みパターン

dashboard_v2.pyのf-string内でJavaScript生成時:
```python
# ✅ 正しい（エスケープ必要）
html = f'''
    if (condition) {{
        const obj = {{ key: 'value' }};
    }}
'''

# ❌ 間違い（SyntaxError）
html = f'''
    if (condition) {
        const obj = { key: 'value' };
    }
'''
```

### 3. ソート機能の実装

#### クライアントサイドソート
- **状態管理**: `currentSort = { column: ..., order: ... }`
- **sortData関数**: 文字列、数値、日付を自動判別
  - YYYY-MM-DD: `new Date(val).getTime()`
  - YYYY年MM月DD日: 正規表現で変換
  - 数値: `parseFloat()` after カンマ削除
- **日付認識パターン**:
  ```javascript
  if (val.match(/^\d{4}-\d{2}-\d{2}$/)) {
      return new Date(val).getTime();
  }
  ```

### 4. レイアウト設計

#### セクション幅の統一
- `.container`: `max-width: 1600px; margin: 0 auto;`
- 条件別集計セクション: 同様の設定を適用

#### テーブル幅制御
- `table-layout: fixed` で幅を固定
- `<colgroup>` でカラムごとの幅を%指定
- 合計が100%になるよう調整

---

## 🐛 過去のトラブルとその解決

### 問題1: 新規開始校が正しく抽出されない
**原因**: `fiscal_year`ベースで判定していたが、イベント日がまたがるケース  
**解決**: `first_event_date`が今年度の範囲内かで判定に変更

### 問題2: 今年度未実施校が0件
**原因**: `sales`ベースで判定していたが、salesは累積値  
**解決**: `event_date`の存在で判定に変更

### 問題3: 学校名の重複（鰭ケ崎/鰭ヶ崎）
**原因**: 小文字の「ケ」と「ヶ」の表記揺れ  
**解決**: `SCHOOL_NAME_MAPPINGS`に追加

### 問題4: イベント開始日別売上のソートが効かない
**原因1**: DBが`ORDER BY DESC`で降順返却  
**解決1**: `ORDER BY ASC`に変更

**原因2**: sortData内でYYYY-MM-DD認識が不十分  
**解決2**: 正規表現パターン追加

### 問題5: セクション幅がバラバラ
**原因**: 条件別集計が`.container`の外に配置  
**解決**: `max-width: 1600px` + `margin: auto`適用

### 問題6: テーブルがはみ出る
**原因**: カラム幅の合計が100%超え（余分な8列目）  
**解決**: colgroup定義を是正（7列 or 8列で合計100%）

### 問題7: タイトル・タブが枠からはみ出る
**原因**: padding: 30pxが大きすぎた  
**解決**: padding: 20pxに削減

---

## 📝 コーディング規約・ベストプラクティス

### Python
- f-string内でJavaScript生成時は `{{` `}}` でエスケープ
- データベース関数は`db_path=None`でデフォルト値設定
- 日付フォーマットは`YYYY-MM-DD`で統一

### JavaScript（dashboard_v2.py内）
- 変数名: camelCase
- データ埋め込み: `const data = {json.dumps(...)};`
- ソート状態: グローバル変数`currentSort`で管理
- alertType別の処理: if-else分岐で明示的に

### HTML/CSS
- インラインスタイル使用（単一ファイル完結のため）
- カラーコード: 緑（売上好調）、オレンジ（改善）、青（トレンド）、紫（イベント）
- レスポンシブ: `max-width: 1600px`で統一

---

## 🔄 次のステップ（優先順位順）

1. **年度別イベント比較**の実装
   - DB関数作成
   - UIフィルター追加
   - 比較テーブル表示

2. **CSV出力機能の調整**
   - 各alertTypeごとのカラム名最適化
   - 日付フォーマット統一

3. **写真館別低下**の実装

4. **パフォーマンス最適化**
   - 大量データ時のページネーション高速化
   - Chart.js描画の最適化

---

## 💡 開発時の注意点

### データベース関連
- **再インポート**: 同じ日付のレポートは自動的に上書きされる
- **会員率計算**: 最新report_idベースで学校ごとに集計
- **fiscal_yearの扱い**: 4月始まりに注意

### UI/UX関連
- **ソート**: 列ヘッダークリックで昇順⇔降順切り替え
- **フィルター**: プルダウン変更で即座にテーブル更新
- **ページネーション**: 50件/ページ（`alertPageSize = 50`）

### デバッグ
- **ブラウザコンソール**: F12でJavaScriptエラー確認
- **データ確認**: `console.log(data)`で埋め込みデータ確認可
- **Python側**: `print()`でクエリ結果確認

---

## 📞 引き継ぎ時の確認事項

1. **現在のタスク**: task.mdを確認
2. **最新のコード**: database_v2.py, dashboard_v2.pyの内容
3. **テストデータ**: サンプルExcelファイルの有無
4. **未解決の問題**: Issue/TODO確認

---

## 📚 参考情報

### ファイルパス
- **プロジェクトルート**: `c:\Users\admin\Documents\06-Python\SP_summary\`
- **生成ダッシュボード**: `dashboard_YYYYMMDD_HHMMSS.html`
- **データベース**: `school_photo.db`

### ユーザープロファイル
- **名前**: はるきち
- **好み**: 親しい口調、段階的実装、エラー時の相談ベース
- **禁止事項**: エージェント側での勝手なコマンド実行

---

**このドキュメントを使って新しいチャットで作業を続ける場合は、まず現在の`task.md`と主要ファイル（database_v2.py, dashboard_v2.py）を確認してから進めてください。**
