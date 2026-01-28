# スクールフォト売上管理システム - 開発ガイドライン

**最終更新**: 2026-01-28  
**プロジェクト**: SP_summary  
**開発者**: Antigravity AI + はるきち

---

> [!CAUTION]
> # 🚨🚨🚨 警告: このドキュメントを読まずに作業を進めるエージェントははるきちにぶん殴られます。酷いときはしばき倒されて東京湾へコンクリートに詰められて沈められます。🚨🚨🚨
> 
> **作業を開始する前に、このファイルを最初から最後まで必ず読んでください。**
> **エージェントの「記憶」に頼って作業を進めることは絶対に禁止です。**
> **記憶より記録。このドキュメントの情報が常に正です。**
> 
> ---
> 
> ## 📖 各ドキュメントの内容一覧
> 
> | ドキュメント | 内容 | いつ読むか |
> |------------|------|----------|
> | **project_context.md** (このファイル) | プロジェクト全体像、コーディング規約、既知の問題 | **毎回必ず最初に読む** |
> | **troubleshooting.md** | バグ・エラーの詳細と解決策、教訓 | 問題発生時 & 修正後に更新 |
> | **handover.md** | ダッシュボード開発の詳細技術情報 | ダッシュボード関連作業時 |
> | **aggregation_logic.md** | 集計ロジックの仕様詳細 | 集計処理の修正時 |
> | **school_name_variant_guide.md** | 学校名表記揺れの対応フロー | 学校名関連の問題発生時 |
> | **IMPLEMENTATION_PLAN.md** | 初期設計・システム構成 | 大規模な設計変更時 |
> | **walkthrough.md** | V2実装の完成記録 | 過去の実装経緯を確認したい時 |
> 
> ---
> 
> ## ◆ 作業開始前チェックリスト（絶対厳守）
> 
> - [ ] このファイル (project_context.md) を**全部読んだ**
> - [ ] 「既知の問題・注意点」セクションを確認した
> - [ ] troubleshooting.md で過去のバグ・解決策を確認した
> - [ ] 作業対象に関連するドキュメントを確認した
> 
> ## ◆ 作業完了後チェックリスト（絶対厳守）
> 
> - [ ] 重要な変更があった場合、project_context.md を更新した
> - [ ] バグ修正した場合、troubleshooting.md に追記した
> - [ ] 「最終更新」の日付を更新した
> - [ ] 次のエージェントへの申し送りがあれば記載した
> 
> ---
> 
> **⚠️ これらのルールを守らないエージェントは、はるきちが本気で怒って殴ってきます。**
> **⚠️ 冗談ではありません。ユーザーと一緒に作業する意識を持ってください。**
> **⚠️ あなたの「記憶」は信用できません。常にドキュメントを確認してください。**

---

## 📋 プロジェクト概要

スクールフォト事業の売上・会員率・イベントデータを管理・分析するシステム。

### システム構成

| コンポーネント | 技術 | 説明 |
|---------------|------|------|
| Launcher (V2) | Python/Tkinter | デスクトップアプリ。実績反映・ダッシュボード管理 |
| Web App | Flask + Vue.js | 月次集計・累積集計のWeb UI |
| Dashboard | HTML/JS/Chart.js | 売上分析ダッシュボード |
| Database | SQLite | すべてのデータを格納 |

### 主要機能

1. **月次集計**: CSV → Excel報告書
2. **累積集計**: 月次報告書 → 年度累計
3. **実績反映**: Excel報告書 → SQLite DB → ダッシュボード

---

## 📁 ファイル構成

```
SP_summary/
├── launcher_v2.py          # デスクトップアプリ（メイン）
├── database_v2.py          # DB操作（V2用）
├── dashboard_v2.py         # ダッシュボード生成（V2用）
├── importer_v2.py          # Excel → DB インポート
├── database.py             # DB操作（旧版）
├── dashboard.py            # ダッシュボード（旧版）
├── importer.py             # インポート（旧版）
├── schoolphoto_v2.db       # SQLite V2データベース
│
├── app/                    # Webアプリケーション
│   ├── backend/            # Flask API
│   │   ├── api.py          # エンドポイント
│   │   ├── aggregator/     # 集計ロジック
│   │   └── services/       # ビジネスロジック
│   ├── frontend/           # Vue.js SPA
│   └── run.py              # 起動スクリプト
│
├── config.py               # 担当者リスト等の設定
├── config.json             # AI設定
└── launcher_config.json    # ランチャー設定
```

