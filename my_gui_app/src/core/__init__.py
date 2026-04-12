# -*- coding: utf-8 -*-
"""
核心数据管理模块

功能描述：提供统一的数据管理接口，支持多数据源：
- DuckDB本地数据库
- Tushare在线API
- QMT历史数据
"""

__version__ = '1.0.0'
__author__ = 'Trae IDE'

from .utils import (
    DownloadConfig,
    retry_with_backoff,
    DailyDataStrategy,
    MinuteDataStrategy,
    TickDataStrategy,
    WeeklyDataStrategy,
    MonthlyDataStrategy,
    StreamingProcessor,
    MemoryMonitor
)
from .data.database.db_manager import get_db_manager
from .data.processing.optimized_processor import OptimizedDataProcessor
from .data.database.connection_pool import get_connection_pool

__all__ = [
    # 工具类
    'DownloadConfig',
    'retry_with_backoff',
    'DailyDataStrategy',
    'MinuteDataStrategy',
    'TickDataStrategy',
    'WeeklyDataStrategy',
    'MonthlyDataStrategy',
    'StreamingProcessor',
    'MemoryMonitor',
    
    # 数据库管理
    'get_db_manager',
    'OptimizedDataProcessor',
    'get_connection_pool'
]
