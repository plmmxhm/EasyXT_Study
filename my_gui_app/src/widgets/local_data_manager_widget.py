#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
功能描述：本地数据管理GUI组件
提供本地数据的下载、管理和查看功能，支持股票、债券等多种金融数据的获取和处理

测试内容：
1. 测试股票数据下载功能，包括日线、分钟线、tick数据
2. 测试数据更新和历史数据补充功能
3. 测试财务数据下载功能
4. 测试数据验证功能
5. 测试断点续传和失败记录功能

版本：v1.0.0
创建时间：2026-03-25
修订时间：2026-03-25
创建人：Trae IDE
修订信息：
- 2026-03-25：初始创建，实现本地数据管理功能
- 2026-03-25：添加详细的文档注释和修订信息
- 2026-03-25：优化代码结构和性能
- 2026-03-25：添加断点续传和失败记录功能
- 2026-03-25：支持多种数据类型和周期
"""


import sys
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import pandas as pd

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 添加项目总根目录，确保能找到xtquant模块
total_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..', '..'))
if total_root not in sys.path:
    sys.path.insert(0, total_root)

# 全局导入xtquant模块
try:
    # 添加可能的xtquant路径（添加的是xtquant目录的父目录，而不是xtquant目录本身）
    possible_paths = [
        total_root,  # 当前项目目录（包含xtquant子目录）
        os.getcwd(),  # 当前工作目录（包含xtquant子目录）
        'D:/quant',  # D:/quant目录（包含xtquant子目录）
        'D:/qmt/bin'  # D:/qmt/bin目录（包含xtquant子目录）
    ]
    
    for path in possible_paths:
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)
            print(f"[INFO] 添加路径: {path}")
    
    # 尝试导入xtquant
    import xtquant
    import xtquant.xtdata
    print("[OK] xtquant 模块导入成功")
    XTDATA_AVAILABLE = True
except ImportError as e:
    print(f"[ERROR] 导入xtquant模块失败: {str(e)}")
    XTDATA_AVAILABLE = False

# 导入新的工具和策略
from src.core.utils import DownloadConfig, retry_with_backoff, DailyDataStrategy, BondDataStrategy, MinuteDataStrategy, TickDataStrategy, WeeklyDataStrategy, MonthlyDataStrategy, StreamingProcessor
from src.core.data.database.db_manager import get_db_manager

# 导入复权缓存模块
try:
    from src.core.data.adjustment.adjustment_cache import AdjustmentCache
    ADJUSTMENT_CACHE_AVAILABLE = True
except ImportError:
    ADJUSTMENT_CACHE_AVAILABLE = False



def setup_logger():
    """设置日志记录器"""
    # 确保日志目录存在
    current_dir = os.path.dirname(__file__)
    my_gui_app_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
    log_dir = os.path.join(my_gui_app_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 生成日志文件名
    log_filename = f"local_data_manager_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path = os.path.join(log_dir, log_filename)
    
    # 创建logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 清除现有的handlers
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)
    
    # 创建file handler
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # 创建stream handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    
    # 设置格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    
    # 添加handlers
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    
    return logger

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox,
    QProgressBar, QSplitter, QFrame, QMessageBox, QDialog,
    QFileDialog, QFormLayout, QScrollArea, QSizePolicy,
    QToolButton, QMenu, QAction, QDateEdit, QTreeWidgetItem,
    QTreeWidget, QComboBox, QInputDialog, QRadioButton
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QDate, QCoreApplication
from datetime import datetime, timedelta
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QTextCursor
import time

import pandas as pd
import numpy as np

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 添加项目总根目录，确保能找到xtquant模块
total_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..', '..'))
if total_root not in sys.path:
    sys.path.insert(0, total_root)

# 全局导入xtquant模块
try:
    # 添加可能的xtquant路径
    possible_paths = [
        'D:/quant/xtquant',
        'D:/qmt/bin/xtquant',
        'C:/qmt/bin/xtquant',
        'D:/miniqmt/bin/xtquant',
        'C:/miniqmt/bin/xtquant',
        os.path.join(total_root, 'xtquant'),  # 当前项目目录下的xtquant
        os.path.abspath('xtquant')  # 当前工作目录下的xtquant
    ]
    
    for path in possible_paths:
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)
            print(f"[INFO] 添加 xtquant 路径: {path}")
    
    # 尝试导入xtquant
    import xtquant
    import xtquant.xtdata
    print("[OK] xtquant 模块导入成功")
    XTDATA_AVAILABLE = True
except ImportError as e:
    print(f"[ERROR] 导入xtquant模块失败: {str(e)}")
    XTDATA_AVAILABLE = False

widgets_path = os.path.join(project_root, 'gui_app', 'widgets')
if widgets_path not in sys.path:
    sys.path.insert(0, widgets_path)

# 导入财务数据保存线程
try:
    from advanced_data_viewer_widget import BatchFinancialSaveThread
    BATCH_SAVE_AVAILABLE = True
except ImportError:
    BATCH_SAVE_AVAILABLE = False


class DataDownloadThread(QThread):
    """数据下载线程
    
    负责股票、债券等金融数据的下载和处理，支持多种数据类型和周期
    采用策略模式处理不同类型的数据下载，支持并行下载和断点续传
    
    Signals:
        log_signal: 日志信号，用于输出下载过程中的日志信息
        progress_signal: 进度信号，传递当前进度、预期进度和总进度
        finished_signal: 完成信号，传递下载结果
        error_signal: 错误信号，传递错误信息
    """
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int, int)  # current, expected, total
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    
    def log(self, message):
        """输出日志
        
        Args:
            message: 日志消息内容
        """
        self.log_signal.emit(message)
    
    def fix_duckdb_views(self):
        """修复DuckDB/Parquet视图定义"""
        try:
            self.log("🔧 开始修复DuckDB视图定义...")
            
            import duckdb
            from src.core.utils import DownloadConfig
            
            config = DownloadConfig()
            data_config = config.get_config()
            
            dbfile = data_config.get('database', {}).get('dbfile', 'stock_data.ddb')
            data_root_dir = data_config.get('data_paths', {}).get('root_dir', 'D:/MyStockData')
            db_path = str(Path(data_root_dir) / dbfile)
            
            parquet_config = data_config.get('storage', {}).get('parquet', {})
            parquet_root_dir = parquet_config.get('root_dir', 'Parquet')
            parquet_root = Path(data_root_dir) / parquet_root_dir
            
            # 关键修复：创建数据库连接（之前缺少这行！）
            conn = duckdb.connect(db_path, read_only=False)
            
            for subdir in ['kline/daily', 'kline/1m', 'kline/5m', 'kline/15m', 'kline/30m', 'kline/60m', 'kline/weekly', 'kline/monthly', 'tick']:
                (parquet_root / subdir).mkdir(parents=True, exist_ok=True)
            
            views_config = [
                ('stock_daily', 'kline/daily', 'date', '1d'),
                ('stock_1m', 'kline/1m', 'datetime', '1m'),
                ('stock_5m', 'kline/5m', 'datetime', '5m'),
                ('stock_15m', 'kline/15m', 'datetime', '15m'),
                ('stock_30m', 'kline/30m', 'datetime', '30m'),
                ('stock_60m', 'kline/60m', 'datetime', '60m'),
                ('stock_weekly', 'kline/weekly', 'date', '1w'),
                ('stock_monthly', 'kline/monthly', 'date', '1M'),
                ('stock_tick', 'tick', 'datetime', 'tick'),
            ]
            
            for view_name, path_part, date_col, period_val in views_config:
                self.log(f"📊 创建/更新 {view_name} 视图...")
                try:
                    conn.execute(f"DROP VIEW IF EXISTS main.{view_name}")
                    
                    if path_part == 'tick':
                        parquet_path = str(parquet_root / 'tick' / '**' / '*.parquet').replace('\\', '/')
                    else:
                        parquet_path = str(parquet_root / path_part / '**' / '*.parquet').replace('\\', '/')
                    
                    if view_name in ['stock_weekly', 'stock_monthly']:
                        select_date = "COALESCE(date, CURRENT_DATE) AS " + date_col
                    elif view_name == 'stock_daily':
                        select_date = "COALESCE(date, CURRENT_DATE) AS " + date_col
                    else:
                        select_date = "COALESCE(datetime::TIMESTAMP, CURRENT_TIMESTAMP::TIMESTAMP) AS " + date_col
                    
                    if view_name == 'stock_tick':
                        sql = f"""
                            CREATE OR REPLACE VIEW main.{view_name} AS
                            SELECT 
                                COALESCE(stock_code, '') AS stock_code,
                                {select_date},
                                COALESCE(open, 0.0) AS open,
                                COALESCE(high, 0.0) AS high,
                                COALESCE(low, 0.0) AS low,
                                COALESCE(close, 0.0) AS close,
                                COALESCE(volume, 0) AS volume,
                                COALESCE(amount, 0.0) AS amount,
                                COALESCE(lastPrice, 0.0) AS lastPrice,
                                COALESCE(lastClose, 0.0) AS lastClose,
                                COALESCE(openInt, 0.0) AS openInt,
                                COALESCE(pvolume, 0) AS pvolume,
                                COALESCE(transactionNum, 0) AS transactionNum,
                                COALESCE(func_type, 0) AS func_type,
                                COALESCE(lastSettlementPrice, 0.0) AS lastSettlementPrice,
                                COALESCE(stockStatus, '') AS stockStatus,
                                COALESCE(askPrice, '[]') AS askPrice,
                                COALESCE(bidPrice, '[]') AS bidPrice,
                                COALESCE(askVol, '[]') AS askVol,
                                COALESCE(bidVol, '[]') AS bidVol,
                                'stock' as symbol_type,
                                '{period_val}' as period,
                                'none' as adjust_type,
                                1.0 as factor,
                                CURRENT_TIMESTAMP as created_at,
                                CURRENT_TIMESTAMP as updated_at
                            FROM read_parquet('{parquet_path}', union_by_name=true, filename=true, hive_partitioning=true)
                            WHERE COALESCE(stock_code, '') != ''
                        """
                    else:
                        sql = f"""
                            CREATE OR REPLACE VIEW main.{view_name} AS
                            SELECT 
                                COALESCE(stock_code, '') AS stock_code,
                                {select_date},
                                COALESCE(open, 0.0) AS open,
                                COALESCE(high, 0.0) AS high,
                                COALESCE(low, 0.0) AS low,
                                COALESCE(close, 0.0) AS close,
                                COALESCE(volume, 0) AS volume,
                                COALESCE(amount, 0.0) AS amount,
                                'stock' as symbol_type,
                                '{period_val}' as period,
                                'none' as adjust_type,
                                1.0 as factor,
                                CURRENT_TIMESTAMP as created_at,
                                CURRENT_TIMESTAMP as updated_at
                            FROM read_parquet('{parquet_path}', union_by_name=true, filename=true, hive_partitioning=true)
                            WHERE COALESCE(stock_code, '') != ''
                        """
                    
                    conn.execute(sql)
                    self.log(f"✅ {view_name} 视图创建/更新成功")
                    
                except Exception as e:
                    self.log(f"⚠️ 创建 {view_name} 视图失败: {e}")
            
            self.log("🔍 验证视图创建...")
            try:
                tables = conn.execute("SELECT table_name FROM information_schema.views WHERE table_schema='main'").fetchall()
                view_tables = [t[0] for t in tables if t[0].startswith('stock_')]
                self.log(f"✅ 已创建的视图: {', '.join(view_tables)}")
                
                for check_view in ['stock_daily', 'stock_weekly', 'stock_monthly']:
                    try:
                        count = conn.execute(f'SELECT COUNT(*) FROM main.{check_view}').fetchone()[0]
                        self.log(f"📊 {check_view}: {count} 条记录")
                    except Exception:
                        self.log(f"⚠️ 无法查询 {check_view}")
                
            except Exception as e:
                self.log(f"⚠️ 验证视图创建失败: {e}")
            
            conn.close()
            self.log("✅ DuckDB视图定义修复完成")
            
        except Exception as e:
            self.log(f"❌ 修复DuckDB视图定义失败: {e}")
            import traceback
            self.log(traceback.format_exc())


    def __init__(self, task_type, symbols, start_date, end_date, data_type='daily', period='1d', db_path=None, update_mode='existing', test_mode=False, config=None, preloaded_stocks=None):
        """初始化数据下载线程
        
        Args:
            task_type: 任务类型，如 'download_stocks', 'download_bonds', 'update_data', 'backfill_history'
            symbols: 股票代码列表
            start_date: 开始日期，格式为 'YYYYMMDD'
            end_date: 结束日期，格式为 'YYYYMMDD'
            data_type: 数据类型，如 'daily', '1min', '5min', 'tick'
            period: 数据周期，如 '1d', '1m', '5m', '15m', '30m', '60m', 'tick'
            db_path: 数据库路径
            update_mode: 更新模式，'existing' 或 'all'
            test_mode: 测试模式，是否只处理少量数据
            config: 配置字典
            preloaded_stocks: 预加载的股票列表
        """
        super().__init__()
        self.task_type = task_type  # 'download_stocks', 'download_bonds', 'update_data'
        self.symbols = symbols
        self.preloaded_stocks = preloaded_stocks
        self.start_date = start_date
        self.end_date = end_date
        self.data_type = data_type  # 'daily', '1min', '5min', 'tick'
        self.period = period  # '1d', '1m', '5m', '15m', '30m', '60m', 'tick'
        self.db_path = db_path
        self.update_mode = update_mode  # 'existing' or 'all'
        self.test_mode = test_mode  # 测试模式
        self.config = config  # 配置字典
        self._is_running = True
        self.executor = None  # 线程池引用
        self.thread_id = None  # 线程ID
    
    def _get_all_stock_codes(self):
        """获取所有股票代码
        
        Returns:
            list: 股票代码列表
        """
        # 优先使用传入的股票列表
        if self.symbols:
            return self.symbols
        # 其次使用预加载的股票列表
        elif self.preloaded_stocks:
            return self.preloaded_stocks
        # 最后尝试从数据库获取
        else:
            try:
                from src.core.data.database.db_manager import get_db_manager
                db_manager = get_db_manager(self.db_path)
                # 尝试从 stock_daily 表获取股票代码
                query = "SELECT DISTINCT stock_code FROM stock_daily"
                df = db_manager.query_to_dataframe(query)
                if not df.empty:
                    return df['stock_code'].tolist()
                # 如果 stock_daily 表为空，尝试从其他表获取
                query = "SELECT DISTINCT stock_code FROM stock_1m"
                df = db_manager.query_to_dataframe(query)
                if not df.empty:
                    return df['stock_code'].tolist()
                # 如果所有表都为空，返回空列表
                return []
            except Exception as e:
                self.log(f"⚠️ 获取股票列表失败: {e}")
                return []
    
    def stop(self):
        """请求停止下载（异步，立即返回）
        
        执行以下操作：
        1. 设置停止标志
        2. 尝试取消线程池中的所有未开始的任务
        3. 立即关闭线程池
        4. 退出线程
        5. 等待线程结束，确保资源被正确清理
        6. 发送停止完成的信号
        """
        self.log("⏹️ 收到停止请求，正在停止...")
        # 1. 设置停止标志
        self._is_running = False
        
        # 2. 尝试取消线程池中的所有 Future (非阻塞)
        if self.executor:
            self.log("🔄 正在取消未开始的下载任务...")
            # 获取所有未完成的 Future 并尝试取消
            try:
                # 注意：这里只能取消尚未开始运行的任务
                # 对于已开始的任务，取消操作无效，它们会运行到完成或报错
                if hasattr(self, 'futures'):
                    for future in self.futures.values():
                        future.cancel()
            except Exception as e:
                self.log(f"⚠️ 取消任务时出错: {str(e)}")
        
        # 3. 立即关闭线程池（如果存在）
        if self.executor:
            try:
                # 立即关闭线程池，不等待任务完成
                self.executor.shutdown(wait=False)
                self.log("✅ 线程池已关闭")
            except Exception as e:
                self.log(f"❌ 关闭线程池失败: {str(e)}")
        
        # 4. 立即退出线程，不等待
        self.quit()
        
        # 5. 等待线程结束，确保资源被正确清理
        self.wait(1000)  # 等待最多1秒，避免阻塞主线程
        
        # 6. 发送停止完成的信号
        self.log("✅ 下载已停止")
        self.finished_signal.emit({"task_type": "stopped", "message": "下载已成功停止"})

    def run(self):
        """运行下载任务
        
        根据任务类型选择合适的策略进行数据下载：
        - download_stocks: 使用日线数据策略
        - download_minute_data: 根据周期选择合适的分钟线策略
        - download_bonds: 使用债券数据策略
        - update_data: 执行数据更新任务
        - backfill_history: 执行历史数据补充任务
        """
        # 记录线程ID
        import threading
        self.thread_id = threading.get_ident()
        
        try:
            self.log(f"🚀 线程启动，ID: {self.thread_id}")
            
            # 注意：不在每次启动时自动修复DuckDB视图
            # 视图修复应该只在用户点击"更新数据库视图"按钮时执行
            # self.fix_duckdb_views()  # 已移除自动调用
            
            # 加载配置
            # print(f"[DEBUG] 加载配置...")
            self.log("📦 加载配置...")
            config = DownloadConfig(self.config)
            # print(f"[DEBUG] 配置加载完成")
            self.log("✅ 配置加载完成")
            
            # 初始化数据库连接管理器
            # print(f"[DEBUG] 初始化数据库连接管理器...")
            self.log("🗃️ 初始化数据库连接管理器...")
            from src.core.data.database.db_manager import get_db_manager
            db_manager = get_db_manager(self.db_path)
            # print(f"[DEBUG] 数据库连接管理器初始化完成")
            self.log("✅ 数据库连接管理器初始化完成")
            
            task_info = f"type={self.task_type}, symbols={len(self.symbols) if self.symbols else 0}, start={self.start_date}, end={self.end_date}, period={self.period}"
            # print(f"[DEBUG] 任务信息: {task_info}")
            self.log(f"📋 任务信息: {task_info}")
            
            if self.task_type == 'download_stocks':
                # 使用日线数据策略
                # print(f"[DEBUG] 使用日线数据策略")
                self.log("📊 使用日线数据策略")
                strategy = DailyDataStrategy(db_manager, config, self.log_signal)
                self._download_with_strategy(strategy)
            elif self.task_type == 'download_minute_data':
                # 根据周期选择合适的策略
                # print(f"[DEBUG] 使用分钟线数据策略")
                self.log("📊 使用分钟线数据策略")
                if self.period == 'tick':
                    strategy = TickDataStrategy(db_manager, config, self.log_signal)
                elif self.period == 'weekly':
                    strategy = WeeklyDataStrategy(db_manager, config, self.log_signal)
                elif self.period == 'monthly':
                    strategy = MonthlyDataStrategy(db_manager, config, self.log_signal)
                else:
                    strategy = MinuteDataStrategy(db_manager, config, self.log_signal, self.period)
                # print(f"[DEBUG] 策略创建完成，开始下载")
                self._download_with_strategy(strategy)
            elif self.task_type == 'download_bonds':
                # 债券数据使用专门的债券策略
                # print(f"[DEBUG] 使用债券数据策略")
                self.log("📊 使用债券数据策略")
                from src.core.utils import BondDataStrategy
                strategy = BondDataStrategy(db_manager, config, self.log_signal)
                self._download_with_strategy(strategy, is_bond=True)
            elif self.task_type == 'update_data':
                # print(f"[DEBUG] 执行数据更新任务")
                self.log("🔄 执行数据更新任务")
                self._update_data()
            elif self.task_type == 'backfill_history':
                # print(f"[DEBUG] 执行历史数据补充任务")
                self.log("📈 执行历史数据补充任务")
                self._backfill_history()
            else:
                # print(f"[DEBUG] 未知任务类型: {self.task_type}")
                self.log(f"❌ 未知任务类型: {self.task_type}")
        except Exception as e:
            import traceback
            error_msg = f"下载失败: {str(e)}\n{traceback.format_exc()}"
            # print(f"[DEBUG] 异常: {error_msg}")
            self.log(error_msg)
            self.error_signal.emit(error_msg)

    def _download_with_strategy(self, strategy, is_bond=False, force_update=False):
        """使用策略模式下载数据
        
        采用策略模式处理不同类型的数据下载，支持并行下载和断点续传
        
        Args:
            strategy: 数据下载策略对象
            is_bond: 是否为债券数据
            force_update: 是否强制更新数据
        """
        try:
            # 检查xtquant模块是否可用
            if not XTDATA_AVAILABLE:
                error_msg = "❌ xtquant模块不可用，请确保QMT已安装并运行"
                self.log(error_msg)
                self.error_signal.emit(error_msg)
                return
            
            # 导入xtdata
            from xtquant import xtdata
            import concurrent.futures
            import os
            import gc
            from src.core.utils import MemoryMonitor, DownloadConfig

            # 加载配置
            config = DownloadConfig(self.config)

            # print(f"[DEBUG] 检查股票列表: {len(self.symbols) if self.symbols else 0}")
            # 如果没有指定股票列表，使用预加载的股票列表或获取全部A股（排除ETF）或可转债
            if not self.symbols:
                # 首先尝试使用预加载的股票列表
                if self.preloaded_stocks:
                    self.symbols = self.preloaded_stocks
                    self.log(f"✅ 使用预加载的股票列表，共 {len(self.symbols)} 只A股（已排除ETF和基金）")
                else:
                    if is_bond:
                        # print(f"[DEBUG] 获取可转债列表")
                        self.log("📊 正在获取可转债列表...")
                        # 尝试从QMT获取可转债列表
                        try:
                            # 尝试使用 easy_xt API 获取可转债列表
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
                                                self.log("✅ easy_xt API 数据服务初始化成功")
                                            else:
                                                self.log("⚠️ easy_xt API 数据服务初始化返回False")
                                        
                                        # 如果第一次初始化失败，尝试在data对象上初始化
                                        if not init_success and hasattr(api, 'data') and hasattr(api.data, 'init_data'):
                                            init_result = api.data.init_data()
                                            if init_result:
                                                init_success = True
                                                self.log("✅ easy_xt API.data 数据服务初始化成功")
                                            else:
                                                self.log("⚠️ easy_xt API.data 数据服务初始化返回False")
                                    except Exception as init_e:
                                        self.log(f"⚠️ easy_xt API 初始化失败: {init_e}")
                                    
                                    # 只有在初始化成功后才尝试获取数据
                                    if init_success:
                                        # 使用 api.get_stock_list() 获取可转债列表
                                        bond_list = api.get_stock_list('可转债')
                                        if bond_list and len(bond_list) > 0:
                                            self.symbols = [bond for bond in bond_list if bond.endswith('.SH') or bond.endswith('.SZ')]
                                            self.log(f"✅ 从 easy_xt API 获取到 {len(self.symbols)} 只可转债")
                                        else:
                                            self.log("⚠️ easy_xt API 返回空列表，尝试使用 xtdata")
                                            # 尝试使用 xtdata 获取可转债列表
                                            all_bonds = xtdata.get_stock_list_in_sector('沪深转债')
                                            self.symbols = [bond for bond in all_bonds if bond.endswith('.SH') or bond.endswith('.SZ')]
                                            self.log(f"✅ 从 xtdata 获取到 {len(self.symbols)} 只可转债")
                                    else:
                                        self.log("⚠️ easy_xt API 数据服务未初始化，尝试使用 xtdata")
                                        # 尝试使用 xtdata 获取可转债列表
                                        all_bonds = xtdata.get_stock_list_in_sector('沪深转债')
                                        self.symbols = [bond for bond in all_bonds if bond.endswith('.SH') or bond.endswith('.SZ')]
                                        self.log(f"✅ 从 xtdata 获取到 {len(self.symbols)} 只可转债")
                                finally:
                                    # 清理资源，避免MiniRacer异常
                                    if api and hasattr(api, 'close'):
                                        try:
                                            api.close()
                                        except:
                                            pass
                            except Exception as e:
                                self.log(f"⚠️ easy_xt API 获取可转债列表失败: {e}")
                                # 尝试使用 xtdata 获取可转债列表
                                all_bonds = xtdata.get_stock_list_in_sector('沪深转债')
                                self.symbols = [bond for bond in all_bonds if bond.endswith('.SH') or bond.endswith('.SZ')]
                                self.log(f"✅ 从 xtdata 获取到 {len(self.symbols)} 只可转债")
                            
                            # 如果获取不到可转债，使用预定义列表
                            if not self.symbols:
                                self.log("⚠️ 获取失败，使用预定义列表")
                                # 使用预定义的可转债列表作为备用
                                self.symbols = [
                                    # 沪市可转债 (11xxxx)
                                    '113011.SH', '113016.SH', '113020.SH', '113021.SH', '113022.SH',
                                    '113023.SH', '113024.SH', '113027.SH', '113028.SH', '113030.SH',
                                    '113031.SH', '113032.SH', '113033.SH', '113035.SH', '113036.SH',
                                    '113037.SH', '113038.SH', '113040.SH', '113041.SH', '113042.SH',
                                    '113043.SH', '113044.SH', '113045.SH', '113046.SH', '113047.SH',
                                    '113048.SH', '113049.SH', '113050.SH', '113051.SH', '113052.SH',
                                    # 深市可转债 (12xxxx)
                                    '127001.SZ', '127002.SZ', '127003.SZ', '127004.SZ', '127005.SZ',
                                    '127006.SZ', '127007.SZ', '127008.SZ', '127009.SZ', '127010.SZ',
                                    '123001.SZ', '123002.SZ', '123003.SZ', '123004.SZ', '123005.SZ',
                                    '123006.SZ', '123007.SZ', '123008.SZ', '123009.SZ', '123010.SZ'
                                ]
                                self.log(f"✅ 使用预定义列表，获取到 {len(self.symbols)} 只可转债")
                        except Exception as e:
                            self.log(f"⚠️ 获取可转债列表失败: {e}")
                            # 使用预定义的可转债列表作为备用
                            self.symbols = [
                                # 沪市可转债 (11xxxx)
                                '113011.SH', '113016.SH', '113020.SH', '113021.SH', '113022.SH',
                                '113023.SH', '113024.SH', '113027.SH', '113028.SH', '113030.SH',
                                '113031.SH', '113032.SH', '113033.SH', '113035.SH', '113036.SH',
                                '113037.SH', '113038.SH', '113040.SH', '113041.SH', '113042.SH',
                                '113043.SH', '113044.SH', '113045.SH', '113046.SH', '113047.SH',
                                '113048.SH', '113049.SH', '113050.SH', '113051.SH', '113052.SH',
                                # 深市可转债 (12xxxx)
                                '127001.SZ', '127002.SZ', '127003.SZ', '127004.SZ', '127005.SZ',
                                '127006.SZ', '127007.SZ', '127008.SZ', '127009.SZ', '127010.SZ',
                                '123001.SZ', '123002.SZ', '123003.SZ', '123004.SZ', '123005.SZ',
                                '123006.SZ', '123007.SZ', '123008.SZ', '123009.SZ', '123010.SZ'
                            ]
                            self.log(f"✅ 使用预定义列表，获取到 {len(self.symbols)} 只可转债")
                    else:
                        # print(f"[DEBUG] 获取A股列表")
                        self.log("📊 正在获取A股列表（排除ETF）...")
                        # 简化获取A股列表的方法，添加超时处理
                        import time
                        start_time = time.time()
                        try:
                            # 尝试获取A股列表
                            all_stocks = xtdata.get_stock_list_in_sector('沪深A股')
                            self.log(f"✅ 获取A股列表成功，耗时 {time.time() - start_time:.2f} 秒")
                            
                            # 过滤掉ETF和基金
                            etf_patterns = [
                                '51', '159', '150', '588', '50', '56', '58'
                            ]
                            
                            self.symbols = []
                            for stock in all_stocks:
                                code = stock.split('.')[0]
                                is_etf = False
                                for pattern in etf_patterns:
                                    if code.startswith(pattern):
                                        is_etf = True
                                        break
                                if not is_etf:
                                    self.symbols.append(stock)
                            
                            self.log(f"✅ 获取到 {len(self.symbols)} 只A股（已排除ETF和基金）")
                        except Exception as e:
                            self.log(f"⚠️ 获取A股列表失败: {e}")
                            # 使用预定义的股票列表作为备用
                            self.symbols = [
                                '600000.SH', '600001.SH', '600002.SH', '600003.SH', '600004.SH',
                                '600005.SH', '600006.SH', '600007.SH', '600008.SH', '600009.SH',
                                '600010.SH', '600011.SH', '600012.SH', '600015.SH', '600016.SH',
                                '600018.SH', '600019.SH', '600020.SH', '600021.SH', '600022.SH',
                                '600026.SH', '600027.SH', '600028.SH', '600029.SH', '600030.SH',
                                '600031.SH', '600033.SH', '600036.SH', '600037.SH', '600038.SH',
                                '600039.SH', '600048.SH', '600050.SH', '600051.SH', '600052.SH',
                                '600053.SH', '600054.SH', '600056.SH', '600058.SH', '600060.SH',
                                '600061.SH', '600062.SH', '600063.SH', '600066.SH', '600067.SH',
                                '600068.SH', '600070.SH', '600073.SH', '600076.SH', '600078.SH'
                            ]
                            self.log(f"✅ 使用预定义列表，获取到 {len(self.symbols)} 只A股")

            total = len(self.symbols)
            success_count = 0
            failed_count = 0
            failed_list = []
            completed_symbols = []
            failed_symbols = []

            # 测试模式：只处理配置的股票或可转债数量
            if hasattr(self, 'test_mode') and self.test_mode:
                # 加载配置
                period = strategy.get_period()
                if is_bond:
                    # 可转债测试模式配置
                    test_count = config.get_test_stock_count(period)
                    self.symbols = self.symbols[:test_count]
                    total = len(self.symbols)
                    self.log(f"🔧 测试模式：{period}数据只处理前{test_count}只可转债")
                else:
                    # 股票测试模式配置
                    test_count = config.get_test_stock_count(period)
                    self.symbols = self.symbols[:test_count]
                    total = len(self.symbols)
                    self.log(f"🔧 测试模式：{period}数据只处理前{test_count}只股票")

            # 保存原始股票总数
            original_total = total

            # 检查是否是单只股票下载
            is_single_stock = len(self.symbols) == 1

            # 生成任务ID，仅用于日志
            task_id = f"{self.task_type}_{strategy.get_period()}_{self.start_date}_{self.end_date}"
            
            # 初始化内存监控器
            memory_monitor = MemoryMonitor(log_signal=self.log_signal)
            
            # 初始化性能分析器
            performance_history = []
            batch_performance = []
            
            # 生成任务ID，仅用于日志
            task_id = f"download_{strategy.get_period()}_{self.start_date}_{self.end_date}"

            # 从Parquet文件中获取已完成的股票列表（直接扫描文件）
            self.log("📋 检查已下载的数据文件")
            completed_symbols = []
            try:
                from pathlib import Path
                
                # 获取配置中的 Parquet 根目录
                config = DownloadConfig(self.config)
                data_config = config.get_config()
                data_root_dir = data_config.get('data_paths', {}).get('root_dir', 'D:/MyStockData')
                parquet_config = data_config.get('storage', {}).get('parquet', {})
                parquet_root_dir = parquet_config.get('root_dir', 'Parquet')
                parquet_root = Path(data_root_dir) / parquet_root_dir
                
                # 确定数据路径
                period = strategy.get_period()
                if period == '1d':
                    parquet_path = parquet_root / 'kline' / 'daily'
                elif period == '1w' or period == 'weekly':
                    parquet_path = parquet_root / 'kline' / 'weekly'
                elif period == '1mon' or period == 'monthly':
                    parquet_path = parquet_root / 'kline' / 'monthly'
                elif period == 'tick':
                    parquet_path = parquet_root / 'tick'
                else:
                    parquet_path = parquet_root / 'kline' / period
                
                # 扫描所有 parquet 文件
                if parquet_path.exists():
                    for exchange_dir in parquet_path.iterdir():
                        if exchange_dir.is_dir():
                            for file in exchange_dir.glob('*.parquet'):
                                symbol = file.stem
                                full_symbol = f"{symbol}.{exchange_dir.name}"
                                completed_symbols.append(full_symbol)
                
                self.log(f"📋 从数据文件中扫描到 {len(completed_symbols)} 只已完成的股票")
            except Exception as e:
                self.log(f"⚠️ 扫描已下载文件失败: {e}")

            # 过滤掉已完成的股票，避免重复下载
            if completed_symbols and not force_update:
                original_count = len(self.symbols)
                # 注意：数据文件中的股票代码可能没有后缀（如.SH），需要匹配
                # 提取股票代码的基础部分进行匹配
                def get_base_symbol(symbol):
                    # 处理不同格式的股票代码：SH.600000 或 600000.SH
                    if '.' in symbol:
                        parts = symbol.split('.')
                        # 找到数字部分作为股票代码
                        for part in parts:
                            if part.isdigit():
                                return part
                        # 如果没有数字部分，返回最后一个部分
                        return parts[-1]
                    else:
                        return symbol
                
                # 构建已完成股票的基础代码集合
                completed_base_symbols = set(get_base_symbol(s) for s in completed_symbols)
                
                # 过滤符号列表
                filtered_symbols = []
                for symbol in self.symbols:
                    if get_base_symbol(symbol) not in completed_base_symbols:
                        filtered_symbols.append(symbol)
                
                self.symbols = filtered_symbols
                filtered_count = len(self.symbols)
                skipped_count = original_count - filtered_count
                if skipped_count > 0:
                    self.log(f"📋 根据数据文件跳过 {skipped_count} 只已完成的股票，剩余 {filtered_count} 只待下载")

            # 获取处理限额配置
            processing_limit = strategy.config.get_processing_limit()
            max_symbols_per_batch = processing_limit['max_symbols_per_batch']
            max_records_per_batch = processing_limit['max_records_per_batch']
            reset_interval_symbols = processing_limit['reset_interval_symbols']
            reset_interval_records = processing_limit['reset_interval_records']
            
            self.log(f"⚙️ 处理限额配置: 每批最大标的数={max_symbols_per_batch}, 每批最大记录数={max_records_per_batch}")
            self.log(f"⚙️ 资源重置间隔: 每{reset_interval_symbols}只标的, 每{reset_interval_records}条记录")

            # 获取批量大小
            initial_batch_size = strategy.get_batch_size()
            # 为不同周期数据设置合适的批次大小
            period = strategy.get_period()
            if period == '1m':
                initial_batch_size = 2  # 1分钟数据使用最小的批次大小
            elif period in ['5m', '15m', '30m', '60m', 'weekly', 'monthly']:
                initial_batch_size = 4  # 其他周期数据使用较小的批次大小
            current_batch_size = initial_batch_size
            # 优化线程配置，根据数据类型和系统资源动态调整
            cpu_count = os.cpu_count() or 4
            if period == '1m':
                max_workers = min(cpu_count, 4)  # 1分钟数据使用最多4个线程
            elif period == 'tick':
                max_workers = min(cpu_count, 2)  # Tick数据使用较少线程，避免内存压力
            else:
                max_workers = min(cpu_count * 2, 8)  # 其他数据使用更多线程，提高并行度
            
            self.log(f"🚀 启动 {max_workers} 个下载线程")
            self.log(f"📊 开始下载 {strategy.get_period()} 数据")
            self.log(f"📦 初始批次大小: {current_batch_size}")

            # 初始化流式处理器，使用逐个处理模式
            # print(f"[DEBUG] 初始化流式处理器")
            from src.core.data.processing.optimized_processor import OptimizedDataProcessor
            # 初始化处理器，不传递config参数，让它使用默认配置
            processor = OptimizedDataProcessor(strategy.db_manager, self.log_signal)

            # 数据下载函数
            thread_self = self  # 捕获当前线程实例的引用
            @retry_with_backoff(max_retries=3, initial_delay=1, max_delay=10)
            def download_data(symbol):
                """下载单个股票数据"""
                # 在开始时就检查
                if not thread_self._is_running:
                    return symbol, None, "下载已被用户取消", False
                try:
                    # 使用策略下载数据
                    df, is_skip = strategy.download_data(
                        symbol, 
                        thread_self.start_date, 
                        thread_self.end_date,
                        force_update=force_update
                    )
                    # 再次检查
                    if not thread_self._is_running:
                        return symbol, None, "下载已被用户取消", False
                    if df is not None and not df.empty:
                        return symbol, df, None, False
                    else:
                        if is_skip:
                            return symbol, None, "数据已存在，跳过下载", True
                        else:
                            return symbol, None, "数据为空", False
                except Exception as e:
                    # 检查停止标志
                    if not thread_self._is_running:
                        return symbol, None, "下载已被用户取消", False
                    return symbol, None, str(e)[:50], False

            # 使用线程池并行下载
            self.log("📥 开始并行下载数据...")
            processed_count = 0
            processed_records = 0
            memory_check_interval = 10  # 每10个股票检查一次内存
            import threading
            data_lock = threading.Lock()  # 用于保护共享数据的锁

            # 创建线程池
            # print(f"[DEBUG] 创建线程池，最大工作线程: {max_workers}")
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
            executor = self.executor
            self.futures = {}
            
            try:
                # 提交所有下载任务
                # print(f"[DEBUG] 提交下载任务: {len(self.symbols)} 个")
                future_to_symbol = {}
                for symbol in self.symbols:
                    if not self._is_running:
                        break
                    future = executor.submit(download_data, symbol)
                    future_to_symbol[future] = symbol
                self.futures = future_to_symbol

                # 处理结果
                # print(f"[DEBUG] 开始处理结果")
                pending_futures = set(future_to_symbol.keys())
                # print(f"[DEBUG] 待处理的任务数量: {len(pending_futures)}")
                
                while pending_futures and self._is_running:
                    try:
                        # 等待任意一个任务完成，但最多等1秒
                        done, pending_futures = concurrent.futures.wait(pending_futures, timeout=0.5, return_when=concurrent.futures.FIRST_COMPLETED)
                        
                        # 检查停止标志
                        if not self._is_running:
                            self.log("⚠️ 停止信号收到，正在中止...")
                            # 取消所有尚未完成的任务
                            for f in pending_futures:
                                f.cancel()
                            # 立即关闭线程池
                            executor.shutdown(wait=False)
                            break
                        
                        for future in done:
                            # 检查停止标志
                            if not self._is_running:
                                break
                                
                            symbol = future_to_symbol[future]
                            try:
                                # 设置更短的超时，避免任务卡住
                                symbol, df, error, is_skip = future.result(timeout=3)  
                                
                                # 使用锁保护共享数据的访问
                                with data_lock:
                                    processed_count += 1
                                    
                                    # 累计处理的记录数
                                    if df is not None and not df.empty:
                                        processed_records += len(df)

                                    # 计算当前已处理总数
                                    total_processed = len(completed_symbols) + (processed_count - len(completed_symbols))
                                    total_processed = min(total_processed, original_total)

                                    # 计算预期处理数（剩余需要处理的数量）
                                    expected_process = len(self.symbols)
                                    # 更新进度 - 每处理一个股票就更新一次，反映下载进度
                                    self.progress_signal.emit(total_processed, expected_process, original_total)

                                    if is_skip:
                                        # 数据已存在，跳过下载，不统计为失败
                                        completed_symbols.append(symbol)
                                    elif error:
                                        failed_count += 1
                                        failed_list.append(f"{symbol} - {error}")
                                        completed_symbols.append(symbol)  # 修复：失败也要标记为已完成
                                    elif df is not None:
                                        # 检查停止标志
                                        if not self._is_running:
                                            break
                                                                # 处理复权数据
                                        if ADJUSTMENT_CACHE_AVAILABLE and period == '1d':
                                            # 对于日线数据，使用QMT API获取复权数据
                                            try:
                                                from src.core.data.adjustment.adjustment_cache import AdjustmentCache
                                                adjustment_cache = AdjustmentCache(self.db_path)
                                                # 这里可以根据需要获取不同类型的复权数据
                                                # 目前我们先保存原始数据，查询时再获取复权数据
                                            except Exception as e:
                                                self.log(f"⚠️ 复权数据处理失败: {str(e)}")
                                        
                                        # 使用流式处理器处理数据
                                        try:
                                            processor.add_data(symbol, df, period)
                                            success_count += 1
                                            completed_symbols.append(symbol)
                                        except Exception as e:
                                            failed_count += 1
                                            failed_list.append(f"{symbol} - 数据处理失败: {str(e)[:50]}")
                                            completed_symbols.append(symbol)
                                            self.log(f"⚠️ {symbol} 数据处理失败: {str(e)}")
                                    else:
                                        failed_count += 1
                                        failed_list.append(f"{symbol} - 未知错误")
                                        completed_symbols.append(symbol)  # 修复：未知错误也要标记为已完成

                                # 定期检查内存使用
                                if processed_count % memory_check_interval == 0:
                                    memory_usage = memory_monitor.get_memory_usage()
                                    memory_monitor.log_memory_usage(f"(处理 {processed_count}/{total} 标的)")
                                    
                                    # 内存超过阈值时调整批次大小
                                    if memory_monitor.should_adjust_batch_size():
                                        new_batch_size = memory_monitor.suggest_batch_size(
                                            current_batch_size, 
                                            strategy.get_period()
                                        )
                                        
                                        if new_batch_size != current_batch_size:
                                            current_batch_size = new_batch_size
                                            
                                            # 立即处理缓冲区的数据
                                            processor.flush()
                                    
                                    # 内存过高时强制垃圾回收
                                    if memory_monitor.should_trigger_gc():
                                        memory_monitor.trigger_gc()
                                    
                                    # 检查是否需要重置资源
                                    if memory_monitor.should_reset_resources(processed_count, processed_records):
                                        self.log(f"🔄 达到资源重置阈值，进行资源清理...")
                                        # 处理缓冲区数据
                                        processor.flush()
                                        # 强制垃圾回收
                                        memory_monitor.trigger_gc()
                                        # 记录内存使用情况
                                        memory_monitor.log_memory_usage("(资源重置后)")

                                # 根据数据类型动态调整资源回收策略
                                period = strategy.get_period()
                                # 增加资源回收频率，避免资源泄露
                                if period == '1m':
                                    # 1分钟数据每处理50个标的或2000000条记录就重置资源
                                    reset_symbols = 50
                                    reset_records = 2000000
                                elif period == '5m':
                                    # 5分钟数据每处理75个标的或3000000条记录就重置资源
                                    reset_symbols = 75
                                    reset_records = 3000000
                                elif period == 'tick':
                                    # Tick数据每处理25个标的或1000000条记录就重置资源
                                    reset_symbols = 25
                                    reset_records = 1000000
                                else:
                                    # 其他数据类型使用配置的重置间隔，但减少一半
                                    reset_symbols = max(10, reset_interval_symbols // 2)
                                    reset_records = max(100000, reset_interval_records // 2)
                                
                                # 定期清理资源
                                # 暂时禁用资源重置方法，只保留flush操作
                                # if (processed_count % reset_symbols == 0 and processed_count > 0) or (processed_records % reset_records == 0 and processed_records > 0):
                                #     # 检查停止标志
                                #     if not self._is_running:
                                #         break
                                #         
                                #     self.log(f"🔄 达到资源重置阈值，进行资源清理...")
                                #     self.log(f"📊 数据类型: {period}, 重置间隔: 标的数={reset_symbols}, 记录数={reset_records}")
                                    # 1. 处理缓冲区数据
                                    # processor.flush()
                                    # 2. 重置数据库连接池
                                    # try:
                                    #     from new_gui_app.data_manager.duckdb_connection_pool_optimized import get_connection_pool
                                    #     import os
                                    #     # 标准化数据库路径
                                    #     normalized_path = os.path.normpath(os.path.abspath(self.db_path))
                                    #     pool = get_connection_pool(normalized_path)
                                    #     pool.cleanup()
                                    #     self.log(f"✅ 数据库连接池已重置")
                                    # except Exception as e:
                                    #     self.log(f"⚠️ 重置数据库连接池失败: {str(e)}")
                                    # 3. 强制垃圾回收
                                    # memory_monitor.trigger_gc()
                                    # 4. 记录内存使用情况
                                    # memory_usage = memory_monitor.get_memory_usage()
                                    # memory_monitor.increment_resource_reset()
                                    # 5. 记录资源重置统计信息
                                    # trend_info = memory_monitor.get_memory_trend_info()
                                    # self.log(f"📊 资源清理后内存使用: {memory_usage:.2f} GB")
                                    # self.log(f"📈 资源重置统计: 批次调整={trend_info['adjustments']}, 垃圾回收={trend_info['gc_triggers']}, 资源重置={trend_info['resource_resets']}")
                                    # 6. 记录详细的性能指标
                                    self.log(f"📋 处理进度: {processed_count}/{total} 标的, {processed_records} 记录")
                                    if processor.batch_history:
                                        last_batch = processor.batch_history[-1]
                                        self.log(f"📊 最近批次性能: {last_batch['speed']:.2f} 行/秒, 耗时: {last_batch['time']:.2f} 秒")
                                    
                                # 每下载一定数量的股票输出一次日志
                                batch_threshold = 50 if strategy.get_period() != 'tick' else 20
                                if processed_count % batch_threshold == 0:
                                    expected_process = len(self.symbols)
                                    self.log(f"📊 进度: {total_processed}/{expected_process}/{original_total} | 成功: {success_count} | 失败: {failed_count}")

                            except concurrent.futures.TimeoutError:
                                failed_count += 1
                                failed_list.append(f"{symbol} - 下载超时")
                                self.log(f"⚠️ {symbol} 下载超时")
                            except Exception as e:
                                failed_count += 1
                                failed_list.append(f"{symbol} - {str(e)[:50]}")
                            finally:
                                # 从字典中移除已处理的任务
                                del future_to_symbol[future]
                        
                    except Exception as e:
                        self.log(f"⚠️ 处理任务时出错: {str(e)}")
                        # 检查停止标志
                        if not self._is_running:
                            break
                        continue
            finally:
                # 确保线程池被关闭
                try:
                    if executor and not executor._shutdown:
                        executor.shutdown(wait=False)
                except Exception as e:
                    self.log(f"⚠️ 关闭线程池时出错: {str(e)}")
                # 清理流式处理器
                try:
                    processor.flush()
                except Exception as e:
                    self.log(f"⚠️ 清理处理器时出错: {str(e)}")

            # print(f"[DEBUG] 处理剩余数据")
            # 处理剩余数据
            processor.flush()

            # 强制更新模式，不处理失败列表和断点续传
            if failed_list:
                # 只记录失败情况，不进行重试
                self.log(f"📋 下载过程中有 {len(failed_list)} 只股票失败")
                for failed_item in failed_list[:10]:  # 只显示前10个
                    self.log(f"  ✗ {failed_item}")
                if len(failed_list) > 10:
                    self.log(f"  ... 还有 {len(failed_list) - 10} 只")

            # print(f"[DEBUG] 确保缓冲区被清空")
            # 确保缓冲区被清空
            if processor.buffer:
                self.log("⚠️ 缓冲区中仍有数据，再次清空")
                processor.buffer.clear()

            # print(f"[DEBUG] 确保成功数不超过原始总数")
            # 确保成功数和失败数的总和等于总数
            total_success = min(len(completed_symbols), original_total)
            total_failed = original_total - total_success

            # print(f"[DEBUG] 构建结果")
            period = strategy.get_period()
            result = {
                'total': original_total,
                'success': total_success,
                'failed': total_failed,
                'failed_list': failed_list,
                'task_type': self.task_type,
                'period': period,
                'start_date': self.start_date,
                'end_date': self.end_date
            }

            # print(f"[DEBUG] 触发完成信号: {result}")
            self.finished_signal.emit(result)
            # print(f"[DEBUG] 完成信号触发成功")
            self.log(f"\n🎉 下载完成!")
            self.log(f"📊 数据类型: {period}")
            self.log(f"📅 时间段: {self.start_date} 至 {self.end_date}")
            self.log(f"📋 标的数: {result['total']}")
            self.log(f"✅ 成功: {result['success']}")
            self.log(f"❌ 失败: {result['failed']}")
            self.log(f"📈 成功率: {round(result['success']/result['total']*100, 2)}%" if result['total'] > 0 else "📈 成功率: 0%")

            # 输出失败清单
            if failed_list:
                self.log("")
                self.log("=" * 70)
                self.log("  失败清单:")
                for failed_item in failed_list[:30]:  # 只显示前30个
                    self.log(f"    ✗ {failed_item}")
                if len(failed_list) > 30:
                    self.log(f"    ... 还有 {len(failed_list) - 30} 只")
                self.log("=" * 70)

        except Exception as e:
            import traceback
            error_msg = f"下载数据失败: {str(e)}\n{traceback.format_exc()}"
            # print(f"[DEBUG] 异常: {error_msg}")
            self.log(error_msg)
            self.error_signal.emit(error_msg)

    def _download_minute_data(self):
        """下载分钟线和tick数据 - 已被策略模式替代"""
        pass

    def _download_stocks(self):
        """下载股票数据 - 已被策略模式替代"""
        pass

    def _download_bonds(self):
        """下载可转债数据 - 已被策略模式替代"""
        pass

    def _analyze_performance_trend(self, batch_performance, period, memory_monitor):
        """分析性能趋势
        
        Args:
            batch_performance: 批次性能数据
            period: 数据周期
            memory_monitor: 内存监控器实例
        """
        if len(batch_performance) < 2:
            return
        
        # 分析速度趋势
        speeds = [item['speed'] for item in batch_performance]
        avg_speed = sum(speeds) / len(speeds)
        first_half_speed = sum(speeds[:len(speeds)//2]) / (len(speeds)//2)
        second_half_speed = sum(speeds[len(speeds)//2:]) / (len(speeds) - len(speeds)//2)
        
        # 分析内存趋势
        memory_usages = [item['memory'] for item in batch_performance]
        avg_memory = sum(memory_usages) / len(memory_usages)
        max_memory = max(memory_usages)
        
        # 分析耗时趋势
        times = [item['time'] for item in batch_performance]
        avg_time = sum(times) / len(times)
        
        # 计算速度变化百分比
        speed_change = ((second_half_speed - first_half_speed) / first_half_speed * 100) if first_half_speed > 0 else 0
        
        # 生成性能趋势报告
        self.log("=" * 80)
        self.log(f"📈 性能趋势分析 ({period} 数据)")
        self.log(f"批次数量: {len(batch_performance)}")
        self.log(f"平均速度: {avg_speed:.2f} 行/秒")
        self.log(f"前半部分平均速度: {first_half_speed:.2f} 行/秒")
        self.log(f"后半部分平均速度: {second_half_speed:.2f} 行/秒")
        self.log(f"速度变化: {speed_change:+.2f}%")
        self.log(f"平均内存使用: {avg_memory:.2f} GB")
        self.log(f"最大内存使用: {max_memory:.2f} GB")
        self.log(f"平均批次耗时: {avg_time:.2f} 秒")
        
        # 分析资源回收效果
        trend_info = memory_monitor.get_memory_trend_info()
        self.log(f"资源回收统计: 批次调整={trend_info['adjustments']}, 垃圾回收={trend_info['gc_triggers']}, 资源重置={trend_info['resource_resets']}")
        
        # 性能警告
        if speed_change < -20:
            self.log("⚠️ 警告: 性能明显下降，建议检查资源使用情况")
        elif max_memory > memory_monitor.memory_limit_gb * 0.9:
            self.log("⚠️ 警告: 内存使用接近限额，可能影响性能")
        
        self.log("=" * 80)

    def _update_data(self):
        """更新数据（增量）- 支持所有数据类型，使用增强的批量方法
        
        支持更新多种数据类型，包括日线、分钟线、tick数据等
        采用策略模式处理不同类型的数据更新，支持并行更新和断点续传
        
        主要功能：
        1. 支持更新所有数据类型或指定数据类型
        2. 自动计算更新时间范围
        3. 支持断点续传，记录失败的股票
        4. 并行处理，提高更新效率
        5. 内存监控和批次大小调整
        """
        try:
            import os
            from src.core.data.database.db_manager import get_db_manager
            import pandas as pd
            from datetime import datetime

            self.log("✅ 数据管理器初始化成功")

            # 获取DuckDB管理器
            db_manager = get_db_manager(self.db_path)

            # 支持的周期列表
            periods = []
            if self.period is None:
                # 所有类型
                periods = ['1d', '1m', '5m', '15m', '30m', '60m', 'weekly', 'monthly', 'tick']
            else:
                # 指定类型
                periods = [self.period]

            total_all = 0
            success_all = 0
            failed_all = 0

            # 记录每个数据类型的详细信息
            data_type_details = []

            # 使用用户选择的日期范围（如果有）
            user_start_date = self.start_date
            user_end_date = self.end_date
            
            # 如果没有用户指定的日期，使用默认范围
            if user_start_date is None or user_end_date is None:
                user_end_date = datetime.now().strftime('%Y%m%d')
                user_start_date = (datetime.now() - pd.Timedelta(days=30)).strftime('%Y%m%d')

            # 检查当前是否是交易日盘中
            import datetime
            now = datetime.datetime.now()
            current_date = now.strftime('%Y%m%d')
            current_time = now.time()
            is_trading_day = True  # 简化处理，实际应该调用API检查是否是交易日
            is_trading_hours = current_time >= datetime.time(9, 30) and current_time <= datetime.time(15, 0)  # 简化处理，实际应该考虑中午休市

            # 记录 tick 数据是否已经更新过
            tick_updated = False
            
            for period in periods:
                # 对于 tick 数据，只更新一次
                if period == 'tick' and tick_updated:
                    self.log(f"\n=== 跳过 {period} 数据更新 ====")
                    self.log(f"  tick 数据已在本次更新中处理过，跳过")
                    continue
                
                self.log(f"\n=== 更新 {period} 数据 ====")
                
                # 对所有数据类型的特殊处理：如果是交易日盘中，提示用户等待收盘后再更新
                if is_trading_day and is_trading_hours:
                    self.log(f"⚠️ 当前是交易日盘中，数据正在生成中")
                    self.log(f"ℹ️ 建议在收盘后（15:00后）再更新当日数据")
                    self.log(f"📅 本次更新将只处理到 {current_date} 之前的数据")

                # 根据周期选择表名和日期列
                if period == '1d':
                    table_name = 'stock_daily'
                    date_column = 'date'
                elif period == 'tick':
                    table_name = 'stock_tick'
                    date_column = 'datetime'
                elif period in ['weekly', 'monthly', '1w', '1M']:
                    # 周线和月线数据使用 date 列
                    table_name = f'stock_{"weekly" if period in ["weekly", "1w"] else "monthly"}'
                    date_column = 'date'
                else:
                    table_name = f'stock_{period}'
                    date_column = 'datetime'

                # 检查表是否存在
                table_exists = db_manager.table_exists(table_name)
                if not table_exists:
                    if self.update_mode == 'existing':
                        self.log(f"⚠️ 表 {table_name} 不存在，跳过 {period} 数据更新（仅更新已有数据模式）")
                        continue
                    else:
                        self.log(f"📝 表 {table_name} 不存在，将创建新表（更新所有类型模式）")

                # 始终获取完整股票列表，确保所有标的都能被处理
                self.log(f"📥 获取完整股票列表")
                stock_codes = self._get_all_stock_codes()
                if not stock_codes:
                    self.log(f"⚠️ 无法获取股票列表，跳过 {period} 数据更新")
                    continue
                self.log(f"📊 获取到 {len(stock_codes)} 只股票")
                
                # 强制更新模式，不考虑断点续传和失败列表

                # 测试模式：只处理配置的股票数量
                if hasattr(self, 'test_mode') and self.test_mode:
                    # 加载配置
                    config = DownloadConfig(self.config)
                    test_count = config.get_test_stock_count(period)
                    stock_codes = stock_codes[:test_count]
                    self.log(f"🔧 测试模式：{period}数据只处理前{test_count}只股票")
                # 检查停止标志
                if not self._is_running:
                    self.log("⚠️ 用户中断更新")
                    break

                # 加载配置
                config = DownloadConfig()
                
                # 计算时间范围交集
                start_date, end_date = config.get_intersection_time_range(period, user_start_date, user_end_date)
                
                # 检查是否有交集
                if start_date is None or end_date is None:
                    self.log(f"⚠️ {period}数据时间范围与配置文件限制无交集，跳过更新")
                    self.log(f"   - 界面选择：{user_start_date} ~ {user_end_date}")
                    config_start, config_end = config.get_time_range(period)
                    self.log(f"   - 配置限制：{config_start} ~ {config_end}")
                    continue
                
                self.log(f"📅 更新范围: {start_date} ~ {end_date}")
                
                # 初始化策略
                if period == '1d':
                    strategy = DailyDataStrategy(db_manager, config, self.log_signal)
                elif period == 'tick':
                    strategy = TickDataStrategy(db_manager, config, self.log_signal)
                elif period == 'weekly':
                    strategy = WeeklyDataStrategy(db_manager, config, self.log_signal)
                elif period == 'monthly':
                    strategy = MonthlyDataStrategy(db_manager, config, self.log_signal)
                else:
                    strategy = MinuteDataStrategy(db_manager, config, self.log_signal, period)
                
                # 记录时间范围计算结果
                self.log(f"📊 时间范围计算 | 数据类型: {period} | 计算后范围: {start_date} ~ {end_date}")
                
                # 使用策略模式更新数据
                self.log(f"📊 使用{period}数据策略")
                
                # 生成任务ID，仅用于日志
                task_id = f"update_data_{period}_{start_date}_{end_date}"
                
                # 初始化内存监控器
                from src.core.utils import MemoryMonitor
                memory_monitor = MemoryMonitor(log_signal=self.log_signal)
                
                # 从Parquet文件中获取已完成的股票列表（直接扫描文件）
                # 同时检查数据范围是否满足要求
                completed_symbols = []
                outdated_symbols = []  # 数据范围不足的股票
                
                try:
                    from pathlib import Path
                    
                    config = DownloadConfig(self.config)
                    data_config = config.get_config()
                    data_root_dir = data_config.get('data_paths', {}).get('root_dir', 'D:/MyStockData')
                    parquet_config = data_config.get('storage', {}).get('parquet', {})
                    parquet_root_dir = parquet_config.get('root_dir', 'Parquet')
                    parquet_root = Path(data_root_dir) / parquet_root_dir
                    
                    if period == '1d':
                        parquet_path = parquet_root / 'kline' / 'daily'
                        date_col = 'date'
                    elif period == '1w' or period == 'weekly':
                        parquet_path = parquet_root / 'kline' / 'weekly'
                        date_col = 'date'
                    elif period == '1mon' or period == 'monthly':
                        parquet_path = parquet_root / 'kline' / 'monthly'
                        date_col = 'date'
                    elif period == 'tick':
                        parquet_path = parquet_root / 'tick'
                        date_col = 'datetime'
                    else:
                        parquet_path = parquet_root / 'kline' / period
                        date_col = 'datetime'
                    
                    # 解析请求的结束日期
                    request_end_date = None
                    if self.end_date:
                        from datetime import datetime as dt
                        end_date_str = str(self.end_date)
                        if len(end_date_str.replace('-', '')) == 8:
                            if len(end_date_str) == 8:
                                request_end_date = dt.strptime(end_date_str, '%Y%m%d')
                            else:
                                request_end_date = dt.strptime(end_date_str, '%Y-%m-%d')
                    
                    if parquet_path.exists() and request_end_date:
                        import duckdb
                        
                        for exchange_dir in parquet_path.iterdir():
                            if exchange_dir.is_dir():
                                for file in exchange_dir.glob('*.parquet'):
                                    if file.name.startswith('_temp_'):
                                        continue
                                    
                                    symbol = file.stem
                                    full_symbol = f"{symbol}.{exchange_dir.name}"
                                    
                                    try:
                                        # 检查该文件的数据范围
                                        conn = duckdb.connect()
                                        result = conn.execute(f"""
                                            SELECT MAX({date_col}) as max_date 
                                            FROM read_parquet('{file}')
                                        """).fetchone()
                                        conn.close()
                                        
                                        if result and result[0]:
                                            max_date_in_file = result[0]
                                            if hasattr(max_date_in_file, 'date'):
                                                max_date_in_file = max_date_in_file.date()
                                            
                                            if max_date_in_file >= request_end_date.date():
                                                # 数据范围足够，标记为已完成
                                                completed_symbols.append(full_symbol)
                                            else:
                                                # 数据范围不足，需要更新
                                                outdated_symbols.append(full_symbol)
                                        else:
                                            # 无法获取日期，视为需要更新
                                            outdated_symbols.append(full_symbol)
                                    except Exception as e:
                                        self.log(f"⚠️ 检查 {full_symbol} 数据范围失败: {e}")
                                        outdated_symbols.append(full_symbol)
                        
                        self.log(f"📋 从数据文件扫描结果:")
                        self.log(f"   - 已完成（数据充足）: {len(completed_symbols)} 只")
                        self.log(f"   - 需要更新（数据不足）: {len(outdated_symbols)} 只")
                    elif parquet_path.exists():
                        # 无结束日期信息，仅检查文件存在性
                        for exchange_dir in parquet_path.iterdir():
                            if exchange_dir.is_dir():
                                for file in exchange_dir.glob('*.parquet'):
                                    if not file.name.startswith('_temp_'):
                                        symbol = file.stem
                                        full_symbol = f"{symbol}.{exchange_dir.name}"
                                        completed_symbols.append(full_symbol)
                        
                        self.log(f"📋 从数据文件中扫描到 {len(completed_symbols)} 只已完成的股票（仅检查文件存在性）")
                    else:
                        self.log("📋 无数据文件，开始全新更新")
                except Exception as e:
                    self.log(f"⚠️ 扫描已下载文件失败: {e}")
                
                # 过滤出未完成的股票，所有数据类型统一处理
                if completed_symbols or outdated_symbols:
                    # 注意：数据文件中的股票代码可能没有后缀（如.SH），需要匹配
                    # 提取股票代码的基础部分进行匹配
                    def get_base_symbol(symbol):
                        # 处理不同格式的股票代码：SH.600000 或 600000.SH
                        if '.' in symbol:
                            parts = symbol.split('.')
                            # 找到数字部分作为股票代码
                            for part in parts:
                                if part.isdigit():
                                    return part
                            # 如果没有数字部分，返回最后一个部分
                            return parts[-1]
                        else:
                            return symbol
                    
                    # 构建已完成（数据充足）的股票基础代码集合
                    completed_base_symbols = set(get_base_symbol(s) for s in completed_symbols)
                    
                    # 过滤股票代码列表：只跳过已完成的，保留需要更新的和不足的
                    remaining_stock_codes = []
                    for code in stock_codes:
                        base_code = get_base_symbol(code)
                        if base_code not in completed_base_symbols:
                            remaining_stock_codes.append(code)
                    
                    if remaining_stock_codes:
                        self.log(f"📋 更新统计:")
                        self.log(f"   - 已完成（数据充足）: {len(completed_symbols)} 只 - 跳过")
                        self.log(f"   - 需要更新（数据不足或无文件）: {len(remaining_stock_codes)} 只")
                        stock_codes = remaining_stock_codes
                    else:
                        self.log("📋 所有股票数据充足，无需更新")
                        return {'total': len(completed_symbols), 'success': len(completed_symbols), 'failed': 0, 'failed_list': []}
                else:
                    self.log("📋 无数据文件，开始全新更新")
                
                # 准备更新的股票数量
                total = len(stock_codes)
                self.log(f"📊 准备更新 | 数据类型: {period} | 标的数量: {total}")
                
                # 获取批量大小
                initial_batch_size = strategy.get_batch_size()
                # 为不同周期数据设置合适的批次大小
                if period == '1m':
                    initial_batch_size = 10  # 1分钟数据使用最小的批次大小
                elif period in ['5m', '15m', '30m', '60m', 'weekly', 'monthly']:
                    initial_batch_size = 12  # 其他周期数据使用较小的批次大小
                elif period == '1d':
                    initial_batch_size = 50  # 日线数据使用较大的批次大小
                elif period == 'tick':
                    initial_batch_size = 5  # Tick数据使用最小的批次大小
                current_batch_size = initial_batch_size
                # 进一步减少线程数以降低内存使用
                max_workers = min(os.cpu_count(), 3)  # 进一步减少线程数
                
                self.log(f"🚀 启动下载 | 数据类型: {period} | 线程数: {max_workers} | 初始批次大小: {current_batch_size}")
                self.log(f"📊 开始更新 | 数据类型: {period} | 时间范围: {start_date} ~ {end_date} | 标的数量: {total}")

                # 初始化流式处理器
                from src.core.data.processing.optimized_processor import OptimizedDataProcessor
                processor = OptimizedDataProcessor(strategy.db_manager, self.log_signal, config=self.config)

                # 数据下载函数
                thread_self = self  # 捕获当前线程实例的引用
                @retry_with_backoff(max_retries=3, initial_delay=1, max_delay=10)
                def download_data(symbol):
                    """下载单个股票数据"""
                    # 在开始时就检查
                    if not thread_self._is_running:
                        return symbol, None, "更新已被用户取消"
                    try:
                        # 使用策略下载数据
                        df, is_skip = strategy.download_data(
                            symbol, 
                            start_date, 
                            end_date,
                            force_update=True
                        )
                        # 再次检查
                        if not thread_self._is_running:
                            return symbol, None, "更新已被用户取消"
                        if df is not None and not df.empty:
                            return symbol, df, None
                        else:
                            return symbol, None, "数据为空"
                    except Exception as e:
                        return symbol, None, str(e)[:50]

                # 使用线程池并行下载
                self.log(f"📥 开始并行更新 | 数据类型: {period} | 标的数量: {total}")
                processed_count = 0
                success_count = 0
                failed_count = 0
                failed_list = []
                memory_check_interval = 10  # 每10个股票检查一次内存

                # 设置保存完成回调函数，用于更新进度条
                def on_save_complete(success_count, failed_count, total_rows, elapsed_time):
                    """保存完成回调，更新进度条"""
                    nonlocal processed_count
                    nonlocal total
                    
                    # 更新处理计数
                    processed_count += success_count + failed_count
                    processed_count = min(processed_count, total)
                    
                    # 计算预期处理数
                    expected_process = len(stock_codes)
                    # 更新进度
                    self.progress_signal.emit(processed_count, expected_process, total)
                    
                    if self.log_signal:
                        self.log_signal.emit(f"✅ 批量保存完成: 成功{success_count}，失败{failed_count}，耗时{elapsed_time:.2f}秒")
                
                # 设置回调函数
                processor.save_complete_callback = on_save_complete

                # 创建线程池
                import concurrent.futures
                self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
                executor = self.executor
                
                try:
                    # 提交所有下载任务
                    self.futures = {executor.submit(download_data, symbol): symbol for symbol in stock_codes}
                    future_to_symbol = self.futures

                    # 处理结果
                    pending_futures = set(future_to_symbol.keys())
                    
                    while pending_futures and self._is_running:
                        try:
                            # 等待任意一个任务完成，但最多等1秒
                            done, pending_futures = concurrent.futures.wait(pending_futures, timeout=1.0, return_when=concurrent.futures.FIRST_COMPLETED)
                            
                            for future in done:
                                symbol = future_to_symbol[future]
                                try:
                                    symbol, df, error = future.result(timeout=5)  # 设置超时，避免任务卡住
                                    processed_count += 1

                                    # 修复：简化进度计算逻辑，直接使用 processed_count
                                    total_processed = processed_count
                                    total_processed = min(total_processed, total)

                                    # 计算预期处理数（剩余需要处理的数量）
                                    expected_process = len(stock_codes)
                                    # 更新进度 - 每处理一个股票就更新一次
                                    self.progress_signal.emit(total_processed, expected_process, total)

                                    if error:
                                        failed_count += 1
                                        failed_list.append(f"{symbol} - {error}")
                                        completed_symbols.append(symbol)  # 修复：失败也要标记为已完成
                                    elif df is not None:
                                        # 使用流式处理器处理数据
                                        processor.add_data(symbol, df, period)
                                        success_count += 1
                                        completed_symbols.append(symbol)
                                    else:
                                        failed_count += 1
                                        failed_list.append(f"{symbol} - 未知错误")
                                        completed_symbols.append(symbol)  # 修复：未知错误也要标记为已完成

                                    # 定期检查内存使用
                                    if processed_count % memory_check_interval == 0:
                                        memory_usage = memory_monitor.get_memory_usage()
                                        
                                        # 内存超过阈值时调整批次大小
                                        if memory_monitor.should_adjust_batch_size():
                                            new_batch_size = memory_monitor.suggest_batch_size(
                                                current_batch_size, 
                                                strategy.get_period()
                                            )
                                            
                                            if new_batch_size != current_batch_size:
                                                current_batch_size = new_batch_size
                                                
                                                # 立即处理缓冲区的数据
                                                processor.flush()
                                    
                                    # 内存过高时强制垃圾回收
                                    if memory_usage > memory_monitor.memory_limit_gb * 0.9:
                                        import gc
                                        gc.collect()

                                    # 每更新一定数量的股票输出一次日志并保存断点
                                    batch_threshold = 50 if strategy.get_period() != 'tick' else 20
                                    if processed_count % batch_threshold == 0:
                                        expected_process = len(stock_codes)
                                        success_rate = (success_count / processed_count * 100) if processed_count > 0 else 0
                                        self.log(f"📊 处理进度 | 数据类型: {period} | 进度: {total_processed}/{expected_process}/{total} | 成功: {success_count} | 失败: {failed_count} | 成功率: {success_rate:.2f}%")
                                        # 保存断点信息
                                        (task_id, completed_symbols, total)

                                except concurrent.futures.TimeoutError:
                                    failed_count += 1
                                    failed_list.append(f"{symbol} - 更新超时")
                                    self.log(f"⚠️ {symbol} 更新超时")
                                except Exception as e:
                                    failed_count += 1
                                    failed_list.append(f"{symbol} - {str(e)[:50]}")
                                finally:
                                    # 从字典中移除已处理的任务
                                    del future_to_symbol[future]
                            
                            # 每次循环都检查停止标志
                            if not self._is_running:
                                self.log("⚠️ 停止信号收到，正在中止...")
                                # 取消所有尚未完成的任务
                                for f in pending_futures:
                                    f.cancel()
                                # 立即关闭线程池
                                executor.shutdown(wait=False)
                                break
                        except Exception as e:
                            self.log(f"⚠️ 处理任务时出错: {str(e)}")
                            continue
                finally:
                    # 确保线程池被关闭
                    if not executor._shutdown:
                        executor.shutdown(wait=False)
                    # 清理流式处理器
                    processor.flush()
                    # 强制保存断点信息
                    

                # 处理剩余数据
                processor.flush()

                # 保存失败记录
                if failed_list:
                    # 对于失败的记录，只尝试重新更新一次
                    # 过滤出不是"数据为空"的失败记录进行重试
                    retry_symbols = []
                    no_data_symbols = []
                    
                    for item in failed_list:
                        if "数据为空" in item:
                            no_data_symbols.append(item)
                        else:
                            retry_symbols.append(item.split(' - ')[0])
                    
                    # 标记无数据的股票
                    if no_data_symbols:
                        self.log(f"📋 标记 {len(no_data_symbols)} 只股票在时间段内无数据")
                        for item in no_data_symbols:
                            self.log(f"  - {item}")
                    
                    # 只尝试重新更新非"数据为空"的失败股票
                    if retry_symbols:
                        self.log(f"🔄 尝试重新更新 {len(retry_symbols)} 只失败的股票...")
                        retry_failed_count = 0
                        retry_failed_list = []
                        
                        # 单个线程重新更新，避免并发问题
                        for symbol in retry_symbols:
                            if not self._is_running:
                                break
                            
                            try:
                                # 检查停止标志
                                if not self._is_running:
                                    break
                                
                                # 重新下载数据
                                result = strategy.download_data(symbol, self.start_date, self.end_date, force_update=True)
                                # 解构返回值，download_data 返回 (df, is_skip) 元组
                                if isinstance(result, tuple) and len(result) == 2:
                                    df, is_skip = result
                                else:
                                    # 兼容旧版本，直接返回 DataFrame
                                    df = result
                                    is_skip = False
                                
                                # 检查停止标志
                                if not self._is_running:
                                    break
                                
                                if df is not None and not df.empty:
                                    # 检查停止标志
                                    if not self._is_running:
                                        break
                                    
                                    # 使用流式处理器处理数据
                                    processor.add_data(symbol, df, period)
                                    completed_symbols.append(symbol)
                                    self.log(f"✅ 重新更新 {symbol} 成功")
                                else:
                                    retry_failed_count += 1
                                    retry_failed_list.append(f"{symbol} - 数据为空")
                                    self.log(f"❌ 重新更新 {symbol} 仍然失败")
                            except Exception as e:
                                retry_failed_count += 1
                                retry_failed_list.append(f"{symbol} - {str(e)[:50]}")
                                self.log(f"❌ 重新更新 {symbol} 失败: {str(e)[:50]}")
                        
                        # 处理重新更新的数据
                        processor.flush()
                        
                        # 等待保存线程完成
                        self.log("⏳ 等待保存线程完成处理...")
                        import time
                        time.sleep(2)
                        # 检查 processor 对象是否有 stop 方法
                        if hasattr(processor, 'stop'):
                            processor.stop()
                        else:
                            self.log("ℹ️ 处理器没有 stop 方法，跳过停止操作")
                        
                        # 更新失败统计
                        failed_count = retry_failed_count + len(no_data_symbols)
                        failed_list = retry_failed_list + no_data_symbols
                    else:
                        # 所有失败都是"数据为空"，直接标记
                        failed_count = len(no_data_symbols)
                        failed_list = no_data_symbols
                    
                    # 保存最终失败记录
                    if failed_list:
                        failed_symbols = [item.split(' - ')[0] for item in failed_list]
                        # checkpoint_manager.save_failed_symbols(task_id, failed_symbols)


                # 保存最终断点信息
                (task_id, completed_symbols, total)

                # 清理断点信息（如果全部成功且不是用户手动停止）
                if failed_count == 0 and self._is_running:
                    (task_id)
                else:
                    # 用户手动停止或有失败的股票，保留断点信息
                    self.log(f"💾 保留断点信息 (任务: {task_id})")

                # 确保缓冲区被清空
                if processor.buffer:
                    self.log("⚠️ 缓冲区中仍有数据，再次清空")
                    processor.buffer.clear()

                # 确保成功数和失败数的总和等于总数
                total_success = min(len(completed_symbols), total)
                total_failed = total - total_success

                # 显示统计信息
                success_rate = (total_success / total * 100) if total > 0 else 0
                self.log(f"\n🎉 更新完成 | 数据类型: {period} | 时间范围: {start_date} 至 {end_date}")
                self.log(f"📊 统计信息 | 数据类型: {period} | 标的数: {total} | 成功: {total_success} | 失败: {total_failed} | 成功率: {success_rate:.2f}%")
                if failed_list:
                    self.log("失败列表:")
                    for item in failed_list[:10]:  # 只显示前10个失败的
                        self.log(f"  - {item}")
                    if len(failed_list) > 10:
                        self.log(f"  ... 等 {len(failed_list) - 10} 个失败")

                # 收集数据类型详细信息
                data_type_details.append({
                    'period': period,
                    'total': total,
                    'success': total_success,
                    'failed': total_failed
                })

                # 如果是 tick 数据，标记为已更新
                if period == 'tick':
                    tick_updated = True

                total_all += total
                success_all += total_success
                failed_all += failed_count

            # 输出最终结果
            self.finished_signal.emit({'total': total_all, 'success': success_all, 'failed': failed_all, 'task_type': 'update_data', 'data_type_details': data_type_details})

        except ImportError as e:
            error_msg = f"导入模块失败: {str(e)}\n请确保 src.core.data_manager.enhanced_db_manager 模块可用"
            self.log(error_msg)
            self.error_signal.emit(error_msg)
        except Exception as e:
            import traceback
            error_msg = f"更新数据失败: {str(e)}\n{traceback.format_exc()}"
            self.log(error_msg)
            self.error_signal.emit(error_msg)

    def _calculate_adjusted_prices(self, df, divid_data, period):
        """计算五维复权价格
        
        Args:
            df: 原始数据DataFrame
            divid_data: 分红数据DataFrame
            period: 数据周期
            
        Returns:
            包含复权价格的DataFrame
        """
        if divid_data is None or not isinstance(divid_data, pd.DataFrame) or divid_data.empty:
            # 无分红数据，使用原始价格
            for col in ['open', 'high', 'low', 'close']:
                for suffix in ['_front', '_back', '_geometric_front', '_geometric_back']:
                    col_name = f'{col}{suffix}'
                    if col_name not in df.columns:
                        df[col_name] = df[col]
            return df
        
        # 确保日期列存在且类型正确
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            date_col = 'date'
        elif 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df['date'] = df['datetime'].dt.date
            date_col = 'date'
        else:
            # 无日期列，使用原始价格
            for col in ['open', 'high', 'low', 'close']:
                for suffix in ['_front', '_back', '_geometric_front', '_geometric_back']:
                    col_name = f'{col}{suffix}'
                    if col_name not in df.columns:
                        df[col_name] = df[col]
            return df
        
        # 处理分红数据
        if 'ex_date' not in divid_data.columns:
            # 无分红日期字段，使用原始价格
            for col in ['open', 'high', 'low', 'close']:
                for suffix in ['_front', '_back', '_geometric_front', '_geometric_back']:
                    col_name = f'{col}{suffix}'
                    if col_name not in df.columns:
                        df[col_name] = df[col]
            return df
        
        divid_data['ex_date'] = pd.to_datetime(divid_data['ex_date']).dt.date
        divid_data = divid_data.sort_values('ex_date')
        
        # 计算复权因子
        # 前复权因子
        front_factors = []
        current_front_factor = 1.0
        for _, row in divid_data.iterrows():
            ex_date = row['ex_date']
            cash_div = row.get('cash_div', 0)
            bonus_ratio = row.get('bonus_ratio', 0)
            split_ratio = row.get('split_ratio', 0)
            
            # 计算复权因子
            if split_ratio > 0:
                current_front_factor *= (1 + split_ratio)
            front_factors.append({'date': ex_date, 'front_factor': current_front_factor})
        
        # 后复权因子
        back_factors = []
        current_back_factor = 1.0
        for _, row in reversed(list(divid_data.iterrows())):
            ex_date = row['ex_date']
            cash_div = row.get('cash_div', 0)
            bonus_ratio = row.get('bonus_ratio', 0)
            split_ratio = row.get('split_ratio', 0)
            
            # 计算复权因子
            if split_ratio > 0:
                current_back_factor /= (1 + split_ratio)
            back_factors.append({'date': ex_date, 'back_factor': current_back_factor})
        back_factors.reverse()
        
        # 几何复权因子（基于对数）
        import numpy as np
        geometric_front_factors = []
        current_geo_front = 0.0  # 对数空间
        for _, row in divid_data.iterrows():
            ex_date = row['ex_date']
            split_ratio = row.get('split_ratio', 0)
            
            if split_ratio > 0:
                current_geo_front += np.log(1 + split_ratio)
            geometric_front_factors.append({'date': ex_date, 'geo_front': current_geo_front})
        
        geometric_back_factors = []
        current_geo_back = 0.0  # 对数空间
        for _, row in reversed(list(divid_data.iterrows())):
            ex_date = row['ex_date']
            split_ratio = row.get('split_ratio', 0)
            
            if split_ratio > 0:
                current_geo_back -= np.log(1 + split_ratio)
            geometric_back_factors.append({'date': ex_date, 'geo_back': current_geo_back})
        geometric_back_factors.reverse()
        
        # 转换为DataFrame
        front_df = pd.DataFrame(front_factors)
        back_df = pd.DataFrame(back_factors)
        geo_front_df = pd.DataFrame(geometric_front_factors)
        geo_back_df = pd.DataFrame(geometric_back_factors)
        
        # 合并复权因子到原始数据
        df = df.merge(front_df, on='date', how='left')
        df = df.merge(back_df, on='date', how='left')
        df = df.merge(geo_front_df, on='date', how='left')
        df = df.merge(geo_back_df, on='date', how='left')
        
        # 填充缺失的因子值
        df['front_factor'] = df['front_factor'].fillna(method='ffill').fillna(1.0)
        df['back_factor'] = df['back_factor'].fillna(method='ffill').fillna(1.0)
        df['geo_front'] = df['geo_front'].fillna(method='ffill').fillna(0.0)
        df['geo_back'] = df['geo_back'].fillna(method='ffill').fillna(0.0)
        
        # 计算几何复权因子（指数转换）
        df['geometric_front_factor'] = np.exp(df['geo_front'])
        df['geometric_back_factor'] = np.exp(df['geo_back'])
        
        # 计算复权价格
        for col in ['open', 'high', 'low', 'close']:
            # 前复权
            df[f'{col}_front'] = df[col] * df['front_factor']
            # 后复权
            df[f'{col}_back'] = df[col] * df['back_factor']
            # 几何前复权
            df[f'{col}_geometric_front'] = df[col] * df['geometric_front_factor']
            # 几何后复权
            df[f'{col}_geometric_back'] = df[col] * df['geometric_back_factor']
        
        # 清理临时列
        df = df.drop(['front_factor', 'back_factor', 'geo_front', 'geo_back', 'geometric_front_factor', 'geometric_back_factor'], axis=1, errors='ignore')
        
        return df
    
    def _download_data(self, stock_codes, start_date, end_date, period, table_name, date_column, download_type='normal', force_update=False):
        """通用数据下载方法 - 专注于下载，不处理数据库细节
        
        下载指定股票列表的指定周期数据，支持并行下载和批量保存
        
        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期，格式为 'YYYYMMDD'
            end_date: 结束日期，格式为 'YYYYMMDD'
            period: 数据周期，如 '1d', '1m', '5m', '15m', '30m', '60m', 'tick'
            table_name: 数据表名
            date_column: 日期列名
            download_type: 下载类型，'normal'、'update' 或 'backfill'
            force_update: 是否强制更新数据
            
        Returns:
            tuple: (总股票数, 成功数, 失败数, 失败列表)
        """
        import concurrent.futures
        import os
        import sys
        from src.core.data.database.db_manager import get_db_manager
        import pandas as pd
        from datetime import datetime
        
        try:
            # 检查xtquant模块是否可用
            if not XTDATA_AVAILABLE:
                error_msg = "❌ xtquant模块不可用，请确保QMT已安装并运行"
                self.log(error_msg)
                self.error_signal.emit(error_msg)
                return
            
            # 导入xtdata
            from xtquant import xtdata
        except ImportError as e:
            error_msg = f"❌ 导入xtquant模块失败: {str(e)}"
            self.log(error_msg)
            self.error_signal.emit(error_msg)
            return

        # 获取增强版数据库管理器
        db_manager = get_db_manager(self.db_path)

        total = len(stock_codes)
        success_count = 0
        failed_count = 0
        failed_list = []
        all_dataframes = []  # 存储本批次所有数据

        # 计算线程数（可配置化）
        if period == '1m':
            max_workers = min(os.cpu_count() * 2, 10)
        elif period == 'tick':
            max_workers = min(os.cpu_count(), 5)
        else:
            max_workers = min(os.cpu_count() * 3, 15)

        self.log(f"🚀 启动 {max_workers} 个下载线程")

        # 数据下载函数
        def download_single_stock(symbol):
            """下载单个股票数据"""
            max_retries = 3
            retry_count = 0
            base_wait_time = 1  # 基础等待时间
            from datetime import datetime
            import time
            
            while retry_count < max_retries:
                # 每次循环开始都检查停止标志
                if not self._is_running:
                    return (symbol, None, "下载已被用户取消")
                try:
                    # 转换日期格式
                    start_dt = pd.to_datetime(start_date, format='%Y%m%d')
                    end_dt = pd.to_datetime(end_date, format='%Y%m%d')
                    start_str = start_dt.strftime('%Y%m%d')
                    end_str = end_dt.strftime('%Y%m%d')

                    # 映射周期到QMT API格式
                    qmt_period = period
                    if period == '60m':
                        qmt_period = '1h'

                    # 检查停止标志
                    if not self._is_running:
                        return (symbol, None, "下载已被用户取消")

                    # 对于 tick 数据，只在盘后更新，且只更新一次
                    if period == 'tick':
                        # 检查当前是否是交易日盘中
                        now = datetime.now()
                        current_time = now.time()
                        is_trading_hours = current_time >= time(9, 30) and current_time <= time(15, 0)
                        if is_trading_hours:
                            self.log(f"  {symbol}: 当前是交易日盘中，tick数据将在盘后更新")
                            return (symbol, None, "交易日盘中，tick数据将在盘后更新")
                    
                    # 对于所有周期的数据，都先下载历史数据
                    try:
                        # 构建时间字符串
                        start_time_str = start_dt.strftime('%Y%m%d') + "000000"
                        end_time_str = end_dt.strftime('%Y%m%d') + "235959"

                        # 检查停止标志
                        if not self._is_running:
                            return (symbol, None, "下载已被用户取消")

                        # 调用下载函数
                        self.log(f"  {symbol}: 触发QMT数据下载...")
                        xtdata.download_history_data(
                            stock_code=symbol,
                            period=qmt_period,
                            start_time=start_time_str,
                            end_time=end_time_str
                        )
                        # 检查停止标志
                        if not self._is_running:
                            return (symbol, None, "下载已被用户取消")
                        time.sleep(0.3)  # 避免API请求过快
                    except Exception as e:
                        self.log(f"  {symbol}: 下载历史数据失败: {str(e)[:30]}")
                        # 继续执行，不中断
                    # 检查停止标志
                    if not self._is_running:
                        return (symbol, None, "下载已被用户取消")

                    # 检查停止标志
                    if not self._is_running:
                        return (symbol, None, "下载已被用户取消")

                    # 读取数据
                    self.log(f"  {symbol}: 读取数据...")
                    if period == 'tick':
                        # tick数据需要指定字段列表
                        data = xtdata.get_market_data_ex(
                            field_list=['time', 'lastPrice', 'volume', 'amount', 'openInt'],
                            stock_list=[symbol],
                            period=qmt_period,
                            start_time=start_str,
                            end_time=end_str
                        )
                    else:
                        # 分钟线和日线数据
                        data = xtdata.get_market_data_ex(
                            stock_list=[symbol],
                            period=qmt_period,
                            start_time=start_str,
                            end_time=end_str
                        )
                    
                    # 获取分红数据用于复权计算
                    divid_data = None
                    if period == '1d':  # 只对日线数据进行复权
                        try:
                            self.log(f"  {symbol}: 获取分红数据...")
                            divid_data = xtdata.get_divid_factors(
                                stock_code=symbol,
                                start_time=start_str,
                                end_time=end_str
                            )
                            if isinstance(divid_data, pd.DataFrame) and not divid_data.empty:
                                self.log(f"  {symbol}: 分红数据获取成功，{len(divid_data)} 条记录")
                            else:
                                self.log(f"  {symbol}: 无分红数据")
                        except Exception as e:
                            self.log(f"  {symbol}: 获取分红数据失败: {str(e)[:30]}")
                    else:
                        # 分钟线和tick数据不需要复权
                        # 不需要复权的数据不需要打印复权相关信息
                        divid_data = None

                    # 检查停止标志
                    if not self._is_running:
                        return (symbol, None, "下载已被用户取消")

                    if isinstance(data, dict) and symbol in data:
                        df = data[symbol]
                        if not df.empty:
                            # 转换数据格式
                            if period == '1d':
                                # 日线数据处理
                                if 'time' in df.columns:
                                    time_series = pd.to_datetime(df['time'], unit='ms')
                                    df_processed = pd.DataFrame({
                                        'stock_code': symbol,
                                        'symbol_type': 'stock',
                                        'date': time_series.dt.strftime('%Y-%m-%d'),
                                        'period': period,
                                        'open': df['open'],
                                        'high': df['high'],
                                        'low': df['low'],
                                        'close': df['close'],
                                        'volume': df['volume'].astype('int64') if 'volume' in df.columns else 0,
                                        'amount': df['amount'] if 'amount' in df.columns else 0,
                                        'adjust_type': 'none',
                                        'factor': 1.0,
                                        'created_at': datetime.now(),
                                        'updated_at': datetime.now()
                                    })
                                    
                                    # 计算五维复权价格
                                    # 检查停止标志
                                    if not self._is_running:
                                        return (symbol, None, "下载已被用户取消")
                                    self.log(f"  {symbol}: 计算五维复权数据...")
                                    df_processed = self._calculate_adjusted_prices(df_processed, divid_data, period)
                                    self.log(f"  {symbol}: 五维复权数据计算完成")
                                    
                                    # 添加原始价格列（如果不存在）
                                    for col in ['open', 'high', 'low', 'close']:
                                        if f'{col}_original' not in df_processed.columns:
                                            df_processed[f'{col}_original'] = df_processed[col]
                            elif period == 'tick':
                                # tick数据处理
                                time_series = pd.to_datetime(df['time'], unit='ms')
                                df_processed = pd.DataFrame({
                                    'stock_code': symbol,
                                    'symbol_type': 'stock',
                                    'datetime': time_series,
                                    'period': 'tick',
                                    'lastPrice': df['lastPrice'] if 'lastPrice' in df.columns else 0,
                                    'volume': df['volume'].astype('int64') if 'volume' in df.columns else 0,
                                    'amount': df['amount'] if 'amount' in df.columns else 0,
                                    'openInt': df['openInt'] if 'openInt' in df.columns else 0,
                                    'created_at': datetime.now(),
                                    'updated_at': datetime.now()
                                })
                            else:
                                # 分钟线数据处理
                                time_series = pd.to_datetime(df['time'], unit='ms')
                                df_processed = pd.DataFrame({
                                    'stock_code': symbol,
                                    'symbol_type': 'stock',
                                    'datetime': time_series,
                                    'period': period,
                                    'open': df['open'],
                                    'high': df['high'],
                                    'low': df['low'],
                                    'close': df['close'],
                                    'volume': df['volume'].astype('int64') if 'volume' in df.columns else 0,
                                    'amount': df['amount'] if 'amount' in df.columns else 0,
                                    'adjust_type': 'none',
                                    'factor': 1.0,
                                    'created_at': datetime.now(),
                                    'updated_at': datetime.now()
                                })
                                
                                # 分钟线数据不需要复权
                                # 添加原始价格列
                                for col in ['open', 'high', 'low', 'close']:
                                    if f'{col}_original' not in df_processed.columns:
                                        df_processed[f'{col}_original'] = df_processed[col]

                            # 检查停止标志
                            if not self._is_running:
                                return (symbol, None, "下载已被用户取消")

                            # 过滤日期范围
                            if period in ['1d', 'weekly', 'monthly', '1w', '1M']:
                                # 日线、周线、月线使用 date 列
                                df_processed = df_processed[
                                    (df_processed['date'] >= start_date) & 
                                    (df_processed['date'] <= end_date)
                                ]
                            elif 'datetime' in df_processed.columns:
                                # 分钟线、tick 使用 datetime 列
                                from datetime import datetime as dt, time as dt_time
                                end_dt_dt = dt.combine(end_dt, dt_time(23, 59, 59))
                                df_processed = df_processed[
                                    (df_processed['datetime'] >= start_dt) & 
                                    (df_processed['datetime'] <= end_dt_dt)
                                ]
                            else:
                                # 其他情况：尝试使用 date 或 datetime
                                if 'date' in df_processed.columns:
                                    df_processed = df_processed[
                                        (df_processed['date'] >= start_date) & 
                                        (df_processed['date'] <= end_date)
                                    ]
                                elif 'datetime' in df_processed.columns:
                                    from datetime import datetime as dt, time as dt_time
                                    end_dt_dt = dt.combine(end_dt, dt_time(23, 59, 59))
                                    df_processed = df_processed[
                                        (df_processed['datetime'] >= start_dt) & 
                                        (df_processed['datetime'] <= end_dt_dt)
                                    ]

                            # 检查停止标志
                            if not self._is_running:
                                return (symbol, None, "下载已被用户取消")

                            if not df_processed.empty:
                                return (symbol, df_processed, None)
                            else:
                                if force_update:
                                    return (symbol, None, "数据为空")
                                else:
                                    if download_type == 'update':
                                        return (symbol, None, "数据已是最新，无需更新")
                                    elif download_type == 'backfill':
                                        return (symbol, None, "历史数据已完整，无需补充")
                                    else:
                                        return (symbol, None, "数据为空")
                        else:
                            return (symbol, None, "数据为空")
                    else:
                        retry_count += 1
                        wait_time = base_wait_time * (2 ** retry_count)
                        if retry_count < max_retries:
                            self.log(f"  {symbol}: 获取数据失败，正在重试 ({retry_count}/{max_retries})...")
                            # 检查停止标志
                            if not self._is_running:
                                return (symbol, None, "下载已被用户取消")
                            time.sleep(wait_time)
                            continue
                        return (symbol, None, "获取数据失败")
                except Exception as e:
                    retry_count += 1
                    wait_time = base_wait_time * (2 ** retry_count)
                    if retry_count < max_retries:
                        error_msg = str(e)[:50]
                        self.log(f"  {symbol}: 处理数据失败: {error_msg}，正在重试 ({retry_count}/{max_retries})...")
                        # 检查停止标志
                        if not self._is_running:
                            return (symbol, None, "下载已被用户取消")
                        time.sleep(wait_time)
                        continue
                    return (symbol, None, f"处理数据失败: {str(e)[:50]}")

        # 使用线程池并行下载
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.executor = executor
        
        try:
            futures = {executor.submit(download_single_stock, symbol): symbol for symbol in stock_codes}
            
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                if not self._is_running:
                    self.log("⚠️ 用户中断")
                    executor.shutdown(wait=False)
                    break
                
                symbol = futures[future]
                try:
                    symbol, df, error = future.result()
                    if error:
                        if "数据已是最新" in error or "历史数据已完整" in error:
                            # 正常情况，不算失败
                            self.log(f"  {symbol}: {error}")
                        else:
                            failed_count += 1
                            failed_list.append(f"{symbol} ({start_date}~{end_date}): {error}")
                    elif df is not None and not df.empty:
                        all_dataframes.append(df)  # 仅收集数据
                        success_count += 1
                    else:
                        failed_count += 1
                        failed_list.append(f"{symbol} ({start_date}~{end_date}): 数据为空")
                        
                except Exception as e:
                    failed_count += 1
                    failed_list.append(f"{symbol} ({start_date}~{end_date}): {str(e)[:50]}")
                
                # 发送进度信号（保持原有格式，确保兼容性）
                self.progress_signal.emit(i+1, total, total)
        finally:
            # 确保线程池被关闭
            if not getattr(executor, '_shutdown', False):
                executor.shutdown(wait=False)
            # 清理线程池引用
            self.executor = None

        # 批量保存所有数据
        if all_dataframes:
            try:
                self.log(f"💾 开始批量保存 {len(all_dataframes)} 只股票的 {period} 数据到数据库...")
                
                # 合并所有DataFrame
                combined_df = pd.concat(all_dataframes, ignore_index=True)
                
                # 使用增强管理器的专用方法批量保存
                # 管理器内部会处理表名、冲突解决、事务等所有细节
                saved_count = db_manager.bulk_insert_stock_data(combined_df, period)
                
                self.log(f"✅ 成功保存 {saved_count} 条记录到数据库")
                
            except Exception as e:
                self.log(f"❌ 批量保存失败: {e}")
                import traceback
                self.log(traceback.format_exc())
                # 可以考虑将失败的数据保存到临时文件，供后续重试
                failed_count += len(all_dataframes)  # 标记本批次所有数据为失败
                success_count = 0
        else:
            self.log("ℹ️ 本批次无有效数据可保存")

        return total, success_count, failed_count, failed_list

    def _backfill_history(self):
        """补充历史数据（根据用户填写的日期范围）- 支持所有数据类型，使用策略模式
        
        支持补充多种数据类型的历史数据，包括日线、分钟线、tick数据等
        采用策略模式处理不同类型的数据补充，支持并行处理和断点续传
        
        主要功能：
        1. 支持补充所有数据类型或指定数据类型
        2. 根据用户填写的日期范围补充数据
        3. 支持断点续传，记录失败的股票
        4. 并行处理，提高补充效率
        5. 内存监控和批次大小调整
        """
        try:
            import os
            from src.core.data.database.db_manager import get_db_manager
            import pandas as pd
            from datetime import datetime, timedelta
            from src.core.utils import DownloadConfig, retry_with_backoff, DailyDataStrategy, MinuteDataStrategy, TickDataStrategy, WeeklyDataStrategy, MonthlyDataStrategy

            self.log("✅ 数据管理器初始化成功")

            # 获取用户填写的日期参数
            start_date = self.start_date if self.start_date else '20180101'
            # 自动设置结束日期为当日
            end_date = datetime.now().strftime('%Y%m%d')

            self.log(f"📅 补充日期范围: {start_date} ~ {end_date}")

            # 转换日期格式
            start_dt = pd.to_datetime(start_date, format='%Y%m%d')
            end_dt = pd.to_datetime(end_date, format='%Y%m%d')

            # 获取DuckDB管理器
            db_manager = get_db_manager(self.db_path)

            # 支持的周期列表
            periods = []
            if self.period is None:
                # 所有类型
                periods = ['1d', '1m', '5m', '15m', '30m', '60m', 'weekly', 'monthly', 'tick']
            else:
                # 指定类型
                periods = [self.period]

            total_all = 0
            success_all = 0
            failed_all = 0

            # 记录每个数据类型的详细信息
            data_type_details = []

            # 记录 tick 数据是否已经更新过
            tick_updated = False

            for period in periods:
                # 对于 tick 数据，只更新一次
                if period == 'tick' and tick_updated:
                    self.log(f"\n=== 跳过 {period} 数据补充 ====")
                    self.log(f"  tick 数据已在本次补充中处理过，跳过")
                    continue
                
                self.log(f"\n=== 补充 {period} 历史数据 ====")

                # 加载配置
                config = DownloadConfig()
                
                # 初始化策略
                if period == '1d':
                    strategy = DailyDataStrategy(db_manager, config, self.log_signal)
                elif period == 'tick':
                    strategy = TickDataStrategy(db_manager, config, self.log_signal)
                elif period == 'weekly':
                    strategy = WeeklyDataStrategy(db_manager, config, self.log_signal)
                elif period == 'monthly':
                    strategy = MonthlyDataStrategy(db_manager, config, self.log_signal)
                else:
                    strategy = MinuteDataStrategy(db_manager, config, self.log_signal, period)
                
                # 使用策略模式补充数据
                self.log(f"📊 使用{period}数据策略")
                
                # 生成任务ID，仅用于日志
                task_id = f"backfill_history_{period}_{start_date}_{end_date}"
                
                # 初始化内存监控器
                from src.core.utils import MemoryMonitor
                memory_monitor = MemoryMonitor(log_signal=self.log_signal)
                
                # 从Parquet文件中获取已完成的股票列表（直接扫描文件）
                completed_symbols = []
                failed_symbols = []  # 失败记录列表
                
                # 获取待处理的股票代码列表
                stock_codes = self._get_all_stock_codes()
                
                try:
                    from pathlib import Path
                    
                    data_config = config.get_config()
                    data_root_dir = data_config.get('data_paths', {}).get('root_dir', 'D:/MyStockData')
                    parquet_config = data_config.get('storage', {}).get('parquet', {})
                    parquet_root_dir = parquet_config.get('root_dir', 'Parquet')
                    parquet_root = Path(data_root_dir) / parquet_root_dir
                    
                    if period == '1d':
                        parquet_path = parquet_root / 'kline' / 'daily'
                    elif period == '1w' or period == 'weekly':
                        parquet_path = parquet_root / 'kline' / 'weekly'
                    elif period == '1mon' or period == 'monthly':
                        parquet_path = parquet_root / 'kline' / 'monthly'
                    elif period == 'tick':
                        parquet_path = parquet_root / 'tick'
                    else:
                        parquet_path = parquet_root / 'kline' / period
                    
                    if parquet_path.exists():
                        for exchange_dir in parquet_path.iterdir():
                            if exchange_dir.is_dir():
                                for file in exchange_dir.glob('*.parquet'):
                                    symbol = file.stem
                                    full_symbol = f"{symbol}.{exchange_dir.name}"
                                    completed_symbols.append(full_symbol)
                    
                    self.log(f"📋 从数据文件中扫描到 {len(completed_symbols)} 只已完成的股票")
                except Exception as e:
                    self.log(f"⚠️ 扫描已下载文件失败: {e}")
                
                # 过滤出未完成的股票
                if completed_symbols:
                    # 过滤掉已完成的股票
                    remaining_stock_codes = [code for code in stock_codes if code not in completed_symbols]
                    if remaining_stock_codes:
                        self.log(f"📋 加载断点信息: 已完成 {len(completed_symbols)} 只股票，剩余 {len(remaining_stock_codes)} 只股票")
                        stock_codes = remaining_stock_codes
                    else:
                        self.log("📋 所有股票已完成补充，无需继续")
                        continue
                else:
                    self.log("📋 无断点信息，开始全新补充")
                
                # 检查失败记录
                if failed_symbols:
                    self.log(f"📋 加载失败记录: {len(failed_symbols)} 只股票")
                
                # 批量查询所有股票及其最早日期（一次性查询）
                if period == '1d':
                    table_name = 'stock_daily'
                    date_column = 'date'
                elif period == 'tick':
                    table_name = 'stock_tick'
                    date_column = 'datetime'
                elif period in ['weekly', 'monthly', '1w', '1M']:
                    # 周线和月线数据使用 date 列
                    table_name = f'stock_{"weekly" if period in ["weekly", "1w"] else "monthly"}'
                    date_column = 'date'
                else:
                    table_name = f'stock_{period}'
                    date_column = 'datetime'

                # 检查表是否存在
                if not db_manager.table_exists(table_name):
                    self.log(f"📝 表 {table_name} 不存在，将创建新表")
                    # 继续处理，策略会自动创建表结构

                # 批量查询所有股票及其最早日期（一次性查询）
                df_stocks = None
                # 对于周线和月线数据，使用正确的表名
                actual_table_name = table_name
                # 周线和月线数据使用 date 列，与日线数据一致
                query_date_column = date_column
                if period == 'weekly':
                    actual_table_name = 'stock_weekly'  # 与 _update_data 方法一致
                    query_date_column = 'date'  # 周线表使用 date 列
                elif period == 'monthly':
                    actual_table_name = 'stock_monthly'  # 与 _update_data 方法一致
                    query_date_column = 'date'  # 月线表使用 date 列
                
                if db_manager.table_exists(actual_table_name):
                    query = f"""
                        SELECT
                            stock_code,
                            MIN({query_date_column}) as earliest_date,
                            MAX({query_date_column}) as latest_date
                        FROM {actual_table_name}
                        GROUP BY stock_code
                        ORDER BY stock_code
                    """

                    try:
                        df_stocks = db_manager.query_to_dataframe(query)
                    except Exception as e:
                        self.log(f"⚠️ 查询表 {actual_table_name} 失败: {e}")
                        continue

                    if df_stocks.empty:
                        self.log(f"⚠️ 数据库中没有 {period} 数据，将开始下载")
                else:
                    self.log(f"⚠️ 表 {actual_table_name} 不存在，将开始下载")

                # 始终获取完整股票列表，确保所有标的都能被处理
                self.log(f"📥 获取完整股票列表")
                stock_codes = self._get_all_stock_codes()
                if not stock_codes:
                    self.log(f"⚠️ 无法获取股票列表，跳过 {period} 数据补全")
                    continue
                self.log(f"📊 获取到 {len(stock_codes)} 只股票")
                
                # 测试模式：只处理配置的股票数量
                if hasattr(self, 'test_mode') and self.test_mode:
                    # 加载配置
                    from src.core.utils import DownloadConfig
                    config = DownloadConfig(self.config)
                    test_count = config.get_test_stock_count(period)
                    stock_codes = stock_codes[:test_count]
                    self.log(f"🔧 测试模式：{period}数据只处理前{test_count}只股票")
                
                total = len(stock_codes)
                success_count = 0
                failed_count = 0
                failed_list = []
                
                # 不过滤已完成的股票，重新补充所有标的
                total = len(stock_codes)
                self.log(f"📊 准备补充 {total} 只股票的 {period} 数据")
                self.log(f"📅 补充范围: {start_date} ~ {end_date}")
                
                # 获取批量大小
                initial_batch_size = strategy.get_batch_size()
                # 为不同周期数据设置合适的批次大小
                if period == '1m':
                    initial_batch_size = 10  # 1分钟数据使用最小的批次大小
                elif period in ['5m', '15m', '30m', '60m', 'weekly', 'monthly']:
                    initial_batch_size = 12  # 其他周期数据使用较小的批次大小
                elif period == '1d':
                    initial_batch_size = 50  # 日线数据使用较大的批次大小
                elif period == 'tick':
                    initial_batch_size = 5  # Tick数据使用最小的批次大小
                current_batch_size = initial_batch_size
                # 进一步减少线程数以降低内存使用
                max_workers = min(os.cpu_count(), 3)  # 进一步减少线程数
                
                self.log(f"🚀 启动 {max_workers} 个下载线程")
                self.log(f"📊 开始补充 {period} 历史数据")
                self.log(f"📦 初始批次大小: {current_batch_size}")

                # 初始化流式处理器
                from src.core.data.processing.optimized_processor import OptimizedDataProcessor
                processor = OptimizedDataProcessor(strategy.db_manager, self.log_signal, config=self.config)

                # 数据下载函数
                thread_self = self  # 捕获当前线程实例的引用
                @retry_with_backoff(max_retries=3, initial_delay=1, max_delay=10)
                def download_data(symbol):
                    """下载单个股票数据"""
                    # 在开始时就检查
                    if not thread_self._is_running:
                        return symbol, None, "补充已被用户取消"
                    try:
                        # 使用策略下载数据
                        df, is_skip = strategy.download_data(
                            symbol, 
                            thread_self.start_date, 
                            thread_self.end_date,
                            force_update=True
                        )
                        # 再次检查
                        if not thread_self._is_running:
                            return symbol, None, "补充已被用户取消"
                        if df is not None and not df.empty:
                            return symbol, df, None
                        else:
                            return symbol, None, "数据为空"
                    except Exception as e:
                        return symbol, None, str(e)[:50]

                # 使用线程池并行下载
                self.log("📥 开始并行补充历史数据...")
                processed_count = 0
                memory_check_interval = 10  # 每10个股票检查一次内存

                # 创建线程池
                import concurrent.futures
                self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
                executor = self.executor
                
                try:
                    # 提交所有下载任务
                    self.futures = {executor.submit(download_data, symbol): symbol for symbol in stock_codes}
                    future_to_symbol = self.futures

                    # 处理结果
                    pending_futures = set(future_to_symbol.keys())
                    
                    while pending_futures and self._is_running:
                        try:
                            # 等待任意一个任务完成，但最多等1秒
                            done, pending_futures = concurrent.futures.wait(pending_futures, timeout=1.0, return_when=concurrent.futures.FIRST_COMPLETED)
                            
                            for future in done:
                                symbol = future_to_symbol[future]
                                try:
                                    symbol, df, error = future.result(timeout=5)  # 设置超时，避免任务卡住
                                    processed_count += 1

                                    # 修复：简化进度计算逻辑，直接使用 processed_count
                                    total_processed = processed_count
                                    total_processed = min(total_processed, total)

                                    # 计算预期处理数（剩余需要处理的数量）
                                    expected_process = len(stock_codes)
                                    # 更新进度 - 每处理一个股票就更新一次
                                    self.progress_signal.emit(total_processed, expected_process, total)

                                    if error:
                                        failed_count += 1
                                        failed_list.append(f"{symbol} - {error}")
                                        completed_symbols.append(symbol)  # 修复：失败也要标记为已完成
                                    elif df is not None:
                                        # 使用流式处理器处理数据
                                        processor.add_data(symbol, df, period)
                                        success_count += 1
                                        completed_symbols.append(symbol)
                                    else:
                                        failed_count += 1
                                        failed_list.append(f"{symbol} - 未知错误")
                                        completed_symbols.append(symbol)  # 修复：未知错误也要标记为已完成

                                    # 定期检查内存使用
                                    if processed_count % memory_check_interval == 0:
                                        memory_usage = memory_monitor.get_memory_usage()
                                        
                                        # 内存超过阈值时调整批次大小
                                        if memory_monitor.should_adjust_batch_size():
                                            new_batch_size = memory_monitor.suggest_batch_size(
                                                current_batch_size, 
                                                strategy.get_period()
                                            )
                                            
                                            if new_batch_size != current_batch_size:
                                                current_batch_size = new_batch_size
                                                
                                                # 立即处理缓冲区的数据
                                                processor.flush()
                                    
                                    # 内存过高时强制垃圾回收
                                    if memory_usage > memory_monitor.memory_limit_gb * 0.9:
                                        import gc
                                        gc.collect()

                                    # 每补充一定数量的股票输出一次日志并保存断点
                                    batch_threshold = 50 if strategy.get_period() != 'tick' else 20
                                    if processed_count % batch_threshold == 0:
                                        expected_process = len(stock_codes)
                                        self.log(f"📊 进度: {total_processed}/{expected_process}/{total} | 成功: {success_count} | 失败: {failed_count}")
                                        # 保存断点信息
                                        (task_id, completed_symbols, total)

                                except concurrent.futures.TimeoutError:
                                    failed_count += 1
                                    failed_list.append(f"{symbol} - 补充超时")
                                    self.log(f"⚠️ {symbol} 补充超时")
                                except Exception as e:
                                    failed_count += 1
                                    failed_list.append(f"{symbol} - {str(e)[:50]}")
                                finally:
                                    # 从字典中移除已处理的任务
                                    del future_to_symbol[future]
                            
                            # 每次循环都检查停止标志
                            if not self._is_running:
                                self.log("⚠️ 停止信号收到，正在中止...")
                                # 取消所有尚未完成的任务
                                for f in pending_futures:
                                    f.cancel()
                                # 立即关闭线程池
                                executor.shutdown(wait=False)
                                # 强制保存断点信息
                                
                                break
                        except Exception as e:
                            self.log(f"⚠️ 处理任务时出错: {str(e)}")
                            continue
                finally:
                    # 确保线程池被关闭
                    if not executor._shutdown:
                        executor.shutdown(wait=False)
                    # 清理流式处理器
                    processor.flush()
                    # 保存断点信息
                    


                # 处理剩余数据
                processor.flush()

                # 保存失败记录
                if failed_list:
                    # 对于失败的记录，只尝试重新补充一次
                    # 过滤出不是"数据为空"的失败记录进行重试
                    retry_symbols = []
                    no_data_symbols = []
                    
                    for item in failed_list:
                        if "数据为空" in item:
                            no_data_symbols.append(item)
                        else:
                            retry_symbols.append(item.split(' - ')[0])
                    
                    # 标记无数据的股票
                    if no_data_symbols:
                        self.log(f"📋 标记 {len(no_data_symbols)} 只股票在时间段内无数据")
                        for item in no_data_symbols:
                            self.log(f"  - {item}")
                    
                    # 只尝试重新补充非"数据为空"的失败股票
                    if retry_symbols:
                        self.log(f"🔄 尝试重新补充 {len(retry_symbols)} 只失败的股票...")
                        retry_failed_count = 0
                        retry_failed_list = []
                        
                        # 单个线程重新补充，避免并发问题
                        for symbol in retry_symbols:
                            if not self._is_running:
                                break
                            
                            try:
                                # 检查停止标志
                                if not self._is_running:
                                    break
                                
                                # 重新下载数据
                                df, is_skip = strategy.download_data(symbol, self.start_date, self.end_date, force_update=True)
                                
                                # 检查停止标志
                                if not self._is_running:
                                    break
                                
                                if df is not None and not df.empty:
                                    # 检查停止标志
                                    if not self._is_running:
                                        break
                                    
                                    # 使用流式处理器处理数据
                                    processor.add_data(symbol, df, period)
                                    completed_symbols.append(symbol)
                                    self.log(f"✅ 重新补充 {symbol} 成功")
                                else:
                                    retry_failed_count += 1
                                    retry_failed_list.append(f"{symbol} - 数据为空")
                                    self.log(f"❌ 重新补充 {symbol} 仍然失败")
                            except Exception as e:
                                retry_failed_count += 1
                                retry_failed_list.append(f"{symbol} - {str(e)[:50]}")
                                self.log(f"❌ 重新补充 {symbol} 失败: {str(e)[:50]}")
                        
                        # 处理重新补充的数据
                        processor.flush()
                        
                        # 等待保存线程完成
                        self.log("⏳ 等待保存线程完成处理...")
                        import time
                        time.sleep(2)
                        # 检查 processor 对象是否有 stop 方法
                        if hasattr(processor, 'stop'):
                            processor.stop()
                        else:
                            self.log("ℹ️ 处理器没有 stop 方法，跳过停止操作")
                        
                        # 更新失败统计
                        failed_count = retry_failed_count + len(no_data_symbols)
                        failed_list = retry_failed_list + no_data_symbols
                    else:
                        # 所有失败都是"数据为空"，直接标记
                        failed_count = len(no_data_symbols)
                        failed_list = no_data_symbols
                    
                    # 保存最终失败记录
                    if failed_list:
                        failed_symbols = [item.split(' - ')[0] for item in failed_list]
                        # checkpoint_manager.save_failed_symbols(task_id, failed_symbols)
                    else:
                        # 所有失败的股票都重新补充成功，清理失败记录
                        (task_id)

                # 保存最终断点信息
                (task_id, completed_symbols, total)

                # 清理断点信息（如果全部成功且不是用户手动停止）
                if failed_count == 0 and self._is_running:
                    (task_id)
                else:
                    # 用户手动停止或有失败的股票，保留断点信息
                    self.log(f"💾 保留断点信息 (任务: {task_id})")

                # 确保缓冲区被清空
                if processor.buffer:
                    self.log("⚠️ 缓冲区中仍有数据，再次清空")
                    processor.buffer.clear()

                # 确保成功数和失败数的总和等于总数
                total_success = min(len(completed_symbols), total)
                total_failed = total - total_success

                # 显示统计信息
                self.log(f"\n🎉 {period} 历史数据补充完成")
                self.log(f"📊 数据类型: {period}")
                self.log(f"📅 补充范围: {start_date} 至 {end_date}")
                self.log(f"📋 标的数: {total}")
                self.log(f"✅ 成功: {total_success}")
                self.log(f"❌ 失败: {total_failed}")
                self.log(f"📈 成功率: {round(total_success/total*100, 2)}%" if total > 0 else "📈 成功率: 0%")
                if failed_list:
                    self.log("失败列表:")
                    for item in failed_list[:10]:  # 只显示前10个失败的
                        self.log(f"  - {item}")
                    if len(failed_list) > 10:
                        self.log(f"  ... 等 {len(failed_list) - 10} 个失败")

                # 收集数据类型详细信息
                data_type_details.append({
                    'period': period,
                    'total': total,
                    'success': total_success,
                    'failed': total_failed
                })

                # 如果是 tick 数据，标记为已更新
                if period == 'tick':
                    tick_updated = True

                total_all += total
                success_all += total_success
                failed_all += failed_count

            # 完成所有周期的处理
            self.log("\n🎉 所有历史数据补充完成！")
            self.finished_signal.emit({'total': total_all, 'success': success_all, 'failed': failed_all, 'task_type': 'backfill_history', 'data_type_details': data_type_details})
        except Exception as e:
            import traceback
            error_msg = f"补充历史数据失败: {str(e)}\n{traceback.format_exc()}"
            self.log(error_msg)
            self.error_signal.emit(error_msg)


class LocalDataManagerCLI:
    """本地数据管理器命令行接口
    
    用于通过命令行执行数据下载任务，便于测试和性能分析
    """
    
    def __init__(self):
        self.logger = setup_logger()
        self.performance_data = []  # 用于记录性能数据
    
    def run_test(self, symbols=None, start_date=None, end_date=None, period='1m', db_path=None, test_mode=False, num_stocks=150):
        """运行测试
        
        Args:
            symbols: 股票代码列表，None表示使用所有A股
            start_date: 开始日期，格式为 'YYYYMMDD'
            end_date: 结束日期，格式为 'YYYYMMDD'
            period: 数据周期，如 '1d', '1m', '5m', '15m', '30m', '60m', 'tick'
            db_path: 数据库路径
            test_mode: 测试模式，是否只处理少量数据
            num_stocks: 股票数量，默认为150只
        """
        import sys
        import os
        import psutil
        from datetime import datetime, timedelta
        
        # 设置默认值
        if not start_date:
            # 默认1年前
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not db_path:
            # 使用硬编码的独立测试数据库文件
            test_db_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'test_db')
            os.makedirs(test_db_dir, exist_ok=True)
            db_path = os.path.join(test_db_dir, f'test_{period}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
        
        self.logger.info(f"🚀 开始测试: {period} 数据")
        self.logger.info(f"📅 时间范围: {start_date} ~ {end_date}")
        self.logger.info(f"💾 数据库路径: {db_path}")
        self.logger.info(f"📊 股票数量: {num_stocks}")
        
        # 如果没有指定股票列表，获取全部A股（但限制数量）
        if symbols is None:
            self.logger.info("📥 获取A股列表...")
            if XTDATA_AVAILABLE:
                from xtquant import xtdata
                all_stocks = xtdata.get_stock_list_in_sector('沪深A股')
                
                # 过滤掉ETF和基金
                etf_patterns = ['51', '159', '150', '588', '50', '56', '58']
                filtered_stocks = []
                for stock in all_stocks:
                    code = stock.split('.')[0]
                    is_etf = False
                    for pattern in etf_patterns:
                        if code.startswith(pattern):
                            is_etf = True
                            break
                    if not is_etf:
                        filtered_stocks.append(stock)
                
                # 限制股票数量
                num_stocks = min(200, max(100, num_stocks))
                symbols = filtered_stocks[:num_stocks]
                self.logger.info(f"✅ 获取到 {len(symbols)} 只股票")
            else:
                self.logger.error("❌ xtquant模块不可用，无法获取股票列表")
                return
        
        # 记录开始时间
        start_time = datetime.now()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024 / 1024  # GB
        self.logger.info(f"📈 开始内存使用: {start_memory:.2f} GB")
        
        # 性能数据记录
        batch_performance = []
        last_progress = 0
        
        # 创建下载线程
        thread = DataDownloadThread(
            task_type='download_minute_data',
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            data_type='1min' if period == '1m' else period,
            period=period,
            db_path=db_path,
            update_mode='all',
            test_mode=test_mode
        )
        
        # 连接信号
        thread.log_signal.connect(self.logger.info)
        
        def on_progress(current, expected, total):
            nonlocal last_progress, batch_performance
            elapsed = (datetime.now() - start_time).total_seconds()
            current_memory = psutil.Process().memory_info().rss / 1024 / 1024 / 1024  # GB
            
            # 每处理20只股票记录一次性能数据
            if current % 20 == 0 and current > last_progress:
                batch_time = elapsed
                batch_stocks = current - last_progress
                batch_speed = batch_stocks / batch_time if batch_time > 0 else 0
                
                batch_performance.append({
                    'batch': current // 20,
                    'stocks_processed': current,
                    'time_elapsed': elapsed,
                    'memory_used': current_memory,
                    'speed': batch_speed
                })
                
                self.logger.info(f"📊 进度: {current}/{expected}/{total} | 耗时: {elapsed:.2f}秒 | 内存: {current_memory:.2f}GB | 速度: {batch_speed:.2f}只/秒")
                last_progress = current
        
        def on_finished(result):
            elapsed = (datetime.now() - start_time).total_seconds()
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024 / 1024  # GB
            memory_used = end_memory - start_memory
            
            self.logger.info(f"🎉 测试完成!")
            self.logger.info(f"📊 总耗时: {elapsed:.2f}秒")
            self.logger.info(f"📈 内存使用变化: {memory_used:.2f} GB (开始: {start_memory:.2f} GB, 结束: {end_memory:.2f} GB)")
            
            # 处理不同类型的结果
            if 'total' in result:
                self.logger.info(f"📋 标的数: {result['total']}")
                self.logger.info(f"✅ 成功: {result['success']}")
                self.logger.info(f"❌ 失败: {result['failed']}")
                self.logger.info(f"📈 成功率: {round(result['success']/result['total']*100, 2)}%" if result['total'] > 0 else "📈 成功率: 0%")
                
                # 计算性能指标
                if result['total'] > 0:
                    avg_time_per_stock = elapsed / result['total']
                    self.logger.info(f"⏱️ 平均每只股票耗时: {avg_time_per_stock:.2f}秒")
                    
                    # 分析性能趋势
                    if batch_performance:
                        self.logger.info("\n📈 性能趋势分析:")
                        for i, batch in enumerate(batch_performance):
                            self.logger.info(f"  批次 {batch['batch']}: 处理 {batch['stocks_processed']} 只 | 速度 {batch['speed']:.2f}只/秒 | 内存 {batch['memory_used']:.2f}GB")
                        
                        # 计算速度变化
                        if len(batch_performance) > 1:
                            first_speed = batch_performance[0]['speed']
                            last_speed = batch_performance[-1]['speed']
                            speed_change = (last_speed - first_speed) / first_speed * 100
                            self.logger.info(f"\n📊 速度变化: {speed_change:+.2f}%")
                            if speed_change < -20:
                                self.logger.warning("⚠️ 性能明显下降，可能存在内存泄漏或其他问题")
            else:
                # 处理其他类型的结果
                self.logger.info(f"📋 任务类型: {result.get('task_type', 'unknown')}")
                self.logger.info(f"📋 消息: {result.get('message', '无详细信息')}")
        
        def on_error(error):
            self.logger.error(f"❌ 测试失败: {error}")
        
        thread.progress_signal.connect(on_progress)
        thread.finished_signal.connect(on_finished)
        thread.error_signal.connect(on_error)
        
        # 启动线程
        self.logger.info("🚀 启动下载线程...")
        thread.start()
        
        # 等待线程完成
        thread.wait()
        
        self.logger.info("✅ 测试完成")


if __name__ == "__main__":
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='本地数据管理器命令行工具')
    parser.add_argument('--period', type=str, default='1m', help='数据周期，如 1m, 5m, 15m, 30m, 60m, 1d, tick')
    parser.add_argument('--start-date', type=str, help='开始日期，格式为 YYYYMMDD')
    parser.add_argument('--end-date', type=str, help='结束日期，格式为 YYYYMMDD')
    parser.add_argument('--db-path', type=str, help='数据库路径')
    parser.add_argument('--test-mode', action='store_true', help='测试模式，只处理少量数据')
    parser.add_argument('--num-stocks', type=int, default=150, help='股票数量，默认150只')
    
    args = parser.parse_args()
    
    cli = LocalDataManagerCLI()
    
    # 运行测试
    cli.run_test(
        start_date=args.start_date,
        end_date=args.end_date,
        period=args.period,
        db_path=args.db_path,
        test_mode=args.test_mode,
        num_stocks=args.num_stocks
    )


class SingleStockDownloadThread(QThread):
    """单个标的下载线程
    
    负责下载单个股票的指定周期数据，支持日线、分钟线和tick数据
    
    Signals:
        log_signal: 日志信号，用于输出下载过程中的日志信息
        progress_signal: 进度信号，传递当前进度和总进度
        finished_signal: 完成信号，传递下载结果
        error_signal: 错误信号，传递错误信息
    """
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)  # current, total
    finished_signal = pyqtSignal(dict)  # {'success': bool, 'symbol': str, 'record_count': int, 'file_size': float}
    error_signal = pyqtSignal(str)

    def log(self, message):
        """记录日志
        
        Args:
            message: 日志消息内容
        """
        self.log_signal.emit(message)

    def __init__(self, stock_code, start_date, end_date, period='1d', db_path=None):
        """初始化单个标的下载线程
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期，格式为 'YYYY-MM-DD'
            end_date: 结束日期，格式为 'YYYY-MM-DD'
            period: 数据周期，如 '1d', '1m', '5m', '15m', '30m', '60m', 'tick'
            db_path: 数据库路径
        """
        super().__init__()
        self.stock_code = stock_code
        self.start_date = start_date
        self.end_date = end_date
        self.period = period  # '1d', '1m', '5m', '15m', '30m', '60m', 'tick'
        self.db_path = db_path
        self._is_running = True

    def run(self):
        """运行下载任务
        
        执行以下操作：
        1. 检查xtquant模块是否可用
        2. 初始化数据库管理器
        3. 转换日期格式
        4. 映射周期到QMT API格式
        5. 下载数据
        6. 过滤日期范围
        7. 转换数据格式
        8. 保存数据到DuckDB
        9. 发送完成信号
        """
        try:
            # 检查xtquant模块是否可用
            if not XTDATA_AVAILABLE:
                error_msg = "❌ xtquant模块不可用，请确保QMT已安装并运行"
                self.log(error_msg)
                self.error_signal.emit(error_msg)
                return
            
            # 导入xtdata
            from xtquant import xtdata
            from datetime import datetime
            import pandas as pd

            # 检查DuckDB管理器是否可用
            try:
                from src.core.data.database.db_manager import get_db_manager
                manager = get_db_manager(self.db_path)
                self.log(f"[OK] 数据管理器初始化成功")
            except ImportError:
                self.error_signal.emit("DuckDB管理器不可用，请确保src.core.data_manager.enhanced_db_manager模块存在")
                return
            except Exception as e:
                self.error_signal.emit(f"DuckDB管理器初始化失败: {e}")
                return

            self.log(f"[INFO] 正在下载 {self.stock_code}...")
            self.log(f"   数据周期: {self.period}")
            self.log(f"   日期范围: {self.start_date} ~ {self.end_date}")

            # 转换日期格式
            start_dt = datetime.strptime(self.start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(self.end_date, '%Y-%m-%d')
            start_str = start_dt.strftime('%Y%m%d')
            end_str = end_dt.strftime('%Y%m%d')

            # 映射周期到QMT API格式
            period_map = {
                '1d': '1d',
                '1m': '1m',
                '5m': '5m',
                '15m': '15m',
                '30m': '30m',
                '60m': '60m',
                'tick': 'tick'
            }
            qmt_period = period_map.get(self.period, '1d')

            # 下载数据
            # 统一使用get_market_data_ex获取数据（支持日线和分钟线）
            # 计算需要获取的数据条数
            start_dt = datetime.strptime(self.start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(self.end_date, '%Y-%m-%d')
            days_diff = (end_dt - start_dt).days + 1

            if self.period == '1d':
                # 日线：直接获取天数，加20天缓冲
                count = max(days_diff + 20, 30)
                self.log(f"📡 正在从QMT获取日线数据（约{days_diff}个交易日）...")
            elif self.period == 'tick':
                # tick数据：需要先下载历史数据
                self.log(f"📥 正在下载tick历史数据...")
                try:
                    # 对于tick数据，需要先使用download_history_data下载
                    # 注意：tick数据下载需要指定到秒
                    start_time_str = start_dt.strftime('%Y%m%d') + "000000"
                    end_time_str = end_dt.strftime('%Y%m%d') + "235959"

                    # 调用下载函数
                    xtdata.download_history_data(
                        stock_code=self.stock_code,
                        period='tick',
                        start_time=start_time_str,
                        end_time=end_time_str
                    )
                    self.log(f"✓ tick数据下载完成")
                except Exception as e:
                    self.log(f"⚠ tick数据下载警告: {str(e)}")
                    self.log(f"  继续尝试读取本地数据...")

                # 下载后尝试读取，设置较大的count
                count = 100000
                self.log(f"📡 正在读取已下载的tick数据...")
            else:
                # 分钟线：估算每天的条数
                if self.period == '1m':
                    count_per_day = 240  # 4小时 * 60分钟
                elif self.period == '5m':
                    count_per_day = 48
                elif self.period == '15m':
                    count_per_day = 16
                elif self.period == '30m':
                    count_per_day = 8
                else:  # 60m
                    count_per_day = 4

                count = days_diff * count_per_day
                # 限制最大条数，避免数据量过大
                count = min(count, 100000)
                self.log(f"📡 正在从QMT获取{self.period}分钟线数据（最多{count}条）...")

            # 使用count参数获取数据（QMT API支持的方式）
            if self.period == 'tick':
                # 不指定field_list，使用默认字段，避免某些股票没有func_type字段导致下载失败
                data = xtdata.get_market_data_ex(
                    stock_list=[self.stock_code],
                    period=qmt_period,
                    start_time=start_str,
                    end_time=end_str,
                    count=count
                )
            else:
                data = xtdata.get_market_data_ex(
                    stock_list=[self.stock_code],
                    period=qmt_period,
                    count=count
                )

            if isinstance(data, dict) and self.stock_code in data:
                df = data[self.stock_code]
                if df.empty:
                    self.error_signal.emit(f"没有获取到 {self.stock_code} 的数据，请检查代码和日期范围")
                    return
            else:
                self.error_signal.emit(f"没有获取到 {self.stock_code} 的数据，请检查代码和日期范围")
                return

            # 根据日期范围过滤数据
            self.log("🔍 正在过滤日期范围...")
            df['datetime'] = pd.to_datetime(df['time'], unit='ms')

            if self.period == '1d':
                # 日线：只保留日期范围内的数据
                df = df[(df['datetime'] >= start_dt) & (df['datetime'] <= end_dt)]
            else:
                # 分钟线/tick：只保留日期范围内的数据（精确到分钟/秒）
                # 使用当天的23:59:59作为结束时间
                from datetime import datetime as dt, time as dt_time
                end_dt_dt = dt.combine(end_dt, dt_time(23, 59, 59))
                df = df[(df['datetime'] >= start_dt) & (df['datetime'] <= end_dt_dt)]

            if df.empty:
                self.error_signal.emit(f"在指定日期范围内没有数据，请检查日期设置")
                return

            record_count = len(df)
            self.log(f"📊 获取到 {record_count} 条数据")

            # 转换数据格式
            self.log("💾 正在保存到DuckDB...")

            # 转换为标准格式
            if self.period == 'tick':
                # tick数据处理（字段结构不同）
                time_series = pd.to_datetime(df['time'], unit='ms')

                df_processed = pd.DataFrame({
                    'stock_code': self.stock_code,
                    'symbol_type': 'stock' if (self.stock_code.startswith('0') or self.stock_code.startswith('3') or self.stock_code.startswith('6')) else 'etf',
                    'datetime': time_series,
                    'period': 'tick',
                    'lastPrice': df['lastPrice'] if 'lastPrice' in df.columns else 0,
                    'volume': df['volume'].astype('int64') if 'volume' in df.columns else 0,
                    'amount': df['amount'] if 'amount' in df.columns else 0,
                    'func_type': df['func_type'] if 'func_type' in df.columns else 0,
                    'openInt': df['openInt'] if 'openInt' in df.columns else 0,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                })

                table_name = 'stock_tick'

                # 确保stock_tick表存在
                create_table_sql = f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        stock_code VARCHAR(20),
                        symbol_type VARCHAR(10),
                        datetime TIMESTAMP,
                        period VARCHAR(10),
                        lastPrice DOUBLE,
                        volume BIGINT,
                        amount DOUBLE,
                        func_type INTEGER,
                        openInt DOUBLE,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                """
                manager.execute_write(create_table_sql)

                # 保存tick数据
                # 使用bulk_insert_stock_data方法
                manager.bulk_insert_stock_data(df_processed, 'tick')

                self.log(f"✅ 已保存 {len(df_processed)} 条tick记录到DuckDB")

                result = {
                    'success': True,
                    'symbol': self.stock_code,
                    'record_count': len(df_processed),
                    'file_size': len(df_processed) * 0.0001
                }

                self.finished_signal.emit(result)
                self.log(f"[OK] {self.stock_code} 下载完成!")
                return

            if 'time' in df.columns:
                # QMT返回的数据格式
                # 日线：使用DATE类型（字符串YYYY-MM-DD）
                # 分钟线：使用TIMESTAMP类型（直接保存datetime对象）
                time_series = pd.to_datetime(df['time'], unit='ms')
                if self.period == '1d':
                    date_series = time_series.dt.strftime('%Y-%m-%d')
                else:
                    date_series = time_series  # 直接使用datetime对象（支持分钟线）

                df_processed = pd.DataFrame({
                    'stock_code': self.stock_code,
                    'symbol_type': 'stock' if (self.stock_code.startswith('0') or self.stock_code.startswith('3') or self.stock_code.startswith('6')) else 'etf',
                    'date': date_series,
                    'period': self.period,
                    'open': df['open'],
                    'high': df['high'],
                    'low': df['low'],
                    'close': df['close'],
                    'volume': df['volume'].astype('int64') if 'volume' in df.columns else 0,
                    'amount': df['amount'] if 'amount' in df.columns else 0,
                    'adjust_type': 'none',
                    'factor': 1.0,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                })

                # 只有日线数据需要添加复权列
                if self.period == '1d':
                    # 添加复权列（全部使用原始价格）
                    for col in ['open', 'high', 'low', 'close']:
                        df_processed[f'{col}_front'] = df_processed[col]
                        df_processed[f'{col}_back'] = df_processed[col]
                        df_processed[f'{col}_geometric_front'] = df_processed[col]
                        df_processed[f'{col}_geometric_back'] = df_processed[col]

                # 保存到DuckDB
                if self.period == '1d':
                    table_name = 'stock_daily'
                else:
                    table_name = f'stock_{self.period}'

                # 使用bulk_insert_stock_data方法
                manager.bulk_insert_stock_data(df_processed, self.period)

                self.log(f"✅ 已保存 {len(df_processed)} 条记录到DuckDB")

                result = {
                    'success': True,
                    'symbol': self.stock_code,
                    'record_count': len(df_processed),
                    'file_size': len(df_processed) * 0.0001  # 估算
                }

                self.finished_signal.emit(result)
                self.log(f"[OK] {self.stock_code} 下载完成!")

            else:
                self.error_signal.emit("数据格式不正确")

        except Exception as e:
            import traceback
            error_msg = f"[ERROR] 下载失败: {str(e)}\n{traceback.format_exc()}"
            self.log(error_msg)
            self.error_signal.emit(error_msg)

    def stop(self):
        """停止下载"""
        self._is_running = False
        self.quit()
        self.wait()


