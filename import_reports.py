#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
報告書Excelをインポートするスクリプト
"""

from pathlib import Path
from importer_v2 import import_excel_v2
from importer import sync_school_master

def import_single_report(report_path, master_path):
    """1つの報告書をインポート"""
    print(f"\n{'='*60}")
    print(f"報告書をインポート: {report_path.name}")
    print(f"{'='*60}")
    
    # 担当者マスタから学校情報を同期
    print("\n[1/2] 担当者マスタから学校情報を同期中...")
    sync_school_master(master_path)
    
    # 報告書をインポート
    print("\n[2/2] 報告書データをインポート中...")
    result = import_excel_v2(report_path)
    result = import_excel_v2(report_path)
    
    if result.get('success'):
        print(f"\n✅ {report_path.name} のインポートが完了しました！")
        print(f"   - 月次集計: {result['stats'].get('monthly_totals', 0)}件")
        print(f"   - 学校別売上: {result['stats'].get('school_monthly_sales', 0)}件")
        print(f"   - 会員率: {result['stats'].get('member_rates', 0)}件")
    else:
        raise Exception(result.get('error', '不明なエラー'))

def find_reports_recursively(base_directories):
    """複数のディレクトリから再帰的に報告書を検索"""
    all_reports = []
    
    for directory in base_directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            print(f"警告: ディレクトリが見つかりません: {directory}")
            continue
        
        # 再帰的に報告書Excelファイルを検索
        for report_file in dir_path.rglob("*報告書*.xlsx"):
            if not report_file.name.startswith('~'):  # 一時ファイルを除外
                all_reports.append(report_file)
    
    return sorted(all_reports, key=lambda x: x.name)

def import_all_reports_from_years(year_directories, master_path):
    """年度別ディレクトリから全報告書をインポート"""
    master = Path(master_path)
    
    if not master.exists():
        print(f"エラー: 担当者マスタが見つかりません: {master}")
        return
    
    # 報告書を検索
    print(f"\n報告書を検索中...")
    report_files = find_reports_recursively(year_directories)
    
    if not report_files:
        print(f"エラー: 報告書が見つかりません")
        return
    
    print(f"\n見つかった報告書: {len(report_files)}件")
    for i, file in enumerate(report_files, 1):
        # 相対パスを表示
        try:
            rel_path = file.relative_to(Path.cwd())
        except:
            rel_path = file
        print(f"  {i}. {rel_path}")
    
    # 確認
    print(f"\n担当者マスタ: {master.name}")
    response = input(f"\nこれらの報告書をインポートしますか？ (y/n): ")
    if response.lower() != 'y':
        print("キャンセルしました。")
        return
    
    # インポート実行
    success_count = 0
    error_count = 0
    
    for file in report_files:
        try:
            import_single_report(file, master)
            success_count += 1
        except Exception as e:
            print(f"\n❌ エラー: {file.name}")
            print(f"   {str(e)}")
            error_count += 1
            
            # エラーが続く場合は停止するか確認
            if error_count >= 3:
                response = input(f"\nエラーが{error_count}件発生しました。続行しますか？ (y/n): ")
                if response.lower() != 'y':
                    print("インポートを中断しました。")
                    break
    
    print(f"\n{'='*60}")
    print(f"インポート完了")
    print(f"{'='*60}")
    print(f"成功: {success_count}件")
    print(f"失敗: {error_count}件")

if __name__ == '__main__':
    # 年度別ディレクトリ
    year_dirs = [
        r'C:\Users\admin\Documents\06-Python\SP_summary\samples\2024年度',
        r'C:\Users\admin\Documents\06-Python\SP_summary\samples\2025年度'
    ]
    master_file = Path(r'C:\Users\admin\Documents\06-Python\SP_summary\samples\test_data\担当者マスタ.xlsx')
    
    print("報告書インポートツール (年度別)")
    print("=" * 60)
    print(f"検索ディレクトリ:")
    for dir_path in year_dirs:
        print(f"  - {dir_path}")
    print(f"\n担当者マスタ: {master_file}")
    
    import_all_reports_from_years(year_dirs, master_file)
