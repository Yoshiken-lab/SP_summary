# トラブルシューティング履歴

**最終更新**: 2026-02-11  
**プロジェクト**: SP_summary

> [!IMPORTANT]
> ## エージェント向け運用ルール
> 
> 1. **バグ修正時は必ずこのファイルに追記すること**
> 2. **作業前にこのファイルを確認し、同じ問題を踏まないこと**
> 3. **解決策だけでなく、教訓も記載すること**

---

## 📋 目次

1. [TSH-001: ModernDialog.show_warning() 未実装エラー](#tsh-001-moderndialogshow_warning-未実装エラー)
2. [TSH-002: 条件別集計CSVの列不一致](#tsh-002-条件別集計csvの列不一致)
3. [TSH-003: 月次集計の総売上と内訳合計の不一致](#tsh-003-月次集計の総売上と内訳合計の不一致)

---

## TSH-001: ModernDialog.show_warning() 未実装エラー

### 基本情報

| 項目 | 内容 |
|------|------|
| **発生日** | 2026-01-28 |
| **報告者** | はるきち |
| **ステータス** | 🟢 解決済み |
| **優先度** | 高 |
| **該当ファイル** | [launcher_v2.py](file:///c:/Users/admin/Documents/06-Python/SP_summary/launcher_v2.py) |
| **該当行** | 2178行目 |

### エラー内容

```
AttributeError: type object 'ModernDialog' has no attribute 'show_warning'
```

### 発生条件

1. Launcher V2 で報告書ファイルをインポート（実績反映）
2. 一部のファイルでエラーが発生（全件成功ではない場合）
3. `_handle_completion()` 関数が「一部完了」の警告を表示しようとする
4. `ModernDialog.show_warning()` を呼び出すがメソッドが存在しない

### 根本原因

`ModernDialog` クラスには以下のメソッドのみ実装済み：
- `show_info()` - 情報表示
- `show_success()` - 成功表示
- `show_error()` - エラー表示
- `ask_yes_no()` - Yes/No確認

**`show_warning()` メソッドが未実装のまま呼び出しコードが追加されていた。**

### 解決策

#### 方法1: show_warning() メソッドを追加（推奨）

`launcher_v2.py` の `ModernDialog` クラス内（529行目付近）に以下を追加：

```python
@classmethod
def show_warning(cls, parent, title, message, detail=None):
    """警告ダイアログを表示"""
    dialog = cls(parent, title, message, type='warning', detail=detail)
    dialog.wait_window()
```

また、`_create_content()` メソッド内に `warning` タイプのアイコン定義を追加：

```python
icons = {
    'info': ('ℹ️', COLORS['accent']),
    'error': ('❌', COLORS['danger']),
    'success': ('✅', COLORS['success']),
    'confirm': ('❓', COLORS['accent']),
    'warning': ('⚠️', COLORS['warning']),  # 追加
}
```

#### 方法2: 既存メソッドに置き換え（暫定対応）

```python
# 変更前
ModernDialog.show_warning(self, "一部完了", ...)

# 変更後（暫定）
ModernDialog.show_error(self, "一部完了", ...)
```

### 教訓・今後の対策

1. **新しいメソッドを呼び出す前に、そのメソッドが実装済みか確認する**
2. **UIコンポーネントに新機能を追加する場合、テストを行う**
3. **`ModernDialog` を拡張する場合は、このトラブルシューティングを参照**

### 関連情報

- [project_context.md の ModernDialog セクション](file:///c:/Users/admin/Documents/06-Python/SP_summary/.agent/project_context.md)

---

## TSH-002: 条件別集計CSVの列不一致

### 基本情報

| 項目 | 内容 |
|------|------|
| **発生日** | 2026-02-11 |
| **報告者** | はるきち |
| **ステータス** | 🟢 解決済み |
| **優先度** | 中 |
| **該当ファイル** | [dashboard_v2.py](file:///c:/Users/admin/Documents/06-Python/SP_summary/dashboard_v2.py) |
| **該当行** | 3123行目付近 (`downloadAlertCSV`) |

### 問題内容

「イベント開始日別売上」を含む条件別集計で、ダッシュボード表示列とCSV出力列が一致しない。  
例: `event_sales_by_date` なのに `今年度売上/前年度売上/成長率` が出力される。

### 根本原因

`downloadAlertCSV()` が一部タブ専用ではなく、共通のデフォルト列構成を流用していた。  
そのため `event_sales_by_date` / `new_schools` / `no_events` / `studio_decline` などで、表示テーブルと異なる列でCSVが生成されていた。

### 解決策

- `downloadAlertCSV()` を alertType ごとの列定義に変更。
- 表示テーブルと同じ順序・同じ意味の列でCSVを生成するよう統一。
- `studio_decline` のCSVファイル名も明示追加。

### 教訓・今後の対策

1. 表示テーブルの列定義とCSV列定義を同じ条件分岐で管理する。
2. 新しい条件別タブを追加したら、CSV出力との差分確認を必ず実施する。
3. サンプルCSVのヘッダーを自動テスト（またはチェックリスト）に入れる。

---

## TSH-003: 月次集計の総売上と内訳合計の不一致

### 基本情報

| 項目 | 内容 |
|------|------|
| **発生日** | 2026-02-10 |
| **報告者** | はるきち |
| **ステータス** | 🟢 解決済み |
| **優先度** | 高 |
| **該当ファイル** | [app/backend/services/file_handler.py](file:///c:/Users/admin/Documents/06-Python/SP_summary/app/backend/services/file_handler.py), [app/backend/aggregator/sales.py](file:///c:/Users/admin/Documents/06-Python/SP_summary/app/backend/aggregator/sales.py) |
| **事象** | 総売上 `12,799,410` に対して、内訳合計が `12,675,161` になる |

### 問題内容

月次集計結果で、以下の整合性が崩れるケースがあった。
- 総売上
- 事業所別合計
- 担当者別合計
- 学校別合計

### 根本原因

1. 旧ロジックで学校マッチング基準が集計単位ごとに揺れていた（ID/名称の扱いが不統一）。
2. 未マッチ学校が内訳集計から脱落しても、総売上側には残るケースが発生していた。
3. CSV読み込み時に文字コードや空白揺れの影響で一致判定が不安定になるケースがあった。

### 解決策

- `file_handler.py`
  - CSV読み込みにエンコーディングフォールバックを追加（`cp932` → `utf-8-sig` → `utf-8`）。
  - 文字列カラムの前後空白除去を共通化（中間空白は保持）。
- `sales.py`
  - 学校マッチングを **ID優先 + 名称フォールバック** に統一。
  - マッチ結果を一度作成し、事業所別/担当者別/イベント別すべて同じマッチ結果で集計。
  - `filtered_df` 基準の厳密バリデーションを導入（未登録学校が1件でもあれば `SchoolMasterMismatchError` で停止）。

### 検証結果

1. 既存データで「真の未登録校 5件」を検出して停止することを確認。
2. 未登録校を除外した検証データでは、  
   `総売上 = 事業所計 = 担当者計 = 学校計` が一致することを確認。

### 教訓・今後の対策

1. 集計ロジックとバリデーションロジックは必ず同一基準にする。
2. 「差分が出たら警告」ではなく「差分が出る入力は停止」を基本方針にする。
3. 月次リリース前に4系統合計一致チェックを実施する。

---

## テンプレート（新規追加時にコピー）

```markdown
## TSH-XXX: [問題のタイトル]

### 基本情報

| 項目 | 内容 |
|------|------|
| **発生日** | YYYY-MM-DD |
| **報告者** | - |
| **ステータス** | 🔴 未解決 / 🟡 対応中 / 🟢 解決済み |
| **優先度** | 高 / 中 / 低 |
| **該当ファイル** | [ファイル名](file:///パス) |
| **該当行** | XX行目 |

### エラー内容



### 発生条件

1. 

### 根本原因



### 解決策



### 教訓・今後の対策

1. 

### 関連情報

- 
```