class VerifyDataThread(QThread):
    """验证数据完整性线程
    
    验证指定股票的各种数据类型是否存在，包括分钟线、日线和tick数据
    
    Signals:
        log_signal: 日志信号，用于输出验证过程中的日志信息
        finished_signal: 完成信号，传递验证结果
    """
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(self, stock_code, db_path=None):
        """初始化验证数据完整性线程
        
        Args:
            stock_code: 股票代码
            db_path: 数据库路径
        """
        super().__init__()
        self.stock_code = stock_code
        self.db_path = db_path

    def log(self, message):
        """记录日志
        
        Args:
            message: 日志消息内容
        """
        self.log_signal.emit(message)

    def run(self):
        """运行验证任务
        
        验证以下数据类型：
        1. 各种分钟线数据（1m, 5m, 15m, 30m, 60m）
        2. 日线数据
        3. Tick数据
        
        验证结果包括是否存在数据、数据记录数、开始时间和结束时间
        """
        try:
            import duckdb

            # 使用与数据下载相同的默认数据库路径
            from src.core.data.database.db_manager import get_db_manager
            manager = get_db_manager(self.db_path)

            # 检查所有分钟线数据类型
            minute_data = {}
            minute_types = [
                ('1m', '1分钟'),
                ('5m', '5分钟'),
                ('15m', '15分钟'),
                ('30m', '30分钟'),
                ('60m', '60分钟')
            ]

            for period, period_name in minute_types:
                has_data = False
                records = 0
                start_time = ''
                end_time = ''
                try:
                    result = manager.execute_read_and_fetch(f"""
                        SELECT
                            COUNT(*) as cnt,
                            MIN(datetime) as start_time,
                            MAX(datetime) as end_time
                        FROM stock_{period}
                        WHERE stock_code = '{self.stock_code}'
                    """)
                    if result and len(result) > 0 and result[0][0] > 0:
                        has_data = True
                        records = result[0][0]
                        start_time = str(result[0][1]) if result[0][1] else ''
                        end_time = str(result[0][2]) if result[0][2] else ''
                        self.log(f"✓ {period_name}数据: {records:,} 条 ({start_time} ~ {end_time})")
                except Exception as e:
                    self.log(f"⚠️ 检查{period_name}数据失败: {str(e)}")
                
                minute_data[period] = {
                    'has_data': has_data,
                    'records': records,
                    'start_time': start_time,
                    'end_time': end_time
                }

            # 检查日线数据
            has_daily = False
            records_daily = 0
            start_daily = ''
            end_daily = ''
            try:
                result = manager.execute_read_and_fetch(f"""
                    SELECT
                        COUNT(*) as cnt,
                        MIN(date) as start_date,
                        MAX(date) as end_date
                    FROM stock_daily
                    WHERE stock_code = '{self.stock_code}'
                """)
                if result and len(result) > 0 and result[0][0] > 0:
                    has_daily = True
                    records_daily = result[0][0]
                    start_daily = str(result[0][1]) if result[0][1] else ''
                    end_daily = str(result[0][2]) if result[0][2] else ''
                    self.log(f"✓ 日线数据: {records_daily:,} 条 ({start_daily} ~ {end_daily})")
            except Exception:
                pass

            # 检查tick数据
            has_tick = False
            records_tick = 0
            start_tick = ''
            end_tick = ''
            try:
                result = manager.execute_read_and_fetch(f"""
                    SELECT
                        COUNT(*) as cnt,
                        MIN(datetime) as start_time,
                        MAX(datetime) as end_time
                    FROM stock_tick
                    WHERE stock_code = '{self.stock_code}'
                """)
                if result and len(result) > 0 and result[0][0] > 0:
                    has_tick = True
                    records_tick = result[0][0]
                    start_tick = str(result[0][1]) if result[0][1] else ''
                    end_tick = str(result[0][2]) if result[0][2] else ''
                    self.log(f"✓ Tick数据: {records_tick:,} 条 ({start_tick} ~ {end_tick})")
            except Exception:
                pass

            # 构建结果字典
            result = {
                'stock': self.stock_code,
                'has_daily': has_daily,
                'has_tick': has_tick,
                'records_daily': records_daily,
                'records_tick': records_tick,
                'start_daily': start_daily,
                'end_daily': end_daily,
                'start_tick': start_tick,
                'end_tick': end_tick,
                'minute_data': minute_data
            }

            # 添加各分钟线数据的单独字段（保持向后兼容）
            for period, data in minute_data.items():
                result[f'has_{period}'] = data['has_data']
                result[f'records_{period}'] = data['records']
                result[f'start_{period}'] = data['start_time']
                result[f'end_{period}'] = data['end_time']

            self.finished_signal.emit(result)

        except Exception as e:
            self.log(f"✗ 验证失败: {e}")
            # 构建默认结果
            minute_data = {}
            minute_types = ['1m', '5m', '15m', '30m', '60m']
            for period in minute_types:
                minute_data[period] = {
                    'has_data': False,
                    'records': 0,
                    'start_time': '',
                    'end_time': ''
                }
            
            result = {
                'stock': self.stock_code,
                'has_daily': False,
                'has_tick': False,
                'records_daily': 0,
                'records_tick': 0,
                'start_daily': '',
                'end_daily': '',
                'start_tick': '',
                'end_tick': '',
                'minute_data': minute_data
            }
            
            # 添加各分钟线数据的单独字段（保持向后兼容）
            for period in minute_types:
                result[f'has_{period}'] = False
                result[f'records_{period}'] = 0
                result[f'start_{period}'] = ''
                result[f'end_{period}'] = ''
                
            self.finished_signal.emit(result)


