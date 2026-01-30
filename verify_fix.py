#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""検証スクリプト: 修正後の関数が正しく動作し、分割入金を集約しているか確認"""
import sqlite3
from pathlib import Path
import sys
import datetime

# database_v2.pyがあるディレクトリにパスを通す
DB_DIR = Path(__file__).parent
sys.path.append(str(DB_DIR))

from database_v2 import (
    get_yearly_event_comparison,
    get_rapid_growth_schools,
    get_sales_unit_price_analysis,
    get_connection, 
    get_current_fiscal_year
)

DB_PATH = DB_DIR / 'schoolphoto_v2.db'

def main():
    print(f"=== 検証開始: {DB_PATH} ===\n")
    
    # 1. get_yearly_event_comparison の検証 (School ID 15: ホタルの集い)
    print("--- 1. get_yearly_event_comparison (School ID 15) ---")
    try:
        # 2024年度のデータを取得
        data = get_yearly_event_comparison(str(DB_PATH), 15, year1=2024)
        
        events = data.get('year1_events', [])
        print(f"イベント数: {len(events)}")
        
        target_event = "02　2024年度　ホタルの集い　スナップ写真"
        found = [e for e in events if target_event in e['event_name']]
        
        if len(found) == 1:
            print(f"✅ OK: '{target_event}' は1行に集約されました。")
            print(f"   売上: ¥{found[0]['sales']:,.0f}")
        elif len(found) > 1:
            print(f"❌ NG: '{target_event}' が複数行表示されています ({len(found)}行)。GROUP BYが効いていません。")
        else:
            print(f"⚠️ Warning: '{target_event}' が見つかりませんでした。")
            
        # 全イベント表示（デバッグ用）
        # for e in events: print(f"  {e['event_name']}: {e['sales']}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

    print("\n--- 2. get_rapid_growth_schools (実行テスト) ---")
    try:
        results = get_rapid_growth_schools(str(DB_PATH))
        print(f"✅ OK: 実行成功。取得数: {len(results)}")
        if results:
            top = results[0]
            print(f"   Top School: {top['school_name']} (成長率: {top['growth_rate']:.1%})")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- 3. get_sales_unit_price_analysis (COUNT DISTINCT検証) ---")
    try:
        results = get_sales_unit_price_analysis(str(DB_PATH))
        print(f"✅ OK: 実行成功。取得数: {len(results)}")
        if results:
            print(f"   Top 3 (Avg Price):")
            for i, res in enumerate(results[:3]):
                print(f"   {i+1}. {res['school_name']}: イベント数={res['event_count']}, 平均単価=¥{res['avg_price']:,.0f}")
                
            # School ID 15のチェック
            school_15 = next((r for r in results if r['school_id'] == 15), None)
            if school_15:
                print(f"   School 15 (明保小): イベント数={school_15['event_count']}, 平均単価=¥{school_15['avg_price']:,.0f}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
