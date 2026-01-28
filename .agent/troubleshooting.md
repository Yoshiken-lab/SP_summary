# トラブルシューティング履歴

**最終更新**: 2026-01-28  
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

---

## TSH-001: ModernDialog.show_warning() 未実装エラー

### 基本情報

| 項目 | 内容 |
|------|------|
| **発生日** | 2026-01-28 |
| **報告者** | はるきち |
| **ステータス** | 🔴 未解決 |
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