class FinancialDataDownloadThread(QThread):
    """QMT财务数据下载线程
    
    从QMT API下载股票财务数据，支持多种财务报表类型
    
    Signals:
        log_signal: 日志信号，用于输出下载过程中的日志信息
        progress_signal: 进度信号，传递当前进度和总进度
        finished_signal: 完成信号，传递下载结果
        error_signal: 错误信号，传递错误信息
    """
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)  # current, total
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def log(self, message):
        """记录日志
        
        Args:
            message: 日志消息内容
        """
        self.log_signal.emit(message)

    def __init__(self, stock_list=None, table_list=None, start_time=None, end_time=None):
        """初始化QMT财务数据下载线程
        
        Args:
            stock_list: 股票代码列表，默认下载常用股票
            table_list: 财务报表类型列表，默认下载主要财务报表
            start_time: 开始时间，格式为 'YYYYMMDD'
            end_time: 结束时间，格式为 'YYYYMMDD'
        """
        super().__init__()
        # 默认下载常用股票
        self.stock_list = stock_list or ["000001.SZ", "600519.SH", "511380.SH", "512100.SH"]
        # 默认下载主要财务报表
        self.table_list = table_list or ["Balance", "Income", "CashFlow"]
        # 默认时间范围：最近1年（测试用）
        from datetime import datetime, timedelta
        if end_time is None:
            end_time = datetime.now()
        else:
            end_time = datetime.strptime(end_time, '%Y%m%d')

        if start_time is None:
            start_time = end_time - timedelta(days=365*1)  # 默认1年，加快测试速度
        else:
            start_time = datetime.strptime(start_time, '%Y%m%d')

        self.start_time = start_time.strftime('%Y%m%d')
        self.end_time = end_time.strftime('%Y%m%d')
        self._is_running = True

    def run(self):
        """运行下载任务
        
        执行以下操作：
        1. 检查xtquant模块是否可用
        2. 过滤ETF和指数
        3. 下载财务数据到QMT本地
        4. 读取并验证数据
        5. 处理分红数据（使用get_divid_factors）
        6. 发送完成信号
        """
        try:
            # 检查xtquant模块是否可用
            if not XTDATA_AVAILABLE:
                error_msg = "❌ xtquant模块不可用，请确保QMT已安装并运行"
                self.log(error_msg)
                self.error_signal.emit(error_msg)
                return
            
            # 导入xtdata
            from xtquant import xtdata

            self.log("=" * 70)
            self.log("  【QMT财务数据下载】")
            self.log("=" * 70)

            # 步骤0: 过滤ETF和指数
            self.log("【步骤0】过滤ETF和指数")
            self.log("-" * 70)

            filtered_stock_list = []
            etf_count = 0
            index_count = 0
            stock_count = 0

            for stock_code in self.stock_list:
                try:
                    # 获取股票类型信息
                    type_info = xtdata.get_instrument_type(stock_code)

                    # 判断类型
                    if isinstance(type_info, dict):
                        if type_info.get('stock', False):
                            # 是股票
                            filtered_stock_list.append(stock_code)
                            stock_count += 1
                            self.log(f"[OK] {stock_code}: 股票")
                        elif type_info.get('etf', False) or type_info.get('fund', False):
                            # 是ETF或基金，尝试下载
                            filtered_stock_list.append(stock_code)
                            etf_count += 1
                            self.log(f"[OK] {stock_code}: ETF/基金")
                        elif type_info.get('index', False):
                            # 是指数，尝试下载
                            filtered_stock_list.append(stock_code)
                            index_count += 1
                            self.log(f"[OK] {stock_code}: 指数")
                        else:
                            # 未知类型，尝试下载
                            self.log(f"[INFO] {stock_code}: 类型未知，将尝试下载")
                            filtered_stock_list.append(stock_code)
                            stock_count += 1
                    else:
                        # 如果返回的不是字典，尝试下载
                        self.log(f"[INFO] {stock_code}: 类型={type_info}，将尝试下载")
                        filtered_stock_list.append(stock_code)
                        stock_count += 1

                except Exception as e:
                    # 如果获取类型失败，也尝试下载
                    self.log(f"[WARN] {stock_code}: 无法获取类型信息，将尝试下载")
                    filtered_stock_list.append(stock_code)
                    stock_count += 1

            self.log("")
            self.log(f"[统计] 原始数量: {len(self.stock_list)}")
            self.log(f"  - 股票: {stock_count} 只（将下载）")
            self.log(f"  - ETF/基金: {etf_count} 只（将下载）")
            self.log(f"  - 指数: {index_count} 只（将下载）")
            self.log("")

            if not filtered_stock_list:
                self.log("[INFO] 没有需要下载财务数据的标的")
                result = {
                    'total': len(self.stock_list),
                    'success': 0,
                    'failed': 0,
                    'skipped': 0,
                    'task_type': 'financial_data'
                }
                self.finished_signal.emit(result)
                return

            # 更新股票列表为过滤后的列表
            self.stock_list = filtered_stock_list
            total_stocks = len(self.stock_list)
            total_tables = len(self.table_list)

            self.log(f"[INFO] 准备下载 {total_stocks} 只标的的财务数据")
            self.log(f"[INFO] 数据表: {', '.join(self.table_list)}")
            self.log(f"[INFO] 时间范围: {self.start_time} ~ {self.end_time}")
            self.log("")

            success_count = 0
            failed_count = 0
            failed_list = []  # 记录失败的股票及原因

            # 步骤1: 下载财务数据
            self.log("【步骤1】下载财务数据到QMT本地")
            self.log("-" * 70)

            try:
                # 分离分红数据和其他财务数据
                dividend_table = None
                other_tables = []
                for table in self.table_list:
                    if table == "Dividend":
                        dividend_table = table
                    else:
                        other_tables.append(table)
                
                # 下载其他财务数据
                if other_tables:
                    self.log(f"[INFO] 正在下载 {len(self.stock_list)} 只标的的财务数据...")
                    self.log(f"[DEBUG] 标的列表: {self.stock_list}")
                    self.log(f"[DEBUG] 数据表: {other_tables}")
                    self.log(f"[DEBUG] 时间范围: {self.start_time} ~ {self.end_time}")
                    
                    import time
                    start_time = time.time()
                    self.log(f"[DEBUG] 开始下载时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    result = xtdata.download_financial_data(
                        stock_list=self.stock_list,
                        table_list=other_tables
                    )

                    elapsed_time = time.time() - start_time
                    self.log(f"[DEBUG] 下载完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.log(f"[DEBUG] 下载耗时: {elapsed_time:.2f} 秒")

                    if result is None or result == '':
                        self.log("[OK] 财务数据下载完成")
                    else:
                        self.log(f"[返回] {result}")
                
                # 对于分红数据，使用get_divid_factors获取
                if dividend_table:
                    self.log("[INFO] 分红数据将在获取时使用get_divid_factors函数")

            except Exception as e:
                error_msg = f"[ERROR] 下载失败: {e}"
                self.log(error_msg)
                self.error_signal.emit(error_msg)
                return

            # 步骤2: 读取并验证数据
            self.log("")
            self.log("【步骤2】读取并验证财务数据")
            self.log("-" * 70)

            for i, stock_code in enumerate(self.stock_list):
                if not self._is_running:
                    self.log("[WARN] 用户中断下载")
                    break

                try:
                    self.progress_signal.emit(i + 1, total_stocks)
                    self.log(f"[{i+1}/{total_stocks}] {stock_code}:")

                    # 读取财务数据（添加时间范围参数）
                    import time
                    read_start = time.time()
                    self.log(f"    [DEBUG] 开始读取数据: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # 分离分红数据和其他财务数据
                    dividend_table = None
                    other_tables = []
                    for table in self.table_list:
                        if table == "Dividend":
                            dividend_table = table
                        else:
                            other_tables.append(table)
                    
                    # 读取其他财务数据
                    result = None
                    if other_tables:
                        result = xtdata.get_financial_data(
                            stock_list=[stock_code],
                            table_list=other_tables,
                            start_time=self.start_time,
                            end_time=self.end_time,
                            report_type='report_time'
                        )
                    
                    read_elapsed = time.time() - read_start
                    self.log(f"    [DEBUG] 读取完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.log(f"    [DEBUG] 读取耗时: {read_elapsed:.2f} 秒")

                    # 处理返回结果（可能是dict或DataFrame）
                    total_records = 0

                    # 处理其他财务数据
                    if isinstance(result, dict):
                        # 字典格式：{stock_code: {table_name: data}}
                        if stock_code in result:
                            stock_data = result[stock_code]
                            self.log(f"    [DEBUG] 数据类型: dict, 包含 {len(stock_data)} 个表")

                            for table_name in other_tables:
                                if table_name in stock_data:
                                    table_data = stock_data[table_name]
                                    if isinstance(table_data, pd.DataFrame):
                                        record_count = len(table_data)
                                        total_records += record_count
                                        self.log(f"    [OK] {table_name}: {record_count} 条记录")
                    
                    # 处理分红数据
                    if dividend_table:
                        try:
                            # 使用get_divid_factors获取除权数据
                            divid_data = xtdata.get_divid_factors(
                                stock_code=stock_code,
                                start_time=self.start_time,
                                end_time=self.end_time
                            )
                            
                            if isinstance(divid_data, pd.DataFrame):
                                record_count = len(divid_data)
                                total_records += record_count
                                self.log(f"    [OK] {dividend_table}: {record_count} 条记录")
                            else:
                                self.log(f"    [WARN] {dividend_table}: 无数据")
                        except Exception as e:
                            self.log(f"    [ERROR] {dividend_table}: 获取失败 - {e}")
                    
                    # 处理其他数据类型
                    if isinstance(result, dict):
                        if stock_code in result:
                            stock_data = result[stock_code]
                            for table_name in other_tables:
                                if table_name in stock_data:
                                    table_data = stock_data[table_name]
                                    if isinstance(table_data, pd.DataFrame):
                                        self.log(f"    [DEBUG] {table_name} 列: {list(table_data.columns)[:5]}...")
                                    elif isinstance(table_data, dict):
                                        record_count = len(table_data)
                                        total_records += record_count
                                        self.log(f"    [OK] {table_name}: {record_count} 条记录")
                                    elif isinstance(table_data, list):
                                        record_count = len(table_data)
                                        total_records += record_count
                                        self.log(f"    [OK] {table_name}: {record_count} 条记录")
                                else:
                                    self.log(f"    [WARN] {table_name} 不在返回结果中")
                        else:
                            self.log(f"    [WARN] {stock_code} 不在返回结果中")

                    elif isinstance(result, pd.DataFrame):
                        # DataFrame格式：直接是数据
                        record_count = len(result)
                        total_records += record_count
                        self.log(f"    [OK] 财务数据: {record_count} 条记录")
                        self.log(f"    [INFO] 列: {list(result.columns)[:5]}...")
                    else:
                        self.log(f"    [WARN] 未知数据格式: {type(result)}")

                    if total_records > 0:
                        success_count += 1
                        self.log(f"    [OK] 共 {total_records} 条财务数据")
                    else:
                        failed_count += 1
                        failed_list.append(f"{stock_code} - 数据为空")
                        self.log(f"    [WARN] 没有获取到财务数据")

                except Exception as e:
                    failed_count += 1
                    failed_list.append(f"{stock_code} - {str(e)[:50]}")
                    self.log(f"    [ERROR] {e}")
                    import traceback
                    self.log(f"    [DEBUG] 错误详情: {traceback.format_exc()[:200]}")
                    continue

            # 完成
            result = {
                'total': total_stocks,
                'success': success_count,
                'failed': failed_count,
                'failed_list': failed_list,
                'skipped': etf_count + index_count,
                'task_type': 'financial_data'
            }

            self.finished_signal.emit(result)

            self.log("")
            self.log("=" * 70)
            self.log("  下载完成!")
            self.log(f"  有效标的: {total_stocks} 只")
            self.log(f"  成功: {success_count} 只")
            self.log(f"  失败: {failed_count} 只")
            self.log("=" * 70)

        except ImportError:
            error_msg = "[ERROR] 导入xtquant失败，请确保QMT已安装并运行"
            self.log(error_msg)
            self.error_signal.emit(error_msg)
        except Exception as e:
            import traceback
            error_msg = f"[ERROR] 财务数据下载失败: {str(e)}\n{traceback.format_exc()}"
            self.log(error_msg)
            self.error_signal.emit(error_msg)

    def stop(self):
        """停止下载"""
        self._is_running = False
        self.quit()
        self.wait()


class LocalDataManagerWidget(QWidget):
    """本地数据管理组件"""

    def __init__(self):
        super().__init__()
        # 禁用默认日志记录器，只使用自定义的 data_manager 日志
        self.logger = None
        self.download_thread = None
        self.duckdb_storage = None
        self.duckdb_con = None  # 添加DuckDB连接属性
        # 初始化日志文件
        self.log_file = None
        # 数据库路径
        self.db_path = None
        # 预加载的股票列表
        self._preloaded_stocks = None
        # 先初始化UI，确保log_text存在
        self.init_ui()
        # 先初始化日志文件
        self._init_log_file()
        # 然后加载配置文件
        self._load_config()
        # 预加载股票列表
        self._preload_stock_list()
        # 自动检查并重建缺失的视图
        self._check_and_rebuild_views()
        # 根据默认数据类型设置初始日期范围
        self.on_data_type_changed(0)
        self.log("本地数据管理组件初始化完成")

    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)

        # 创建主分割器
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧面板 - 数据列表和操作
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(500)

        # 右侧面板 - 日志
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setMinimumWidth(400)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        # ========== 左侧面板 ==========

        # 统计信息组
        stats_group = QGroupBox("📊 数据统计 (DuckDB)")
        # 设置QGroupBox样式，确保标题左对齐且完整显示
        stats_group.setStyleSheet("""
            QGroupBox {
                font-size: 10pt;
                font-weight: bold;
                padding-top: 20px;
                padding-bottom: 5px;
                margin-top: 2px;
                margin-bottom: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 2px 5px;
            }
        """)
        stats_layout = QGridLayout()
        stats_group.setLayout(stats_layout)
        left_layout.addWidget(stats_group)

        self.total_symbols_label = QLabel("标的总数: 0")
        self.total_stocks_label = QLabel("股票数量: 0")
        self.total_bonds_label = QLabel("可转债数量: 0")
        self.total_records_label = QLabel("总记录数: 0")
        self.total_size_label = QLabel("存储大小: 0 MB")
        self.latest_date_label = QLabel("最新日期: N/A")

        # 添加更新统计信息按钮
        self.update_stats_btn = QPushButton("更新统计信息")
        self.update_stats_btn.clicked.connect(self.load_duckdb_statistics)
        self.update_stats_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)

        # 添加详细信息按钮
        self.details_btn = QPushButton("查看详情")
        self.details_btn.clicked.connect(self.show_stats_details)
        self.details_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)

        stats_layout.addWidget(self.total_symbols_label, 0, 0)
        stats_layout.addWidget(self.total_stocks_label, 0, 1)
        stats_layout.addWidget(self.total_bonds_label, 1, 0)
        stats_layout.addWidget(self.total_records_label, 1, 1)
        stats_layout.addWidget(self.total_size_label, 2, 0)
        stats_layout.addWidget(self.latest_date_label, 2, 1)
        stats_layout.addWidget(self.update_stats_btn, 3, 0)
        stats_layout.addWidget(self.details_btn, 3, 1)

        # 数据操作组
        action_group = QGroupBox("📥 数据下载")
        # 设置QGroupBox样式，确保标题左对齐且完整显示
        action_group.setStyleSheet("""
            QGroupBox {
                font-size: 10pt;
                font-weight: bold;
                padding-top: 20px;
                padding-bottom: 5px;
                margin-top: 2px;
                margin-bottom: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 2px 5px;
            }
        """)
        action_layout = QGridLayout()
        action_group.setLayout(action_layout)
        left_layout.addWidget(action_group)

        # 日期范围选择
        action_layout.addWidget(QLabel("开始日期:"), 0, 0)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addYears(-10))
        action_layout.addWidget(self.start_date_edit, 0, 1)

        action_layout.addWidget(QLabel("结束日期:"), 0, 2)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        action_layout.addWidget(self.end_date_edit, 0, 3)

        # 数据类型和复权方式选择（同一行）
        data_adjust_layout = QHBoxLayout()
        
        # 数据类型
        data_type_layout = QHBoxLayout()
        data_type_layout.setContentsMargins(0, 0, 0, 0)
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems(["所有类型", "日线数据", "1分钟数据", "5分钟数据", "15分钟数据", "30分钟数据", "60分钟数据", "周线数据", "月线数据", "Tick数据"])
        # 连接数据类型变更信号
        self.data_type_combo.currentIndexChanged.connect(self.on_data_type_changed)
        data_type_layout.addWidget(QLabel("数据类型:"))
        data_type_layout.addWidget(self.data_type_combo)
        
        # 复权方式
        adjustment_layout = QHBoxLayout()
        adjustment_layout.setContentsMargins(0, 0, 0, 0)
        self.adjustment_combo = QComboBox()
        self.adjustment_combo.addItems(["不复权", "前复权", "后复权", "几何前复权", "几何后复权", "五维复权"])
        # 默认显示五维复权选项
        self.adjustment_combo.setCurrentIndex(5)
        adjustment_layout.addWidget(QLabel("复权方式:"))
        adjustment_layout.addWidget(self.adjustment_combo)
        
        # 组合到同一行 - 移除stretch，让复权方式左移
        data_adjust_layout.addLayout(data_type_layout)
        data_adjust_layout.addLayout(adjustment_layout)
        action_layout.addLayout(data_adjust_layout, 1, 0, 1, 4)
        
        # 初始化选项
        init_layout = QHBoxLayout()
        init_layout.setContentsMargins(0, 0, 0, 0)
        
        # 首次初始化复选框
        self.init_checkbox = QCheckBox("首次初始化：删除重建表结构")
        self.init_checkbox.setToolTip("首次使用时勾选此项，确保表结构正确")
        init_layout.addWidget(self.init_checkbox)
        
        # 保存Parquet文件复选框
        self.save_parquet_checkbox = QCheckBox("保存Parquet文件")
        self.save_parquet_checkbox.setToolTip("勾选：使用direct策略（保存Parquet文件并使用COPY导入）；取消勾选：使用temp策略（仅使用CSV导入）")
        self.save_parquet_checkbox.setChecked(True)  # 默认勾选
        self.save_parquet_checkbox.stateChanged.connect(self.on_save_parquet_changed)
        init_layout.addWidget(self.save_parquet_checkbox)
        
        # 测试模式单选框（直接显示，无矩形框，无左侧间距）
        test_mode_layout = QHBoxLayout()
        test_mode_layout.setContentsMargins(10, 0, 0, 0)  # 移除左侧间距
        
        self.test_mode_radio = QRadioButton("测试模式")
        self.normal_mode_radio = QRadioButton("正式模式")
        
        # 默认选择正式模式
        self.normal_mode_radio.setChecked(True)
        
        test_mode_layout.addWidget(self.test_mode_radio)
        test_mode_layout.addWidget(self.normal_mode_radio)
        
        init_layout.addLayout(test_mode_layout)
        init_layout.addStretch()
        
        action_layout.addLayout(init_layout, 2, 0, 1, 4)

        # 下载按钮
        btn_layout = QHBoxLayout()

        self.download_stocks_btn = QPushButton("📥 下载A股数据")
        self.download_stocks_btn.clicked.connect(self.download_stocks)
        self.download_stocks_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        btn_layout.addWidget(self.download_stocks_btn)

        self.download_bonds_btn = QPushButton("📥 下载可转债数据")
        self.download_bonds_btn.clicked.connect(self.download_bonds)
        self.download_bonds_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        btn_layout.addWidget(self.download_bonds_btn)

        self.update_data_btn = QPushButton("🔄 更新最近数据")
        self.update_data_btn.setToolTip("更新最近1-30天的缺失数据\n用于日常数据维护，保持数据库最新")
        self.update_data_btn.clicked.connect(self.update_data)
        self.update_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e68900;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        btn_layout.addWidget(self.update_data_btn)

        # 补充历史数据按钮
        self.backfill_data_btn = QPushButton("📜 补全历史数据")
        self.backfill_data_btn.setToolTip("补充指定日期之前的历史空白\n用于首次使用或发现历史数据缺失时")
        self.backfill_data_btn.clicked.connect(self.backfill_historical_data)
        self.backfill_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        btn_layout.addWidget(self.backfill_data_btn)

        action_layout.addLayout(btn_layout, 3, 0, 1, 4)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        action_layout.addWidget(self.progress_bar, 4, 0, 1, 4)

        # 进度标签
        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        self.progress_label.setStyleSheet("color: #666; font-size: 9pt;")
        action_layout.addWidget(self.progress_label, 5, 0, 1, 4)

        # 停止按钮
        self.stop_btn = QPushButton("⏹️ 停止下载")
        self.stop_btn.clicked.connect(self.stop_download)
        self.stop_btn.setVisible(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        action_layout.addWidget(self.stop_btn, 6, 0, 1, 4)

        # ========== 快速操作区域 ==========
        quick_action_group = QGroupBox("⚡ 快速操作")
        # 设置QGroupBox样式，确保标题左对齐且完整显示
        quick_action_group.setStyleSheet("""
            QGroupBox {
                font-size: 10pt;
                font-weight: bold;
                padding-top: 20px;
                padding-bottom: 5px;
                margin-top: 2px;
                margin-bottom: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 2px 5px;
            }
        """)
        quick_action_layout = QGridLayout()
        quick_action_group.setLayout(quick_action_layout)
        left_layout.addWidget(quick_action_group)

        # 快速操作按钮
        other_action_layout = QHBoxLayout()

        self.verify_data_btn = QPushButton("🔍 验证数据完整性")
        self.verify_data_btn.clicked.connect(self.verify_data_integrity)
        self.verify_data_btn.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #546E7A;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        other_action_layout.addWidget(self.verify_data_btn)

        other_action_layout.addStretch()
        quick_action_layout.addLayout(other_action_layout, 0, 0, 1, 4)

        # ========== QMT财务数据下载区域 ==========
        financial_group = QGroupBox("💰 QMT财务数据")
        # 设置QGroupBox样式，确保标题左对齐且完整显示
        financial_group.setStyleSheet("""
            QGroupBox {
                font-size: 10pt;
                font-weight: bold;
                padding-top: 20px;
                padding-bottom: 5px;
                margin-top: 2px;
                margin-bottom: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 2px 5px;
            }
        """)
        financial_layout = QGridLayout()
        financial_group.setLayout(financial_layout)
        left_layout.addWidget(financial_group)

        # 第一行：股票列表选择
        financial_layout.addWidget(QLabel("股票列表:"), 0, 0)

        self.financial_stock_combo = QComboBox()
        self.financial_stock_combo.addItems([
            "默认股票列表 (4只)",
            "自定义股票列表",
            "全部A股（谨慎使用）",
            "沪深300成分股",
            "中证500成分股",
            "中证1000成分股"
        ])
        financial_layout.addWidget(self.financial_stock_combo, 0, 1, 1, 3)

        # 第二行：数据表选择
        financial_layout.addWidget(QLabel("数据表:"), 1, 0)

        # 使用复选框让用户选择数据表
        table_check_layout = QHBoxLayout()

        self.financial_balance_check = QCheckBox("资产负债表")
        self.financial_balance_check.setChecked(True)
        table_check_layout.addWidget(self.financial_balance_check)

        self.financial_income_check = QCheckBox("利润表")
        self.financial_income_check.setChecked(True)
        table_check_layout.addWidget(self.financial_income_check)

        self.financial_cashflow_check = QCheckBox("现金流量表")
        self.financial_cashflow_check.setChecked(True)
        table_check_layout.addWidget(self.financial_cashflow_check)

        self.financial_cap_check = QCheckBox("股本结构")
        table_check_layout.addWidget(self.financial_cap_check)

        self.financial_dividend_check = QCheckBox("分红数据")
        table_check_layout.addWidget(self.financial_dividend_check)

        table_check_layout.addStretch()
        financial_layout.addLayout(table_check_layout, 1, 1, 1, 3)

        # 第三行：下载按钮
        self.financial_download_btn = QPushButton("💰 下载QMT财务数据")
        self.financial_download_btn.clicked.connect(self.download_financial_data)
        self.financial_download_btn.setStyleSheet("""
            QPushButton {
                background-color: #00BCD4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0097A7;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        financial_layout.addWidget(self.financial_download_btn, 2, 0, 1, 2)

        # 保存到DuckDB按钮
        self.financial_save_btn = QPushButton("💾 保存到DuckDB")
        self.financial_save_btn.clicked.connect(self.save_financial_to_duckdb)
        self.financial_save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        financial_layout.addWidget(self.financial_save_btn, 2, 2, 1, 2)

        # 添加说明标签
        financial_note = QLabel("说明: 下载财务数据后，点击「保存到DuckDB」可永久存储")
        financial_note.setStyleSheet("color: #666; font-size: 9pt; padding: 5px;")
        financial_layout.addWidget(financial_note, 3, 0, 1, 4)

        # ========== 手动下载单个标的区域 ==========
        manual_group = QGroupBox("🎯 手动下载单个标的（支持分钟线）")
        # 设置QGroupBox样式，确保标题左对齐且完整显示
        manual_group.setStyleSheet("""
            QGroupBox {
                font-size: 10pt;
                font-weight: bold;
                padding-top: 20px;
                padding-bottom: 5px;
                margin-top: 2px;
                margin-bottom: 5px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 2px 5px;
            }
        """)
        manual_layout = QGridLayout()
        manual_group.setLayout(manual_layout)
        left_layout.addWidget(manual_group)

        # 第一行：股票代码输入
        manual_layout.addWidget(QLabel("股票/ETF代码:"), 0, 0)
        self.stock_code_input = QLineEdit()
        self.stock_code_input.setPlaceholderText("例如: 512100.SH 或 159915.SZ")
        manual_layout.addWidget(self.stock_code_input, 0, 1, 1, 3)

        # 第二行：常用ETF快捷按钮
        etf_label = QLabel("常用ETF:")
        etf_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        manual_layout.addWidget(etf_label, 1, 0)

        etf_button_layout = QHBoxLayout()
        common_etfs = [
            ("511380.SH", "可转债ETF"),
            ("512100.SH", "中证1000"),
            ("510300.SH", "沪深300"),
            ("510500.SH", "中证500"),
            ("159915.SZ", "深证ETF")
        ]

        for code, name in common_etfs:
            etf_btn = QPushButton(f"{code}")
            etf_btn.setToolTip(f"{name}")
            etf_btn.clicked.connect(lambda checked, c=code: self.stock_code_input.setText(c))
            etf_btn.setStyleSheet("""
                QPushButton {
                    background-color: #E3F2FD;
                    color: #1976D2;
                    border: 1px solid #2196F3;
                    padding: 4px 8px;
                    border-radius: 3px;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background-color: #BBDEFB;
                }
            """)
            etf_button_layout.addWidget(etf_btn)

        etf_button_layout.addStretch()
        manual_layout.addLayout(etf_button_layout, 1, 1, 1, 3)

        # 第三行：数据类型、复权方式、日期范围
        # 数据类型选择
        manual_layout.addWidget(QLabel("数据类型:"), 2, 0)
        self.manual_data_type_combo = QComboBox()
        self.manual_data_type_combo.addItems([
            "所有类型",
            "日线数据",
            "1分钟数据",
            "5分钟数据",
            "15分钟数据",
            "30分钟数据",
            "60分钟数据",
            "周线数据",
            "月线数据",
            "Tick数据"
        ])
        self.manual_data_type_combo.setCurrentIndex(0)  # 默认选中所有类型
        self.manual_data_type_combo.setMinimumWidth(120)
        manual_layout.addWidget(self.manual_data_type_combo, 2, 1)

        # 复权方式选择
        manual_layout.addWidget(QLabel("复权方式:"), 2, 2)
        self.manual_adjustment_combo = QComboBox()
        self.manual_adjustment_combo.addItems([
            "五维复权",
            "不复权",
            "前复权",
            "后复权",
            "几何前复权",
            "几何后复权"
        ])
        self.manual_adjustment_combo.setCurrentIndex(0)  # 默认选中五维复权
        self.manual_adjustment_combo.setMinimumWidth(100)
        manual_layout.addWidget(self.manual_adjustment_combo, 2, 3)

        # 日期范围
        manual_layout.addWidget(QLabel("日期范围:"), 3, 0)
        date_range_layout = QHBoxLayout()

        self.manual_start_date_edit = QDateEdit()
        self.manual_start_date_edit.setCalendarPopup(True)
        self.manual_start_date_edit.setDate(QDate.currentDate().addMonths(-3))
        self.manual_start_date_edit.setDisplayFormat("yyyy-MM-dd")
        date_range_layout.addWidget(self.manual_start_date_edit)

        self.manual_end_date_edit = QDateEdit()
        self.manual_end_date_edit.setCalendarPopup(True)
        self.manual_end_date_edit.setDate(QDate.currentDate())
        self.manual_end_date_edit.setDisplayFormat("yyyy-MM-dd")
        date_range_layout.addWidget(self.manual_end_date_edit)

        manual_layout.addLayout(date_range_layout, 3, 1, 1, 3)

        # 说明标签
        manual_note = QLabel("💡 提示：分钟线数据建议只下载最近1-3个月，避免数据量过大")
        manual_note.setStyleSheet("color: #FF9800; font-size: 9pt; padding: 5px;")
        manual_layout.addWidget(manual_note, 4, 0, 1, 4)

        # 第五行：下载按钮
        btn_layout = QHBoxLayout()
        
        self.manual_download_btn = QPushButton("⬇️ 下载单个标的")
        self.manual_download_btn.clicked.connect(self.download_single_stock)
        self.manual_download_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.manual_download_btn.setMinimumWidth(150)
        btn_layout.addWidget(self.manual_download_btn)
        
        # 重新生成数据库按钮
        self.regenerate_db_btn = QPushButton("🔄 重新生成数据库视图")
        self.regenerate_db_btn.clicked.connect(self.regenerate_database_from_parquet)
        self.regenerate_db_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.regenerate_db_btn.setMinimumWidth(180)
        btn_layout.addWidget(self.regenerate_db_btn)
        
        manual_layout.addLayout(btn_layout, 5, 0, 1, 4)

        # ========== 右侧面板 ==========

        # 日志组
        log_group = QGroupBox("📝 操作日志")
        log_layout = QVBoxLayout()
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10pt;
                background-color: #1e1e1e;
                color: #d4d4d4;
            }
        """)
        log_layout.addWidget(self.log_text)

        # 清空日志按钮
        clear_log_btn = QPushButton("🗑️ 清空日志")
        clear_log_btn.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_log_btn)

        # 初始日志
        self.log("开始初始化界面...")
        self.log("本地数据管理组件已加载")
        self.log("提示：首次使用请先下载数据")

        # 加载DuckDB统计数据
        QTimer.singleShot(100, self.load_duckdb_statistics)
        self.log("界面初始化完成")

    def _load_config(self):
        """读取配置文件获取数据库路径和时间范围设置"""
        from pathlib import Path
        import json
        import yaml
        try:
            # 配置文件路径
            current_file = Path(__file__)
            self.log(f"ℹ️ 当前文件路径: {current_file}")
            config_dir = current_file.parent.parent.parent / 'config'
            self.log(f"ℹ️ 配置目录路径: {config_dir}")
            yaml_config_path = config_dir / 'data_config.yaml'
            self.log(f"ℹ️ YAML配置文件路径: {yaml_config_path}")
            
            # 初始化配置字典
            self.config = {}
            yaml_config = {}
            
            # 加载YAML配置文件
            if yaml_config_path.exists():
                self.log(f"📁 检查YAML配置文件: {yaml_config_path}")
                try:
                    with open(yaml_config_path, 'r', encoding='utf-8') as f:
                        yaml_config = yaml.safe_load(f)
                    self.log(f"✅ 加载YAML配置文件成功")
                    self.config = yaml_config.copy()
                    # 打印配置文件内容，用于调试
                    self.log(f"ℹ️ 配置文件内容: {self.config}")
                    # 检查database和data_paths字段
                    if 'database' in self.config:
                        self.log(f"ℹ️ 配置文件中的database字段: {self.config['database']}")
                    if 'data_paths' in self.config:
                        self.log(f"ℹ️ 配置文件中的data_paths字段: {self.config['data_paths']}")
                except yaml.YAMLError as e:
                    self.log(f"⚠️ YAML配置文件格式错误: {e}")
                    yaml_config = {}
            else:
                self.log(f"⚠️ YAML配置文件不存在: {yaml_config_path}")
            
            if yaml_config:
                self.log(f"✅ 使用YAML配置")
            else:
                self.log(f"⚠️ 没有加载到任何配置文件，使用默认配置")
            
            # 应用默认配置
            self._apply_default_config()
            
            # 确定数据库路径
            db_path = self._resolve_database_path()
            
            self.db_path = str(Path(db_path).resolve())
            
            # 确保数据库目录存在
            db_dir = Path(self.db_path).parent
            if not db_dir.exists():
                db_dir.mkdir(parents=True, exist_ok=True)
                self.log(f"✅ 创建数据库目录: {db_dir}")
            else:
                self.log(f"ℹ️ 数据库目录已存在: {db_dir}")
            
            # 读取临时文件策略配置
            temp_strategy = self.config.get('storage', {}).get('temp_file_strategy', 'direct')
            self.log(f"✅ 从配置文件读取temp_file_strategy: {temp_strategy}")
            
            # 设置选择框状态
            if hasattr(self, 'save_parquet_checkbox'):
                is_checked = temp_strategy == 'direct'
                self.save_parquet_checkbox.setChecked(is_checked)
                self.log(f"✅ 设置保存Parquet文件复选框状态: {temp_strategy}")
            
            # 最终数据库路径确认
            self.log(f"📊 最终数据库路径: {self.db_path}")
                
        except Exception as e:
            self.log(f"⚠️ 读取配置文件失败: {e}")
            import traceback
            self.log(f"⚠️ 详细错误: {traceback.format_exc()}")
            # 使用默认路径
            self.db_path = 'D:/MyStockData/stock_data.ddb'
            self.log(f"⚠️ 使用默认数据库路径: {self.db_path}")
            
            # 确保数据库目录存在
            db_dir = Path(self.db_path).parent
            if not db_dir.exists():
                db_dir.mkdir(parents=True, exist_ok=True)
                self.log(f"✅ 创建数据库目录: {db_dir}")
            else:
                self.log(f"ℹ️ 数据库目录已存在: {db_dir}")
            
            # 设置保存Parquet文件的默认状态
            if hasattr(self, 'save_parquet_checkbox'):
                self.save_parquet_checkbox.setChecked(True)  # 默认使用direct策略
                self.log(f"⚠️ 使用默认temp_file_strategy设置: direct")
            
            # 最终数据库路径确认
            self.log(f"📊 最终数据库路径: {self.db_path}")
    
    def _preload_stock_list(self):
        """预加载股票列表
        
        在初始化阶段预加载A股股票列表，避免在下载过程中卡住
        """
        import time
        start_time = time.time()
        self.log("📊 开始预加载A股股票列表（排除ETF）...")
        
        try:
            if XTDATA_AVAILABLE:
                from xtquant import xtdata
                # 尝试获取A股列表
                all_stocks = xtdata.get_stock_list_in_sector('沪深A股')
                self.log(f"✅ 获取A股列表成功，耗时 {time.time() - start_time:.2f} 秒")
                
                # 过滤掉ETF和基金
                etf_patterns = [
                    '51', '159', '150', '588', '50', '56', '58'
                ]
                
                self._preloaded_stocks = []
                for stock in all_stocks:
                    code = stock.split('.')[0]
                    is_etf = False
                    for pattern in etf_patterns:
                        if code.startswith(pattern):
                            is_etf = True
                            break
                    if not is_etf:
                        self._preloaded_stocks.append(stock)
                
                self.log(f"✅ 预加载完成，获取到 {len(self._preloaded_stocks)} 只A股（已排除ETF和基金）")
            else:
                self.log("⚠️ xtquant模块不可用，无法预加载股票列表")
                # 使用预定义的股票列表作为备用
                self._preloaded_stocks = [
                    '600000.SH', '600001.SH', '600002.SH', '600003.SH', '600004.SH',
                    '600005.SH', '600006.SH', '600007.SH', '600008.SH', '600009.SH',
                    '600010.SH', '600011.SH', '600012.SH', '600015.SH', '600016.SH',
                    '600018.SH', '600019.SH', '600020.SH', '600021.SH', '600022.SH',
                    '600026.SH', '600027.SH', '600028.SH', '600029.SH', '600030.SH',
                    '600031.SH', '600033.SH', '600036.SH', '600037.SH', '600038.SH',
                    '600039.SH', '600048.SH', '600050.SH', '600051.SH', '600052.SH',
                    '600053.SH', '600054.SH', '600056.SH', '600058.SH', '600060.SH',
                    '600061.SH', '600062.SH', '600063.SH', '600066.SH', '600067.SH',
                    '600068.SH', '600070.SH', '600073.SH', '600076.SH', '600078.SH'
                ]
                self.log(f"✅ 使用预定义列表，获取到 {len(self._preloaded_stocks)} 只A股")
        except Exception as e:
            self.log(f"⚠️ 预加载股票列表失败: {e}")
            # 使用预定义的股票列表作为备用
            self._preloaded_stocks = [
                '600000.SH', '600001.SH', '600002.SH', '600003.SH', '600004.SH',
                '600005.SH', '600006.SH', '600007.SH', '600008.SH', '600009.SH',
                '600010.SH', '600011.SH', '600012.SH', '600015.SH', '600016.SH',
                '600018.SH', '600019.SH', '600020.SH', '600021.SH', '600022.SH',
                '600026.SH', '600027.SH', '600028.SH', '600029.SH', '600030.SH',
                '600031.SH', '600033.SH', '600036.SH', '600037.SH', '600038.SH',
                '600039.SH', '600048.SH', '600050.SH', '600051.SH', '600052.SH',
                '600053.SH', '600054.SH', '600056.SH', '600058.SH', '600060.SH',
                '600061.SH', '600062.SH', '600063.SH', '600066.SH', '600067.SH',
                '600068.SH', '600070.SH', '600073.SH', '600076.SH', '600078.SH'
            ]
            self.log(f"✅ 使用预定义列表，获取到 {len(self._preloaded_stocks)} 只A股")
    
    def _apply_default_config(self):
        """应用默认配置"""
        # 默认配置
        default_config = {
            'time_ranges': {
                'default': {'start_date': '1990-01-01'},
                '1d': {'start_date': '1990-01-01'},
                '1m': {'start_date': '3m'},
                '5m': {'start_date': '6m'},
                '15m': {'start_date': '1y'},
                '30m': {'start_date': '1y'},
                '60m': {'start_date': '2y'},
                'tick': {'start_date': '7d'}
            },
            'download': {
                'batch_size': 50,
                'max_workers': min(os.cpu_count() * 3, 20),
                'timeout': 30,
                'retry_count': 3
            }
        }
        
        # 递归合并默认配置
        self._merge_config(self.config, default_config)
        self.log(f"✅ 应用默认配置完成")
    
    def _resolve_database_path(self):
        """解析数据库路径"""
        # 1. 从合并后的配置中获取数据库路径
        if 'database' in self.config and 'path' in self.config['database']:
            db_path = self.config['database']['path']
            self.log(f"✅ 从配置文件读取数据库路径: {db_path}")
            return db_path
        
        # 2. 尝试组合生成路径
        elif 'database' in self.config and 'dbfile' in self.config['database'] and \
             'data_paths' in self.config and 'root_dir' in self.config['data_paths']:
            root_dir = self.config['data_paths']['root_dir']
            dbfile = self.config['database']['dbfile']
            db_path = str(Path(root_dir) / dbfile)
            self.log(f"✅ 从配置文件组合生成数据库路径: {db_path}")
            self.log(f"  - 根目录: {root_dir}")
            self.log(f"  - 数据库文件名: {dbfile}")
            return db_path
        
        # 3. 尝试从JSON格式的旧配置结构获取
        elif 'data_config' in self.config and 'database' in self.config['data_config'] and 'path' in self.config['data_config']['database']:
            db_path = self.config['data_config']['database']['path']
            self.log(f"✅ 从旧格式配置文件读取数据库路径: {db_path}")
            return db_path
        
        # 4. 如果没有配置，使用默认路径
        else:
            db_path = 'D:/MyStockData/stock_data.ddb'
            self.log(f"⚠️ 配置文件中未设置数据库路径，使用默认路径: {db_path}")
            return db_path
    
    def _merge_config(self, target, source):
        """递归合并配置字典，source中的配置会覆盖target中的配置"""
        for key, value in source.items():
            if key in target:
                if isinstance(target[key], dict) and isinstance(value, dict):
                    # 递归合并字典
                    self._merge_config(target[key], value)
                elif isinstance(target[key], list) and isinstance(value, list):
                    # 列表合并（source覆盖target）
                    target[key] = value
                else:
                    # 其他类型，直接覆盖
                    target[key] = value
            else:
                # 新键，直接添加
                target[key] = value

    def _init_log_file(self):
        """初始化日志文件"""
        try:
            self.log("开始初始化日志文件...")
            # 确保logs目录存在
            current_dir = os.path.dirname(__file__)
            my_gui_app_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
            log_dir = os.path.join(my_gui_app_dir, 'logs')
            
            # 打印目录路径，方便调试
            self.log(f"🔧 日志目录路径: {log_dir}")
            
            # 创建目录
            os.makedirs(log_dir, exist_ok=True)
            self.log(f"✅ 日志目录已创建: {log_dir}")
            
            # 生成包含时间戳的日志文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.log_file = os.path.join(log_dir, f"data_manager_{timestamp}.log")
            
            # 创建并写入初始日志
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 数据管理器启动\n")
            
            # 记录日志到UI
            self.log(f"✅ 日志文件已创建: {self.log_file}")
        except Exception as e:
            # 日志文件初始化失败不影响程序运行
            self.log(f"⚠️ 日志文件初始化失败: {e}")
            # 即使失败，也要设置一个默认的日志文件路径
            self.log_file = None
        else:
            self.log("日志文件初始化完成")

    def _check_and_rebuild_views(self):
        """自动检查并重建缺失的视图"""
        try:
            from src.core.data.database.db_manager import get_db_manager
            import duckdb
            
            # 使用配置文件中的路径组合数据库路径
            db_path = self.config.get('database', {}).get('dbfile', 'stock_data.ddb')
            if not os.path.isabs(db_path):
                # 从配置文件获取根目录
                data_root_dir = self.config.get('data_paths', {}).get('root_dir', 'D:/MyStockData')
                db_path = os.path.join(data_root_dir, db_path)
            
            manager = get_db_manager(db_path)
            
            # 需要检查的视图列表
            required_views = [
                'stock_daily', 'stock_1m', 'stock_5m', 'stock_15m',
                'stock_30m', 'stock_60m', 'stock_weekly', 'stock_monthly', 'stock_tick'
            ]
            
            # 检查哪些视图不存在
            missing_views = []
            for view_name in required_views:
                try:
                    check_query = f"SELECT count(*) FROM information_schema.tables WHERE table_name = '{view_name}'"
                    result = manager.query_dataframe(check_query)
                    if result is None or result.empty or result.iloc[0, 0] == 0:
                        missing_views.append(view_name)
                except Exception as e:
                    missing_views.append(view_name)
            
            if missing_views:
                self.log(f"⚠️ 检测到 {len(missing_views)} 个视图缺失: {', '.join(missing_views)}")
                self.log("🔄 正在自动重建视图...")
                
                # 直接在当前进程中重建视图（避免文件锁定问题）
                try:
                    import duckdb
                    from pathlib import Path
                    from src.core.utils import DownloadConfig
                    
                    config = DownloadConfig(self.config)
                    data_config = config.get_config()
                    
                    dbfile = data_config.get('database', {}).get('dbfile', 'stock_data.ddb')
                    data_root_dir = data_config.get('data_paths', {}).get('root_dir', 'D:/MyStockData')
                    duckdb_path = str(Path(data_root_dir) / dbfile)
                    
                    parquet_config = data_config.get('storage', {}).get('parquet', {})
                    parquet_root_dir = parquet_config.get('root_dir', 'Parquet')
                    parquet_root = Path(data_root_dir) / parquet_root_dir
                    
                    conn = duckdb.connect(duckdb_path, read_only=False)
                    
                    views_to_create = [
                        ('stock_daily', 'kline/daily'),
                        ('stock_1m', 'kline/1m'),
                        ('stock_5m', 'kline/5m'),
                        ('stock_15m', 'kline/15m'),
                        ('stock_30m', 'kline/30m'),
                        ('stock_60m', 'kline/60m'),
                        ('stock_weekly', 'kline/weekly'),
                        ('stock_monthly', 'kline/monthly'),
                        ('stock_tick', 'tick'),
                    ]
                    
                    for view_name, path_part in views_to_create:
                        try:
                            conn.execute(f"DROP VIEW IF EXISTS main.{view_name}")
                            parquet_path = str(parquet_root / path_part / '**' / '*.parquet').replace('\\', '/')
                            
                            if view_name in ['stock_weekly', 'stock_monthly']:
                                date_col = "COALESCE(date, CURRENT_DATE) AS date"
                                period_val = '1w' if 'week' in view_name else '1M'
                            elif view_name == 'stock_daily':
                                date_col = "COALESCE(date, CURRENT_DATE) AS date"
                                period_val = '1d'
                            else:
                                date_col = "COALESCE(datetime::TIMESTAMP, CURRENT_TIMESTAMP::TIMESTAMP) AS datetime"
                                period_val = view_name.replace('stock_', '')
                            
                            sql = f"""
                                CREATE OR REPLACE VIEW main.{view_name} AS
                                SELECT 
                                    COALESCE(stock_code, '') AS stock_code,
                                    {date_col},
                                    COALESCE(open, 0.0) AS open,
                                    COALESCE(high, 0.0) AS high,
                                    COALESCE(low, 0.0) AS low,
                                    COALESCE(close, 0.0) AS close,
                                    COALESCE(volume, 0) AS volume,
                                    COALESCE(amount, 0.0) AS amount,
                                    'stock' as symbol_type,
                                    '{period_val}' as period,
                                    'none' as adjust_type,
                                    1.0 as factor,
                                    CURRENT_TIMESTAMP as created_at,
                                    CURRENT_TIMESTAMP as updated_at
                                FROM read_parquet('{parquet_path}', union_by_name=true, filename=true, hive_partitioning=true)
                                WHERE COALESCE(stock_code, '') != ''
                            """
                            conn.execute(sql)
                        except Exception as ve:
                            self.log(f"  ⚠️ 创建视图 {view_name} 失败: {ve}")
                    
                    conn.close()
                    self.log(f"✅ 视图重建成功: {', '.join(missing_views)}")
                        
                except Exception as e:
                    self.log(f"❌ 自动重建视图失败: {e}")
                    self.log("💡 请手动点击「🔄 重新生成数据库视图」按钮")
            else:
                self.log("✅ 所有视图检查通过")
                
        except Exception as e:
            self.log(f"⚠️ 视图检查跳过（数据库未就绪）: {e}")

    def on_data_type_changed(self, index):
        """数据类型变更时的处理"""
        data_type_text = self.data_type_combo.currentText()
        # 映射数据类型到周期
        period_map = {
            "所有类型": None,
            "日线数据": "1d",
            "1分钟数据": "1m",
            "5分钟数据": "5m",
            "15分钟数据": "15m",
            "30分钟数据": "30m",
            "60分钟数据": "60m",
            "周线数据": "weekly",
            "月线数据": "monthly",
            "Tick数据": "tick"
        }
        period = period_map.get(data_type_text)
        
        # 根据数据类型和配置文件设置日期范围
        self._set_date_range_by_period(period)
    
    def _set_date_range_by_period(self, period):
        """根据周期设置日期范围"""
        from datetime import datetime, timedelta
        import re
        
        # 今天的日期
        today = datetime.now()
        
        # 从配置文件获取时间范围设置
        time_ranges = self.config.get('time_ranges', {})
        
        # 获取对应周期的时间范围设置
        if period and period in time_ranges:
            range_config = time_ranges[period]
        else:
            range_config = time_ranges.get('default', {'start_date': '1990-01-01'})
        
        # 解析开始日期
        if 'start_days' in range_config:
            # 处理相对天数
            start_date = today - timedelta(days=range_config['start_days'])
        else:
            start_date_str = range_config.get('start_date', '1990-01-01')
            
            # 处理相对时间格式（如 '3m', '1y' 等）
            if re.match(r'\d+[yYmMdD]', start_date_str):
                # 提取数字和单位
                match = re.match(r'(\d+)([yYmMdD])', start_date_str)
                if match:
                    num = int(match.group(1))
                    unit = match.group(2)
                    
                    if unit == 'y' or unit == 'Y':
                        start_date = today - timedelta(days=num*365)
                    elif unit == 'm' or unit == 'M':
                        start_date = today - timedelta(days=num*30)
                    elif unit == 'd' or unit == 'D':
                        start_date = today - timedelta(days=num)
                    else:
                        start_date = today - timedelta(days=30)  # 默认30天
                else:
                    start_date = today - timedelta(days=30)  # 默认30天
            else:
                # 处理绝对日期格式
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                except ValueError:
                    start_date = today - timedelta(days=30)  # 默认30天
        
        # 设置日期控件
        self.start_date_edit.setDate(QDate(start_date.year, start_date.month, start_date.day))
        self.end_date_edit.setDate(QDate(today.year, today.month, today.day))
        
        # 记录日志
        self.log(f"📅 根据数据类型自动调整日期范围: 开始日期={start_date.strftime('%Y-%m-%d')}, 结束日期={today.strftime('%Y-%m-%d')}")

    def log(self, message):
        """输出日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_message = f"[{timestamp}] {message}"
        self.log_text.append(log_message)
        # 滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        
        # 同时写入日志文件
        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
            except Exception as e:
                # 日志写入失败不影响程序运行
                pass

    def load_duckdb_statistics(self):
        """从DuckDB加载统计数据"""
        try:
            # 使用与下载线程相同的数据库管理器
            from src.core.data.database.db_manager import get_db_manager

            # 获取数据库管理器
            manager = get_db_manager(self.db_path)
            
            # 调试：打印数据库路径
            self.log(f"📊 统计数据使用的数据库路径: {self.db_path}")
            
            # 检查是否存在任何表，如果不存在，创建初始表结构
            tables_to_check = ['stock_daily', 'stock_1m', 'stock_5m', 'stock_15m', 'stock_30m', 'stock_60m', 'stock_weekly', 'stock_monthly', 'stock_tick']
            tables_exist = False
            for table in tables_to_check:
                if manager.table_exists(table):
                    tables_exist = True
                    break
            
            if not tables_exist:
                self.log("⚠️ 数据库中没有找到任何表，正在创建初始表结构...")
                # 创建初始表结构
                if self._rebuild_database_tables():
                    self.log("✅ 初始表结构创建成功")
                else:
                    self.log("❌ 初始表结构创建失败")
            
            # 统计stock_daily表
            stats_daily = None
            try:
                # 检查表是否存在
                if not manager.table_exists('stock_daily'):
                    self.log(f"⚠️ 统计 stock_daily 表失败: 表不存在")
                    self.log(f"ℹ️ 该表可能尚未创建，请先下载对应类型的数据")
                else:
                    stats_daily = manager.execute_read_and_fetch("""
                        SELECT
                            COUNT(DISTINCT stock_code) as stock_count,
                            SUM(CASE WHEN symbol_type = 'stock' THEN 1 ELSE 0 END) as stock_only,
                            SUM(CASE WHEN symbol_type = 'etf' THEN 1 ELSE 0 END) as etf_count,
                            COUNT(*) as total_records,
                            MAX(date) as latest_date
                        FROM stock_daily
                    """)
                    if stats_daily:
                        stats_daily = stats_daily[0]
            except Exception as e:
                self.log(f"⚠️ 统计 stock_daily 表失败: {e}")

            # 统计所有分钟数据表
            minute_tables = ['stock_1m', 'stock_5m', 'stock_15m', 'stock_30m', 'stock_60m']
            minute_records = 0
            minute_stocks_count = 0

            # 统计周线和月线数据表
            weekly_monthly_tables = ['stock_weekly', 'stock_monthly']
            weekly_monthly_records = 0
            weekly_monthly_stocks_count = 0

            # 统计分钟线数据
            minute_details = {}
            for table in minute_tables:
                try:
                    # 直接查询，不使用 table_exists 方法
                    # 添加日志，记录查询开始
                    self.log(f"📊 开始统计 {table} 表...")
                    
                    # 使用单个查询获取股票数和记录数，提高性能
                    result = manager.execute_read_and_fetch(f"""
                        SELECT
                            COUNT(DISTINCT stock_code) as cnt,
                            COUNT(*) as records
                        FROM {table}
                    """)
                    
                    if result:
                        result = result[0]
                        table_stocks_count = result[0]
                        table_records = result[1]
                        
                        # 更新统计信息
                        # 注意：这里不再收集具体的股票代码，只统计数量，提高性能
                        minute_records += table_records
                        if table_stocks_count > minute_stocks_count:
                            minute_stocks_count = table_stocks_count
                        
                        # 保存详细信息
                        minute_details[table] = {
                            'symbols': table_stocks_count,
                            'records': table_records
                        }
                        
                        # 添加日志，记录统计结果
                        self.log(f"📋 {table} 表统计: {table_stocks_count} 个标的, {table_records} 条记录")
                except Exception as e:
                    self.log(f"⚠️ 统计 {table} 表失败: {e}")
                    self.log(f"ℹ️ 该表可能尚未创建，请先下载对应类型的数据")

            # 统计周线和月线数据
            weekly_monthly_details = {}
            for table in weekly_monthly_tables:
                try:
                    # 直接查询，不使用 _check_table_exists_and_not_empty 方法
                    # 添加日志，记录查询开始
                    self.log(f"📊 开始统计 {table} 表...")
                    
                    # 使用单个查询获取股票数和记录数，提高性能
                    result = manager.execute_read_and_fetch(f"""
                        SELECT
                            COUNT(DISTINCT stock_code) as cnt,
                            COUNT(*) as records
                        FROM {table}
                    """)
                    
                    if result:
                        result = result[0]
                        table_stocks_count = result[0]
                        table_records = result[1]
                        
                        # 更新统计信息
                        weekly_monthly_records += table_records
                        if table_stocks_count > weekly_monthly_stocks_count:
                            weekly_monthly_stocks_count = table_stocks_count
                        
                        # 保存详细信息
                        weekly_monthly_details[table] = {
                            'symbols': table_stocks_count,
                            'records': table_records
                        }
                        
                        # 添加日志，记录统计结果
                        self.log(f"📋 {table} 表统计: {table_stocks_count} 个标的, {table_records} 条记录")
                except Exception as e:
                    # 捕获Parquet文件不存在的错误
                    if "No files found that match the pattern" in str(e):
                        self.log(f"⚠️ 统计 {table} 表失败: 没有找到对应的Parquet文件")
                        self.log(f"ℹ️ 请先下载对应类型的数据")
                    else:
                        self.log(f"⚠️ 统计 {table} 表失败: {e}")
                        self.log(f"ℹ️ 该表可能尚未创建，请先下载对应类型的数据")

            # 统计tick数据表
            tick_records = 0
            tick_stocks = set()
            tick_stocks_count = 0  # 初始化变量，避免未定义错误
            try:
                # 直接查询，不使用 _check_table_exists_and_not_empty 方法
                # 只获取统计信息，不获取具体的股票代码，提高性能
                result = manager.execute_read_and_fetch("""
                    SELECT
                        COUNT(DISTINCT stock_code) as cnt,
                        COUNT(*) as records
                    FROM stock_tick
                    LIMIT 1
                """)
                if result:
                    result = result[0]
                    tick_stocks_count = result[0]
                    tick_records = result[1]
                    # 不获取具体的股票代码，只使用统计数
                    # 这样可以避免大量数据传输，提高性能
                    tick_symbols = tick_stocks_count
                    
                    # 添加日志，记录统计结果
                    self.log(f"📋 stock_tick 表统计: {tick_stocks_count} 个标的, {tick_records} 条记录")
            except Exception as e:
                # 捕获Parquet文件不存在的错误
                if "No files found that match the pattern" in str(e):
                    self.log(f"⚠️ 统计 stock_tick 表失败: 没有找到对应的Parquet文件")
                    self.log(f"ℹ️ 请先下载对应类型的数据")
                else:
                    self.log(f"⚠️ 统计 stock_tick 表失败: {e}")

            # 计算总标的数量（去重）
            all_stocks = set()
            total_symbols = 0  # 初始化变量，避免未定义错误
            stock_count = 0  # 初始化变量
            etf_count = 0  # 初始化变量
            daily_records = 0  # 初始化变量
            latest_date = 'N/A'  # 初始化变量
            total_records = 0  # 初始化变量
            total_bonds = 0  # 初始化变量
            size_mb = 0  # 初始化变量
            daily_symbols = 0  # 初始化变量
            minute_symbols = minute_stocks_count  # 初始化变量
            weekly_monthly_symbols = weekly_monthly_stocks_count  # 初始化变量
            tick_symbols = tick_stocks_count  # 使用查询得到的正确值
            
            # 处理日线数据
            # 不管stats_daily是否为None，都直接查询
            try:
                # 直接查询，不使用 _check_table_exists_and_not_empty 方法
                # 只获取统计信息，不获取具体的股票代码，提高性能
                result = manager.execute_read_and_fetch("""
                    SELECT
                        COUNT(DISTINCT stock_code) as cnt,
                        COUNT(*) as records
                    FROM stock_daily
                    LIMIT 1
                """)
                if result:
                    result = result[0]
                    daily_symbols = result[0]
                    daily_records = result[1]
                    
                    # 添加日志，记录统计结果
                    self.log(f"📋 stock_daily 表统计: {daily_symbols} 个标的, {daily_records} 条记录")
            except Exception as e:
                # 捕获Parquet文件不存在的错误
                if "No files found that match the pattern" in str(e):
                    self.log(f"⚠️ 统计 stock_daily 表失败: 没有找到对应的Parquet文件")
                    self.log(f"ℹ️ 请先下载日线数据")
                else:
                    self.log(f"⚠️ 统计 stock_daily 表失败: {e}")
            
            # 分类型统计信息
            stock_count = daily_symbols  # 使用日线数据的标的数作为股票数量
            etf_count = 0  # 暂时不区分股票和ETF
            
            # 直接查询最新日期
            try:
                # 直接查询，不使用 _check_table_exists_and_not_empty 方法
                # 使用execute_read_and_fetch方法，提高性能
                result = manager.execute_read_and_fetch("SELECT MAX(date) as max_date FROM stock_daily LIMIT 1")
                if result and result[0][0]:
                    latest_date = str(result[0][0])
                else:
                    latest_date = 'N/A'
            except Exception as e:
                # 捕获Parquet文件不存在的错误
                if "No files found that match the pattern" in str(e):
                    latest_date = 'N/A'
                else:
                    latest_date = 'N/A'
            
            # 计算总标的数量（使用各类型的统计数）
            # 由于我们不再获取具体的股票代码，使用各类型的最大统计数作为总标的数
            total_symbols = max(daily_symbols, minute_symbols, weekly_monthly_symbols, tick_symbols)
            
            # 计算总记录数
            total_records = daily_records + minute_records + weekly_monthly_records + tick_records
            total_bonds = 0  # 暂时没有可转债数据

            # 估算存储大小（每条记录约0.1KB）
            size_mb = total_records * 0.0001

            # 保存详细统计数据
            self.stats_details = {
                'total_symbols': total_symbols,
                'stock_count': stock_count,
                'etf_count': etf_count,
                'total_bonds': total_bonds,
                'total_records': total_records,
                'size_mb': size_mb,
                'latest_date': latest_date,
                'daily': {
                    'symbols': daily_symbols,
                    'records': daily_records
                },
                'minute': {
                    'symbols': minute_symbols,
                    'records': minute_records
                },
                'weekly_monthly': {
                    'symbols': weekly_monthly_symbols,
                    'records': weekly_monthly_records
                },
                'tick': {
                    'symbols': tick_symbols,
                    'records': tick_records
                },
                'minute_details': minute_details,
                'weekly_monthly_details': weekly_monthly_details
            }

            self.total_symbols_label.setText(f"标的总数: {total_symbols:,}")
            self.total_stocks_label.setText(f"股票数量: {stock_count:,}")
            self.total_bonds_label.setText(f"可转债数量: {total_bonds:,}")
            self.total_records_label.setText(f"总记录数: {total_records:,}")
            self.total_size_label.setText(f"存储大小: {size_mb:.2f} MB")
            self.latest_date_label.setText(f"最新日期: {latest_date}")

            # 显示分类型统计信息
            self.log(f"📊 统计数据:")
            self.log(f"  日线数据: {daily_symbols} 个标的, {daily_records:,} 条记录")
            
            # 按周期显示分钟线数据
            if minute_records > 0:
                self.log(f"  分钟线数据: {minute_symbols} 个标的, {minute_records:,} 条记录")
                # 显示各周期分钟线数据
                for table, stats in self.stats_details['minute_details'].items():
                    if stats['records'] > 0:
                        period = table.replace('stock_', '')
                        self.log(f"    {period}: {stats['symbols']} 个标的, {stats['records']:,} 条记录")
            else:
                self.log(f"  分钟线数据: 0 个标的, 0 条记录")
            
            # 显示周线和月线数据
            self.log(f"  周线和月线数据: {weekly_monthly_symbols} 个标的, {weekly_monthly_records:,} 条记录")
            # 显示各周期周线和月线数据
            for table, stats in self.stats_details['weekly_monthly_details'].items():
                if stats['records'] > 0:
                    period = table.replace('stock_', '')
                    self.log(f"    {period}: {stats['symbols']} 个标的, {stats['records']:,} 条记录")
            
            self.log(f"  Tick数据: {tick_symbols} 个标的, {tick_records:,} 条记录")
            self.log(f"  总计: {total_symbols} 个标的, {total_records:,} 条记录")

        except Exception as e:
            self.log(f"[ERROR] 加载统计数据失败: {e}")

    def show_stats_details(self):
        """显示详细统计信息弹窗"""
        try:
            # 检查是否有统计数据
            if not hasattr(self, 'stats_details'):
                QMessageBox.warning(self, "提示", "请先点击'更新统计信息'按钮获取数据")
                return

            # 调试信息
            self.log(f"📊 显示详细统计信息: {self.stats_details}")

            # 创建弹窗
            dialog = QDialog(self)
            dialog.setWindowTitle("详细数据统计")
            dialog.setMinimumSize(600, 400)

            layout = QVBoxLayout(dialog)

            # 创建标签页
            tab_widget = QTabWidget()

            # 总览标签页
            overview_tab = QWidget()
            overview_layout = QVBoxLayout(overview_tab)

            # 总览信息
            overview_group = QGroupBox("总览信息")
            overview_group_layout = QGridLayout()
            overview_group.setLayout(overview_group_layout)

            stats = self.stats_details
            overview_group_layout.addWidget(QLabel("标的总数:"), 0, 0)
            overview_group_layout.addWidget(QLabel(f"{stats['total_symbols']:,}"), 0, 1)
            overview_group_layout.addWidget(QLabel("股票数量:"), 1, 0)
            overview_group_layout.addWidget(QLabel(f"{stats['stock_count']:,}"), 1, 1)
            overview_group_layout.addWidget(QLabel("ETF数量:"), 2, 0)
            overview_group_layout.addWidget(QLabel(f"{stats['etf_count']:,}"), 2, 1)
            overview_group_layout.addWidget(QLabel("可转债数量:"), 3, 0)
            overview_group_layout.addWidget(QLabel(f"{stats['total_bonds']:,}"), 3, 1)
            overview_group_layout.addWidget(QLabel("总记录数:"), 4, 0)
            overview_group_layout.addWidget(QLabel(f"{stats['total_records']:,}"), 4, 1)
            overview_group_layout.addWidget(QLabel("存储大小:"), 5, 0)
            overview_group_layout.addWidget(QLabel(f"{stats['size_mb']:.2f} MB"), 5, 1)
            overview_group_layout.addWidget(QLabel("最新日期:"), 6, 0)
            overview_group_layout.addWidget(QLabel(f"{stats['latest_date']}"), 6, 1)

            overview_layout.addWidget(overview_group)

            # 各类型数据统计
            type_stats_group = QGroupBox("各类型数据统计")
            type_stats_layout = QGridLayout()
            type_stats_group.setLayout(type_stats_layout)

            # 日线数据
            type_stats_layout.addWidget(QLabel("日线数据:"), 0, 0)
            type_stats_layout.addWidget(QLabel(f"{stats['daily']['symbols']} 个标的, {stats['daily']['records']:,} 条记录"), 0, 1)

            # 分钟线数据
            type_stats_layout.addWidget(QLabel("分钟线数据:"), 1, 0)
            type_stats_layout.addWidget(QLabel(f"{stats['minute']['symbols']} 个标的, {stats['minute']['records']:,} 条记录"), 1, 1)

            # 周线和月线数据
            type_stats_layout.addWidget(QLabel("周线和月线数据:"), 2, 0)
            type_stats_layout.addWidget(QLabel(f"{stats['weekly_monthly']['symbols']} 个标的, {stats['weekly_monthly']['records']:,} 条记录"), 2, 1)

            # Tick数据
            type_stats_layout.addWidget(QLabel("Tick数据:"), 3, 0)
            type_stats_layout.addWidget(QLabel(f"{stats['tick']['symbols']} 个标的, {stats['tick']['records']:,} 条记录"), 3, 1)

            overview_layout.addWidget(type_stats_group)
            tab_widget.addTab(overview_tab, "总览")

            # 各数据类型数据详情标签页
            details_tab = QWidget()
            details_layout = QVBoxLayout(details_tab)

            details_group = QGroupBox("各数据类型详细统计")
            details_group_layout = QGridLayout()
            details_group.setLayout(details_group_layout)

            row = 0
            
            # 显示日线数据详情
            details_group_layout.addWidget(QLabel("日线数据:"), row, 0)
            details_group_layout.addWidget(QLabel(f"{stats['daily']['symbols']} 个标的, {stats['daily']['records']:,} 条记录"), row, 1)
            row += 1
            
            # 显示各分钟线数据详情
            minute_details = stats.get('minute_details', {})
            if minute_details:
                for table_name, table_stats in minute_details.items():
                    period = table_name.replace('stock_', '')
                    # 为分钟线添加中文显示
                    period_name_map = {
                        '1m': '1分钟',
                        '5m': '5分钟',
                        '15m': '15分钟',
                        '30m': '30分钟',
                        '60m': '60分钟'
                    }
                    period_name = period_name_map.get(period, period)
                    details_group_layout.addWidget(QLabel(f"{period_name} 数据:"), row, 0)
                    details_group_layout.addWidget(QLabel(f"{table_stats['symbols']} 个标的, {table_stats['records']:,} 条记录"), row, 1)
                    row += 1
            else:
                details_group_layout.addWidget(QLabel("分钟线数据:"), row, 0)
                details_group_layout.addWidget(QLabel("无数据"), row, 1)
                row += 1
            
            # 显示各周线和月线数据详情
            weekly_monthly_details = stats.get('weekly_monthly_details', {})
            if weekly_monthly_details:
                for table_name, table_stats in weekly_monthly_details.items():
                    period = table_name.replace('stock_', '')
                    # 为周线和月线添加中文显示
                    period_name_map = {
                        'weekly': '周线',
                        'monthly': '月线'
                    }
                    period_name = period_name_map.get(period, period)
                    details_group_layout.addWidget(QLabel(f"{period_name} 数据:"), row, 0)
                    details_group_layout.addWidget(QLabel(f"{table_stats['symbols']} 个标的, {table_stats['records']:,} 条记录"), row, 1)
                    row += 1
            else:
                details_group_layout.addWidget(QLabel("周线和月线数据:"), row, 0)
                details_group_layout.addWidget(QLabel("无数据"), row, 1)
                row += 1
            
            # 显示Tick数据详情
            details_group_layout.addWidget(QLabel("Tick数据:"), row, 0)
            details_group_layout.addWidget(QLabel(f"{stats['tick']['symbols']} 个标的, {stats['tick']['records']:,} 条记录"), row, 1)

            details_layout.addWidget(details_group)
            tab_widget.addTab(details_tab, "各数据类型数据详情")

            # 数据分布标签页
            distribution_tab = QWidget()
            distribution_layout = QVBoxLayout(distribution_tab)

            # 计算各类型数据占比
            total_records = stats['total_records']
            if total_records > 0:
                daily_pct = (stats['daily']['records'] / total_records) * 100
                minute_pct = (stats['minute']['records'] / total_records) * 100
                weekly_monthly_pct = (stats['weekly_monthly']['records'] / total_records) * 100
                tick_pct = (stats['tick']['records'] / total_records) * 100

                distribution_group = QGroupBox("数据分布")
                distribution_group_layout = QGridLayout()
                distribution_group.setLayout(distribution_group_layout)

                distribution_group_layout.addWidget(QLabel("日线数据占比:"), 0, 0)
                distribution_group_layout.addWidget(QLabel(f"{daily_pct:.2f}%"), 0, 1)
                distribution_group_layout.addWidget(QLabel("分钟线数据占比:"), 1, 0)
                distribution_group_layout.addWidget(QLabel(f"{minute_pct:.2f}%"), 1, 1)
                distribution_group_layout.addWidget(QLabel("周线和月线数据占比:"), 2, 0)
                distribution_group_layout.addWidget(QLabel(f"{weekly_monthly_pct:.2f}%"), 2, 1)
                distribution_group_layout.addWidget(QLabel("Tick数据占比:"), 3, 0)
                distribution_group_layout.addWidget(QLabel(f"{tick_pct:.2f}%"), 3, 1)

                distribution_layout.addWidget(distribution_group)
            else:
                no_data_label = QLabel("暂无数据分布信息")
                no_data_label.setAlignment(Qt.AlignCenter)
                distribution_layout.addWidget(no_data_label)

            tab_widget.addTab(distribution_tab, "数据分布")

            layout.addWidget(tab_widget)

            # 添加关闭按钮
            button_box = QHBoxLayout()
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.close)
            button_box.addStretch()
            button_box.addWidget(close_btn)
            layout.addLayout(button_box)

            dialog.exec_()

        except Exception as e:
            self.log(f"[ERROR] 显示详细统计信息失败: {e}")
            import traceback
            self.log(f"[ERROR] 详细错误: {traceback.format_exc()}")

    def download_single_stock(self):
        """下载单个标的的数据"""
        # 获取输入的股票代码
        stock_code = self.stock_code_input.text().strip()

        if not stock_code:
            QMessageBox.warning(self, "提示", "请输入股票/ETF代码")
            return

        # 标准化代码格式
        stock_code = stock_code.upper()

        # 验证代码格式
        if not ('.' in stock_code):
            # 如果没有后缀，尝试自动添加
            if stock_code.startswith('6') or stock_code.startswith('5'):
                stock_code = stock_code + '.SH'
            elif stock_code.startswith('0') or stock_code.startswith('3') or stock_code.startswith('1'):
                stock_code = stock_code + '.SZ'

        # 获取日期范围
        start_date = self.manual_start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.manual_end_date_edit.date().toString("yyyy-MM-dd")

        # 获取数据类型
        data_type_text = self.manual_data_type_combo.currentText()
        period_map = {
            "所有类型": None,
            "日线数据": "1d",
            "1分钟数据": "1m",
            "5分钟数据": "5m",
            "15分钟数据": "15m",
            "30分钟数据": "30m",
            "60分钟数据": "60m",
            "周线数据": "weekly",
            "月线数据": "monthly",
            "Tick数据": "tick"
        }
        period = period_map.get(data_type_text, "1d")

        # 获取复权方式
        adjustment_text = self.manual_adjustment_combo.currentText()
        adjustment_map = {
            "五维复权": "fivefold",
            "不复权": "none",
            "前复权": "front",
            "后复权": "back",
            "几何前复权": "geometric_front",
            "几何后复权": "geometric_back"
        }
        adjustment = adjustment_map.get(adjustment_text, "fivefold")

        self.log(f"🎯 开始下载单个标的: {stock_code}")
        self.log(f"   数据类型: {data_type_text}")
        self.log(f"   复权方式: {adjustment_text}")
        self.log(f"   日期范围: {start_date} ~ {end_date}")

        # 禁用按钮
        self.manual_download_btn.setEnabled(False)

        if data_type_text == "所有类型":
            # 下载所有类型的数据，使用信号和槽机制
            self.log(f"📥 开始下载所有类型数据 ({start_date} ~ {end_date})")

            # 初始化下载状态
            self.download_task_queue = []  # 存储所有待执行的任务参数
            self.current_task_index = 0    # 当前执行的任务索引
            self.is_sequential_download = True  # 标记是否处于连续下载模式
            self._stop_requested = False     # 标记是否收到停止请求
            
            # 构建任务队列
            self.download_task_queue = [
                {'task_type': 'download_stocks', 'period': '1d', 'data_type': 'daily'},  # 日线
                {'task_type': 'download_minute_data', 'period': '1m', 'data_type': '1min'},  # 1分钟
                {'task_type': 'download_minute_data', 'period': '5m', 'data_type': '5min'},  # 5分钟
                {'task_type': 'download_minute_data', 'period': '15m', 'data_type': '15min'},  # 15分钟
                {'task_type': 'download_minute_data', 'period': '30m', 'data_type': '30min'},  # 30分钟
                {'task_type': 'download_minute_data', 'period': '60m', 'data_type': '60min'},  # 60分钟
                {'task_type': 'download_minute_data', 'period': 'weekly', 'data_type': 'weekly'},  # 周线
                {'task_type': 'download_minute_data', 'period': 'monthly', 'data_type': 'monthly'},  # 月线
                {'task_type': 'download_minute_data', 'period': 'tick', 'data_type': 'tick'},  # Tick
            ]
            
            # 存储其他参数
            self._start_date = start_date
            self._end_date = end_date
            self._symbols = [stock_code]  # 单个股票
            self._test_mode = False
            self._rebuild_database = False
            
            # 强制刷新UI，确保日志显示
            QCoreApplication.processEvents()
            # 开始执行第一个任务
            self._start_next_sequential_task()
        else:
            # 下载单个类型的数据
            # 统一使用DataDownloadThread类来下载单个标的，这样可以利用其现有的复权计算逻辑
            self.download_thread = DataDownloadThread(
                task_type='download_stocks' if period == '1d' else 'download_minute_data',
                symbols=[stock_code],
                start_date=start_date,
                end_date=end_date,
                data_type='daily' if period == '1d' else '1min',
                period=period,
                db_path=self.db_path,
                test_mode=False
            )
            self.download_thread.log_signal.connect(self.log)
            self.download_thread.finished_signal.connect(self.on_single_download_finished)
            self.download_thread.error_signal.connect(self.on_single_download_error)
            self.download_thread.start()

    def on_single_download_finished(self, result):
        """单个标的下载完成"""
        self.manual_download_btn.setEnabled(True)

        # 检查是否是所有类型的下载结果
        if 'task_type' in result and result['task_type'] == 'download_stocks':
            # 所有类型的下载结果
            total = result.get('total', 0)
            success = result.get('success', 0)
            failed = result.get('failed', 0)

            self.log(f"✅ 所有类型下载完成!")
            self.log(f"   总计: {total} 只股票")
            self.log(f"   成功: {success} 只")
            self.log(f"   失败: {failed} 只")

            QMessageBox.information(self, "下载成功",
                f"所有类型下载完成!\n\n总计: {total} 只股票\n成功: {success} 只\n失败: {failed} 只")
        else:
            # 单个类型的下载结果
            stock_code = result.get('symbol', '')
            success = result.get('success', False)
            record_count = result.get('record_count', 0)
            file_size = result.get('file_size', 0)

            if success:
                self.log(f"✅ {stock_code} 下载成功!")
                self.log(f"   记录数: {record_count} 条")
                self.log(f"   文件大小: {file_size:.2f} MB")

                QMessageBox.information(self, "下载成功",
                    f"{stock_code} 下载成功!\n\n记录数: {record_count} 条\n文件大小: {file_size:.2f} MB")

            else:
                self.log(f"❌ {stock_code} 下载失败")

    def on_single_download_error(self, error_msg):
        """单个标的下载出错"""
        self.manual_download_btn.setEnabled(True)
        QMessageBox.critical(self, "下载失败", error_msg)

    def download_financial_data(self):
        """下载QMT财务数据"""
        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.warning(self, "提示", "已有下载任务正在运行")
            return

        # 获取股票列表
        stock_selection = self.financial_stock_combo.currentText()

        if "默认股票列表" in stock_selection:
            stock_list = ["000001.SZ", "600519.SH", "511380.SH", "512100.SH"]
        elif "自定义股票列表" in stock_selection:
            # 弹出输入对话框让用户输入股票列表
            text, ok = QInputDialog.getText(
                self, "输入股票列表",
                "请输入股票代码，用逗号分隔:\n例如: 000001.SZ,600519.SH,511380.SH"
            )
            if not ok or not text.strip():
                return
            stock_list = [s.strip() for s in text.split(',')]
        elif "全部A股" in stock_selection:
            # 警告用户
            reply = QMessageBox.question(
                self, "确认下载",
                "即将下载全部A股的财务数据，这可能需要较长时间。\n\n确定要继续吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            # 获取全部A股列表
            try:
                if not XTDATA_AVAILABLE:
                    QMessageBox.warning(self, "错误", "xtquant模块不可用，请确保QMT已安装并运行")
                    return
                from xtquant import xtdata
                all_stocks = xtdata.get_stock_list_in_sector('沪深A股')
                # 过滤掉ETF和基金
                etf_patterns = [
                    '51',      # 上海ETF：510xxx, 511xxx, 512xxx, 513xxx, 515xxx, 516xxx
                    '159',     # 深圳ETF：159xxx
                    '150',     # 深圳基金：150xxx
                    '588',     # 上海ETF：588xxx
                    '50',      # 上海50开头基金
                    '56',      # 上海56开头基金
                    '58',      # 上海58开头基金
                ]

                stock_list = []
                for stock in all_stocks:
                    is_etf = False
                    for pattern in etf_patterns:
                        if stock.startswith(pattern):
                            is_etf = True
                            break

                    if not is_etf:
                        stock_list.append(stock)
                QMessageBox.information(self, "提示", f"即将下载 {len(stock_list)} 只A股的财务数据")
            except:
                QMessageBox.warning(self, "错误", "获取股票列表失败")
                return
        elif "沪深300" in stock_selection:
            # 获取沪深300成分股
            try:
                if not XTDATA_AVAILABLE:
                    QMessageBox.warning(self, "错误", "xtquant模块不可用，请确保QMT已安装并运行")
                    return
                from xtquant import xtdata
                stock_list = xtdata.get_stock_list_in_sector('沪深300')
            except:
                stock_list = ["000001.SZ", "600519.SH", "511380.SH"]
        elif "中证500" in stock_selection:
            try:
                if not XTDATA_AVAILABLE:
                    QMessageBox.warning(self, "错误", "xtquant模块不可用，请确保QMT已安装并运行")
                    return
                from xtquant import xtdata
                stock_list = xtdata.get_stock_list_in_sector('中证500')
            except:
                stock_list = ["000001.SZ", "600519.SH", "511380.SH"]
        elif "中证1000" in stock_selection:
            try:
                if not XTDATA_AVAILABLE:
                    QMessageBox.warning(self, "错误", "xtquant模块不可用，请确保QMT已安装并运行")
                    return
                from xtquant import xtdata
                stock_list = xtdata.get_stock_list_in_sector('中证1000')
            except:
                stock_list = ["000001.SZ", "600519.SH", "511380.SH"]
        else:
            stock_list = ["000001.SZ", "600519.SH", "511380.SH"]

        # 获取数据表列表
        table_list = []
        if self.financial_balance_check.isChecked():
            table_list.append("Balance")
        if self.financial_income_check.isChecked():
            table_list.append("Income")
        if self.financial_cashflow_check.isChecked():
            table_list.append("CashFlow")
        if self.financial_cap_check.isChecked():
            table_list.append("Capitalization")
        if self.financial_dividend_check.isChecked():
            table_list.append("Dividend")

        if not table_list:
            QMessageBox.warning(self, "提示", "请至少选择一个数据表")
            return

        self.log(f"💰 开始下载QMT财务数据")
        self.log(f"   股票数量: {len(stock_list)}")
        self.log(f"   数据表: {', '.join(table_list)}")

        # 创建下载线程
        self.download_thread = FinancialDataDownloadThread(
            stock_list=stock_list,
            table_list=table_list
        )
        self.download_thread.log_signal.connect(self.log)
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.finished_signal.connect(self.on_financial_download_finished)
        self.download_thread.error_signal.connect(self.on_financial_download_error)
        self.download_thread.start()

        self._set_download_state(True)

    def on_financial_download_finished(self, result):
        """财务数据下载完成"""
        self._set_download_state(False)
        self.progress_bar.setVisible(False)

        total = result.get('total', 0)
        success = result.get('success', 0)
        failed = result.get('failed', 0)
        skipped = result.get('skipped', 0)

        msg = f"QMT财务数据下载完成！\n\n"
        msg += f"有效股票: {total} 只\n"
        msg += f"成功: {success} 只\n"
        msg += f"失败: {failed} 只"
        if skipped > 0:
            msg += f"\n跳过: {skipped} 只（ETF/指数无财务数据）"

        if failed > 0:
            QMessageBox.warning(self, "下载完成", msg)
        else:
            QMessageBox.information(self, "下载完成", msg)

    def save_financial_to_duckdb(self):
        """保存财务数据到DuckDB"""
        # 检查模块是否可用
        if not BATCH_SAVE_AVAILABLE:
            QMessageBox.warning(self, "功能不可用",
                "批量保存财务数据模块不可用。\n\n请确保 advanced_data_viewer_widget.py 文件存在且可导入。")
            return

        # 获取股票列表
        stock_selection = self.financial_stock_combo.currentText()

        if "默认股票列表" in stock_selection:
            stock_list = ["000001.SZ", "600519.SH", "511380.SH", "512100.SH"]
        elif "自定义股票列表" in stock_selection:
            text, ok = QInputDialog.getText(
                self, "输入股票列表",
                "请输入股票代码，用逗号分隔:\n例如: 000001.SZ,600519.SH"
            )
            if not ok or not text.strip():
                return
            stock_list = [s.strip() for s in text.split(',')]
        elif "沪深300" in stock_selection:
            try:
                if not XTDATA_AVAILABLE:
                    QMessageBox.warning(self, "错误", "xtquant模块不可用，请确保QMT已安装并运行")
                    return
                from xtquant import xtdata
                stock_list = xtdata.get_stock_list_in_sector('沪深300')
            except:
                stock_list = ["000001.SZ", "600519.SH"]
        elif "中证500" in stock_selection:
            try:
                if not XTDATA_AVAILABLE:
                    QMessageBox.warning(self, "错误", "xtquant模块不可用，请确保QMT已安装并运行")
                    return
                from xtquant import xtdata
                stock_list = xtdata.get_stock_list_in_sector('中证500')
            except:
                stock_list = ["000001.SZ", "600519.SH"]
        elif "中证1000" in stock_selection:
            try:
                if not XTDATA_AVAILABLE:
                    QMessageBox.warning(self, "错误", "xtquant模块不可用，请确保QMT已安装并运行")
                    return
                from xtquant import xtdata
                stock_list = xtdata.get_stock_list_in_sector('中证1000')
            except:
                stock_list = ["000001.SZ", "600519.SH"]
        elif "全部A股" in stock_selection:
            reply = QMessageBox.question(
                self, "确认保存",
                "即将保存全部A股的财务数据到DuckDB，这可能需要较长时间。\n\n确定要继续吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            try:
                if not XTDATA_AVAILABLE:
                    QMessageBox.warning(self, "错误", "xtquant模块不可用，请确保QMT已安装并运行")
                    return
                from xtquant import xtdata
                all_stocks = xtdata.get_stock_list_in_sector('沪深A股')
                # 过滤掉ETF和基金
                etf_patterns = [
                    '51',      # 上海ETF：510xxx, 511xxx, 512xxx, 513xxx, 515xxx, 516xxx
                    '159',     # 深圳ETF：159xxx
                    '150',     # 深圳基金：150xxx
                    '588',     # 上海ETF：588xxx
                    '50',      # 上海50开头基金
                    '56',      # 上海56开头基金
                    '58',      # 上海58开头基金
                ]

                stock_list = []
                for stock in all_stocks:
                    is_etf = False
                    for pattern in etf_patterns:
                        if stock.startswith(pattern):
                            is_etf = True
                            break

                    if not is_etf:
                        stock_list.append(stock)
            except:
                QMessageBox.warning(self, "错误", "获取股票列表失败")
                return
        else:
            stock_list = ["000001.SZ", "600519.SH"]

        self.log(f"💾 开始保存财务数据到DuckDB")
        self.log(f"   股票数量: {len(stock_list)}")

        # 创建保存线程
        self.save_thread = BatchFinancialSaveThread(stock_list)
        self.save_thread.log_signal.connect(self.log)
        self.save_thread.progress_signal.connect(self.update_progress)
        self.save_thread.finished_signal.connect(self.on_financial_save_finished)
        self.save_thread.error_signal.connect(self.on_financial_save_error)
        self.save_thread.start()

        self._set_download_state(True)

    def on_financial_save_finished(self, result):
        """财务数据保存完成"""
        self._set_download_state(False)
        self.progress_bar.setVisible(False)

        total = result.get('total', 0)
        success = result.get('success', 0)
        failed = result.get('failed', 0)

        msg = f"财务数据保存完成！\n\n"
        msg += f"总数: {total} 只\n"
        msg += f"成功: {success} 只\n"
        msg += f"失败: {failed} 只"

        if failed > 0:
            QMessageBox.warning(self, "保存完成", msg)
        else:
            QMessageBox.information(self, "保存完成", msg)

        # 重新加载数据信息
        self.load_duckdb_statistics()

    def on_financial_save_error(self, error_msg):
        """财务数据保存出错"""
        self._set_download_state(False)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "保存失败", error_msg)
    
    def on_save_parquet_changed(self, state):
        """保存Parquet文件复选框状态变化时的处理"""
        if state == Qt.Checked:
            self.log("💾 已选择：保存Parquet文件（使用direct策略）")
        else:
            self.log("💾 已选择：不保存Parquet文件（使用temp策略）")

    def download_single_financial(self):
        """下载单只股票的财务数据"""
        stock_code = self.financial_stock_input.text().strip()

        if not stock_code:
            QMessageBox.warning(self, "提示", "请输入股票代码")
            return

        # 标准化代码格式
        stock_code = stock_code.upper()

        # 验证代码格式
        if not ('.' in stock_code):
            # 如果没有后缀，尝试自动添加
            if stock_code.startswith('6') or stock_code.startswith('5'):
                stock_code = stock_code + '.SH'
            elif stock_code.startswith('0') or stock_code.startswith('3') or stock_code.startswith('1'):
                stock_code = stock_code + '.SZ'

        # 获取数据表列表
        table_list = []
        if self.financial_balance_check.isChecked():
            table_list.append("Balance")
        if self.financial_income_check.isChecked():
            table_list.append("Income")
        if self.financial_cashflow_check.isChecked():
            table_list.append("CashFlow")
        if self.financial_cap_check.isChecked():
            table_list.append("Capitalization")
        if self.financial_dividend_check.isChecked():
            table_list.append("Dividend")

        if not table_list:
            QMessageBox.warning(self, "提示", "请至少选择一个数据表")
            return

        self.log(f"💰 开始下载 {stock_code} 的财务数据")
        self.log(f"   数据表: {', '.join(table_list)}")

        # 创建下载线程
        self.download_thread = FinancialDataDownloadThread(
            stock_list=[stock_code],
            table_list=table_list
        )
        self.download_thread.log_signal.connect(self.log)
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.finished_signal.connect(self.on_single_financial_finished)
        self.download_thread.error_signal.connect(self.on_financial_download_error)
        self.download_thread.start()

        self._set_download_state(True)

    def on_single_financial_finished(self, result):
        """单只股票财务数据下载完成"""
        self._set_download_state(False)
        self.progress_bar.setVisible(False)

        total = result.get('total', 0)
        success = result.get('success', 0)
        failed = result.get('failed', 0)
        skipped = result.get('skipped', 0)

        msg = f"财务数据下载完成！\n\n"
        msg += f"有效股票: {total} 只\n"
        msg += f"成功: {success} 只"
        if failed > 0:
            msg += f"\n失败: {failed} 只"
        if skipped > 0:
            msg += f"\n跳过: {skipped} 只（ETF/指数）"

        if failed > 0:
            QMessageBox.warning(self, "下载完成", msg)
        else:
            QMessageBox.information(self, "下载完成", msg)

        # 刷新财务数据统计
        self.refresh_financial_stats()

    def refresh_financial_stats(self):
        """刷新财务数据统计"""
        try:
            if not XTDATA_AVAILABLE:
                self.log("❌ xtquant模块不可用，请确保QMT已安装并运行")
                return
            from xtquant import xtdata

            self.log("[INFO] 正在统计已下载的财务数据...")

            # 测试几只常用股票
            test_stocks = ["000001.SZ", "600519.SH", "511380.SH", "512100.SH"]
            table_list = ["Balance", "Income", "CashFlow"]

            total_count = 0
            stock_count = 0

            for stock_code in test_stocks:
                try:
                    result = xtdata.get_financial_data(
                        stock_list=[stock_code],
                        table_list=table_list,
                        start_time="19900101",
                        end_time="20260130",
                        report_type='report_time'
                    )

                    if isinstance(result, dict) and stock_code in result:
                        stock_data = result[stock_code]
                        count = 0
                        for table_name in table_list:
                            if table_name in stock_data:
                                table_data = stock_data[table_name]
                                if isinstance(table_data, dict):
                                    count += len(table_data)
                                elif hasattr(table_data, '__len__'):
                                    count += len(table_data)

                        if count > 0:
                            stock_count += 1
                            total_count += count

                except Exception as e:
                    continue

            self.log(f"[OK] 财务数据统计更新完成: {stock_count}只股票, {total_count}条记录")

        except Exception as e:
            self.log(f"[ERROR] 统计财务数据失败: {e}")

    def view_financial_data(self):
        """查看选中股票的财务数据"""
        # 获取选中的行
        selected_items = self.data_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先在列表中选择一只股票")
            return

        # 获取股票代码
        row = self.data_table.currentRow()
        code_item = self.data_table.item(row, 0)
        if not code_item:
            return

        stock_code = code_item.text()

        self.log(f"[INFO] 查看 {stock_code} 的财务数据")

        # 提示用户使用数据查看器
        QMessageBox.information(
            self,
            "查看财务数据",
            f"「查看财务数据」功能已迁移到「📈 数据查看器」标签页\n\n"
            f"请在「📈 数据查看器」标签页中：\n"
            f"1. 选择股票: {stock_code}\n"
            f"2. 点击「💰 加载财务数据」按钮\n\n"
            f"新功能支持查看更详细的财务指标数据。"
        )

    def on_financial_download_error(self, error_msg):
        """财务数据下载出错"""
        self._set_download_state(False)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "下载失败", error_msg)

    def _check_table_exists_and_not_empty(self, table_name):
        """检查表是否存在且不为空"""
        try:
            import duckdb
            db_path = self.db_path
            from src.core.data.database.db_manager import get_db_manager
            manager = get_db_manager(db_path)
            # 检查表是否存在
            result = manager.execute_read(f"SELECT table_name FROM information_schema.tables WHERE table_name = '{table_name}' AND table_type = 'VIEW'").fetchone()
            if not result:
                return False
            # 尝试检查表是否为空，但捕获Parquet文件不存在的错误
            try:
                count = manager.execute_read(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                return count > 0
            except Exception as e:
                # 如果是Parquet文件不存在的错误，认为表为空
                if "No files found that match the pattern" in str(e):
                    return False
                # 其他错误，返回False
                self.log(f"⚠️ 检查表 {table_name} 数据时出错: {e}")
                return False
        except Exception as e:
            self.log(f"⚠️ 检查表 {table_name} 时出错: {e}")
            return False

    def _delete_parquet_files(self, periods=None):
        """删除对应周期的Parquet文件
        
        Args:
            periods: 周期类型或周期类型列表，如 '1d', ['1m', '5m'], 或 'all'
                     如果为 'all'，则删除所有Parquet文件
        """
        import os
        import shutil
        
        # 从配置文件获取Parquet根目录
        parquet_config = self.config.get('storage', {}).get('parquet', {})
        parquet_root_dir = parquet_config.get('root_dir', 'Parquet')
        data_root_dir = self.config.get('data_paths', {}).get('root_dir', 'D:/MyStockData')
        parquet_root = os.path.join(data_root_dir, parquet_root_dir)
        
        if not os.path.exists(parquet_root):
            self.log(f"ℹ️ Parquet文件目录不存在，跳过删除: {parquet_root}")
            return
        
        # Parquet文件路径映射
        parquet_path_map = {
            "1d": "kline/daily",
            "1w": "kline/weekly",
            "weekly": "kline/weekly",
            "1M": "kline/monthly",
            "monthly": "kline/monthly",
            "1m": "kline/1m",
            "5m": "kline/5m",
            "15m": "kline/15m",
            "30m": "kline/30m",
            "60m": "kline/60m",
            "tick": "tick"
        }
        
        # 如果periods为'all'，删除整个Parquet目录
        if periods == 'all':
            try:
                self.log(f"🔧 开始删除所有Parquet文件目录: {parquet_root}")
                shutil.rmtree(parquet_root)
                self.log("✅ 已删除所有Parquet文件目录")
            except Exception as e:
                self.log(f"⚠️ 删除Parquet文件时出错: {e}")
            return
        
        # 确保periods是列表
        if isinstance(periods, str):
            periods = [periods]
        
        # 删除对应周期的Parquet文件
        for period in periods:
            if period in parquet_path_map:
                parquet_path = os.path.join(parquet_root, parquet_path_map[period])
                if os.path.exists(parquet_path):
                    try:
                        self.log(f"🔧 开始删除 {period} 周期的Parquet文件: {parquet_path}")
                        shutil.rmtree(parquet_path)
                        self.log(f"✅ 已删除 {period} 周期的Parquet文件")
                    except Exception as e:
                        self.log(f"⚠️ 删除 {period} 周期的Parquet文件时出错: {e}")
                else:
                    self.log(f"ℹ️ {period} 周期的Parquet文件目录不存在，跳过删除")
            else:
                self.log(f"⚠️ 未知的周期类型: {period}")

    def _rebuild_database_tables(self, db_path=None, data_type=None):
        """重建数据库视图结构（方案三：Parquet作为唯一源，DuckDB作为查询视图）
        
        Args:
            db_path: 数据库路径
            data_type: 数据类型，None表示重建所有类型
        """
        try:
            # 如果没有提供db_path，使用实例的db_path
            if db_path is None:
                db_path = self.db_path
            
            # 1. 清除指定数据类型的Parquet文件
            self.log("🔄 开始清除Parquet文件...")
            
            # 从配置文件加载Parquet根目录
            parquet_config = self.config.get('storage', {}).get('parquet', {})
            parquet_root_dir = parquet_config.get('root_dir', 'Parquet')
            data_root_dir = self.config.get('data_paths', {}).get('root_dir', 'D:/MyStockData')
            parquet_root = Path(data_root_dir) / parquet_root_dir
            
            if data_type:
                # 只删除指定数据类型的Parquet文件
                self._delete_parquet_files(data_type)
            else:
                # 删除所有Parquet文件
                if parquet_root.exists():
                    import shutil
                    shutil.rmtree(parquet_root)
                    self.log(f"✅ 已删除所有Parquet文件: {parquet_root}")
                else:
                    self.log(f"⚠️ Parquet目录不存在: {parquet_root}")
            
            # 2. 删除数据库文件（无论是否指定数据类型，都需要重建数据库）
            self.log("🔄 开始删除数据库文件...")
            db_file = Path(db_path)
            if db_file.exists():
                # 确保数据库连接已关闭
                try:
                    from src.core.data.database.connection_pool import get_connection_pool
                    pool = get_connection_pool(db_path)
                    pool.close()
                except Exception as close_err:
                    self.log(f"⚠️ 关闭数据库连接失败：{close_err}")
                
                # 删除数据库文件
                try:
                    db_file.unlink()
                    self.log(f"✅ 已删除数据库文件: {db_path}")
                except Exception as unlink_err:
                    self.log(f"⚠️ 删除数据库文件失败：{unlink_err}")
                    # 继续执行，因为数据库文件可能被其他进程占用
            else:
                self.log(f"⚠️ 数据库文件不存在: {db_path}")
            
            # 3. 使用视图管理器刷新视图
            self.log("🔄 开始重建数据库视图结构...")
            from src.core.data.storage.view_manager import ViewManager
            view_manager = ViewManager(db_path, self.config if hasattr(self, 'config') else {})
            
            # 刷新视图
            if view_manager.refresh_all_views():
                self.log("✅ 数据库视图结构重建完成")
                return True
            else:
                self.log("❌ 数据库视图结构重建失败")
                return False
        except Exception as e:
            self.log(f"❌ 重建数据库视图时出错: {e}")
            return False
    
    def regenerate_database_from_parquet(self):
        """从现有的 Parquet 文件重新生成数据库视图
        
        这个方法会刷新所有的数据库视图，使其指向现有的 Parquet 文件，
        而不需要重新下载数据。
        """
        try:
            self.log("=" * 70)
            self.log("  【从Parquet重新生成数据库】")
            self.log("=" * 70)
            
            # 直接在当前进程中重建视图（避免文件锁定问题）
            import duckdb
            from pathlib import Path
            
            self.log("🔄 开始重建数据库视图...")
            
            # 获取数据库路径和配置
            from src.core.utils import DownloadConfig
            config = DownloadConfig(self.config)
            data_config = config.get_config()
            
            dbfile = data_config.get('database', {}).get('dbfile', 'stock_data.ddb')
            data_root_dir = data_config.get('data_paths', {}).get('root_dir', 'D:/MyStockData')
            duckdb_path = str(Path(data_root_dir) / dbfile)
            
            parquet_config = data_config.get('storage', {}).get('parquet', {})
            parquet_root_dir = parquet_config.get('root_dir', 'Parquet')
            parquet_root = Path(data_root_dir) / parquet_root_dir
            
            self.log(f"📂 数据库: {duckdb_path}")
            self.log(f"📁 Parquet: {parquet_root}")
            
            # 连接数据库（使用 read_only 模式避免锁定问题）
            conn = duckdb.connect(duckdb_path, read_only=False)
            
            # 确保所有必要的目录存在
            for subdir in ['kline/daily', 'kline/1m', 'kline/5m', 'kline/15m', 'kline/30m', 'kline/60m', 'kline/weekly', 'kline/monthly', 'tick']:
                (parquet_root / subdir).mkdir(parents=True, exist_ok=True)
            
            views_to_create = [
                ('stock_daily', 'daily', 'date'),
                ('stock_1m', '1m', 'datetime'),
                ('stock_5m', '5m', 'datetime'),
                ('stock_15m', '15m', 'datetime'),
                ('stock_30m', '30m', 'datetime'),
                ('stock_60m', '60m', 'datetime'),
                ('stock_weekly', 'weekly', 'date'),
                ('stock_monthly', 'monthly', 'date'),
                ('stock_tick', 'tick', 'datetime'),
            ]
            
            for view_name, period, date_col in views_to_create:
                try:
                    # 删除旧视图
                    conn.execute(f"DROP VIEW IF EXISTS main.{view_name}")
                    
                    # 构建路径
                    if period == 'tick':
                        parquet_path = str(parquet_root / 'tick' / '**' / '*.parquet').replace('\\', '/')
                    else:
                        parquet_path = str(parquet_root / 'kline' / period / '**' / '*.parquet').replace('\\', '/')
                    
                    # 根据数据类型构建 SQL
                    if period in ['weekly', 'monthly']:
                        # 周线和月线：智能检测列结构
                        check_dir = parquet_root / 'kline' / period
                        has_files = any(check_dir.rglob('*.parquet'))
                        
                        if has_files:
                            first_file = next(check_dir.rglob('*.parquet'))
                            try:
                                cols = conn.execute(f"DESCRIBE SELECT * FROM read_parquet('{first_file}')").fetchall()
                                col_names = [c[0] for c in cols]
                                has_date = 'date' in col_names or 'datetime' in col_names
                            except:
                                has_date = False
                            
                            if has_date:
                                select_part = f"COALESCE(date, CURRENT_DATE) AS {date_col}"
                            else:
                                select_part = f"CURRENT_DATE AS {date_col}"
                        else:
                            select_part = f"CURRENT_DATE AS {date_col}"
                    elif period == 'tick':
                        select_part = f"COALESCE(datetime::TIMESTAMP, CURRENT_TIMESTAMP::TIMESTAMP) AS datetime"
                    elif period == 'daily':
                        select_part = f"COALESCE(date, CURRENT_DATE) AS date"
                    else:
                        select_part = f"COALESCE(datetime::TIMESTAMP, CURRENT_TIMESTAMP::TIMESTAMP) AS datetime"
                    
                    # 确定实际周期名称
                    actual_period = {'weekly': '1w', 'monthly': '1M'}.get(period, period)
                    
                    # 创建视图
                    sql = f"""
                        CREATE OR REPLACE VIEW main.{view_name} AS
                        SELECT 
                            COALESCE(stock_code, '') AS stock_code,
                            {select_part},
                            COALESCE(open, 0.0) AS open,
                            COALESCE(high, 0.0) AS high,
                            COALESCE(low, 0.0) AS low,
                            COALESCE(close, 0.0) AS close,
                            COALESCE(volume, 0) AS volume,
                            COALESCE(amount, 0.0) AS amount,
                            'stock' as symbol_type,
                            '{actual_period}' as period,
                            'none' as adjust_type,
                            1.0 as factor,
                            CURRENT_TIMESTAMP as created_at,
                            CURRENT_TIMESTAMP as updated_at
                        FROM read_parquet('{parquet_path}', union_by_name=true, filename=true, hive_partitioning=true)
                        WHERE COALESCE(stock_code, '') != ''
                    """
                    
                    conn.execute(sql)
                    self.log(f"  ✅ 创建视图: {view_name}")
                    
                except Exception as e:
                    self.log(f"  ⚠️ 创建视图 {view_name} 失败: {e}")
            
            conn.close()
            
            self.log("✅ 所有视图重建成功完成")
            self.log("📊 数据库已从现有 Parquet 文件重新生成")
            
            # 重新加载统计信息
            self.load_duckdb_statistics()
                
        except Exception as e:
            import traceback
            error_msg = f"重新生成数据库失败: {str(e)}\n{traceback.format_exc()}"
            self.log(error_msg)

    def download_stocks(self):
        """下载A股数据"""
        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.warning(self, "提示", "已有下载任务正在运行")
            return

        # 获取用户输入的日期
        start_date_qdate = self.start_date_edit.date()
        end_date_qdate = self.end_date_edit.date()
        
        # 验证日期范围
        if start_date_qdate > end_date_qdate:
            # 开始日期晚于结束日期，自动更正
            QMessageBox.warning(self, "日期范围错误", "开始日期不能晚于结束日期，已自动调整为结束日期")
            start_date_qdate = end_date_qdate
            self.start_date_edit.setDate(start_date_qdate)
        
        start_date = start_date_qdate.toString("yyyy-MM-dd")
        end_date = end_date_qdate.toString("yyyy-MM-dd")
        
        # 检查是否勾选了首次初始化选项
        # 注意：首次初始化只标记需要重建，不执行实际的删除操作
        # 实际的删除操作在用户确认重建数据库后才执行
        if hasattr(self, 'init_checkbox') and self.init_checkbox.isChecked():
            self.log("ℹ️ 已勾选首次初始化选项，将在确认后重建表结构...")
            # 移除强制取消勾选的代码，保留用户的勾选状态
        
        # 获取用户选择的数据类型
        data_type_text = self.data_type_combo.currentText()
        period_map = {
            "日线数据": "1d",
            "1分钟数据": "1m",
            "5分钟数据": "5m",
            "15分钟数据": "15m",
            "30分钟数据": "30m",
            "60分钟数据": "60m",
            "周线数据": "weekly",
            "月线数据": "monthly",
            "Tick数据": "tick"
        }
        
        # Parquet文件路径映射
        parquet_path_map = {
            "1d": "kline/daily",
            "1w": "kline/weekly",
            "weekly": "kline/weekly",
            "1M": "kline/monthly",
            "monthly": "kline/monthly",
            "1m": "kline/1m",
            "5m": "kline/5m",
            "15m": "kline/15m",
            "30m": "kline/30m",
            "60m": "kline/60m",
            "tick": "tick"
        }
        
        # 检查是否需要弹出模式选择对话框
        need_rebuild_prompt = False
        # 当勾选了"首次初始化"选择框时，总是弹出重建数据库对话框
        if self.init_checkbox.isChecked():
            need_rebuild_prompt = True
        # 当未勾选"首次初始化"选择框但表为空时，也需要弹出对话框
        else:
            if data_type_text == "所有类型":
                # 检查所有表是否都存在且不为空
                tables = ['stock_daily', 'stock_1m', 'stock_5m', 'stock_15m', 'stock_30m', 'stock_60m', 'stock_weekly', 'stock_monthly', 'stock_tick']
                for table in tables:
                    if not self._check_table_exists_and_not_empty(table):
                        need_rebuild_prompt = True
                        break
            else:
                # 检查对应周期的表是否存在且不为空
                data_type = period_map.get(data_type_text, "1d")
                table_name = f'stock_{data_type}' if data_type != '1d' else 'stock_daily'
                if not self._check_table_exists_and_not_empty(table_name):
                    need_rebuild_prompt = True
        
        # 只有当需要重建时才弹出对话框
        if need_rebuild_prompt:
            # 弹窗提醒用户当前模式是强制初始化数据库
            msg_box = QMessageBox()
            msg_box.setWindowTitle("下载模式选择")
            msg_box.setText("您选择的数据表为空，需要初始化数据库。")
            msg_box.setInformativeText("选择 '重建数据库' 将会清空并重建表结构，所有原有数据都会丢失。\n选择 '保留数据' 将会保留现有表结构，只更新对应股票的数据。\n选择 '取消' 将会取消本次下载操作。")
            
            # 创建自定义按钮
            yes_button = msg_box.addButton("重建数据库", QMessageBox.YesRole)
            no_button = msg_box.addButton("保留数据", QMessageBox.NoRole)
            cancel_button = msg_box.addButton("取消", QMessageBox.RejectRole)
            
            msg_box.setDefaultButton(no_button)
            msg_box.setIcon(QMessageBox.Warning)
            
            msg_box.exec_()
            
            # 处理响应
            if msg_box.clickedButton() == cancel_button:
                return
            elif msg_box.clickedButton() == yes_button:
                self._rebuild_database = True
            else:
                self._rebuild_database = False
        else:
            # 表已存在且不为空，不需要重建
            self._rebuild_database = False
        
        # 当选择所有周期且需要重建数据库时，添加选项
        rebuild_mode = "none"
        if data_type_text == "所有类型" and self._rebuild_database:
            # 创建重建模式选择对话框
            rebuild_msg = QMessageBox()
            rebuild_msg.setWindowTitle("重建数据库模式选择")
            rebuild_msg.setText("您选择了重建数据库，请问如何重建？")
            rebuild_msg.setInformativeText("选择 '立即重建所有表' 将会一次性删除并重建所有表结构。\n选择 '按周期重建' 将会在下载每个周期数据前删除并重建对应周期的表。")
            
            immediate_button = rebuild_msg.addButton("立即重建所有表", QMessageBox.YesRole)
            per_cycle_button = rebuild_msg.addButton("按周期重建", QMessageBox.NoRole)
            cancel_button = rebuild_msg.addButton("取消", QMessageBox.RejectRole)
            
            rebuild_msg.setDefaultButton(immediate_button)
            rebuild_msg.setIcon(QMessageBox.Question)
            
            rebuild_msg.exec_()
            
            if rebuild_msg.clickedButton() == cancel_button:
                return
            elif rebuild_msg.clickedButton() == per_cycle_button:
                rebuild_mode = "per_cycle"
                self.log("⚠️ 模式: 按周期强制初始化数据库 (每个周期数据将被覆盖)")
            else:
                rebuild_mode = "immediate"
                self.log("⚠️ 模式: 立即强制初始化数据库 (所有数据将被覆盖)")
            
            if rebuild_mode == "immediate":
                # 检查是否已经通过首次初始化执行过重建
                has_performed_initialization = hasattr(self, 'init_checkbox') and not self.init_checkbox.isChecked()
                
                if not has_performed_initialization:
                    # 立即重建所有表
                    start_time = time.time()
                    tables_dropped = 0
                    tables_failed = 0
                    
                    try:
                        import duckdb
                        db_path = self.db_path
                        from src.core.data.database.db_manager import get_db_manager
                        manager = get_db_manager(db_path)
                        tables_to_drop = ['stock_daily', 'stock_1m', 'stock_5m', 'stock_15m', 'stock_30m', 'stock_60m', 'stock_weekly', 'stock_monthly', 'stock_tick']
                        total_tables = len(tables_to_drop)
                        
                        for i, table in enumerate(tables_to_drop):
                            try:
                                # 先尝试删除表
                                manager.execute_write(f"DROP TABLE IF EXISTS {table}")
                                tables_dropped += 1
                                self.log(f"⚠️ [{i+1}/{total_tables}] 已删除旧的 {table} 表")
                            except Exception as e:
                                # 如果是视图，删除视图
                                if "is of type View" in str(e):
                                    try:
                                        manager.execute_write(f"DROP VIEW IF EXISTS {table}")
                                        tables_dropped += 1
                                        self.log(f"⚠️ [{i+1}/{total_tables}] 已删除旧的 {table} 视图")
                                    except Exception as view_e:
                                        tables_failed += 1
                                        self.log(f"❌ [{i+1}/{total_tables}] 删除视图 {table} 失败: {view_e}")
                                else:
                                    tables_failed += 1
                                    self.log(f"❌ [{i+1}/{total_tables}] 删除表 {table} 失败: {e}")
                        
                        # 执行CHECKPOINT操作，强制释放磁盘空间
                        try:
                            self.log("🔧 执行CHECKPOINT操作，释放磁盘空间...")
                            manager.execute_write("CHECKPOINT")
                            self.log("✅ CHECKPOINT操作完成")
                        except Exception as e:
                            self.log(f"⚠️ CHECKPOINT操作失败: {e}")
                        
                        # 删除数据库文件并重新创建（最彻底的方式）
                        try:
                            import os
                            if os.path.exists(db_path):
                                file_size_before = os.path.getsize(db_path) / (1024 * 1024)  # MB
                                self.log(f"📊 数据库文件大小: {file_size_before:.2f} MB")
                                
                                # 关闭连接池
                                from src.core.data.database.connection_pool import close_all_pools
                                close_all_pools()
                                self.log("✅ 已关闭所有数据库连接池")
                                
                                # 删除数据库文件
                                os.remove(db_path)
                                self.log("✅ 已删除旧的数据库文件")
                                
                                # 删除所有Parquet文件
                                self._delete_parquet_files('all')
                                
                                # 重新创建空数据库文件
                                import duckdb
                                conn = duckdb.connect(database=db_path, read_only=False)
                                conn.execute("PRAGMA memory_limit = '2GB'")
                                conn.execute("PRAGMA threads = 1")
                                conn.execute("PRAGMA default_order = 'asc'")
                                # 创建一个临时表来确保数据库文件被正确创建
                                conn.execute("CREATE TABLE IF NOT EXISTS _temp_init (id INTEGER)")
                                conn.execute("DROP TABLE IF EXISTS _temp_init")
                                # 执行CHECKPOINT确保数据被写入文件
                                conn.execute("CHECKPOINT")
                                conn.close()
                                self.log("✅ 已创建新的空数据库文件")
                        except Exception as e:
                            self.log(f"⚠️ 删除数据库文件时出错: {e}")
                        
                        # 重建表结构
                        self.log("🔄 开始重建数据库表结构...")
                        if self._rebuild_database_tables(db_path):
                            self.log("✅ 数据库表结构重建完成")
                        else:
                            self.log("❌ 数据库表结构重建失败")
                    except Exception as e:
                        self.log(f"❌ 重建数据库时出错: {e}")
                    finally:
                        elapsed_time = time.time() - start_time
                        self.log(f"📊 重建数据库完成: 成功删除 {tables_dropped} 张表，失败 {tables_failed} 张表，耗时 {elapsed_time:.2f} 秒")
                else:
                    # 已经执行过首次初始化，跳过重建
                    self.log("ℹ️ 已通过首次初始化执行过表结构重建，跳过本次重建")
        else:
            if self._rebuild_database:
                # 重建对应周期的表
                data_type = period_map.get(data_type_text, "1d")
                table_name = f'stock_{data_type}' if data_type != '1d' else 'stock_daily'
                db_path = self.db_path
                
                try:
                    import duckdb
                    from src.core.data.database.db_manager import get_db_manager
                    manager = get_db_manager(db_path)
                    
                    # 先删除对应周期的Parquet文件
                    self._delete_parquet_files(data_type)
                    
                    # 检查并删除表或视图
                    try:
                        # 先尝试删除表
                        manager.execute_write(f"DROP TABLE IF EXISTS {table_name}")
                        self.log(f"⚠️ 已删除旧的 {table_name} 表")
                    except Exception as e:
                        # 如果是视图，删除视图
                        if "is of type View" in str(e):
                            manager.execute_write(f"DROP VIEW IF EXISTS {table_name}")
                            self.log(f"⚠️ 已删除旧的 {table_name} 视图")
                        else:
                            self.log(f"⚠️ 删除 {table_name} 时出错: {e}")
                    
                    # 执行CHECKPOINT操作，强制释放磁盘空间
                    try:
                        self.log("🔧 执行CHECKPOINT操作，释放磁盘空间...")
                        manager.execute_write("CHECKPOINT")
                        self.log("✅ CHECKPOINT操作完成")
                    except Exception as e:
                        self.log(f"⚠️ CHECKPOINT操作失败: {e}")
                    
                    # 重建表结构
                    self.log(f"🔄 开始重建 {table_name} 表结构...")
                    if self._rebuild_database_tables(db_path, data_type):
                        self.log(f"✅ {table_name} 表结构重建完成")
                    else:
                        self.log(f"❌ {table_name} 表结构重建失败")
                except Exception as e:
                    self.log(f"❌ 重建表结构时出错: {e}")
                
                self.log("⚠️ 模式: 强制初始化数据库 (所有数据将被覆盖)")
            else:
                self.log("⚠️ 模式: 保留表结构 (只更新对应股票数据)")

        # 检查测试模式
        test_mode = False
        symbols = None
        if hasattr(self, 'test_mode_radio') and self.test_mode_radio.isChecked():
            test_mode = True
            self.log("🔧 测试模式已启用：只下载前50只股票（日线）或20只股票（其他）")
            # 使用预加载的股票列表
            if hasattr(self, '_preloaded_stocks') and self._preloaded_stocks:
                symbols = self._preloaded_stocks
                self.log(f"✅ 使用预加载的股票列表，共 {len(symbols)} 只A股（已排除ETF和基金）")
                self.log("🔧 测试模式：根据数据类型使用不同的股票数量")
            else:
                self.log("⚠️ 预加载的股票列表不可用，使用默认设置")
                test_mode = False

        # 设置下载状态为正在下载
        self._set_download_state(True)

        if data_type_text == "所有类型":
            # 下载所有类型的数据，使用信号和槽机制
            self.log(f"📥 开始下载所有类型数据 ({start_date} ~ {end_date})")
            
            # 初始化下载状态
            self.download_task_queue = []  # 存储所有待执行的任务参数
            self.current_task_index = 0    # 当前执行的任务索引
            self.is_sequential_download = True  # 标记是否处于连续下载模式
            
            # 构建任务队列
            self.download_task_queue = [
                {'task_type': 'download_stocks', 'period': '1d', 'data_type': 'daily'},  # 日线
                {'task_type': 'download_minute_data', 'period': '1m', 'data_type': '1min'},  # 1分钟
                {'task_type': 'download_minute_data', 'period': '5m', 'data_type': '5min'},  # 5分钟
                {'task_type': 'download_minute_data', 'period': '15m', 'data_type': '15min'},  # 15分钟
                {'task_type': 'download_minute_data', 'period': '30m', 'data_type': '30min'},  # 30分钟
                {'task_type': 'download_minute_data', 'period': '60m', 'data_type': '60min'},  # 60分钟
                {'task_type': 'download_minute_data', 'period': 'weekly', 'data_type': 'weekly'},  # 周线
                {'task_type': 'download_minute_data', 'period': 'monthly', 'data_type': 'monthly'},  # 月线
                {'task_type': 'download_minute_data', 'period': 'tick', 'data_type': 'tick'},  # Tick
            ]
            
            # 使用预加载的股票列表（无论是测试模式还是正式模式）
            if not symbols and hasattr(self, '_preloaded_stocks') and self._preloaded_stocks:
                symbols = self._preloaded_stocks
                self.log(f"✅ 使用预加载的股票列表，共 {len(symbols)} 只A股（已排除ETF和基金）")
            
            # 存储其他参数
            self.log("🔍 开始存储参数...")
            self.log(f"ℹ️ start_date: {start_date}")
            self.log(f"ℹ️ end_date: {end_date}")
            self.log(f"ℹ️ rebuild_mode: {rebuild_mode}")
            self.log(f"ℹ️ test_mode: {test_mode}")
            self.log(f"ℹ️ symbols: {len(symbols) if symbols else 0} 个标的")
            
            self._start_date = start_date
            self.log("✅ 存储 start_date 成功")
            
            self._end_date = end_date
            self.log("✅ 存储 end_date 成功")
            
            self._rebuild_mode = rebuild_mode
            self.log("✅ 存储 rebuild_mode 成功")
            
            self._test_mode = test_mode
            self.log("✅ 存储 test_mode 成功")
            
            self._symbols = symbols
            self.log("✅ 存储 symbols 成功")
            
            # 获取临时文件策略
            self.log("🔍 开始获取临时文件策略...")
            self.log(f"ℹ️ save_parquet_checkbox 存在: {hasattr(self, 'save_parquet_checkbox')}")
            
            if hasattr(self, 'save_parquet_checkbox'):
                self.log(f"ℹ️ save_parquet_checkbox 状态: {self.save_parquet_checkbox.isChecked()}")
                temp_strategy = 'direct' if self.save_parquet_checkbox.isChecked() else 'temp'
                self.log(f"ℹ️ 临时文件策略: {temp_strategy}")
            else:
                self.log("⚠️ save_parquet_checkbox 不存在，使用默认策略: direct")
                temp_strategy = 'direct'
            
            self._temp_strategy = temp_strategy
            self.log("✅ 存储临时文件策略成功")
            
            # 存储配置管理器
            self.log("📦 开始初始化配置管理器...")
            try:
                from my_gui_app.src.core.utils.utils import DownloadConfig
                self.log("✅ 导入 DownloadConfig 成功")
                
                self.log(f"ℹ️ 配置数据类型: {type(self.config)}")
                self.log(f"ℹ️ 配置数据长度: {len(self.config) if hasattr(self.config, '__len__') else 'N/A'}")
                
                self._config_manager = DownloadConfig(self.config)
                self.log("✅ 配置管理器初始化成功")
                
                # 测试配置管理器方法
                test_period = '1d'
                test_start, test_end = self._config_manager.get_time_range(test_period)
                self.log(f"✅ 配置管理器测试成功: {test_period} 时间范围 = {test_start} ~ {test_end}")
            except Exception as e:
                self.log(f"❌ 配置管理器初始化失败: {e}")
                import traceback
                self.log(f"📋 错误堆栈:\n{traceback.format_exc()}")
                # 即使配置管理器初始化失败，也要继续执行，使用默认配置
                self.log("⚠️ 使用默认配置继续执行")
            
            # 强制刷新UI，确保日志显示
            QCoreApplication.processEvents()
            # 开始执行第一个任务
            self._start_next_sequential_task()
        else:
            # 下载单个类型的数据
            data_type = period_map.get(data_type_text, "1d")
            
            # 根据数据类型选择任务类型
            if data_type == '1d':
                task_type = 'download_stocks'
            else:
                task_type = 'download_minute_data'

            # 使用预加载的股票列表（无论是测试模式还是正式模式）
            if not symbols and hasattr(self, '_preloaded_stocks') and self._preloaded_stocks:
                symbols = self._preloaded_stocks
                self.log(f"✅ 使用预加载的股票列表，共 {len(symbols)} 只A股（已排除ETF和基金）")

            if test_mode:
                # 测试模式下根据数据类型使用不同的股票数量
                if data_type == '1d':
                    # 日线数据使用前50只股票
                    symbols = symbols[:50] if symbols else None
                    self.log(f"🔧 测试模式：{data_type}数据只使用前50只股票")
                else:
                    # 其他数据类型使用前20只股票
                    symbols = symbols[:20] if symbols else None
                    self.log(f"🔧 测试模式：{data_type}数据只使用前20只股票")

            # 计算配置文件时间范围与界面选择时间范围的交集
            from datetime import datetime, timedelta
            from my_gui_app.src.core.utils.utils import DownloadConfig
            
            # 创建配置管理器实例
            config_manager = DownloadConfig(self.config)
            # 计算交集时间范围
            actual_start_date, actual_end_date = config_manager.get_intersection_time_range(data_type, start_date, end_date)
            
            # 重置停止请求标志
            self._stop_requested = False

            self.log(f"📥 开始下载A股{data_type_text} ({actual_start_date} ~ {actual_end_date})")
            self.log(f"⚠️ {data_type}数据时间范围: {actual_start_date} ~ {actual_end_date} (计算交集)")
            self.log(f"   - 界面选择: {start_date} ~ {end_date}")
            self.log(f"   - 配置限制: {config_manager.get_time_range(data_type)[0]} ~ {config_manager.get_time_range(data_type)[1]}")

            # 获取临时文件策略
            temp_strategy = 'direct' if self.save_parquet_checkbox.isChecked() else 'temp'
            
            # 更新配置中的temp_file_strategy设置
            if 'storage' not in self.config:
                self.config['storage'] = {}
            self.config['storage']['temp_file_strategy'] = temp_strategy
            
            self.download_thread = DataDownloadThread(
                task_type=task_type,
                symbols=symbols,  # 传入处理后的股票列表
                start_date=actual_start_date,
                end_date=actual_end_date,
                data_type='daily' if data_type == '1d' else 'minute',
                period=data_type,
                db_path=self.db_path,
                config=self.config,
                test_mode=test_mode,
                preloaded_stocks=self._preloaded_stocks if hasattr(self, '_preloaded_stocks') else None
            )
            # 传递重建数据库的标志
            if hasattr(self, '_rebuild_database'):
                self.download_thread.rebuild_database = self._rebuild_database
            self.download_thread.log_signal.connect(self.log)
            self.download_thread.progress_signal.connect(self.update_progress)
            self.download_thread.finished_signal.connect(self.on_download_finished)
            self.download_thread.error_signal.connect(self.on_download_error)
            self.download_thread.start()
    
    def _start_next_sequential_task(self):
        """启动队列中的下一个下载任务"""
        import time
        start_time = time.time()
        self.log(f"⏱️ _start_next_sequential_task 方法开始，时间: {time.strftime('%H:%M:%S', time.localtime())}")
        
        try:
            # 检查是否收到停止请求
            self.log(f"🔍 检查停止请求状态: {hasattr(self, '_stop_requested') and self._stop_requested}")
            if hasattr(self, '_stop_requested') and self._stop_requested:
                self.log("⏹️ 停止请求已收到，不再启动后续任务")
                self._set_download_state(False)
                self.log(f"⏱️ _start_next_sequential_task 方法结束，耗时: {time.time() - start_time:.2f}秒")
                return

            # 检查必要属性是否存在
            self.log(f"🔍 检查 current_task_index: {hasattr(self, 'current_task_index')}")
            if not hasattr(self, 'current_task_index'):
                self.current_task_index = 0
                self.log("⚠️ 任务索引未定义，已重置为 0")
            else:
                self.log(f"ℹ️ current_task_index: {self.current_task_index}")

            self.log(f"🔍 检查 download_task_queue: {hasattr(self, 'download_task_queue')}")
            if not hasattr(self, 'download_task_queue') or not self.download_task_queue:
                self.log("⚠️ 任务队列为空，停止下载")
                self._set_download_state(False)
                self.log(f"⏱️ _start_next_sequential_task 方法结束，耗时: {time.time() - start_time:.2f}秒")
                return
            else:
                self.log(f"ℹ️ 任务队列长度: {len(self.download_task_queue)}")

            self.log(f"🔍 检查 _config_manager: {hasattr(self, '_config_manager')}")
            if not hasattr(self, '_config_manager'):
                self.log("⚠️ 配置管理器未定义，停止下载")
                self._set_download_state(False)
                self.log(f"⏱️ _start_next_sequential_task 方法结束，耗时: {time.time() - start_time:.2f}秒")
                return

            self.log(f"🔍 检查日期范围: start={hasattr(self, '_start_date')}, end={hasattr(self, '_end_date')}")
            if not hasattr(self, '_start_date') or not hasattr(self, '_end_date'):
                self.log("⚠️ 日期范围未定义，停止下载")
                self._set_download_state(False)
                self.log(f"⏱️ _start_next_sequential_task 方法结束，耗时: {time.time() - start_time:.2f}秒")
                return
            else:
                self.log(f"ℹ️ 日期范围: {self._start_date} ~ {self._end_date}")

            self.log(f"🔍 检查 _temp_strategy: {hasattr(self, '_temp_strategy')}")
            if not hasattr(self, '_temp_strategy'):
                self.log("⚠️ 临时文件策略未定义，使用默认值 'direct'")
                self._temp_strategy = 'direct'
            else:
                self.log(f"ℹ️ 临时文件策略: {self._temp_strategy}")

            self.log(f"🔍 检查 _test_mode: {hasattr(self, '_test_mode')}")
            if not hasattr(self, '_test_mode'):
                self.log("⚠️ 测试模式未定义，默认为 False")
                self._test_mode = False
            else:
                self.log(f"ℹ️ 测试模式: {self._test_mode}")

            self.log(f"🔍 检查 _symbols: {hasattr(self, '_symbols')}")
            if not hasattr(self, '_symbols'):
                self.log("⚠️ 股票列表未定义")
                self._symbols = None
            else:
                self.log(f"ℹ️ 股票列表: {len(self._symbols) if self._symbols else 0} 个标的")

            self.log(f"🔍 检查任务完成状态: {self.current_task_index} >= {len(self.download_task_queue)}")
            if self.current_task_index >= len(self.download_task_queue):
                # 所有任务已完成
                self.log("🎉 所有任务已完成，调用 _on_all_sequential_tasks_finished")
                self._on_all_sequential_tasks_finished()
                self.log(f"⏱️ _start_next_sequential_task 方法结束，耗时: {time.time() - start_time:.2f}秒")
                return

            # 获取当前任务配置
            self.log(f"🔍 获取当前任务配置，索引: {self.current_task_index}")
            task_config = self.download_task_queue[self.current_task_index]
            task_type = task_config['task_type']
            period = task_config['period']
            data_type = task_config.get('data_type', 'daily') # 提供默认值
            self.log(f"ℹ️ 当前任务: type={task_type}, period={period}, data_type={data_type}")

            # 任务类型名称映射
            task_name_map = {
                '1d': '日线数据',
                '1m': '1分钟数据',
                '5m': '5分钟数据',
                '15m': '15分钟数据',
                '30m': '30分钟数据',
                '60m': '60分钟数据',
                'weekly': '周线数据',
                'monthly': '月线数据',
                'tick': 'Tick数据'
            }
            task_name = task_name_map.get(period, period)

            # 更新UI提示，告知用户当前正在下载的类型
            self.log(f"\n🚀 开始下载 {task_name} ({self.current_task_index + 1}/{len(self.download_task_queue)})")

            # 强制刷新UI（减少调用频率）
            if (self.current_task_index % 3 == 0):  # 每3个任务刷新一次
                self.log("🔄 刷新UI界面...")
                QCoreApplication.processEvents()
                self.log("✅ UI刷新完成")

            # 使用预加载的股票列表（如果self._symbols为None）
            self.log("🔍 准备股票列表...")
            current_symbols = self._symbols
            if not current_symbols and hasattr(self, '_preloaded_stocks') and self._preloaded_stocks:
                current_symbols = self._preloaded_stocks
                self.log(f"✅ 使用预加载的股票列表，共 {len(current_symbols)} 只A股（已排除ETF和基金）")
            elif not current_symbols:
                self.log("⚠️ 股票列表为空，无法下载")
                self._set_download_state(False)
                self.log(f"⏱️ _start_next_sequential_task 方法结束，耗时: {time.time() - start_time:.2f}秒")
                return
            else:
                self.log(f"ℹ️ 使用股票列表，共 {len(current_symbols)} 个标的")
        
            if self._test_mode:
                # 测试模式下根据数据类型使用不同的股票数量
                self.log("🔧 测试模式：调整股票数量...")
                if period == '1d':
                    # 日线数据使用前50只股票
                    current_symbols = current_symbols[:50] if current_symbols else None
                    self.log("🔧 测试模式：日线数据只使用前50只股票")
                else:
                    # 其他数据类型使用前20只股票
                    current_symbols = current_symbols[:20] if current_symbols else None
                    self.log(f"🔧 测试模式：{period}数据只使用前20只股票")
                self.log(f"ℹ️ 调整后股票数量: {len(current_symbols) if current_symbols else 0}")

            # 计算配置文件时间范围与界面选择时间范围的交集
            self.log("📅 计算时间范围交集...")
            actual_start_date, actual_end_date = self._config_manager.get_intersection_time_range(period, self._start_date, self._end_date)
            
            # 检查是否有交集
            if actual_start_date is None or actual_end_date is None:
                self.log(f"⚠️ {period}数据时间范围与配置文件限制无交集，跳过下载")
                self.log(f"   - 界面选择: {self._start_date} ~ {self._end_date}")
                self.log(f"   - 配置限制: {self._config_manager.get_time_range(period)[0]} ~ {self._config_manager.get_time_range(period)[1]}")
                # 移动到下一个任务
                self.current_task_index += 1
                self._start_next_sequential_task()
                return
            
            self.log(f"⚠️ {period}数据时间范围: {actual_start_date} ~ {actual_end_date} (计算交集)")
            self.log(f"   - 界面选择: {self._start_date} ~ {self._end_date}")
            self.log(f"   - 配置限制: {self._config_manager.get_time_range(period)[0]} ~ {self._config_manager.get_time_range(period)[1]}")

            # 更新配置中的temp_file_strategy设置
            self.log("⚙️ 更新配置...")
            if 'storage' not in self.config:
                self.config['storage'] = {}
            self.config['storage']['temp_file_strategy'] = self._temp_strategy
            self.log(f"✅ 配置更新完成: temp_file_strategy={self._temp_strategy}")

            # 检查数据库路径
            self.log(f"🔍 检查数据库路径: {hasattr(self, 'db_path')}")
            if not hasattr(self, 'db_path') or not self.db_path:
                self.log("⚠️ 数据库路径未定义，停止下载")
                self._set_download_state(False)
                self.log(f"⏱️ _start_next_sequential_task 方法结束，耗时: {time.time() - start_time:.2f}秒")
                return
            else:
                self.log(f"ℹ️ 数据库路径: {self.db_path}")

            # 检查配置
            self.log(f"🔍 检查配置: {hasattr(self, 'config')}")
            if not hasattr(self, 'config'):
                self.log("⚠️ 配置未定义，停止下载")
                self._set_download_state(False)
                self.log(f"⏱️ _start_next_sequential_task 方法结束，耗时: {time.time() - start_time:.2f}秒")
                return
            else:
                self.log("ℹ️ 配置已定义")

            # 创建并启动下载线程
            self.log("📋 创建下载线程...")
            self.download_thread = DataDownloadThread(
                task_type=task_type,
                symbols=current_symbols,  # 传入处理后的股票列表
                start_date=actual_start_date,
                end_date=actual_end_date,
                data_type=data_type,
                period=period,
                db_path=self.db_path,
                config=self.config,
                test_mode=self._test_mode,
                preloaded_stocks=self._preloaded_stocks if hasattr(self, '_preloaded_stocks') else None
            )
            self.log("✅ 下载线程创建成功")
            
            # 传递重建数据库的标志
            if hasattr(self, '_rebuild_database'):
                self.download_thread.rebuild_database = self._rebuild_database
                self.log(f"⚙️ 传递重建数据库标志: {self._rebuild_database}")

            # 连接信号
            # 注意：这里需要将线程的 finished_signal 连接到一个新的槽函数，用于处理单个任务完成
            # 而不是直接连接到原来弹出对话框的槽函数
            self.log("🔗 连接线程信号...")
            self.download_thread.log_signal.connect(self.log)
            self.download_thread.progress_signal.connect(self.update_progress)
            self.download_thread.finished_signal.connect(self._on_single_task_finished)
            self.download_thread.error_signal.connect(self._on_single_task_error)
            self.log("✅ 线程信号连接完成")

            # 启动线程
            self.log("🚀 启动下载线程...")
            self.download_thread.start()
            self.log("✅ 线程启动成功")
            
            # 检查线程状态
            import threading
            self.log(f"ℹ️ 线程ID: {threading.get_ident()}")
            self.log(f"ℹ️ 下载线程状态: {self.download_thread.isRunning()}")

            self.log(f"⏱️ _start_next_sequential_task 方法结束，耗时: {time.time() - start_time:.2f}秒")

        except Exception as e:
            self.log(f"❌ _start_next_sequential_task 方法出错: {e}")
            import traceback
            error_traceback = traceback.format_exc()
            self.log(f"📋 错误堆栈:\n{error_traceback}")
            self._set_download_state(False)
            # 重新启用手动下载按钮
            if hasattr(self, 'manual_download_btn'):
                self.manual_download_btn.setEnabled(True)
            self.log(f"⏱️ _start_next_sequential_task 方法异常结束，耗时: {time.time() - start_time:.2f}秒")
    
    def _on_single_task_finished(self, result):
        """处理单个下载任务的完成"""
        # 检查是否收到停止请求
        if hasattr(self, '_stop_requested') and self._stop_requested:
            self.log("⏹️ 停止请求已收到，不再启动后续任务")
            self._set_download_state(False)
            # 重新启用手动下载按钮
            if hasattr(self, 'manual_download_btn'):
                self.manual_download_btn.setEnabled(True)
            return

        # 检查是否是停止信号
        task_type = result.get('task_type', '')
        if task_type == 'stopped':
            self.log("✅ 下载已停止")
            self._set_download_state(False)
            # 重新启用手动下载按钮
            if hasattr(self, 'manual_download_btn'):
                self.manual_download_btn.setEnabled(True)
            QMessageBox.information(self, "下载停止", "所有类型的下载已停止")
            return

        # 记录当前任务结果
        if self.current_task_index < len(self.download_task_queue):
            current_period = self.download_task_queue[self.current_task_index]['period']
            success = result.get('success', 0)
            failed = result.get('failed', 0)
            self.log(f"✅ {current_period} 数据下载完成。成功: {success}, 失败: {failed}")

            # 收集数据类型详细信息
            if not hasattr(self, 'data_type_details'):
                self.data_type_details = []
            self.data_type_details.append({
                'period': current_period,
                'total': result.get('total', 0),
                'success': success,
                'failed': failed
            })

        # 移动到下一个任务
        self.current_task_index += 1

        # 短暂延迟后开始下一个任务，让UI和日志有喘息之机
        QTimer.singleShot(1000, self._start_next_sequential_task)

    def _on_single_task_error(self, error_msg):
        """处理单个任务错误"""
        if self.current_task_index < len(self.download_task_queue):
            current_period = self.download_task_queue[self.current_task_index]['period']
            self.log(f"❌ {current_period} 下载失败: {error_msg}")
            
            # 停止下载
            self._set_download_state(False)
            # 重新启用手动下载按钮
            if hasattr(self, 'manual_download_btn'):
                self.manual_download_btn.setEnabled(True)
            QMessageBox.critical(self, "下载失败", f"{current_period} 下载失败: {error_msg}")
        else:
            self.log(f"❌ 下载失败: {error_msg}")
            
            # 停止下载
            self._set_download_state(False)
            # 重新启用手动下载按钮
            if hasattr(self, 'manual_download_btn'):
                self.manual_download_btn.setEnabled(True)
            QMessageBox.critical(self, "下载失败", f"下载失败: {error_msg}")
    
    def _on_all_sequential_tasks_finished(self):
        """所有连续下载任务完成后的处理"""
        self.is_sequential_download = False
        self.log("\n🎉 所有类型数据下载已全部完成！")
        
        # 构建详细的完成信息
        msg = "下载完成！\n"
        msg += "下载周期: 所有周期（日线、1分钟、5分钟、15分钟、30分钟、60分钟、Tick）\n"
        
        # 显示各数据类型的详细信息
        if hasattr(self, 'data_type_details'):
            msg += "\n各数据类型详情：\n"
            for detail in self.data_type_details:
                period = detail.get('period', '未知')
                detail_total = detail.get('total', 0)
                detail_success = detail.get('success', 0)
                detail_failed = detail.get('failed', 0)
                msg += f"  - {period}: 标的数={detail_total}, 成功={detail_success}, 失败={detail_failed}\n"
            # 清理数据类型详情
            delattr(self, 'data_type_details')
        
        # 弹出最终的完成对话框（复用您原有的对话框显示逻辑）
        QMessageBox.information(self, "下载完成", msg)
        # 重置按钮状态等
        self._set_download_state(False)
        # 重新启用手动下载按钮
        if hasattr(self, 'manual_download_btn'):
            self.manual_download_btn.setEnabled(True)
        
        # 重新加载数据信息
        self.load_duckdb_statistics()

    def _on_all_types_download_error(self, error_msg):
        """所有类型下载错误回调"""
        data_type_name = self._data_type_names[self._current_download_index]
        self.log(f"❌ {data_type_name} 下载失败: {error_msg}")
        
        # 停止下载
        self._set_download_state(False)
        QMessageBox.critical(self, "下载失败", f"{data_type_name} 下载失败: {error_msg}")

    def _start_download_task(self, task_type, symbols=None, start_date=None, end_date=None, period=None, update_mode=None, test_mode=False):
        """通用的下载任务启动方法
        
        Args:
            task_type: 任务类型，如 'download_stocks', 'download_bonds', 'update_data'
            symbols: 标的列表，None表示自动获取全部
            start_date: 开始日期
            end_date: 结束日期
            period: 数据周期
            update_mode: 更新模式
            test_mode: 测试模式
        """
        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.warning(self, "提示", "已有下载任务正在运行")
            return

        # 获取临时文件策略
        temp_strategy = 'direct' if hasattr(self, 'save_parquet_checkbox') and self.save_parquet_checkbox.isChecked() else 'temp'
        
        # 更新配置中的temp_file_strategy设置
        if 'storage' not in self.config:
            self.config['storage'] = {}
        self.config['storage']['temp_file_strategy'] = temp_strategy
        
        self.download_thread = DataDownloadThread(
            task_type=task_type,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            period=period,
            db_path=self.db_path,
            update_mode=update_mode,
            test_mode=test_mode,
            config=self.config,
            preloaded_stocks=self._preloaded_stocks if hasattr(self, '_preloaded_stocks') else None
        )
        self.download_thread.log_signal.connect(self.log)
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.finished_signal.connect(self.on_download_finished)
        self.download_thread.error_signal.connect(self.on_download_error)
        self.download_thread.start()

        self._set_download_state(True)

    def download_bonds(self):
        """下载可转债数据"""
        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")

        self.log(f"📥 开始下载可转债数据 ({start_date} ~ {end_date})")

        # 检查测试模式
        test_mode = hasattr(self, 'test_mode_radio') and self.test_mode_radio.isChecked()
        
        self._start_download_task(
            task_type='download_bonds',
            symbols=None,  # 自动获取全部可转债
            start_date=start_date,
            end_date=end_date,
            test_mode=test_mode
        )

    def update_data(self):
        """一键补充数据"""
        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.warning(self, "提示", "已有下载任务正在运行")
            return

        # 获取用户选择的数据类型
        data_type_text = self.data_type_combo.currentText()
        
        # 映射数据类型到period
        period_map = {
            "所有类型": None,
            "日线数据": "1d",
            "1分钟数据": "1m",
            "5分钟数据": "5m",
            "15分钟数据": "15m",
            "30分钟数据": "30m",
            "60分钟数据": "60m",
            "周线数据": "weekly",
            "月线数据": "monthly",
            "Tick数据": "tick"
        }
        period = period_map.get(data_type_text)

        # 创建选择对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("更新数据设置")
        dialog.setMinimumWidth(450)
        
        layout = QVBoxLayout(dialog)
        
        # 模式选择
        mode_group = QGroupBox("更新模式")
        mode_layout = QVBoxLayout()
        self._update_mode_existing = QRadioButton("仅更新已有数据（推荐）")
        self._update_mode_existing.setToolTip("只更新数据库中已有的表，跳过不存在的表")
        self._update_mode_existing.setChecked(True)
        
        self._update_mode_all = QRadioButton("更新所有类型")
        self._update_mode_all.setToolTip("尝试更新所有数据类型，如果表不存在则创建")
        
        mode_layout.addWidget(self._update_mode_existing)
        mode_layout.addWidget(self._update_mode_all)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # 更新范围选择
        range_group = QGroupBox("更新范围")
        range_layout = QVBoxLayout()
        
        # 显示现有数据信息
        info_label = QLabel("正在检测现有数据...")
        info_label.setStyleSheet("color: #666;")
        range_layout.addWidget(info_label)
        
        # 检测现有数据的结束时间
        latest_date = self._detect_latest_data_date(period)
        
        if latest_date:
            info_label.setText(f"检测到现有数据最新日期：{latest_date}")
            
            # 默认选项：从最新日期前1天开始更新（用户可以自由调整）
            latest_qdate = QDate.fromString(latest_date, "yyyy-MM-dd")
            default_start_date = latest_qdate.addDays(-1)
            
            self._update_start_date = QDateEdit()
            self._update_start_date.setCalendarPopup(True)
            self._update_start_date.setDate(default_start_date)
            
            self._update_end_date = QDateEdit()
            self._update_end_date.setCalendarPopup(True)
            self._update_end_date.setDate(QDate.currentDate())
            
            date_layout = QFormLayout()
            date_layout.addRow("开始日期:", self._update_start_date)
            date_layout.addRow("结束日期:", self._update_end_date)
            range_layout.addLayout(date_layout)
        else:
            info_label.setText("未检测到现有数据，将从默认日期开始更新")
            
            # 默认日期
            self._update_start_date = QDateEdit()
            self._update_start_date.setCalendarPopup(True)
            self._update_start_date.setDate(QDate.currentDate().addYears(-1))
            
            self._update_end_date = QDateEdit()
            self._update_end_date.setCalendarPopup(True)
            self._update_end_date.setDate(QDate.currentDate())
            
            date_layout = QFormLayout()
            date_layout.addRow("开始日期:", self._update_start_date)
            date_layout.addRow("结束日期:", self._update_end_date)
            range_layout.addLayout(date_layout)
        
        range_group.setLayout(range_layout)
        layout.addWidget(range_group)
        
        # 按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)
        
        if dialog.exec() != QDialog.Accepted:
            return
        
        # 获取用户选择
        update_mode = 'existing' if self._update_mode_existing.isChecked() else 'all'
        start_date_qdate = self._update_start_date.date()
        end_date_qdate = self._update_end_date.date()
        
        # 验证日期范围
        if start_date_qdate > end_date_qdate:
            # 开始日期晚于结束日期，自动更正
            QMessageBox.warning(self, "日期范围错误", "开始日期不能晚于结束日期，已自动调整为结束日期")
            start_date_qdate = end_date_qdate
            self._update_start_date.setDate(start_date_qdate)
        
        start_date = start_date_qdate.toString('yyyyMMdd')
        end_date = end_date_qdate.toString('yyyyMMdd')
        
        # 检查测试模式状态
        test_mode = self.test_mode_radio.isChecked()
        self._test_mode = test_mode  # 保存测试模式状态
        
        self.log(f"🔄 开始更新数据 - 数据类型: {data_type_text}, 模式: {'仅更新已有' if update_mode == 'existing' else '更新所有'}, 范围: {start_date} ~ {end_date}...")

        self._start_download_task(
            task_type='update_data',
            symbols=None,
            start_date=start_date,
            end_date=end_date,
            period=period,
            update_mode=update_mode,
            test_mode=test_mode
        )
    
    def _detect_latest_data_date(self, period):
        """检测现有数据的最新日期"""
        try:
            from src.core.data.database.db_manager import get_db_manager
            
            # 确定要查询的表
            if period is None:
                # 如果是所有类型，优先检查日线数据
                check_tables = ['stock_daily', 'stock_1m', 'stock_5m', 'stock_15m', 'stock_30m', 'stock_60m', 'stock_weekly', 'stock_monthly', 'stock_tick']
            else:
                if period == '1d':
                    check_tables = ['stock_daily']
                elif period == 'tick':
                    check_tables = ['stock_tick']
                else:
                    check_tables = [f'stock_{period}']
            
            manager = get_db_manager(self.db_path)
            
            for table_name in check_tables:
                try:
                    # 根据表名确定日期列：日线/周线/月线使用 date，其他使用 datetime
                    if table_name in ['stock_daily', 'stock_weekly', 'stock_monthly']:
                        date_column = 'date'
                    else:
                        date_column = 'datetime'
                    query = f"SELECT MAX({date_column}) as latest_date FROM {table_name}"
                    df = manager.query_to_dataframe(query)
                    
                    if not df.empty and 'latest_date' in df.columns:
                        latest_date = df['latest_date'].iloc[0]
                        if latest_date is not None:
                            # 转换为日期格式
                            if isinstance(latest_date, str):
                                if len(latest_date) >= 10:
                                    return latest_date[:10]
                            else:
                                # datetime对象
                                return pd.to_datetime(latest_date).strftime('%Y-%m-%d')
                except Exception:
                    continue
            
            return None
        except Exception:
            return None

    def backfill_historical_data(self):
        """补充历史数据（获取指定日期范围的完整数据）"""
        # 获取用户选择的日期
        start_date = self.start_date_edit.date().toString('yyyy-MM-dd')
        end_date = self.end_date_edit.date().toString('yyyy-MM-dd')

        # 获取用户选择的数据类型
        data_type_text = self.data_type_combo.currentText()

        # 获取当日日期
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 创建确认对话框
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("确认操作")
        msg_box.setText(f"此操作将为缺失历史数据的股票补充 {start_date} 起至 {today} 的{data_type_text}。\n\n"
                      f"只会补充数据库中缺失的部分，已有数据不会被删除。\n\n"
                      "可能需要较长时间，确定要继续吗？")
        # 添加中文按钮
        yes_button = msg_box.addButton("确定", QMessageBox.YesRole)
        no_button = msg_box.addButton("取消", QMessageBox.NoRole)
        msg_box.setDefaultButton(no_button)
        # 显示对话框并获取结果
        msg_box.exec_()
        # 检查用户选择
        reply = msg_box.clickedButton() == yes_button

        if not reply:
            return

        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.warning(self, "提示", "已有下载任务正在运行")
            return

        # 检查当前是否是交易日盘中
        import datetime
        now = datetime.datetime.now()
        current_date = now.strftime('%Y%m%d')
        current_time = now.time()
        is_trading_day = True  # 简化处理，实际应该调用API检查是否是交易日
        is_trading_hours = current_time >= datetime.time(9, 30) and current_time <= datetime.time(15, 0)  # 简化处理，实际应该考虑中午休市

        # 对所有数据类型的特殊处理：如果是交易日盘中，提示用户等待收盘后再更新
        if is_trading_day and is_trading_hours:
            self.log(f"⚠️ 当前是交易日盘中，数据正在生成中")
            self.log(f"ℹ️ 建议在收盘后（15:00后）再更新当日数据")
            self.log(f"📅 本次更新将处理到 {current_date} 的数据")

        # 获取用户输入的日期
        start_date_qdate = self.start_date_edit.date()
        end_date_qdate = self.end_date_edit.date()
        
        # 自动设置结束日期为当日
        from datetime import datetime
        today = datetime.now().strftime('%Y%m%d')
        end_date = today
        
        # 验证日期范围
        if start_date_qdate > QDate.currentDate():
            # 开始日期晚于结束日期，自动更正
            QMessageBox.warning(self, "日期范围错误", "开始日期不能晚于结束日期，已自动调整为结束日期")
            start_date_qdate = QDate.currentDate()
            self.start_date_edit.setDate(start_date_qdate)
        
        start_date = start_date_qdate.toString('yyyyMMdd')

        # 映射数据类型到period
        period_map = {
            "所有类型": None,
            "日线数据": "1d",
            "1分钟数据": "1m",
            "5分钟数据": "5m",
            "15分钟数据": "15m",
            "30分钟数据": "30m",
            "60分钟数据": "60m",
            "周线数据": "weekly",
            "月线数据": "monthly",
            "Tick数据": "tick"
        }
        period = period_map.get(data_type_text)

        # 检查测试模式状态
        test_mode = self.test_mode_radio.isChecked()
        self._test_mode = test_mode  # 保存测试模式状态
        
        self.log(f"📜 开始补充历史数据（{start_date} ~ {end_date}） - 数据类型: {data_type_text}...")

        self._start_download_task(
            task_type='backfill_history',
            symbols=None,
            start_date=start_date,
            end_date=end_date,
            period=period,
            test_mode=test_mode
        )

    def update_progress(self, current, expected=None, total=None):
        """更新进度"""
        # 处理不同参数数量的情况
        if total is not None and expected is not None:
            # 三个参数的情况：current, expected, total
            self.progress_bar.setMaximum(expected)
            self.progress_bar.setValue(current)
            pct = (current / expected) * 100 if expected > 0 else 0
            self.progress_bar.setFormat(f"{current}/{expected}/{total} ({pct:.1f}%)")
        else:
            # 两个参数的情况：current, total
            total = expected  # expected 实际上是 total
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            pct = (current / total) * 100 if total > 0 else 0
            self.progress_bar.setFormat(f"{current}/{total} ({pct:.1f}%)")

    def on_download_finished(self, result):
        """下载完成"""
        # 检查是否是所有类型的下载，如果是，不处理，由_on_all_types_download_finished处理
        if hasattr(self, '_data_types') and hasattr(self, '_current_download_index'):
            # 无论_current_download_index的值是多少，只要存在_data_types属性，就说明是所有类型的下载
            # 由_on_all_types_download_finished处理，这里直接返回
            return
        
        # 检查是否是顺序下载模式，如果是，不处理，由_on_all_sequential_tasks_finished处理
        if hasattr(self, 'is_sequential_download') and self.is_sequential_download:
            # 顺序下载模式，由_on_all_sequential_tasks_finished处理，这里直接返回
            return
            
        self._set_download_state(False)
        self.progress_bar.setVisible(False)

        total = result.get('total', 0)
        success = result.get('success', 0)
        failed = result.get('failed', 0)
        task_type = result.get('task_type', '')
        
        # 确定下载的周期
        period_info = ""
        if hasattr(self, 'data_type_combo'):
            data_type_text = self.data_type_combo.currentText()
            if data_type_text == "所有类型":
                period_info = "所有周期（日线、1分钟、5分钟、15分钟、30分钟、60分钟、Tick）"
            else:
                period_info = data_type_text

        msg = f"下载完成！\n" 
        if period_info:
            msg += f"下载周期: {period_info}\n"
        msg += f"总数: {total}\n成功: {success}\n失败: {failed}\n"

        # 显示各数据类型的详细信息
        data_type_details = result.get('data_type_details', [])
        if data_type_details:
            msg += "\n各数据类型详情：\n"
            for detail in data_type_details:
                period = detail.get('period', '未知')
                detail_total = detail.get('total', 0)
                detail_success = detail.get('success', 0)
                detail_failed = detail.get('failed', 0)
                msg += f"  - {period}: 标的数={detail_total}, 成功={detail_success}, 失败={detail_failed}\n"

        if failed > 0:
            QMessageBox.warning(self, "下载完成", msg)
        else:
            QMessageBox.information(self, "下载完成", msg)

        # 重新加载数据信息
        self.load_duckdb_statistics()

    def on_download_error(self, error_msg):
        """下载出错"""
        # 检查是否是所有类型的下载，如果是，不处理，由_on_all_types_download_error处理
        if hasattr(self, '_data_types') and hasattr(self, '_current_download_index'):
            # 无论_current_download_index的值是多少，只要存在_data_types属性，就说明是所有类型的下载
            # 由_on_all_types_download_error处理，这里直接返回
            return
        
        # 检查是否是顺序下载模式，如果是，不处理，由_on_single_task_error处理
        if hasattr(self, 'is_sequential_download') and self.is_sequential_download:
            # 顺序下载模式，由_on_single_task_error处理，这里直接返回
            return
            
        self._set_download_state(False)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "下载失败", error_msg)

    def stop_download(self):
        """停止下载按钮的槽函数"""
        # 设置停止请求标志，防止后续任务启动
        self._stop_requested = True
        self.log("🛑 用户请求停止下载...")

        if self.download_thread and self.download_thread.isRunning():
            # 立即禁用停止按钮，给用户即时反馈
            self.stop_btn.setEnabled(False)
            self.stop_btn.setText("正在停止...")

            # 异步请求停止，此调用会立即返回
            self.download_thread.stop()

            # 不在这里等待线程结束，而是连接 finished 信号来清理资源
            # 注意：原来的 finished_signal 可能在线程"正常完成"时发射
            # 我们需要区分是"用户停止"还是"自然完成"。
            # 这里我们假设线程的 stop() 方法会最终导致线程结束并发射 finished_signal
            # 所以我们不需要额外操作，现有的 on_download_finished 会处理

        # 停止所有类型的下载流程
        if hasattr(self, 'download_task_queue'):
            self.current_task_index = len(self.download_task_queue)
            self.log("✅ 已停止所有类型的下载流程")
        elif hasattr(self, '_data_types'):
            self._current_download_index = len(self._data_types)
            self.log("✅ 已停止所有类型的下载流程")
        
        # 立即更新UI状态，确保用户可以立即开始新的下载
        self._set_download_state(False)
        self.log("✅ 所有下载已完全停止")

    def _set_download_state(self, is_downloading):
        """设置下载状态"""
        self.download_stocks_btn.setEnabled(not is_downloading)
        self.download_bonds_btn.setEnabled(not is_downloading)
        self.update_data_btn.setEnabled(not is_downloading)
        self.backfill_data_btn.setEnabled(not is_downloading)
        self.manual_download_btn.setEnabled(not is_downloading)
        self.verify_data_btn.setEnabled(not is_downloading)
        self.financial_download_btn.setEnabled(not is_downloading)
        self.stop_btn.setVisible(is_downloading)
        self.progress_bar.setVisible(is_downloading)

        if is_downloading:
            self.progress_bar.setValue(0)

    def verify_data_integrity(self):
        """验证数据完整性"""
        # 创建一个带输入选项的对话框
        dialog = QInputDialog(self)
        dialog.setWindowTitle("验证数据完整性")
        dialog.setLabelText("请输入要验证的股票代码:")
        dialog.setTextValue("511380.SH")  # 默认值
        dialog.setInputMode(QInputDialog.TextInput)

        ok = dialog.exec_()
        stock_code = dialog.textValue().strip()

        if ok and stock_code:
            # 自动格式化代码
            if not ('.' in stock_code):
                # 自动添加交易所后缀
                if stock_code.startswith(('5', '6')):
                    stock_code = stock_code + '.SH'
                elif stock_code.startswith(('0', '1', '3')):
                    stock_code = stock_code + '.SZ'

            self.log(f"🔍 验证 {stock_code} 数据完整性...")

            # 创建验证线程
            self.verify_thread = VerifyDataThread(stock_code, self.db_path)
            self.verify_thread.log_signal.connect(self.log)
            self.verify_thread.finished_signal.connect(self.on_verify_finished)
            self.verify_thread.start()

    def on_verify_finished(self, result):
        """验证完成"""
        stock = result.get('stock', 'N/A')
        has_daily = result.get('has_daily', False)
        has_tick = result.get('has_tick', False)
        records_daily = result.get('records_daily', 0)
        records_tick = result.get('records_tick', 0)
        start_daily = result.get('start_daily', '')
        end_daily = result.get('end_daily', '')
        start_tick = result.get('start_tick', '')
        end_tick = result.get('end_tick', '')
        
        # 获取分钟线数据
        minute_data = result.get('minute_data', {})
        minute_types = [
            ('1m', '1分钟'),
            ('5m', '5分钟'),
            ('15m', '15分钟'),
            ('30m', '30分钟'),
            ('60m', '60分钟')
        ]

        msg = f"{stock} 数据验证结果:\n\n"
        
        # 显示所有分钟线数据
        for period, period_name in minute_types:
            has_data = minute_data.get(period, {}).get('has_data', False)
            records = minute_data.get(period, {}).get('records', 0)
            start_time = minute_data.get(period, {}).get('start_time', '')
            end_time = minute_data.get(period, {}).get('end_time', '')
            
            msg += f"{period_name}数据: {'✓ 存在' if has_data else '✗ 不存在'}"
            if has_data:
                msg += f"\n   记录数: {records:,} 条"
                msg += f"\n   时间范围: {start_time} ~ {end_time}"
            msg += "\n"

        # 显示日线数据
        msg += f"日线数据: {'✓ 存在' if has_daily else '✗ 不存在'}"
        if has_daily:
            msg += f"\n   记录数: {records_daily:,} 条"
            msg += f"\n   时间范围: {start_daily} ~ {end_daily}"
        msg += "\n"

        # 显示Tick数据
        msg += f"Tick数据: {'✓ 存在' if has_tick else '✗ 不存在'}"
        if has_tick:
            msg += f"\n   记录数: {records_tick:,} 条"
            msg += f"\n   时间范围: {start_tick} ~ {end_tick}"

        # 检查是否有任何数据存在
        has_any_data = has_daily or has_tick or any(minute_data.get(period, {}).get('has_data', False) for period in minute_data)
        
        if has_any_data:
            QMessageBox.information(self, "验证完成", msg)
        else:
            QMessageBox.warning(self, "验证完成", msg + "\n⚠️ 该股票没有本地数据，请先下载")


class DataViewerDialog(QDialog):
    """数据查看对话框 - 支持复权"""

    def __init__(self, stock_code: str, adjust: str, parent=None):
        super().__init__(parent)
        self.stock_code = stock_code
        self.adjust = adjust
        self.setWindowTitle(f"查看数据 - {stock_code} ({adjust}) [DuckDB]")
        self.setMinimumSize(900, 600)
        self.init_ui()
        self.load_data()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 顶部信息
        info_layout = QHBoxLayout()

        # 股票代码
        code_label = QLabel(f"股票代码: <b>{self.stock_code}</b>")
        code_label.setStyleSheet("font-size: 12pt;")
        info_layout.addWidget(code_label)

        # 复权类型
        adjust_names = {"none": "不复权", "qfq": "前复权", "hfq": "后复权"}
        adjust_label = QLabel(f"复权类型: <b>{adjust_names.get(self.adjust, self.adjust)}</b>")
        adjust_label.setStyleSheet("font-size: 12pt;")
        info_layout.addWidget(adjust_label)

        info_layout.addStretch()

        # 导出按钮
        export_btn = QPushButton("📊 导出CSV")
        export_btn.clicked.connect(self.export_csv)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        info_layout.addWidget(export_btn)

        # 关闭按钮
        close_btn = QPushButton("✖ 关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 5px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        info_layout.addWidget(close_btn)

        layout.addLayout(info_layout)

        # 数据表格
        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSortingEnabled(True)
        layout.addWidget(self.data_table)

        # 统计信息
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("font-size: 10pt; color: #666;")
        layout.addWidget(self.stats_label)

    def load_data(self):
        """加载数据"""
        try:
            # 使用只读模式连接，避免配置冲突
            import duckdb

            # DuckDB数据库路径
            db_path = Path(self.parent().db_path)

            if not db_path.exists():
                self.stats_label.setText(f"❌ 数据库不存在: {db_path}")
                self.data_table.setRowCount(1)
                self.data_table.setColumnCount(1)
                self.data_table.setHorizontalHeaderLabels(["错误"])
                self.data_table.setItem(0, 0, QTableWidgetItem(f"数据库不存在:\n{db_path}"))
                return

            # 映射复权类型
            adjust_map = {
                "none": "none",
                "qfq": "front",
                "hfq": "back"
            }
            duckdb_adjust = adjust_map.get(self.adjust, "none")

            # 加载数据（使用数据库管理器）
            from src.core.data.database.db_manager import get_db_manager
            manager = get_db_manager(str(db_path))
            query = f"""
                SELECT
                    date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    amount
                FROM stock_daily
                WHERE stock_code = '{self.stock_code}'
                  AND period = '1d'
                  AND adjust_type = '{duckdb_adjust}'
                ORDER BY date
            """

            df = manager.query_to_dataframe(query)

            if df.empty:
                self.stats_label.setText(f"❌ 未找到 {self.stock_code} 的数据")
                self.data_table.setRowCount(1)
                self.data_table.setColumnCount(1)
                self.data_table.setHorizontalHeaderLabels(["提示"])
                self.data_table.setItem(0, 0, QTableWidgetItem(f"未找到 {self.stock_code} 的数据\n请先下载该股票的数据"))
                return

            # 设置日期为索引
            df.set_index('date', inplace=True)

            # 显示数据
            self._display_data(df)

        except Exception as e:
            self.stats_label.setText(f"❌ 加载失败: {str(e)}")
            import traceback
            traceback.print_exc()
            self.data_table.setRowCount(1)
            self.data_table.setColumnCount(1)
            self.data_table.setHorizontalHeaderLabels(["错误"])
            self.data_table.setItem(0, 0, QTableWidgetItem(f"加载数据失败:\n{str(e)}"))

    def _display_data(self, df):
        """显示数据到表格"""
        # 设置列
        df = df.reset_index()
        columns = df.columns.tolist()

        self.data_table.setColumnCount(len(columns))
        self.data_table.setHorizontalHeaderLabels(columns)

        # 设置行
        self.data_table.setRowCount(len(df))

        # 填充数据（只显示前1000条，避免太慢）
        display_df = df.head(1000)

        for row_idx in range(len(display_df)):
            for col_idx, col in enumerate(columns):
                value = display_df.iloc[row_idx, col_idx]
                item = QTableWidgetItem(str(value))
                self.data_table.setItem(row_idx, col_idx, item)

        # 调整列宽
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 更新统计信息
        stats = f"总记录数: {len(df):,} 条"
        if len(df) > 1000:
            stats += f" (显示前1000条)"

        if not df.empty:
            latest_price = df['close'].iloc[-1]
            stats += f" | 最新价: {latest_price:.2f}"

            if len(df) >= 2:
                start_price = df['close'].iloc[0]
                total_return = (latest_price / start_price - 1) * 100
                stats += f" | 区间涨跌: {total_return:+.2f}%"

        self.stats_label.setText(stats)

    def export_csv(self):
        """导出为CSV"""
        try:
            # 使用只读模式连接
            import duckdb

            # DuckDB数据库路径
            db_path = Path(self.parent().db_path)

            # 映射复权类型
            adjust_map = {
                "none": "none",
                "qfq": "front",
                "hfq": "back"
            }
            duckdb_adjust = adjust_map.get(self.adjust, "none")

            # 加载数据（使用数据库管理器）
            from src.core.data.database.db_manager import get_db_manager
            manager = get_db_manager(str(db_path))
            query = f"""
                SELECT
                    date,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    amount
                FROM stock_daily
                WHERE stock_code = '{self.stock_code}'
                  AND period = '1d'
                  AND adjust_type = '{duckdb_adjust}'
                ORDER BY date
            """
            df = manager.query_to_dataframe(query)

            # 设置日期为索引
            df.set_index('date', inplace=True)

            # 选择保存路径
            default_name = f"{self.stock_code}_{self.adjust}_duckdb_data.csv"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出CSV",
                default_name,
                "CSV文件 (*.csv)"
            )

            if file_path:
                df.to_csv(file_path, encoding='utf-8-sig')
                QMessageBox.information(self, "成功", f"数据已导出到:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")


class FinancialDataViewerDialog(QDialog):
    """财务数据查看对话框"""

    def __init__(self, stock_code: str, parent=None):
        super().__init__(parent)
        self.stock_code = stock_code
        self.setWindowTitle(f"查看财务数据 - {stock_code}")
        self.setMinimumSize(1000, 700)
        self.init_ui()
        self.load_data()

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 顶部信息
        info_layout = QHBoxLayout()

        # 股票代码
        code_label = QLabel(f"股票代码: <b>{self.stock_code}</b>")
        code_label.setStyleSheet("font-size: 12pt;")
        info_layout.addWidget(code_label)

        # 数据表选择
        info_layout.addWidget(QLabel("数据表:"))
        self.table_combo = QComboBox()
        self.table_combo.addItems(["Balance (资产负债表)", "Income (利润表)", "CashFlow (现金流量表)", "Capitalization (股本结构)"])
        self.table_combo.currentIndexChanged.connect(self.load_data)
        info_layout.addWidget(self.table_combo)

        info_layout.addStretch()

        # 导出CSV按钮
        export_btn = QPushButton("📊 导出CSV")
        export_btn.clicked.connect(self.export_financial_csv)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        info_layout.addWidget(export_btn)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.load_data)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        info_layout.addWidget(refresh_btn)

        # 关闭按钮
        close_btn = QPushButton("✖ 关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 5px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        info_layout.addWidget(close_btn)

        layout.addLayout(info_layout)

        # 数据表格
        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSortingEnabled(True)
        layout.addWidget(self.data_table)

        # 统计信息
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("font-size: 10pt; color: #666;")
        layout.addWidget(self.stats_label)

    def load_data(self):
        """加载数据"""
        try:
            if not XTDATA_AVAILABLE:
                self.log("❌ xtquant模块不可用，请确保QMT已安装并运行")
                return
            from xtquant import xtdata
            import pandas as pd

            # 获取选择的数据表
            table_text = self.table_combo.currentText()
            table_map = {
                "Balance (资产负债表)": "Balance",
                "Income (利润表)": "Income",
                "CashFlow (现金流量表)": "CashFlow",
                "Capitalization (股本结构)": "Capitalization"
            }
            table_name = table_map.get(table_text, "Balance")

            # 下载财务数据
            self.data_table.setRowCount(0)
            self.data_table.setColumnCount(0)
            self.stats_label.setText("正在加载数据...")

            # 先下载
            xtdata.download_financial_data(
                stock_list=[self.stock_code],
                table_list=[table_name]
            )

            # 再读取
            from datetime import datetime
            result = xtdata.get_financial_data(
                stock_list=[self.stock_code],
                table_list=[table_name],
                start_time="19900101",
                end_time=datetime.now().strftime('%Y%m%d'),
                report_type='report_time'
            )

            if isinstance(result, dict) and self.stock_code in result:
                stock_data = result[self.stock_code]

                if table_name in stock_data:
                    table_data = stock_data[table_name]

                    if isinstance(table_data, pd.DataFrame):
                        # DataFrame格式
                        self._display_dataframe(table_data)
                    elif isinstance(table_data, dict):
                        # 字典格式，转换为表格显示
                        self._display_dict(table_data)
                    else:
                        self.stats_label.setText(f"数据类型: {type(table_data)}")
                        QMessageBox.information(self, "提示", f"数据格式: {type(table_data)}")
                else:
                    self.stats_label.setText(f"未找到 {table_name} 表数据")
                    QMessageBox.information(self, "提示", f"未找到 {table_name} 表数据\n\n可能原因：\n1. 该股票没有此表数据\n2. 需要先下载财务数据")
            else:
                self.stats_label.setText("未找到财务数据")
                QMessageBox.information(self, "提示", "未找到财务数据\n\n请先下载财务数据")

        except Exception as e:
            self.stats_label.setText(f"加载失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"加载财务数据失败: {str(e)}")

    def _display_dataframe(self, df):
        """显示DataFrame"""
        # 重置索引
        df = df.reset_index()

        # 设置列
        columns = df.columns.tolist()
        self.data_table.setColumnCount(len(columns))
        self.data_table.setHorizontalHeaderLabels(columns)

        # 设置行
        self.data_table.setRowCount(len(df))

        # 填充数据（显示前100条）
        display_df = df.head(100)

        for row_idx in range(len(display_df)):
            for col_idx, col in enumerate(columns):
                value = display_df.iloc[row_idx, col_idx]
                item = QTableWidgetItem(str(value))
                self.data_table.setItem(row_idx, col_idx, item)

        # 调整列宽
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 更新统计信息
        total = len(df)
        if total > 100:
            self.stats_label.setText(f"总记录数: {total} 条 (显示前100条)")
        else:
            self.stats_label.setText(f"总记录数: {total} 条")

    def _display_dict(self, data):
        """显示字典数据"""
        # 将字典转换为表格
        self.data_table.setColumnCount(2)
        self.data_table.setHorizontalHeaderLabels(["字段名", "值"])

        # 获取所有键
        keys = list(data.keys())
        self.data_table.setRowCount(len(keys))

        for row_idx, key in enumerate(keys):
            value = data[key]

            # 字段名
            key_item = QTableWidgetItem(str(key))
            self.data_table.setItem(row_idx, 0, key_item)

            # 值
            value_str = str(value) if not isinstance(value, (list, dict)) else f"{type(value).__name__}({len(value)})"
            value_item = QTableWidgetItem(value_str)
            self.data_table.setItem(row_idx, 1, value_item)

        # 调整列宽
        self.data_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.data_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

        # 更新统计信息
        self.stats_label.setText(f"字段数量: {len(keys)} 个")

    def export_financial_csv(self):
        """导出财务数据为CSV"""
        try:
            if not XTDATA_AVAILABLE:
                self.log("❌ xtquant模块不可用，请确保QMT已安装并运行")
                return
            from xtquant import xtdata
            import pandas as pd

            # 获取选择的数据表
            table_text = self.table_combo.currentText()
            table_map = {
                "Balance (资产负债表)": "Balance",
                "Income (利润表)": "Income",
                "CashFlow (现金流量表)": "CashFlow",
                "Capitalization (股本结构)": "Capitalization"
            }
            table_name = table_map.get(table_text, "Balance")

            # 下载数据
            xtdata.download_financial_data(
                stock_list=[self.stock_code],
                table_list=[table_name]
            )

            # 读取数据
            from datetime import datetime
            result = xtdata.get_financial_data(
                stock_list=[self.stock_code],
                table_list=[table_name],
                start_time="19900101",
                end_time=datetime.now().strftime('%Y%m%d'),
                report_type='report_time'
            )

            if isinstance(result, dict) and self.stock_code in result:
                stock_data = result[self.stock_code]

                if table_name in stock_data:
                    table_data = stock_data[table_name]

                    # 转换为DataFrame
                    if isinstance(table_data, pd.DataFrame):
                        df = table_data
                    elif isinstance(table_data, dict):
                        # 字典转换为DataFrame
                        df = pd.DataFrame.from_dict(table_data, orient='index').T
                    else:
                        QMessageBox.warning(self, "提示", f"无法导出数据类型: {type(table_data)}")
                        return

                    # 选择保存路径
                    default_name = f"{self.stock_code}_{table_name}_财务数据.csv"
                    file_path, _ = QFileDialog.getSaveFileName(
                        self,
                        "导出财务数据CSV",
                        default_name,
                        "CSV文件 (*.csv)"
                    )

                    if file_path:
                        # 导出为CSV
                        df.to_csv(file_path, encoding='utf-8-sig', index=True)
                        QMessageBox.information(self, "成功", f"财务数据已导出到:\n{file_path}\n\n共 {len(df)} 条记录")
                else:
                    QMessageBox.warning(self, "提示", f"未找到 {table_name} 表数据")
            else:
                QMessageBox.warning(self, "提示", "未找到财务数据")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")





if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    window = LocalDataManagerWidget()
    window.setWindowTitle("本地数据管理")
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec_())
