#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统计数据管理器

功能描述：
- 统一处理DuckDB数据库和Parquet文件的统计
- 提供数据一致性检查和冲突解决机制
- 支持按数据类型、周期进行详细统计
- 为断点续传提供数据范围分析

版本：v1.0.0
创建时间：2026-04-04
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta
import pandas as pd


class StatisticsManager:
    """统计数据管理器"""
    
    def __init__(self, db_manager, log_signal=None):
        """
        初始化统计管理器
        
        Args:
            db_manager: 数据库管理器实例
            log_signal: 日志信号，用于输出日志
        """
        self.db_manager = db_manager
        self.log_signal = log_signal
        self.logger = logging.getLogger(__name__)
        
        # 数据表配置
        self.table_config = {
            'daily': {'table': 'stock_daily', 'period': '1d', 'name': '日线'},
            '1m': {'table': 'stock_1m', 'period': '1m', 'name': '1分钟'},
            '5m': {'table': 'stock_5m', 'period': '5m', 'name': '5分钟'},
            '15m': {'table': 'stock_15m', 'period': '15m', 'name': '15分钟'},
            '30m': {'table': 'stock_30m', 'period': '30m', 'name': '30分钟'},
            '60m': {'table': 'stock_60m', 'period': '60m', 'name': '60分钟'},
            'weekly': {'table': 'stock_weekly', 'period': '1w', 'name': '周线'},
            'monthly': {'table': 'stock_monthly', 'period': '1mon', 'name': '月线'},
            'tick': {'table': 'stock_tick', 'period': 'tick', 'name': 'Tick'},
        }
    
    def log(self, message: str):
        """输出日志"""
        if self.log_signal:
            self.log_signal.emit(message)
        self.logger.info(message)
    
    def get_table_statistics(self, table_name: str) -> Dict:
        """
        获取单个表的统计信息
        
        Args:
            table_name: 表名
            
        Returns:
            统计信息字典
        """
        stats = {
            'exists': False,
            'symbols': 0,
            'records': 0,
            'min_date': None,
            'max_date': None,
            'symbol_list': [],
            'date_range_by_symbol': {}
        }
        
        try:
            # 检查表是否存在
            if not self.db_manager.table_exists(table_name):
                return stats
            
            stats['exists'] = True
            
            # 查询标的数和记录数
            result = self.db_manager.execute_read_and_fetch(f"""
                SELECT 
                    COUNT(DISTINCT stock_code) as symbol_count,
                    COUNT(*) as record_count
                FROM {table_name}
            """)
            
            if result and result[0]:
                stats['symbols'] = result[0][0]
                stats['records'] = result[0][1]
            
            # 查询日期范围
            date_col = 'date' if 'daily' in table_name or 'weekly' in table_name or 'monthly' in table_name else 'datetime'
            
            date_result = self.db_manager.execute_read_and_fetch(f"""
                SELECT 
                    MIN({date_col}) as min_date,
                    MAX({date_col}) as max_date
                FROM {table_name}
            """)
            
            if date_result and date_result[0]:
                stats['min_date'] = date_result[0][0]
                stats['max_date'] = date_result[0][1]
            
            # 查询每个标的的日期范围（用于断点续传）
            symbol_date_result = self.db_manager.execute_read_and_fetch(f"""
                SELECT 
                    stock_code,
                    MIN({date_col}) as min_date,
                    MAX({date_col}) as max_date
                FROM {table_name}
                GROUP BY stock_code
            """)
            
            if symbol_date_result:
                for row in symbol_date_result:
                    if row and len(row) >= 3:
                        symbol, min_date, max_date = row[0], row[1], row[2]
                        stats['date_range_by_symbol'][symbol] = {
                            'min_date': min_date,
                            'max_date': max_date
                        }
                        stats['symbol_list'].append(symbol)
            else:
                # 备用查询：只获取stock_code列表
                try:
                    symbol_result = self.db_manager.execute_read_and_fetch(f"""
                        SELECT DISTINCT stock_code
                        FROM {table_name}
                    """)
                    if symbol_result:
                        for row in symbol_result:
                            if row and row[0]:
                                stats['symbol_list'].append(row[0])
                except Exception as e:
                    self.logger.error(f"获取stock_code列表失败: {e}")
            
            return stats
            
        except Exception as e:
            self.logger.error(f"统计表 {table_name} 失败: {e}")
            return stats
    
    def get_all_statistics(self) -> Dict:
        """
        获取所有数据类型的统计信息
        
        Returns:
            完整的统计数据字典
        """
        all_stats = {
            'timestamp': datetime.now().isoformat(),
            'tables': {},
            'summary': {
                'total_symbols': set(),
                'total_records': 0
            }
        }
        
        for key, config in self.table_config.items():
            table_name = config['table']
            self.log(f"📊 正在统计 {config['name']} 数据 ({table_name})...")
            
            stats = self.get_table_statistics(table_name)
            all_stats['tables'][key] = {
                'config': config,
                'stats': stats
            }
            
            # 更新汇总信息
            if stats['exists']:
                all_stats['summary']['total_symbols'].update(stats['symbol_list'])
                all_stats['summary']['total_records'] += stats['records']
        
        # 转换set为list以便序列化
        all_stats['summary']['total_symbols'] = len(all_stats['summary']['total_symbols'])
        
        return all_stats
    
    def analyze_download_gaps(self, symbol_list: List[str], start_date: str, end_date: str, period: str) -> Dict:
        """
        分析数据下载缺口，用于断点续传优化
        
        Args:
            symbol_list: 需要下载的标的列表
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期
            
        Returns:
            下载缺口分析结果
        """
        # 查找对应的表名
        table_name = None
        for key, config in self.table_config.items():
            if config['period'] == period:
                table_name = config['table']
                break
        
        if not table_name:
            self.logger.error(f"未找到周期 {period} 对应的表")
            return {
                'completed_symbols': [],
                'partial_symbols': [],
                'missing_symbols': symbol_list,
                'download_plan': []
            }
        
        # 获取该表的统计信息
        stats = self.get_table_statistics(table_name)
        
        completed_symbols = []
        partial_symbols = []
        missing_symbols = []
        download_plan = []
        
        for symbol in symbol_list:
            if symbol in stats['date_range_by_symbol']:
                symbol_range = stats['date_range_by_symbol'][symbol]
                existing_start = symbol_range['min_date']
                existing_end = symbol_range['max_date']
                
                # 检查是否完全覆盖
                if existing_start and existing_end:
                    existing_start_str = str(existing_start)[:10]
                    existing_end_str = str(existing_end)[:10]
                    
                    if existing_start_str <= start_date and existing_end_str >= end_date:
                        # 数据已完整
                        completed_symbols.append(symbol)
                    else:
                        # 数据部分存在
                        partial_symbols.append({
                            'symbol': symbol,
                            'existing_range': (existing_start_str, existing_end_str),
                            'needed_range': (start_date, end_date),
                            'missing_before': existing_start_str > start_date,
                            'missing_after': existing_end_str < end_date
                        })
                        
                        # 计算需要下载的范围
                        if existing_start_str > start_date:
                            download_plan.append({
                                'symbol': symbol,
                                'range': (start_date, existing_start_str),
                                'type': 'before'
                            })
                        if existing_end_str < end_date:
                            download_plan.append({
                                'symbol': symbol,
                                'range': (existing_end_str, end_date),
                                'type': 'after'
                            })
            else:
                # 数据完全缺失
                missing_symbols.append(symbol)
                download_plan.append({
                    'symbol': symbol,
                    'range': (start_date, end_date),
                    'type': 'full'
                })
        
        return {
            'completed_symbols': completed_symbols,
            'partial_symbols': partial_symbols,
            'missing_symbols': missing_symbols,
            'download_plan': download_plan,
            'total_symbols': len(symbol_list),
            'completed_count': len(completed_symbols),
            'partial_count': len(partial_symbols),
            'missing_count': len(missing_symbols)
        }
    
    def check_data_consistency(self) -> Dict:
        """
        检查DuckDB和Parquet文件的一致性
        
        Returns:
            一致性检查结果
        """
        # TODO: 实现Parquet文件扫描和与DuckDB的对比
        # 目前仅返回DuckDB的统计信息
        return self.get_all_statistics()
    
    def format_statistics_report(self, stats: Dict) -> str:
        """
        格式化统计报告
        
        Args:
            stats: 统计数据字典
            
        Returns:
            格式化的报告字符串
        """
        lines = []
        lines.append("=" * 60)
        lines.append("📊 数据统计报告")
        lines.append(f"生成时间: {stats.get('timestamp', 'N/A')}")
        lines.append("=" * 60)
        
        # 按类别分组显示
        categories = {
            '日线数据': ['daily'],
            '分钟线数据': ['1m', '5m', '15m', '30m', '60m'],
            '周线数据': ['weekly'],
            '月线数据': ['monthly'],
            'Tick数据': ['tick']
        }
        
        for category, keys in categories.items():
            lines.append(f"\n【{category}】")
            category_symbols = set()
            category_records = 0
            
            for key in keys:
                if key in stats['tables']:
                    table_stats = stats['tables'][key]['stats']
                    config = stats['tables'][key]['config']
                    
                    if table_stats['exists'] and table_stats['records'] > 0:
                        lines.append(f"  {config['name']}: {table_stats['symbols']} 个标的, {table_stats['records']:,} 条记录")
                        if table_stats['min_date'] and table_stats['max_date']:
                            lines.append(f"    日期范围: {table_stats['min_date']} ~ {table_stats['max_date']}")
                        category_symbols.update(table_stats['symbol_list'])
                        category_records += table_stats['records']
            
            if category_records > 0:
                lines.append(f"  {category}合计: {len(category_symbols)} 个标的, {category_records:,} 条记录")
        
        lines.append("\n" + "=" * 60)
        lines.append(f"总计: {stats['summary']['total_symbols']} 个标的, {stats['summary']['total_records']:,} 条记录")
        lines.append("=" * 60)
        
        return "\n".join(lines)


def get_statistics_manager(db_manager, log_signal=None):
    """
    获取统计管理器实例
    
    Args:
        db_manager: 数据库管理器实例
        log_signal: 日志信号
        
    Returns:
        StatisticsManager实例
    """
    return StatisticsManager(db_manager, log_signal)
