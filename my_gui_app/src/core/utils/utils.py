#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据下载工具模块

功能描述：包含配置管理、重试机制、策略模式等优化功能，支持多种数据类型的下载和处理

测试内容：
1. 内存监控和批次大小调整功能
2. 断点续传和失败记录功能
3. 不同数据类型的下载策略
4. 并行处理和数据保存性能

版本：v1.0.0
创建时间：2026-03-21
修订时间：2026-03-26
创建人：Trae IDE
修订信息：
- 2026-03-21：初始创建，实现配置管理和重试机制
- 2026-03-26：添加详细的文档注释和版本信息，明确保存性能日志信息
"""

import os
import time
import gc
import psutil
from functools import wraps
from typing import Callable, Type, Tuple, Any, Dict, List
from datetime import datetime, timedelta
import pandas as pd
import json
from abc import ABC, abstractmethod


def normalize_symbol(symbol: str) -> str:
    """标准化股票代码"""
    # 移除空格
    symbol = symbol.strip()
    # 确保格式为 6 位数字
    if len(symbol) == 6 and symbol.isdigit():
        # 自动添加交易所后缀
        if symbol.startswith(('0', '3')):
            return f"{symbol}.SZ"
        elif symbol.startswith('6'):
            return f"{symbol}.SH"
    return symbol


def validate_date(date_str: str) -> bool:
    """验证日期格式"""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def convert_date_format(date_str: str, input_format: str = '%Y-%m-%d', output_format: str = '%Y%m%d') -> str:
    """转换日期格式"""
    try:
        date_obj = datetime.strptime(date_str, input_format)
        return date_obj.strftime(output_format)
    except ValueError:
        return date_str


def normalize_symbols(symbols: List[str]) -> List[str]:
    """标准化股票代码列表"""
    return [normalize_symbol(symbol) for symbol in symbols]


def get_trading_date_range(start_date: str, end_date: str) -> List[str]:
    """获取交易日范围"""
    # 这里简化实现，实际应该使用交易日历
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    date_range = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # 周一到周五
            date_range.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    return date_range


def validate_symbol(symbol: str) -> bool:
    """验证股票代码"""
    # 简单验证，实际应该更严格
    if not symbol:
        return False
    # 检查是否是有效的股票代码格式
    parts = symbol.split('.')
    if len(parts) != 2:
        return False
    code, exchange = parts
    if not code.isdigit() or len(code) != 6:
        return False
    if exchange not in ['SH', 'SZ']:
        return False
    return True


def is_sh_stock(symbol: str) -> bool:
    """判断是否是上海股票"""
    # 简化实现，实际应该更准确
    return symbol.endswith('.SH') or (len(symbol) == 6 and symbol.startswith('6'))


def is_sz_stock(symbol: str) -> bool:
    """判断是否是深圳股票"""
    # 简化实现，实际应该更准确
    return symbol.endswith('.SZ') or (len(symbol) == 6 and symbol.startswith(('0', '3')))


class MemoryMonitor:
    """内存监控工具"""
    
    def __init__(self, log_signal=None, memory_limit_gb: float = 4.0):
        self.log_signal = log_signal
        self.memory_limit_gb = memory_limit_gb  # 内存使用限额
        self.last_memory_usage = 0
        self.memory_trend = []
        self.memory_history = []  # 更详细的内存历史记录
        self.batch_size_adjustments = 0  # 记录批次大小调整次数
        self.gc_triggers = 0  # 记录垃圾回收触发次数
        self.resource_resets = 0  # 记录资源重置次数
        self.last_gc_time = time.time()  # 上次垃圾回收时间
        self.gc_interval = 30  # 垃圾回收最小间隔（秒）
    
    def get_memory_usage(self) -> float:
        """获取当前内存使用情况（GB）"""
        process = psutil.Process(os.getpid())
        memory_gb = process.memory_info().rss / (1024 ** 3)
        # 记录内存使用趋势
        self.memory_trend.append(memory_gb)
        if len(self.memory_trend) > 30:  # 增加趋势分析窗口
            self.memory_trend.pop(0)
        # 记录详细历史
        self.memory_history.append((time.time(), memory_gb))
        if len(self.memory_history) > 200:  # 保持合理长度
            self.memory_history.pop(0)
        self.last_memory_usage = memory_gb
        return memory_gb
    
    def log_memory_usage(self, message: str = ""):
        """记录内存使用情况"""
        if self.log_signal:
            memory_gb = self.get_memory_usage()
            self.log_signal.emit(f"📊 内存使用: {memory_gb:.2f} GB {message}")
            # 内存使用警告
            if memory_gb > self.memory_limit_gb * 0.8:
                self.log_signal.emit(f"⚠️ 内存使用接近限额 ({memory_gb:.2f} GB / {self.memory_limit_gb} GB)")
            elif memory_gb > self.memory_limit_gb:
                self.log_signal.emit(f"❌ 内存使用超出限额 {memory_gb:.2f} GB (阈值: {self.memory_limit_gb} GB)")
    
    def should_adjust_batch_size(self, threshold: float = None) -> bool:
        """判断是否需要调整批次大小"""
        if threshold is None:
            threshold = self.memory_limit_gb * 0.65  # 降低调整阈值，提前预防内存问题
        current_memory = self.get_memory_usage()
        
        # 检查内存趋势
        if len(self.memory_trend) >= 5:  # 增加趋势分析样本
            # 计算内存增长速率
            recent_trend = self.memory_trend[-5:]
            trend_increasing = all(recent_trend[i] < recent_trend[i+1] for i in range(len(recent_trend)-1))
            trend_rate = (recent_trend[-1] - recent_trend[0]) / len(recent_trend)
            
            # 更智能的判断逻辑
            if trend_increasing and trend_rate > 0.08 and current_memory > threshold:
                self.batch_size_adjustments += 1
                return True
            elif current_memory > self.memory_limit_gb * 0.85:
                # 紧急情况，立即调整
                self.batch_size_adjustments += 1
                return True
        return current_memory > threshold
    
    def should_trigger_gc(self) -> bool:
        """判断是否需要触发垃圾回收"""
        current_memory = self.get_memory_usage()
        current_time = time.time()
        # 当内存使用超过75%且距离上次垃圾回收超过最小间隔时触发
        return current_memory > self.memory_limit_gb * 0.75 and (current_time - self.last_gc_time) > self.gc_interval
    
    def is_memory_exceeded(self) -> bool:
        """判断内存是否超出限额"""
        return self.get_memory_usage() > self.memory_limit_gb
    
    def get_memory_trend_info(self) -> dict:
        """获取内存趋势信息"""
        if not self.memory_trend:
            return {"current": 0, "average": 0, "trend": "stable"}
        
        current = self.memory_trend[-1]
        average = sum(self.memory_trend) / len(self.memory_trend)
        
        # 分析趋势
        if len(self.memory_trend) >= 3:
            recent_change = self.memory_trend[-1] - self.memory_trend[0]
            if recent_change > 0.4:
                trend = "increasing"
            elif recent_change < -0.4:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return {
            "current": current,
            "average": average,
            "trend": trend,
            "adjustments": self.batch_size_adjustments,
            "gc_triggers": self.gc_triggers,
            "resource_resets": self.resource_resets
        }
    
    def suggest_batch_size(self, current_batch_size: int, data_type: str = "1d") -> int:
        """根据内存使用情况建议批次大小"""
        trend_info = self.get_memory_trend_info()
        
        # 基于内存趋势调整批次大小
        if trend_info["trend"] == "increasing" and trend_info["current"] > self.memory_limit_gb * 0.7:
            # 内存持续增长，减小批次大小
            new_batch_size = max(1, current_batch_size // 2)
            if self.log_signal:
                self.log_signal.emit(f"📈 内存持续增长，调整批次大小: {current_batch_size} → {new_batch_size}")
            return new_batch_size
        elif trend_info["trend"] == "decreasing" and trend_info["current"] < self.memory_limit_gb * 0.5:
            # 内存持续下降，适当增大批次大小
            new_batch_size = min(100, current_batch_size * 2)
            if self.log_signal:
                self.log_signal.emit(f"📉 内存持续下降，调整批次大小: {current_batch_size} → {new_batch_size}")
            return new_batch_size
        
        # 根据数据类型设置合理的默认值
        if data_type == '1m':
            return max(1, min(30, current_batch_size))
        elif data_type == 'tick':
            return max(1, min(20, current_batch_size))
        else:
            return max(1, min(100, current_batch_size))
    
    def trigger_gc(self):
        """触发垃圾回收并记录"""
        current_time = time.time()
        if (current_time - self.last_gc_time) < self.gc_interval:
            return
        
        if self.log_signal:
            before_memory = self.get_memory_usage()
            self.log_signal.emit(f"🧹 触发垃圾回收前内存使用: {before_memory:.2f} GB")
        
        gc.collect()
        self.gc_triggers += 1
        self.last_gc_time = current_time
        
        if self.log_signal:
            after_memory = self.get_memory_usage()
            freed_memory = before_memory - after_memory
            self.log_signal.emit(f"✅ 垃圾回收完成，释放内存: {freed_memory:.2f} GB，当前内存: {after_memory:.2f} GB")
    
    def increment_resource_reset(self):
        """增加资源重置计数"""
        self.resource_resets += 1
    
    def should_reset_resources(self, processed_symbols: int, processed_records: int) -> bool:
        """判断是否需要重置资源"""
        # 根据处理的标的数和记录数判断是否需要重置资源
        reset_symbols = 50  # 每处理50个标的重置一次
        reset_records = 1000000  # 每处理100万条记录重置一次
        
        return (processed_symbols > 0 and processed_symbols % reset_symbols == 0) or \
               (processed_records > 0 and processed_records % reset_records == 0)


class DownloadConfig:
    """下载配置管理"""
    
    # 配置缓存
    _config_cache = {}
    _cache_timestamp = 0
    _cache_timeout = 300  # 缓存超时时间（秒）
    
    def __init__(self, config_yaml: dict = None):
        if config_yaml:
            self.config = config_yaml
        else:
            # 自动加载配置文件
            self.config = self._load_config()
        self._validate_config()
        self.download_config = self.config.get('download', {})
        self.time_ranges = self.config.get('time_ranges', {})
        self.resource_config = self.config.get('resource', {})
        self.cache_config = self.config.get('cache', {})
    
    def _load_config(self) -> dict:
        """加载配置文件"""
        # 检查缓存是否有效
        current_time = time.time()
        if current_time - self._cache_timestamp < self._cache_timeout and self._config_cache:
            return self._config_cache
        
        try:
            import yaml
            from pathlib import Path
            
            # 配置文件路径
            current_file = Path(__file__)
            # current_file = my_gui_app/src/core/utils/utils.py
            # parent.parent = my_gui_app/src/core
            # parent.parent.parent = my_gui_app/src (错误！)
            # 应该再往上找，找到 my_gui_app 目录
            my_gui_app_dir = current_file.parent.parent.parent.parent  # my_gui_app
            config_dir = my_gui_app_dir / 'config'
            yaml_config_path = config_dir / 'data_config.yaml'
            
            if yaml_config_path.exists():
                with open(yaml_config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                # 更新缓存
                self._config_cache = config
                self._cache_timestamp = current_time
                return config
        except Exception as e:
            pass
        
        # 默认配置
        default_config = {
            'download': {
                'max_workers': min(os.cpu_count() * 3, 20)
            },
            'time_ranges': {
                'default': {
                    'start_date': '1990-01-01',
                    'end_date': 'today'
                },
                '1d': {
                    'start_date': '1990-01-01',
                    'end_date': 'today'
                },
                '1m': {
                    'start_days': 365,
                    'end_date': 'today'
                },
                '5m': {
                    'start_days': 365,
                    'end_date': 'today'
                },
                '15m': {
                    'start_days': 365,
                    'end_date': 'today'
                },
                '30m': {
                    'start_days': 365,
                    'end_date': 'today'
                },
                '60m': {
                    'start_days': 365,
                    'end_date': 'today'
                },
                'tick': {
                    'start_days': 31,
                    'end_date': 'today'
                },
                'weekly': {
                    'start_date': '1990-01-01',
                    'end_date': 'today'
                },
                'monthly': {
                    'start_date': '1990-01-01',
                    'end_date': 'today'
                }
            },
            'resource': {
                'processing_limit': {
                    'max_symbols_per_batch': 150,
                    'max_records_per_batch': 1000000,
                    'reset_interval_symbols': 600,
                    'reset_interval_records': 4000000
                }
            },
            'cache': {
                'memory_limit_gb': 4.0
            },
            'test': {
                'daily_stock_count': 50,
                'other_stock_count': 20
            }
        }
        
        # 更新缓存
        self._config_cache = default_config
        self._cache_timestamp = current_time
        return default_config
    
    def _validate_config(self):
        """验证配置的有效性"""
        # 确保必要的配置项存在
        if 'time_ranges' not in self.config:
            self.config['time_ranges'] = {}
        if 'resource' not in self.config:
            self.config['resource'] = {}
        if 'processing_limit' not in self.config['resource']:
            self.config['resource']['processing_limit'] = {
                'max_symbols_per_batch': 150,
                'max_records_per_batch': 1000000,
                'reset_interval_symbols': 600,
                'reset_interval_records': 4000000
            }
        if 'cache' not in self.config:
            self.config['cache'] = {'memory_limit_gb': 4.0}
        if 'test' not in self.config:
            self.config['test'] = {'daily_stock_count': 50, 'other_stock_count': 20}
    
    def get_max_workers(self, period: str) -> int:
        """根据周期获取线程数"""
        default_workers = min(os.cpu_count() * 3, 20)
        return self.download_config.get('max_workers', default_workers)
    
    def get_batch_size(self, period: str) -> int:
        """根据周期获取批量大小"""
        # 获取特定周期的批量大小
        period_key = f'batch_size_{period}'
        if period_key in self.download_config:
            return self.download_config[period_key]
        
        # 根据数据类型设置默认批量大小
        if period == '1m':
            return 20  # 1分钟数据使用较小的批次
        elif period == 'tick':
            return 10  # Tick数据使用更小的批次
        elif period in ['5m', '15m', '30m', '60m']:
            return 30  # 其他分钟线数据使用中等批次
        else:
            return 100  # 日线、周线、月线使用较大批次
    
    def get_time_range(self, period: str) -> tuple:
        """获取时间范围"""
        period_config = self.time_ranges.get(period, {})
        
        # 计算开始日期
        if 'start_days' in period_config:
            start_date = (datetime.now() - timedelta(days=period_config['start_days'])).strftime('%Y-%m-%d')
        else:
            start_date = period_config.get('start_date', '1990-01-01')
        
        # 结束日期
        end_date = period_config.get('end_date', 'today')
        if end_date == 'today':
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        return start_date, end_date
    
    def get_memory_limit(self) -> float:
        """获取内存使用限额（GB）"""
        return self.cache_config.get('memory_limit_gb', 4.0)
    
    def get_test_stock_count(self, period: str) -> int:
        """获取测试模式下的股票数量"""
        test_config = self.config.get('test', {})
        if period == '1d':
            return test_config.get('daily_stock_count', 50)
        else:
            return test_config.get('other_stock_count', 20)
    
    def get_processing_limit(self) -> dict:
        """获取处理限额配置"""
        return self.resource_config.get('processing_limit', {
            'max_symbols_per_batch': 150,  # 每批处理的最大标的数（100-200之间）
            'max_records_per_batch': 1000000,  # 每批处理的最大记录数（考虑tick数据的大量记录）
            'reset_interval_symbols': 600,  # 处理多少标的后重置资源
            'reset_interval_records': 4000000  # 处理多少记录后重置资源
        })
    
    def get_intersection_time_range(self, period: str, user_start_date: str, user_end_date: str) -> tuple:
        """计算用户指定时间范围和配置文件时间范围的交集
        
        Args:
            period: 数据周期
            user_start_date: 用户指定的开始日期（格式：YYYYMMDD 或 YYYY-MM-DD）
            user_end_date: 用户指定的结束日期（格式：YYYYMMDD 或 YYYY-MM-DD）
            
        Returns:
            交集时间范围 (start_date, end_date) - 格式：YYYY-MM-DD
        """
        from datetime import datetime, timedelta
        
        # 获取配置文件中的时间范围（已经包含了配置文件中的时间限制）
        config_start, config_end = self.get_time_range(period)
        
        # 转换为日期对象
        config_start_dt = datetime.strptime(config_start, '%Y-%m-%d')
        config_end_dt = datetime.strptime(config_end, '%Y-%m-%d')
        # 处理不同格式的日期
        def parse_date(date_str):
            if len(date_str) == 8 and '-' not in date_str:
                # YYYYMMDD 格式
                return datetime.strptime(date_str, '%Y%m%d')
            else:
                # YYYY-MM-DD 格式
                return datetime.strptime(date_str, '%Y-%m-%d')
        
        user_start_dt = parse_date(user_start_date)
        user_end_dt = parse_date(user_end_date)
        
        # 计算交集
        start_dt = max(config_start_dt, user_start_dt)
        end_dt = min(config_end_dt, user_end_dt)
        
        # 确保开始日期不晚于结束日期
        if start_dt > end_dt:
            # 如果没有交集，返回 None
            return None, None
        
        # 转换回字符串格式
        start_date = start_dt.strftime('%Y-%m-%d')
        end_date = end_dt.strftime('%Y-%m-%d')
        
        return start_date, end_date
    
    def refresh_config(self):
        """刷新配置，重新加载配置文件"""
        self._config_cache = {}
        self._cache_timestamp = 0
        self.config = self._load_config()
        self._validate_config()
        self.download_config = self.config.get('download', {})
        self.time_ranges = self.config.get('time_ranges', {})
        self.resource_config = self.config.get('resource', {})
        self.cache_config = self.config.get('cache', {})
    
    def get_config(self) -> dict:
        """获取完整配置"""
        return self.config


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """重试装饰器，支持指数退避"""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        time.sleep(min(delay, max_delay))
                        delay *= backoff_factor
                        continue
                    else:
                        raise last_exception
            
            raise last_exception
        
        return wrapper
    return decorator


class DataDownloadStrategy(ABC):
    """数据下载策略基类"""
    
    def __init__(self, db_manager, config: DownloadConfig, log_signal):
        self.db_manager = db_manager
        self.config = config
        self.log_signal = log_signal
        # 初始化logger
        import logging
        self.logger = logging.getLogger(__name__)
    
    @abstractmethod
    def download_single_symbol(self, symbol: str, start_date: str, end_date: str) -> Dict:
        """下载单个标的的数据"""
        pass
    
    @abstractmethod
    def transform_data(self, symbol: str, raw_data: Dict) -> pd.DataFrame:
        """转换原始数据为标准格式"""
        pass
    
    def get_period(self) -> str:
        """获取周期"""
        return '1d'
    
    def get_batch_size(self) -> int:
        """获取批量大小"""
        return self.config.get_batch_size(self.get_period())
    
    def get_parquet_root(self):
        """获取Parquet根目录路径"""
        from pathlib import Path
        
        data_config = {}
        try:
            config_path = Path('D:/StockData/config/data_config.yaml')
            if config_path.exists():
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    data_config = yaml.safe_load(f)
        except Exception:
            pass
        
        data_root_dir = data_config.get('data_paths', {}).get('root_dir', 'D:/MyStockData')
        parquet_config = data_config.get('storage', {}).get('parquet', {})
        parquet_root_dir = parquet_config.get('root_dir', 'Parquet')
        
        return Path(data_root_dir) / parquet_root_dir
    
    def get_file_path_for_symbol(self, period: str, symbol: str) -> str:
        """获取指定股票和周期的Parquet文件路径"""
        from pathlib import Path
        
        parquet_root = self.get_parquet_root()
        
        if '.' in symbol:
            parts = symbol.split('.')
            if parts[0].isalpha():
                exchange = parts[0]
                base_symbol = parts[1]
            else:
                base_symbol = parts[0]
                exchange = parts[1]
        else:
            base_symbol = symbol
            exchange = 'SH'
        
        if period == '1d':
            parquet_path = parquet_root / 'kline' / 'daily' / exchange / f"{base_symbol}.parquet"
        elif period == '1w' or period == 'weekly':
            parquet_path = parquet_root / 'kline' / 'weekly' / exchange / f"{base_symbol}.parquet"
        elif period == '1mon' or period == 'monthly':
            parquet_path = parquet_root / 'kline' / 'monthly' / exchange / f"{base_symbol}.parquet"
        elif period == 'tick':
            parquet_path = parquet_root / 'tick' / exchange / f"{base_symbol}.parquet"
        else:
            parquet_path = parquet_root / 'kline' / period / exchange / f"{base_symbol}.parquet"
        
        return str(parquet_path) if parquet_path.exists() else ""
    
    def get_existing_time_range(self, symbol: str) -> tuple:
        """获取Parquet文件中已有数据的时间范围"""
        try:
            import os
            from pathlib import Path
            
            period = self.get_period()
            
            # 获取正确的Parquet文件路径
            parquet_path = self.get_file_path_for_symbol(period, symbol)
            if not parquet_path:
                return None, None
            
            # 确定日期列名
            if period in ['1d', '1w', 'weekly', '1mon', 'monthly']:
                date_column = 'date'
            else:
                date_column = 'datetime'
            
            # 检查Parquet文件是否存在
            if not os.path.exists(parquet_path):
                return None, None
            
            # 读取Parquet文件并获取时间范围
            import pandas as pd
            df = pd.read_parquet(parquet_path)
            
            if df.empty:
                return None, None
            
            if date_column in df.columns:
                min_date = df[date_column].min()
                max_date = df[date_column].max()
                

                # 转换为字符串格式
                if isinstance(min_date, pd.Timestamp):
                    min_date = min_date.strftime('%Y-%m-%d')
                elif isinstance(min_date, datetime):
                    min_date = min_date.strftime('%Y-%m-%d')
                
                if isinstance(max_date, pd.Timestamp):
                    max_date = max_date.strftime('%Y-%m-%d')
                elif isinstance(max_date, datetime):
                    max_date = max_date.strftime('%Y-%m-%d')
                
                return min_date, max_date
            else:
                return None, None
        except Exception as e:
            if self.log_signal:
                self.log_signal.emit(f"❌ 获取已有数据时间范围失败: {str(e)}")
            return None, None
    
    def download_data(self, symbol: str, start_date: str, end_date: str, force_update=False) -> tuple:
        """下载数据并转换
        
        Returns:
            tuple: (df, is_skip) - 数据DataFrame和是否因为数据已存在而跳过
        """
        import time
        start_time = time.time()
        is_skip = False
        intersect_start = start_date
        intersect_end = end_date
        try:
            period = self.get_period()
            
            # 计算时间范围交集
            intersect_start, intersect_end = self.config.get_intersection_time_range(period, start_date, end_date)
            
            # 记录下载信息
            if self.log_signal:
                self.log_signal.emit(f"📥 开始下载 | 标的: {symbol} | 类型: {period} | 时间范围: {intersect_start} 至 {intersect_end}")
            
            # 检查是否需要强制更新
            if not force_update:
                # 获取已有数据的时间范围
                existing_start, existing_end = self.get_existing_time_range(symbol)
                if existing_start and existing_end:
                    # 比较时间范围，只下载缺失的部分
                    start_dt = datetime.strptime(intersect_start, '%Y-%m-%d')
                    end_dt = datetime.strptime(intersect_end, '%Y-%m-%d')
                    existing_start_dt = datetime.strptime(existing_start, '%Y-%m-%d')
                    existing_end_dt = datetime.strptime(existing_end, '%Y-%m-%d')
                    
                    # 对于所有数据类型，检查数据完整性
                    need_update = False
                    try:
                        from .cycle_data_validator import get_cycle_validator
                        validator = get_cycle_validator()
                        
                        # 检查最新数据是否完整
                        if validator.should_refresh_data(existing_end_dt, period):
                            need_update = True
                            if self.log_signal:
                                if period == '1d':
                                    self.log_signal.emit(f"⚠️ 数据不完整 | 标的: {symbol} | 类型: {period} | 原因: 当日数据可能不完整，建议收盘后下载")
                                elif period in ['1m', '5m', '15m', '30m', '60m']:
                                    self.log_signal.emit(f"⚠️ 数据不完整 | 标的: {symbol} | 类型: {period} | 原因: 当日分钟线数据可能不完整，建议16:00后下载")
                                elif period == '1w' or period == 'weekly':
                                    self.log_signal.emit(f"⚠️ 数据不完整 | 标的: {symbol} | 类型: {period} | 原因: 本周数据可能不完整，建议周日收盘后下载")
                                elif period == '1mon' or period == 'monthly':
                                    self.log_signal.emit(f"⚠️ 数据不完整 | 标的: {symbol} | 类型: {period} | 原因: 本月数据可能不完整，建议月末收盘后下载")
                    except Exception as e:
                        # 如果验证失败，继续正常流程
                        if self.log_signal:
                            self.log_signal.emit(f"⚠️ 数据完整性检查失败: {str(e)}")
                    
                    # 检查是否需要下载
                    if start_dt >= existing_start_dt and end_dt <= existing_end_dt and not need_update:
                        if self.log_signal:
                            self.log_signal.emit(f"ℹ️ 跳过下载 | 标的: {symbol} | 类型: {period} | 原因: 数据已存在且完整")
                        is_skip = True
                        return pd.DataFrame(), is_skip
                    elif need_update or (start_dt >= existing_start_dt and end_dt > existing_end_dt):
                        # 只下载新增的部分（包括不完整的周期数据）
                        intersect_start = existing_end if not need_update else intersect_start
                        if self.log_signal:
                            self.log_signal.emit(f"ℹ️ 部分下载 | 标的: {symbol} | 类型: {period} | 时间范围: {intersect_start} 至 {intersect_end} | 原因: {'更新不完整数据' if need_update else '只下载新增部分'}")
                    elif start_dt < existing_start_dt and end_dt <= existing_end_dt:
                        # 只下载前面缺失的部分
                        intersect_end = existing_start
                        if self.log_signal:
                            self.log_signal.emit(f"ℹ️ 部分下载 | 标的: {symbol} | 类型: {period} | 时间范围: {intersect_start} 至 {intersect_end} | 原因: 只下载前面缺失部分")
                    # 其他情况：两边都有缺失，下载完整范围
            
            # 标准两步法：先下载到本地缓存，再从缓存读取
            try:
                from xtquant import xtdata
                # 转换日期格式为YYYYMMDD
                start_date_str = intersect_start.replace('-', '')
                end_date_str = intersect_end.replace('-', '')
                
                # 映射周期参数，确保download_history_data支持
                qmt_period = period
                if period == '1mon':
                    qmt_period = 'monthly'
                elif period == '1w':
                    qmt_period = 'weekly'
                
                # 下载数据到本地缓存（包括tick数据）
                xtdata.download_history_data(
                    symbol,  # 股票代码
                    qmt_period,  # 周期（使用QMT API支持的格式）
                    start_date_str,  # 开始日期
                    end_date_str     # 结束日期
                )
                if self.log_signal:
                    self.log_signal.emit(f"✅ 已将数据下载到本地缓存 | 标的: {symbol} | 类型: {period}")
                
                # 从本地缓存读取数据
                raw_data = self.download_single_symbol(symbol, intersect_start, intersect_end)
                df = self.transform_data(symbol, raw_data)
            except Exception as e:
                # 下载失败
                if self.log_signal:
                    self.log_signal.emit(f"❌ 下载失败: {str(e)}")
                return pd.DataFrame(), False
            
            # 计算耗时
            elapsed_time = time.time() - start_time
            
            # 记录下载结果
            if self.log_signal:
                if not df.empty:
                    self.log_signal.emit(f"✅ 下载成功 | 标的: {symbol} | 类型: {period} | 时间范围: {intersect_start} 至 {intersect_end} | 记录数: {len(df)} | 耗时: {elapsed_time:.2f}s")
                else:
                    if force_update:
                        # 强制更新模式下，数据为空可能是因为QMT API没有返回数据，而不是数据已存在
                        self.log_signal.emit(f"ℹ️ 下载完成 | 标的: {symbol} | 类型: {period} | 时间范围: {intersect_start} 至 {intersect_end} | 记录数: 0 | 耗时: {elapsed_time:.2f}s | 原因: 强制更新模式，QMT API未返回数据")
                    else:
                        # 检查是否是因为数据已存在而跳过
                        existing_start, existing_end = self.get_existing_time_range(symbol)
                        if existing_start and existing_end:
                            is_skip = True
                            self.log_signal.emit(f"ℹ️ 下载完成 | 标的: {symbol} | 类型: {period} | 时间范围: {intersect_start} 至 {intersect_end} | 记录数: 0 | 耗时: {elapsed_time:.2f}s | 原因: 数据已存在且完整，跳过下载")
                        else:
                            self.log_signal.emit(f"⚠️ 下载完成 | 标的: {symbol} | 类型: {period} | 时间范围: {intersect_start} 至 {intersect_end} | 记录数: 0 | 耗时: {elapsed_time:.2f}s | 原因: 无数据返回")
            
            return df, is_skip
        except Exception as e:
            # 计算耗时
            elapsed_time = time.time() - start_time
            if self.log_signal:
                period = self.get_period()
                self.log_signal.emit(f"❌ 下载失败 | 标的: {symbol} | 类型: {period} | 时间范围: {intersect_start} 至 {intersect_end} | 耗时: {elapsed_time:.2f}s | 错误: {str(e)}")
            return pd.DataFrame(), False


class DailyDataStrategy(DataDownloadStrategy):
    """日线数据下载策略"""
    
    def __init__(self, db_manager, config: DownloadConfig, log_signal):
        super().__init__(db_manager, config, log_signal)
    
    def download_single_symbol(self, symbol: str, start_date: str, end_date: str) -> Dict:
        # 使用QMT API下载日线数据
        import xtquant.xtdata as xt_data
        data = xt_data.get_market_data_ex(
            stock_list=[symbol],
            period='1d',
            start_time=start_date.replace('-', ''),
            end_time=end_date.replace('-', ''),
            fill_data=True
        )
        return data
    
    def transform_data(self, symbol: str, raw_data: Dict) -> pd.DataFrame:
        if symbol not in raw_data or raw_data[symbol] is None:
            return pd.DataFrame()
        
        # 【修复】创建副本而不是视图，避免SettingWithCopyWarning
        df = raw_data[symbol].copy()
        
        # 标准化列名
        df.columns = df.columns.str.lower()
        
        # 确保必要的列存在
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0.0
        
        # 计算成交额（如果不存在）
        if 'amount' not in df.columns:
            df['amount'] = df['close'] * df['volume']
        
        # 将索引转换为日期列
        if not df.empty:
            df['date'] = df.index
            df['date'] = pd.to_datetime(df['date'])
            # 确保日期格式正确
            df['date'] = df['date'].dt.date
        
        # 添加元数据
        df['stock_code'] = symbol
        df['period'] = '1d'
        df['symbol_type'] = 'stock'
        df['adjust_type'] = 'none'
        df['factor'] = 1.0
        

        
        df['created_at'] = pd.Timestamp.now()
        df['updated_at'] = pd.Timestamp.now()
        
        return df


class BondDataStrategy(DataDownloadStrategy):
    """可转债数据下载策略"""
    
    def __init__(self, db_manager, config: DownloadConfig, log_signal):
        super().__init__(db_manager, config, log_signal)
    
    def download_single_symbol(self, symbol: str, start_date: str, end_date: str) -> Dict:
        # 尝试使用 easy_xt API 获取可转债数据（对可转债支持更好）
        try:
            import easy_xt
            api = None
            try:
                api = easy_xt.get_api()
                # 初始化数据服务
                init_success = False
                try:
                    if hasattr(api, 'init_data'):
                        init_result = api.init_data()
                        if init_result:
                            init_success = True
                    
                    # 如果第一次初始化失败，尝试在data对象上初始化
                    if not init_success and hasattr(api, 'data') and hasattr(api.data, 'init_data'):
                        init_result = api.data.init_data()
                        if init_result:
                            init_success = True
                except Exception as init_e:
                    # 初始化失败，继续尝试获取数据
                    pass
                
                # 只有在初始化成功后才尝试获取数据
                if init_success:
                    from datetime import datetime
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    days = (end_dt - start_dt).days
                    
                    # 使用 api.get_price() 获取数据
                    df = api.get_price(symbol, period='1d', count=days + 500)  # 多取一些确保覆盖
                    
                    if df is not None and not df.empty:
                        # 过滤日期范围
                        if 'time' in df.columns:
                            df['time'] = pd.to_datetime(df['time'])
                            # 【修复】使用.copy()避免SettingWithCopyWarning
                            df = df[(df['time'] >= start_dt) & (df['time'] <= end_dt)].copy()
                            df = df.set_index('time')
                        else:
                            df = df.loc[start_dt:end_dt]
                        
                        # 标准化列名
                        df.columns = df.columns.str.lower()
                        
                        # 转换为与 xtdata.get_market_data_ex 相同的格式
                        result = {symbol: df}
                        return result
            finally:
                # 清理资源，避免MiniRacer异常
                if api and hasattr(api, 'close'):
                    try:
                        api.close()
                    except:
                        pass
        except Exception as e:
            # 如果 easy_xt API 失败，使用 xtdata API 作为备用
            pass
        
        # 使用QMT API下载可转债数据作为备用
        import xtquant.xtdata as xt_data
        data = xt_data.get_market_data_ex(
            stock_list=[symbol],
            period='1d',
            start_time=start_date.replace('-', ''),
            end_time=end_date.replace('-', ''),
            fill_data=True
        )
        return data
    
    def transform_data(self, symbol: str, raw_data: Dict) -> pd.DataFrame:
        if symbol not in raw_data or raw_data[symbol] is None:
            return pd.DataFrame()
        
        # 【修复】创建副本而不是视图，避免SettingWithCopyWarning
        df = raw_data[symbol].copy()
        
        # 标准化列名
        df.columns = df.columns.str.lower()
        
        # 确保必要的列存在
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0.0
        
        # 计算成交额（如果不存在）
        if 'amount' not in df.columns:
            df['amount'] = df['close'] * df['volume']
        
        # 将索引转换为日期列
        if not df.empty:
            df['date'] = df.index
            df['date'] = pd.to_datetime(df['date'])
            # 确保日期格式正确
            df['date'] = df['date'].dt.date
        
        # 添加元数据
        df['stock_code'] = symbol
        df['period'] = '1d'
        df['symbol_type'] = 'bond'  # 标记为债券类型
        df['adjust_type'] = 'none'
        df['factor'] = 1.0
        

        
        df['created_at'] = pd.Timestamp.now()
        df['updated_at'] = pd.Timestamp.now()
        
        return df


class MinuteDataStrategy(DataDownloadStrategy):
    """分钟线数据下载策略"""
    
    def __init__(self, db_manager, config: DownloadConfig, log_signal, period: str = '1m'):
        super().__init__(db_manager, config, log_signal)
        self.period = period
        self.period_mapping = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '60m': '60m'
        }
    
    def get_period(self) -> str:
        """获取周期"""
        return self.period
    
    def download_single_symbol(self, symbol: str, start_date: str, end_date: str) -> Dict:
        # 映射周期
        import xtquant.xtdata as xt_data
        qmt_period = self.period_mapping.get(self.period, '1m')
        
        # 下载数据
        data = xt_data.get_market_data_ex(
            stock_list=[symbol],
            period=qmt_period,
            start_time=start_date.replace('-', ''),
            end_time=end_date.replace('-', ''),
            fill_data=True
        )
        return data
    
    def transform_data(self, symbol: str, raw_data: Dict) -> pd.DataFrame:
        if symbol not in raw_data or raw_data[symbol] is None:
            return pd.DataFrame()
        
        df = raw_data[symbol]
        
        # 将索引转换为日期时间列
        if not df.empty:
            df['datetime'] = df.index
            df['datetime'] = pd.to_datetime(df['datetime'])
        
        # 标准化处理
        df['stock_code'] = symbol
        df['period'] = self.period
        df['symbol_type'] = 'stock'
        df['adjust_type'] = 'none'
        df['factor'] = 1.0
        

        
        df['created_at'] = pd.Timestamp.now()
        df['updated_at'] = pd.Timestamp.now()
        
        return df


class TickDataStrategy(DataDownloadStrategy):
    """Tick数据下载策略"""
    
    def __init__(self, db_manager, config: DownloadConfig, log_signal):
        super().__init__(db_manager, config, log_signal)
    
    def get_period(self) -> str:
        """获取周期"""
        return 'tick'
    
    def download_single_symbol(self, symbol: str, start_date: str, end_date: str) -> Dict:
        # Tick数据使用默认字段，避免某些股票没有func_type字段导致下载失败
        import xtquant.xtdata as xt_data
        data = xt_data.get_market_data_ex(
            stock_list=[symbol],
            period='tick',
            start_time=start_date.replace('-', ''),
            end_time=end_date.replace('-', '')
        )
        return data
    
    def transform_data(self, symbol: str, raw_data: Dict) -> pd.DataFrame:
        if symbol not in raw_data or raw_data[symbol] is None:
            return pd.DataFrame()
        
        # 【修复】创建副本而不是视图，避免SettingWithCopyWarning
        df = raw_data[symbol].copy()
        
        # 转换时间格式
        if 'time' in df.columns:
            # 转换为北京时间（UTC+8）
            df['datetime'] = pd.to_datetime(df['time'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai')
            # 移除时区信息，只保留本地时间
            df['datetime'] = df['datetime'].dt.tz_localize(None)
        elif not df.empty:
            # 如果没有time列，使用索引
            df['datetime'] = df.index
            df['datetime'] = pd.to_datetime(df['datetime'])
        
        # 确保开高收低字段有正确的值
        if not df.empty:
            # 直接使用API返回的原始值，不进行修正
            for col in ['open', 'high', 'low', 'close']:
                if col not in df.columns:
                    # 如果字段不存在，使用lastPrice
                    df[col] = df.get('lastPrice', 0)
        
        # 确保成交笔数字段有正确的值
        if not df.empty and 'transactionNum' in df.columns:
            # 填充NaN值为0
            df['transactionNum'] = df['transactionNum'].fillna(0)
        
        # 确保成交方向字段有正确的值
        if 'func_type' in df.columns:
            # 填充NaN值为0
            df['func_type'] = df['func_type'].fillna(0)
        else:
            # 如果字段不存在，添加默认值0
            df['func_type'] = 0
        
        # 过滤非交易时间数据
        if not df.empty:
            # 过滤出交易时间的数据
            # 上午：9:15-11:30
            # 下午：13:00-15:00
            # 【修复】使用.copy()避免SettingWithCopyWarning
            df = df[
                ((df['datetime'].dt.hour >= 9) & (df['datetime'].dt.hour < 12)) |
                ((df['datetime'].dt.hour >= 13) & (df['datetime'].dt.hour < 15))
            ].copy()
        
        # 添加元数据
        df['stock_code'] = symbol
        df['period'] = 'tick'
        df['symbol_type'] = 'stock' if symbol.startswith(('0', '3', '6')) else 'etf'
        df['adjust_type'] = 'none'
        df['factor'] = 1.0
        
        # 添加其他QMT API返回的字段
        if not df.empty:
            # 确保其他字段存在
            fields_to_keep = [
                'lastClose', 'pvolume', 'stockStatus', 'lastSettlementPrice',
                'askPrice', 'bidPrice', 'askVol', 'bidVol', 'transactionNum'
            ]
            
            for field in fields_to_keep:
                if field not in df.columns:
                    if field in ['askPrice', 'bidPrice', 'askVol', 'bidVol']:
                        # 这些字段是数组，设置为空列表
                        df[field] = None
                    else:
                        # 其他字段设置为0或NaN
                        df[field] = 0
        
        df['created_at'] = pd.Timestamp.now()
        df['updated_at'] = pd.Timestamp.now()
        
        return df


class WeeklyDataStrategy(DataDownloadStrategy):
    """周线数据下载策略"""
    
    def __init__(self, db_manager, config: DownloadConfig, log_signal):
        super().__init__(db_manager, config, log_signal)
    
    def get_period(self) -> str:
        """获取周期"""
        return 'weekly'
    
    def download_single_symbol(self, symbol: str, start_date: str, end_date: str) -> Dict:
        # 使用QMT API下载周线数据
        # 先下载到本地缓存，再读取
        import xtquant.xtdata as xt_data
        import pandas as pd
        
        try:
            # 【最优策略】基于API测试结果（2026-04-11验证）
            # 
            # 测试结论：
            # 1. 周六(4/11)可以获取本周周线，最新日期为20260412（本周六）
            # 2. 指定end_time时，API自动返回 ≤ end_time 的最新完整周期K线
            # 3. 不需要手动扩展结束日期！
            #
            # 策略：
            # - 开始日期：前向扩展到周一（确保能获取到该周的完整K线）
            # - 结束日期：直接使用用户指定的日期（不过度延伸）
            # - API会智能返回范围内最新的完整周期数据
            
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            
            # 调整开始日期到所在周的周一（0=周一, 6=周日）
            start_weekday = start_dt.weekday()
            adjusted_start = start_dt - pd.Timedelta(days=start_weekday)
            
            # 【关键】结束日期不扩展！直接使用用户指定的日期
            # API会自动返回 ≤ end_dt 的最新完整周线K线
            adjusted_end = end_dt
            
            self.logger.info(f"📅 周线查询: {adjusted_start.strftime('%Y-%m-%d')} ~ {adjusted_end.strftime('%Y-%m-%d')}")
            
            # 转换日期格式为YYYYMMDD
            start_time = adjusted_start.strftime('%Y%m%d')
            end_time = adjusted_end.strftime('%Y%m%d')
            
            # 先下载数据到本地缓存
            xt_data.download_history_data(
                stock_code=symbol,
                period='1w',
                start_time=start_time,
                end_time=end_time
            )
            
            # 再从本地缓存读取数据
            data = xt_data.get_market_data_ex(
                stock_list=[symbol],
                period='1w',
                start_time=start_time,
                end_time=end_time,
                fill_data=True
            )
            return data
        except Exception as e:
            if self.log_signal:
                self.log_signal.emit(f"❌ 下载周线数据失败 {symbol}: {str(e)}")
            return {symbol: None}
    
    def transform_data(self, symbol: str, raw_data: Dict) -> pd.DataFrame:
        if symbol not in raw_data or raw_data[symbol] is None:
            return pd.DataFrame()
        
        df = raw_data[symbol]
        
        # 标准化列名
        df.columns = df.columns.str.lower()
        
        # 确保必要的列存在
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0.0
        
        # 计算成交额（如果不存在）
        if 'amount' not in df.columns:
            df['amount'] = df['close'] * df['volume']
        
        # 使用API返回的索引作为日期
        # API返回的周线索引已经是该周的最后一个交易日（如20260412表示4/6-4/11那周）
        if not df.empty:
            df['date'] = pd.to_datetime(df.index)
            df['date'] = df['date'].dt.date
        
        # 添加元数据
        df['stock_code'] = symbol
        df['period'] = 'weekly'
        df['symbol_type'] = 'stock'
        df['adjust_type'] = 'none'
        df['factor'] = 1.0
        
        # 移除不需要的列
        if 'datetime' in df.columns:
            df = df.drop('datetime', axis=1)
        if 'time' in df.columns:
            df = df.drop('time', axis=1)
        
        df['created_at'] = pd.Timestamp.now()
        df['updated_at'] = pd.Timestamp.now()
        
        return df


class MonthlyDataStrategy(DataDownloadStrategy):
    """月线数据下载策略"""
    
    def __init__(self, db_manager, config: DownloadConfig, log_signal):
        super().__init__(db_manager, config, log_signal)
    
    def get_period(self) -> str:
        """获取周期"""
        return 'monthly'
    
    def download_single_symbol(self, symbol: str, start_date: str, end_date: str) -> Dict:
        # 使用QMT API下载月线数据
        # 先下载到本地缓存，再读取
        import xtquant.xtdata as xt_data
        import pandas as pd
        
        try:
            # 【最优策略】基于API测试结果（2026-04-11验证）
            #
            # 测试结论：
            # 1. 指定end_time=今天(4/11) → API返回最新3月末(20260331) ✅
            # 2. 指定end_time=月中(3/15) → API返回最新2月末(20260228) ✅
            # 3. 不指定end_time → API返回4月末(20260430) ❌ 误导！
            #
            # 策略：
            # - 开始日期：前向扩展到月初（确保能获取到该月的完整K线）
            # - 结束日期：直接使用用户指定的日期（不过度延伸！）
            # - API会智能返回 ≤ end_time 的最新完整月线K线
            
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            
            # 调整开始日期到当月第一天
            adjusted_start = start_dt.replace(day=1)
            
            # 【关键】结束日期不扩展！直接使用用户指定的日期
            # 测试证明：API会自动过滤出 ≤ end_dt 的最新月线K线
            adjusted_end = end_dt
            
            self.logger.info(f"📅 月线查询: {adjusted_start.strftime('%Y-%m-%d')} ~ {adjusted_end.strftime('%Y-%m-%d')}")
            
            # 转换日期格式为YYYYMMDD
            start_time = adjusted_start.strftime('%Y%m%d')
            end_time = adjusted_end.strftime('%Y%m%d')
            
            # 先下载数据到本地缓存
            xt_data.download_history_data(
                stock_code=symbol,
                period='1mon',
                start_time=start_time,
                end_time=end_time
            )
            
            # 使用get_market_data_ex获取月线数据
            data = xt_data.get_market_data_ex(
                stock_list=[symbol],
                period='1mon',
                start_time=start_time,
                end_time=end_time,
                fill_data=True
            )
            
            return data
        except Exception as e:
            if self.log_signal:
                self.log_signal.emit(f"❌ 下载月线数据失败 {symbol}: {str(e)}")
            return {symbol: None}
    
    def transform_data(self, symbol: str, raw_data: Dict) -> pd.DataFrame:
        if symbol not in raw_data or raw_data[symbol] is None:
            return pd.DataFrame()
        
        df = raw_data[symbol]
        
        # 标准化列名
        df.columns = df.columns.str.lower()
        
        # 确保必要的列存在
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0.0
        
        # 计算成交额（如果不存在）
        if 'amount' not in df.columns:
            df['amount'] = df['close'] * df['volume']
        
        # 使用API返回的索引作为日期
        # API返回的月线索引是该月的最后一天（如20260331表示3月份）
        # 注意：即使在月中查询，API也只返回已完整结束的月份
        if not df.empty:
            df['date'] = pd.to_datetime(df.index)
            df['date'] = df['date'].dt.date
        
        # 添加元数据
        df['stock_code'] = symbol
        df['period'] = 'monthly'
        df['symbol_type'] = 'stock'
        df['adjust_type'] = 'none'
        df['factor'] = 1.0
        
        # 移除不需要的列
        if 'datetime' in df.columns:
            df = df.drop('datetime', axis=1)
        if 'time' in df.columns:
            df = df.drop('time', axis=1)
        if 'month' in df.columns:
            df = df.drop('month', axis=1)
        
        # 添加创建时间和更新时间
        df['created_at'] = pd.Timestamp.now()
        df['updated_at'] = pd.Timestamp.now()
        
        return df


class StreamingProcessor:
    """流式处理器，控制内存使用"""
    
    def __init__(self, strategy, max_batch_size: int = 15, log_signal=None):
        self.strategy = strategy
        self.initial_max_batch_size = max_batch_size
        self.max_batch_size = max_batch_size
        self.log_signal = log_signal
        self.buffer = []
        # 从配置中获取内存限额
        memory_limit = 2.5  # 进一步降低内存限额以更早触发内存管理
        if hasattr(strategy, 'config') and hasattr(strategy.config, 'get_memory_limit'):
            memory_limit = strategy.config.get_memory_limit()
        self.memory_monitor = MemoryMonitor(log_signal, memory_limit)
        self.batch_history = []
        # 并行处理相关
        import queue
        self.data_queue = queue.Queue(maxsize=2)  # 数据队列，最大2个批次，进一步减少内存占用
        self.is_running = True
        self.save_thread = None
        # 启动保存线程
        self._start_save_thread()
    
    def _start_save_thread(self):
        """启动保存线程"""
        import threading
        self.save_thread = threading.Thread(target=self._save_worker, daemon=True)
        self.save_thread.start()
    
    def _save_worker(self):
        """保存线程工作函数"""
        import queue
        while self.is_running:
            try:
                # 从队列中获取数据，超时1秒
                batch_data = self.data_queue.get(timeout=1)
                if batch_data is None:
                    break
                
                try:
                    # 处理数据
                    self._process_batch(batch_data)
                except Exception as e:
                    if self.log_signal:
                        self.log_signal.emit(f"❌ 处理批次数据出错: {str(e)}")
                finally:
                    # 标记任务完成，确保队列不会被阻塞
                    self.data_queue.task_done()
            except queue.Empty:
                # 队列为空是正常的超时情况，不是错误
                continue
            except Exception as e:
                if self.log_signal:
                    self.log_signal.emit(f"❌ 保存线程出错: {str(e)}")
    
    def _process_batch(self, batch_data):
        """处理单个批次数据"""
        df_all = None
        all_data = None
        try:
            # 逐个处理股票数据，避免一次性合并大量数据
            period = self.strategy.get_period()
            if period == '1d':
                table_name = 'stock_daily'
            elif period == 'tick':
                table_name = 'stock_tick'
            elif period == '1w':
                table_name = 'stock_weekly'
            elif period == '1M':
                table_name = 'stock_monthly'
            else:
                table_name = f'stock_{period}'
            
            total_records = 0
            total_rows = 0
            symbol_count = 0
            start_time = time.time()
            
            # 逐个处理每个股票的数据
            for symbol, df in batch_data:
                if not df.empty:
                    try:
                        # 直接保存单个股票的数据，避免合并大数据框
                        rows = self.strategy.db_manager.smart_bulk_insert(df, period)
                        total_rows += rows
                        total_records += len(df)
                        symbol_count += 1
                        
                        # 暂时禁用频繁的内存清理，避免可能的崩溃
                        # if symbol_count % 3 == 0:
                        #     import gc
                        #     gc.collect()
                        #     # 检查内存使用
                        #     current_memory = self.memory_monitor.get_memory_usage()
                        #     if current_memory > self.memory_monitor.memory_limit_gb * 0.7:
                        #         # 内存使用较高，暂停一下
                        #         time.sleep(0.1)
                    except Exception as insert_error:
                        if self.log_signal:
                            self.log_signal.emit(f"❌ 插入 {symbol} 数据失败: {str(insert_error)}")
                    finally:
                        # 清理单个股票的数据
                        del df
                        # 暂时禁用频繁的内存清理
                        # import gc
                        # gc.collect()
            
            elapsed_time = time.time() - start_time
            speed = total_records / elapsed_time if elapsed_time > 0 else 0
            
            if self.log_signal and symbol_count > 0:
                self.log_signal.emit(f"✅ 成功保存 {total_rows} 条记录到 {table_name} (来自 {symbol_count} 只股票)")
                self.log_signal.emit(f"📊 保存到DuckDB性能: {speed:.2f} 行/秒, 耗时: {elapsed_time:.2f} 秒")
                
        except Exception as e:
            if self.log_signal:
                self.log_signal.emit(f"❌ 处理数据失败: {str(e)}")
        finally:
            # 清理大型对象
            if 'df_all' in locals() and df_all is not None:
                del df_all
            if 'all_data' in locals() and all_data is not None:
                del all_data
            # 暂时禁用强制垃圾回收
            # import gc
            # gc.collect()
    
    def add_data(self, symbol: str, data: pd.DataFrame):
        """添加数据到缓冲区"""
        if not data.empty:
            # 检查内存使用情况，动态调整批次大小
            if self.memory_monitor.should_adjust_batch_size():
                # 内存使用过高，减少批次大小并立即处理
                new_batch_size = max(5, self.max_batch_size // 2)
                if new_batch_size != self.max_batch_size:
                    self.max_batch_size = new_batch_size
                self.flush()
            
            # 检查内存是否超出限额
            if self.memory_monitor.is_memory_exceeded():
                # 内存超出限额，立即处理
                self.flush()
                # 暂时禁用强制垃圾回收，避免可能的崩溃
                # import gc
                # gc.collect()
            
            self.buffer.append((symbol, data))
            if len(self.buffer) >= self.max_batch_size:
                self.flush()
    
    def flush(self):
        """清空缓冲区并将数据添加到队列"""
        if not self.buffer:
            return
        
        try:
            # 检查队列是否已满
            if self.data_queue.qsize() >= 10:
                # 等待队列有空间
                while self.data_queue.qsize() >= 8:
                    import time
                    time.sleep(0.5)
            
            # 复制缓冲区数据
            batch_data = self.buffer.copy()
            # 清空缓冲区
            self.buffer.clear()
            
            # 将数据添加到队列
            self.data_queue.put(batch_data)
            if self.log_signal:
                total_records = sum(len(df) for _, df in batch_data if not df.empty)
                symbol_count = len([symbol for symbol, df in batch_data if not df.empty])
                self.log_signal.emit(f"📥 批次数据已添加到处理队列，等待保存 ({symbol_count} 只股票, {total_records} 条记录)")
        except Exception as e:
            if self.log_signal:
                self.log_signal.emit(f"❌ 刷新缓冲区失败: {str(e)}")
        finally:
            # 暂时禁用强制垃圾回收，避免可能的崩溃
            # import gc
            # gc.collect()
            
            # 定期恢复批次大小
            if self.max_batch_size < self.initial_max_batch_size:
                current_memory = self.memory_monitor.get_memory_usage()
                if current_memory < self.memory_monitor.memory_limit_gb * 0.5:
                    # 内存使用较低，恢复批次大小
                    self.max_batch_size = min(self.initial_max_batch_size, self.max_batch_size * 2)
    
    def stop(self):
        """停止处理"""
        self.is_running = False
        # 向队列中添加None以结束保存线程
        try:
            self.data_queue.put(None, timeout=1)
        except:
            pass
        # 等待保存线程结束
        if self.save_thread and self.save_thread.is_alive():
            self.save_thread.join(timeout=5)
        # 清空队列
        while not self.data_queue.empty():
            try:
                self.data_queue.get_nowait()
                self.data_queue.task_done()
            except:
                break