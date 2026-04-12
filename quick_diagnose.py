"""
快速诊断：查看当前 Parquet 文件的列结构
"""
import duckdb
from pathlib import Path

parquet_root = Path('D:/MyStockData/Parquet')

print("=" * 70)
print("快速诊断：Parquet 文件列结构")
print("=" * 70)

# 检查周线数据
weekly_dir = parquet_root / 'kline' / 'weekly'
all_weekly_files = list(weekly_dir.rglob('*.parquet'))
real_weekly_files = [f for f in all_weekly_files if not f.name.startswith('_temp_')]

print(f"\n【周线目录】{weekly_dir}")
print(f"  总文件数: {len(all_weekly_files)}")
print(f"  实际数据文件数: {len(real_weekly_files)}")

if real_weekly_files:
    test_file = real_weekly_files[0]
    print(f"\n  检查文件: {test_file.name}")
    
    conn = duckdb.connect()
    columns_info = conn.execute(f"DESCRIBE SELECT * FROM read_parquet('{test_file}')").fetchall()
    column_names = [col[0] for col in columns_info]
    
    print(f"\n  DuckDB 检测到的列:")
    for col in columns_info:
        print(f"    - {col[0]}: {col[1]}")
    
    print(f"\n  关键信息:")
    print(f"    ✓ date 列存在: {'date' in column_names}")
    print(f"    ✓ __index_level_0__ 存在: {'__index_level_0__' in column_names}")
    
    # 尝试查询
    try:
        result = conn.execute(f"""
            SELECT stock_code, date, count(*) 
            FROM read_parquet('{test_file}') 
            GROUP BY stock_code, date 
            LIMIT 5
        """).fetchall()
        
        print(f"\n  ✅ 使用 date 列查询成功:")
        for row in result:
            print(f"    {row}")
    except Exception as e:
        print(f"\n  ❌ 使用 date 列查询失败: {e}")
    
    try:
        result2 = conn.execute(f"""
            SELECT stock_code, __index_level_0__, count(*) 
            FROM read_parquet('{test_file}') 
            GROUP BY stock_code, __index_level_0__ 
            LIMIT 5
        """).fetchall()
        
        print(f"\n  ✅ 使用 __index_level_0__ 查询成功:")
        for row in result2:
            print(f"    {row}")
    except Exception as e:
        print(f"\n  ❌ 使用 __index_level_0__ 查询失败: {e}")
    
    conn.close()

# 检查月线数据
monthly_dir = parquet_root / 'kline' / 'monthly'
all_monthly_files = list(monthly_dir.rglob('*.parquet'))
real_monthly_files = [f for f in all_monthly_files if not f.name.startswith('_temp_')]

print(f"\n\n【月线目录】{monthly_dir}")
print(f"  总文件数: {len(all_monthly_files)}")
print(f"  实际数据文件数: {len(real_monthly_files)}")

if real_monthly_files:
    test_file = real_monthly_files[0]
    print(f"\n  检查文件: {test_file.name}")
    
    conn = duckdb.connect()
    columns_info = conn.execute(f"DESCRIBE SELECT * FROM read_parquet('{test_file}')").fetchall()
    column_names = [col[0] for col in columns_info]
    
    print(f"\n  DuckDB 检测到的列:")
    for col in columns_info:
        print(f"    - {col[0]}: {col[1]}")
    
    print(f"\n  关键信息:")
    print(f"    ✓ date 列存在: {'date' in column_names}")
    print(f"    ✓ __index_level_0__ 存在: {'__index_level_0__' in column_names}")
    
    conn.close()

print("\n" + "=" * 70)