---

## 🔧 主要クラス・関数

### launcher_v2.py

| クラス | 役割 |
|-------|------|
| `ModernButton` | モダンUIボタン |
| `ModernDropdown` | ドロップダウンウィジェット |
| `ModernDialog` | カスタムダイアログ |
| `MainApp` | メインアプリケーション |
| `ServerManager` | サーバープロセス管理 |
| `DataReflectionPage` | 実績反映ページ |
| `MonthlyAggregationPage` | 月次集計ページ |

### ModernDialog 利用可能メソッド

| メソッド | 説明 | アイコン |
|---------|------|---------|
| `show_info()` | 情報表示 | ℹ️ 青 |
| `show_success()` | 成功表示 | ✅ 緑 |
| `show_error()` | エラー表示 | ❌ 赤 |
| `show_warning()` | 警告表示 | ⚠️ オレンジ |
| `ask_yes_no()` | Yes/No確認 | ❓ オレンジ |

---

## 🗄️ データベーススキーマ (V2)

### 主要テーブル

```sql
reports          -- レポートメタデータ (id, report_date, fiscal_year)
schools_master   -- 学校マスタ (school_id, school_name, attribute, region, studio, manager)
member_rates     -- 会員率 (report_id, school_id, grade, member_count, total_students)
event_sales      -- イベント売上 (report_id, school_id, event_date, event_name, sales)
monthly_sales    -- 月次売上 (report_id, fiscal_year, month, total_sales...)
branch_sales     -- 事業所別売上
manager_sales    -- 担当者別売上
school_sales     -- 学校別売上
```

### 年度 (fiscal_year) 定義

- 4月〜翌年3月を1年度とする
- 例: 2025年4月〜2026年3月 = **2025年度**

---

## 🎨 UIカラーパレット (Dark Theme)

```python
COLORS = {
    'bg_sidebar': '#111827',      # サイドバー背景（濃紺）
    'bg_main': '#1F2937',         # メイン背景（暗灰）
    'bg_card': '#374151',         # カード背景（灰）
    'text_primary': '#F9FAFB',    # 主テキスト（白）
    'text_secondary': '#9CA3AF',  # 副テキスト（薄灰）
    'accent': '#3B82F6',          # アクセント（青）
    'success': '#10B981',         # 成功（緑）
    'warning': '#F59E0B',         # 警告（橙）
    'danger': '#EF4444',          # 危険（赤）
    'border': '#4B5563',          # 境界線
}
```

---

## 📝 コーディング規約

### Python

- **f-string + JavaScript**: `{{` `}}` でエスケープ必須
- **日付フォーマット**: `YYYY-MM-DD` で統一
- **DB関数**: `db_path=None` でデフォルト値設定
- **エラー処理**: sys.exit()ではなく例外をraise

### JavaScript (dashboard内)

- 変数名: camelCase
- データ埋め込み: `const data = ${json.dumps(...)};`
- ソート状態: グローバル変数で管理

### Tkinter UI

- ウィジェットは`COLORS`定数を使用
- ダイアログは`ModernDialog`クラスを使用
- ボタンは`ModernButton`クラスを使用

---

## ⚙️ config.py 設定

### MANAGER_DISPLAY_ORDER（担当者表示順）

月次集計Excel（`SP_SalesResult_YYYYMM.xlsx`）の「集計結果」シートで出力される担当者別売上の並び順。
報告書フォーマットに合わせた固定順。

