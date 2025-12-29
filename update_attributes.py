#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
担当者マスタから属性をschools_masterに反映するスクリプト
"""

import pandas as pd
from pathlib import Path
from database_v2 import get_connection

def update_attributes_from_master(master_path, db_path='schoolphoto_v2.db'):
    """担当者マスタから属性をschools_masterに反映"""
    
    print(f"担当者マスタから属性を反映: {master_path}")
    
    # 担当者マスタ読み込み
    df = pd.read_excel(master_path, header=0)
    df = df.dropna(axis=1, how='all')
    
    # カラムを特定
    id_col = None
    name_col = None
    attribute_col = None
    
    for col in df.columns:
        col_str = str(col)
        if col_str == 'ID' or 'ID' in col_str:
            id_col = col
        elif '学校名' in col_str:
            name_col = col
        elif '属性' in col_str:
            attribute_col = col
    
    if not attribute_col:
        print("エラー: 属性カラムが見つかりません")
        return
    
    print(f"カラム検出: ID={id_col}, 学校名={name_col}, 属性={attribute_col}")
    
    # DB接続
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    updated_count = 0
    skipped_count = 0
    not_found_count = 0
    
    try:
        for _, row in df.iterrows():
            if pd.isna(row[name_col]) or pd.isna(row[attribute_col]):
                skipped_count += 1
                continue
            
            school_name = str(row[name_col]).strip()
            attribute = str(row[attribute_col]).strip()
            
            # 学校名でschools_masterを検索
            cursor.execute('''
                SELECT school_id FROM schools_master WHERE school_name = ? LIMIT 1
            ''', (school_name,))
            result = cursor.fetchone()
            
            if result:
                school_id = result[0]
                cursor.execute('''
                    UPDATE schools_master SET attribute = ? WHERE school_id = ?
                ''', (attribute, school_id))
                updated_count += 1
            else:
                not_found_count += 1
        
        conn.commit()
        print(f"\n更新完了:")
        print(f"  属性を更新: {updated_count}件")
        print(f"  学校が見つからない: {not_found_count}件")
        print(f"  スキップ: {skipped_count}件")
        
    finally:
        conn.close()

if __name__ == '__main__':
    master_path = Path(r'C:\Users\admin\Documents\06-Python\SP_summary\samples\test_data\担当者マスタ.xlsx')
    update_attributes_from_master(master_path)
    print("\n属性の反映が完了しました！")