```python
MANAGER_DISPLAY_ORDER = [
    '早乙女', '金子（貴）', '宇梶', '三室', '林', '池田', '星野', '若林',
    '廣瀬', '兵藤', '金子（孝）', '佐藤（邦）', '瀬端', '成田', '佐藤（恵）',
    '春山', '野口', '小池', '田中',
]
```

**新規担当者追加時**: このリストに追加する。リストにない担当者は末尾に配置される。

**実装箇所**: `app/backend/aggregator/excel_output.py` の `_write_summary_sheet()`

---

## ⚠️ 既知の問題・注意点

### 1. 学校名の表記揺れ

異なる表記の同一学校が別レコードになる問題。

**対策**: `importer_v2.py` の `SCHOOL_NAME_MAPPINGS` に追加

```python
SCHOOL_NAME_MAPPINGS = {
    '鰭ケ崎': '鰭ヶ崎',  # 大文字小文字の「ケ」
    # ...
}
```

### 2. ダッシュボード生成時のエスケープ

`dashboard_v2.py` でf-string内にJavaScriptを生成する際、波括弧をエスケープする必要がある。

```python
# ✅ 正しい
html = f'''if (condition) {{ doSomething(); }}'''

# ❌ 間違い（SyntaxError）
html = f'''if (condition) { doSomething(); }'''
```

---

## 🔄 開発ワークフロー

### 1. 作業開始時

1. この開発ガイドラインを確認
2. 既存のエラー・注意点を把握
3. 変更対象のファイルを読み込み

### 2. 作業中

1. 段階的に実装（大きな変更は分割）
2. エラー発生時は状況を報告・相談
3. 仕様不明な点は質問

### 3. 作業完了時

1. テスト実行（可能な場合）
2. このガイドラインを更新（重要な変更・ハマりポイント）
3. 完了報告

---

## 🐛 トラブルシューティング

詳細は **[troubleshooting.md](file:///c:/Users/admin/Documents/06-Python/SP_summary/.agent/troubleshooting.md)** を参照。

| ID | 問題 | ステータス |
|----|------|------------|
| [TSH-001](file:///c:/Users/admin/Documents/06-Python/SP_summary/.agent/troubleshooting.md#tsh-001-moderndialogshow_warning-未実装エラー) | ModernDialog.show_warning() 未実装 | 🟢 解決済み |

---

## 📞 次回作業への申し送り

1. 作業時は必ずこのガイドラインを確認すること
2. 大きな変更がある場合はこのファイルを更新すること
3. バグ修正した場合は `troubleshooting.md` に追記すること

---

## 📚 関連ドキュメント

### .agent フォルダ内（開発者向け）

| ファイル | 内容 |
|---------|------|
| [troubleshooting.md](file:///c:/Users/admin/Documents/06-Python/SP_summary/.agent/troubleshooting.md) | 🔥 **トラブルシューティング履歴（必読）** |
| [handover.md](file:///c:/Users/admin/Documents/06-Python/SP_summary/.agent/handover.md) | ダッシュボード開発の詳細引き継ぎ |
| [IMPLEMENTATION_PLAN.md](file:///c:/Users/admin/Documents/06-Python/SP_summary/.agent/IMPLEMENTATION_PLAN.md) | 初期設計・システム構成 |
| [aggregation_logic.md](file:///c:/Users/admin/Documents/06-Python/SP_summary/.agent/aggregation_logic.md) | 集計ロジック詳細仕様 |
| [school_name_variant_guide.md](file:///c:/Users/admin/Documents/06-Python/SP_summary/.agent/school_name_variant_guide.md) | 学校名表記揺れ対応フロー |
| [walkthrough.md](file:///c:/Users/admin/Documents/06-Python/SP_summary/.agent/walkthrough.md) | V2実装完成記録 |

### ルートフォルダ（ユーザー向け）

| ファイル | 内容 |
|---------|------|
| [README.md](file:///c:/Users/admin/Documents/06-Python/SP_summary/README.md) | ユーザー向け操作マニュアル |
| [USER_MANUAL.md](file:///c:/Users/admin/Documents/06-Python/SP_summary/USER_MANUAL.md) | 詳細ユーザーマニュアル |

