#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级数据查看器组件
符合现有GUI的浅色主题风格
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QComboBox, QDateEdit,
    QFrame, QMessageBox, QFileDialog, QSplitter, QLineEdit,
    QTabWidget, QRadioButton, QButtonGroup, QApplication,
    QSpinBox, QCheckBox, QListWidget, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDate, QTimer
from PyQt5.QtGui import QFont, QColor

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
            print(f"ℹ️ 添加路径: {path}")
    
    # 尝试导入xtquant
    import xtquant
    import xtquant.xtdata
    print("✅ xtquant 模块导入成功")
    XTDATA_AVAILABLE = True
except ImportError as e:
    print(f"❌ 导入xtquant模块失败: {str(e)}")
    XTDATA_AVAILABLE = False

try:
    from src.core.data.database.db_manager import get_db_manager
    DB_MANAGER_AVAILABLE = True
    FINANCIAL_SAVER_AVAILABLE = False  # 暂时禁用财务数据保存器
except ImportError:
    DB_MANAGER_AVAILABLE = False
    FINANCIAL_SAVER_AVAILABLE = False


class DataLoadThread(QThread):
    """数据加载线程"""
    data_ready = pyqtSignal(pd.DataFrame, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, stock_code: str, start_date: str, end_date: str, adjust_type: str = 'none', data_type: str = '1d', db_path: str = None):
        super().__init__()
        self.stock_code = stock_code
        self.start_date = start_date
        self.end_date = end_date
        self.adjust_type = adjust_type
        self.data_type = data_type  # 数据类型：1d, 1m, 5m, 15m, 30m, 60m, weekly, monthly, tick
        self.db_path = db_path

    def run(self):
        try:
            print(f"🔍 [DataLoadThread] 开始加载数据...")
            print(f"   - 数据库路径: {self.db_path}")
            print(f"   - 股票代码: {self.stock_code}")
            print(f"   - 数据类型: {self.data_type}")
            print(f"   - 时间范围: {self.start_date} ~ {self.end_date}")
            print(f"   - DB_MANAGER_AVAILABLE: {DB_MANAGER_AVAILABLE}")
            
            if DB_MANAGER_AVAILABLE and self.db_path:
                manager = get_db_manager(self.db_path)
                print(f"✅ [DataLoadThread] 数据库管理器创建成功")

                # 根据数据类型选择表名和日期列
                if self.data_type == '1d':
                    table_name = 'stock_daily'
                    date_column = 'date'
                elif self.data_type == 'weekly':
                    table_name = 'stock_weekly'
                    date_column = 'date'  # 使用date列
                elif self.data_type == 'monthly':
                    table_name = 'stock_monthly'
                    date_column = 'date'  # 使用date列
                elif self.data_type == 'tick':
                    table_name = 'stock_tick'
                    date_column = 'datetime'
                elif self.data_type in ['weekly', '1w']:
                    table_name = 'stock_weekly'
                    date_column = 'date'  # 周线使用date列
                elif self.data_type in ['monthly', '1M']:
                    table_name = 'stock_monthly'
                    date_column = 'date'  # 月线使用date列
                else:
                    table_name = f'stock_{self.data_type}'
                    date_column = 'datetime'

                print(f"📊 [DataLoadThread] 查询表: {table_name}, 日期列: {date_column}")

                # 根据复权类型选择列（只适用于日线数据）
                if self.data_type == '1d':
                    if self.adjust_type == 'none':
                        price_cols = ['open', 'high', 'low', 'close']
                    elif self.adjust_type == 'front':
                        price_cols = ['open_front', 'high_front', 'low_front', 'close_front']
                    elif self.adjust_type == 'back':
                        price_cols = ['open_back', 'high_back', 'low_back', 'close_back']
                    else:
                        price_cols = ['open', 'high', 'low', 'close']
                else:
                    # 分钟线、周线、月线和Tick数据使用原始价格
                    price_cols = ['open', 'high', 'low', 'close']

                # 构建查询语句，支持更多数据列
                if self.data_type == 'tick':
                    # Tick数据的特殊处理
                    query = f"""
                        SELECT
                            {date_column},
                            price as close,
                            volume,
                            amount,
                            bid_price1,
                            bid_volume1,
                            ask_price1,
                            ask_volume1,
                            func_type
                        FROM {table_name}
                        WHERE stock_code = '{self.stock_code}'
                          AND {date_column} >= '{self.start_date}'
                          AND {date_column} <= '{self.end_date}'
                        ORDER BY {date_column}
                    """
                else:
                    # 其他数据类型
                    query = f"""
                        SELECT
                            {date_column},
                            {price_cols[0]} as open,
                            {price_cols[1]} as high,
                            {price_cols[2]} as low,
                            {price_cols[3]} as close,
                            volume,
                            amount
                        FROM {table_name}
                        WHERE stock_code = '{self.stock_code}'
                          AND {date_column} >= '{self.start_date}'
                          AND {date_column} <= '{self.end_date}'
                        ORDER BY {date_column}
                    """

                print(f"📝 [DataLoadThread] 执行查询:")
                print(query)
                
                df = manager.query_dataframe(query)
                print(f"✅ [DataLoadThread] 查询完成, 返回 {len(df)} 条记录")
            else:
                # 不再使用直接的duckdb.connect，避免递归调用
                print(f"⚠️ [DataLoadThread] DB_MANAGER_AVAILABLE={DB_MANAGER_AVAILABLE}, db_path={self.db_path}")
                df = pd.DataFrame()

            if not df.empty:
                df = df.set_index(date_column)
                
                # 计算额外的技术指标
                if self.data_type != 'tick':
                    # 【修复】修正均价计算逻辑（2026-04-12）
                    # 均价 = 成交额 / 成交量
                    # 注意：数据库中volume单位是"手"（1手=100股），amount单位是"元"
                    # 要得到"元/股"的均价，需要：amount / (volume * 100)
                    if 'amount' in df.columns and 'volume' in df.columns:
                        # 安全除法：避免除以零或NaN
                        df['avg_price'] = np.where(
                            (df['volume'] > 0) & (pd.notna(df['volume'])) & (pd.notna(df['amount'])),
                            df['amount'] / (df['volume'] * 100),  # 【关键修复】volume从"手"转换为"股"
                            np.nan  # 无效数据返回NaN而不是0
                        )
                    
                    # 计算涨跌
                    if 'close' in df.columns:
                        df['change'] = df['close'].diff()
                        df['change_pct'] = df['close'].pct_change() * 100

            self.data_ready.emit(df, self.stock_code)

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.error_occurred.emit(f"{str(e)}\n\n详细信息:\n{error_detail}")


class AdvancedDataViewerWidget(QWidget):
    """高级数据查看器组件 - 浅色主题风格"""

    def __init__(self):
        super().__init__()
        self.current_stock = None
        self.current_data = None
        self.search_timer = None  # 搜索延迟定时器
        self.db_path = None  # 数据库路径
        self.config = {}  # 初始化配置字典
        self.data_type = '1d'  # 当前数据类型（默认日线）
        
        # 【新增】数据缓存系统（2026-04-12）
        self._data_cache = {}  # 格式: {(stock_code, data_type, start_date, end_date): DataFrame}
        self._cache_enabled = True  # 缓存开关状态
        self._cache_max_size = 50  # 最大缓存条目数
        self._cache_hits = 0  # 缓存命中次数
        self._cache_misses = 0  # 缓存未命中次数
        
        self._load_config()  # 加载配置
        self._resolve_database_path()  # 解析数据库路径
        self.init_ui()
        self.load_initial_data()
    
    def _load_config(self):
        """读取配置文件获取数据库路径和时间范围设置"""
        from pathlib import Path
        import json
        import yaml
        try:
            # 配置文件路径
            current_file = Path(__file__)
            print(f"ℹ️ 当前文件路径: {current_file}")
            config_dir = current_file.parent.parent.parent / 'config'
            print(f"ℹ️ 配置目录路径: {config_dir}")
            yaml_config_path = config_dir / 'data_config.yaml'
            print(f"ℹ️ YAML配置文件路径: {yaml_config_path}")
            
            # 初始化配置字典
            self.config = {}
            yaml_config = {}
            
            # 加载YAML配置文件
            if yaml_config_path.exists():
                print(f"📁 检查YAML配置文件: {yaml_config_path}")
                try:
                    with open(yaml_config_path, 'r', encoding='utf-8') as f:
                        yaml_config = yaml.safe_load(f)
                    print(f"✅ 加载YAML配置文件成功")
                    self.config = yaml_config.copy()
                    # 打印配置文件内容，用于调试
                    print(f"ℹ️ 配置文件内容: {self.config}")
                    # 检查database和data_paths字段
                    if 'database' in self.config:
                        print(f"ℹ️ 配置文件中的database字段: {self.config['database']}")
                    if 'data_paths' in self.config:
                        print(f"ℹ️ 配置文件中的data_paths字段: {self.config['data_paths']}")
                except yaml.YAMLError as e:
                    print(f"⚠️ YAML配置文件格式错误: {e}")
                    yaml_config = {}
            else:
                print(f"⚠️ YAML配置文件不存在: {yaml_config_path}")
            
            if yaml_config:
                print(f"✅ 使用YAML配置")
            else:
                print(f"⚠️ 没有加载到任何配置文件，使用默认配置")
            
            # 应用默认配置
            self._apply_default_config()
            
            # 确定数据库路径
            db_path = self._resolve_database_path()
            
            self.db_path = str(Path(db_path).resolve())
            
            # 确保数据库目录存在
            db_dir = Path(self.db_path).parent
            if not db_dir.exists():
                db_dir.mkdir(parents=True, exist_ok=True)
                print(f"✅ 创建数据库目录: {db_dir}")
            else:
                print(f"ℹ️ 数据库目录已存在: {db_dir}")
            
            # 最终数据库路径确认
            print(f"📊 最终数据库路径: {self.db_path}")
                
        except Exception as e:
            print(f"⚠️ 读取配置文件失败: {e}")
            import traceback
            print(f"⚠️ 详细错误: {traceback.format_exc()}")
            # 使用默认路径，与local_data_manager_widget.py保持一致
            self.db_path = 'D:/MyStockData/stock_data.duckdb'
            print(f"⚠️ 使用默认数据库路径: {self.db_path}")
            
            # 确保数据库目录存在
            db_dir = Path(self.db_path).parent
            if not db_dir.exists():
                db_dir.mkdir(parents=True, exist_ok=True)
                print(f"✅ 创建数据库目录: {db_dir}")
            else:
                print(f"ℹ️ 数据库目录已存在: {db_dir}")
            
            # 最终数据库路径确认
            print(f"📊 最终数据库路径: {self.db_path}")
    
    def _apply_default_config(self):
        """应用默认配置"""
        # 默认配置，与local_data_manager_widget.py保持一致
        default_config = {
            'data_paths': {
                'root_dir': 'D:/MyStockData',
                'raw_data': 'raw',
                'factors': 'factors',
                'cache': 'cache',
                'metadata': 'metadata.db'
            },
            'database': {
                'dbfile': 'stock_data.duckdb',
                'batch_size': 100000,
                'max_connections': 10,
                'overwrite_existing': True
            },
            'storage': {
                'format': 'parquet',
                'compression': 'snappy',
                'partition_by': 'year',
                'temp_file_strategy': 'direct',
                'temp_dir': 'W:/TEMP'
            }
        }
        
        # 合并默认配置
        for key, value in default_config.items():
            if key not in self.config:
                self.config[key] = value
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if sub_key not in self.config[key]:
                        self.config[key][sub_key] = sub_value
        
        print("✅ 应用默认配置完成")
    
    def _resolve_database_path(self):
        """
        解析数据库路径（2026-04-12 重构）
        
        支持多种配置格式：
        1. 新版双库架构: database.data_db.dbfile / database.view_db.dbfile
        2. 单库模式: database.path 或 database.dbfile
        3. 旧版JSON格式: data_config.database.path
        """
        # 检查 self.config 是否为 None
        if self.config is None:
            print("⚠️ self.config 为 None，使用默认数据库路径")
            db_path = 'D:/MyStockData/stock_data.duckdb'
            print(f"⚠️ 使用默认数据库路径: {db_path}")
            return db_path
        
        # 1. 【新增】优先支持新版双数据库架构（2026-04-12）
        if 'database' in self.config:
            db_config = self.config['database']
            
            # 尝试 data_db.dbfile（物理表数据库）
            if 'data_db' in db_config and 'dbfile' in db_config.get('data_db', {}):
                root_dir = self.config.get('data_paths', {}).get('root_dir', 'D:/MyStockData')
                dbfile = db_config['data_db']['dbfile']
                db_path = str(Path(root_dir) / dbfile)
                print(f"✅ 从双库配置读取物理表数据库路径: {db_path}")
                return db_path
            
            # 兼容旧的单库 path 字段
            if 'path' in db_config:
                db_path = db_config['path']
                print(f"✅ 从 database.path 读取: {db_path}")
                return db_path
        
        # 2. 尝试组合生成路径（兼容旧格式）
        elif 'database' in self.config and 'dbfile' in self.config['database'] and \
             'data_paths' in self.config and 'root_dir' in self.config['data_paths']:
            root_dir = self.config['data_paths']['root_dir']
            dbfile = self.config['database']['dbfile']
            db_path = str(Path(root_dir) / dbfile)
            print(f"✅ 从配置文件组合生成数据库路径: {db_path}")
            return db_path
        
        # 3. 尝试从JSON格式的旧配置结构获取
        elif 'data_config' in self.config and 'database' in self.config['data_config'] and 'path' in self.config['data_config']['database']:
            db_path = self.config['data_config']['database']['path']
            print(f"✅ 从旧格式配置文件读取数据库路径: {db_path}")
            return db_path
        
        # 4. 如果没有配置，使用默认路径（2026-04-12 修正：与配置文件一致使用.duckdb）
        else:
            db_path = 'D:/MyStockData/stock_data.duckdb'
            print(f"⚠️ 配置文件中未设置数据库路径，使用默认路径: {db_path}")
            return db_path

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 控制面板
        control_panel = self.create_control_panel()
        layout.addWidget(control_panel)

        # 主分割器（上下分栏）
        main_splitter = QSplitter(Qt.Vertical)

        # 上部：股票选择
        stock_panel = self.create_stock_selection_panel()
        main_splitter.addWidget(stock_panel)

        # 下部：详细数据
        data_panel = self.create_data_table_panel()
        main_splitter.addWidget(data_panel)

        # 设置分割比例（上3下7）
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 7)

        layout.addWidget(main_splitter)

    def create_control_panel(self):
        """创建控制面板 - 优化布局设计（2026-04-12）"""
        group = QGroupBox("控制面板")
        main_layout = QVBoxLayout(group)
        main_layout.setSpacing(8)
        
        # ===== 第1行：股票信息和基本设置 =====
        row1_layout = QHBoxLayout()
        
        # 左侧：股票信息
        info_layout = QVBoxLayout()
        self.stock_label = QLabel("当前股票: 未选择")
        self.stock_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.stock_label.setStyleSheet("color: #2196F3;")
        info_layout.addWidget(self.stock_label)
        
        self.record_count_label = QLabel("记录数: 0")
        self.record_count_label.setStyleSheet("color: #757575; font-size: 12px;")
        info_layout.addWidget(self.record_count_label)
        
        row1_layout.addLayout(info_layout)
        row1_layout.addSpacing(20)
        
        # 中间：数据类型、复权
        control_layout = QGridLayout()
        control_layout.setSpacing(8)
        
        control_layout.addWidget(QLabel("数据类型:"), 0, 0)
        self.data_type_combo = QComboBox()
        self.data_type_combo.addItems(["日线", "1分钟", "5分钟", "15分钟", "30分钟", "60分钟", "周线", "月线"])
        self.data_type_combo.setMinimumWidth(100)
        self.data_type_combo.currentTextChanged.connect(self.on_data_type_changed)
        control_layout.addWidget(self.data_type_combo, 0, 1)
        
        control_layout.addWidget(QLabel("复权类型:"), 0, 2)
        self.adjust_combo = QComboBox()
        self.adjust_combo.addItems(["不复权", "前复权", "后复权"])
        self.adjust_combo.setMinimumWidth(100)
        self.adjust_combo.currentTextChanged.connect(self.on_adjust_changed)
        control_layout.addWidget(self.adjust_combo, 0, 3)
        
        row1_layout.addLayout(control_layout)
        row1_layout.addStretch()
        
        # 右侧：操作按钮
        btn_layout = QHBoxLayout()
        self.load_btn = QPushButton("📥 加载数据")
        self.load_btn.clicked.connect(self.load_current_stock)
        btn_layout.addWidget(self.load_btn)
        
        self.export_btn = QPushButton("📤 导出Excel")
        self.export_btn.clicked.connect(self.export_to_excel)
        btn_layout.addWidget(self.export_btn)
        
        # 【新增】性能测试按钮
        self.perf_test_btn = QPushButton("⚡ 性能测试")
        self.perf_test_btn.setToolTip("批量测试不同查询方式的性能\n支持多标的、多数据类型对比")
        self.perf_test_btn.clicked.connect(self.show_performance_test_dialog)
        btn_layout.addWidget(self.perf_test_btn)
        
        # 【新增】缓存模式切换按钮
        self.cache_toggle_btn = QPushButton("💾 缓存: 开启")
        self.cache_toggle_btn.setCheckable(True)
        self.cache_toggle_btn.setChecked(True)  # 默认开启缓存
        self.cache_toggle_btn.setToolTip("切换数据缓存模式\n开启：从内存缓存加载数据（快速）\n关闭：每次都查询数据库（准确）")
        self.cache_toggle_btn.clicked.connect(self.on_cache_mode_changed)
        btn_layout.addWidget(self.cache_toggle_btn)
        
        # 【新增】缓存条数设置（2026-04-12）
        btn_layout.addWidget(QLabel("📦容量:"))
        self.cache_size_spin = QSpinBox()
        self.cache_size_spin.setRange(10, 500)  # 缓存10-500条数据
        self.cache_size_spin.setValue(50)  # 默认50条，根据机器配置和内存占用设置的合理初始值
        self.cache_size_spin.setSuffix(" 条")
        self.cache_size_spin.setToolTip("设置最大缓存条目数\n建议值：\n• 普通配置: 30-50条\n• 高配机器: 100-200条\n• 服务器级: 300-500条")
        self.cache_size_spin.valueChanged.connect(self.on_cache_size_changed)
        btn_layout.addWidget(self.cache_size_spin)
        
        row1_layout.addLayout(btn_layout)
        main_layout.addLayout(row1_layout)
        
        # ===== 第2行：日期范围 + 查询方式 =====
        row2_layout = QHBoxLayout()
        
        # 日期范围
        date_group = QFrame()
        date_group.setFrameStyle(QFrame.StyledPanel)
        date_layout = QHBoxLayout(date_group)
        date_layout.setContentsMargins(8, 4, 8, 4)
        
        date_layout.addWidget(QLabel("📅 起始日期:"))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-120))
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setMinimumWidth(130)  # 【修复】加宽以完整显示日期
        date_layout.addWidget(self.start_date_edit)
        
        date_layout.addWidget(QLabel("结束日期:"))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setMinimumWidth(130)  # 【修复】加宽以完整显示日期
        date_layout.addWidget(self.end_date_edit)
        
        row2_layout.addWidget(date_group)
        row2_layout.addSpacing(20)
        
        # 查询方式选择
        query_group = QFrame()
        query_group.setFrameStyle(QFrame.StyledPanel)
        query_layout = QHBoxLayout(query_group)
        query_layout.setContentsMargins(8, 4, 8, 4)
        
        query_layout.addWidget(QLabel("🔍 查询方式:"))
        self.query_mode_group = QButtonGroup()
        
        self.query_view_radio = QRadioButton("视图查询(Parquet)")
        self.query_view_radio.setChecked(True)
        self.query_view_radio.setToolTip("通过 DuckDB 视图查询 Parquet 文件\n✅ 完整历史数据 | ⚠️ 速度较慢")
        self.query_mode_group.addButton(self.query_view_radio, 0)
        query_layout.addWidget(self.query_view_radio)
        
        self.query_table_radio = QRadioButton("物理表查询(DuckDB)")
        self.query_table_radio.setToolTip("直接查询 DuckDB 物理表\n✅ 快速响应 | ⚠️ 仅限已下载数据")
        self.query_mode_group.addButton(self.query_table_radio, 1)
        query_layout.addWidget(self.query_table_radio)
        
        self.query_mode_group.buttonClicked.connect(self.on_query_mode_changed)
        
        row2_layout.addWidget(query_group)
        row2_layout.addStretch()
        main_layout.addLayout(row2_layout)
        
        # ===== 第3行：存储模式和性能信息（大字体显示）=====
        row3_layout = QHBoxLayout()
        
        # 存储模式信息面板
        storage_frame = QFrame()
        storage_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        storage_layout = QHBoxLayout(storage_frame)
        storage_layout.setContentsMargins(10, 6, 10, 6)
        
        self.storage_mode_label = QLabel("📦 存储模式: 检测中...")
        self.storage_mode_label.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #1976D2;
            padding: 2px 8px;
            background-color: #E3F2FD;
            border-radius: 4px;
        """)
        storage_layout.addWidget(self.storage_mode_label)
        
        # 数据库架构标签
        self.db_arch_label = QLabel("")
        self.db_arch_label.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 4px;
        """)
        storage_layout.addWidget(self.db_arch_label)
        
        storage_layout.addSpacing(30)
        
        # 当前数据类型状态（联动显示）
        self.current_dtype_label = QLabel("📊 当前数据类型: --")
        self.current_dtype_label.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #388E3C;
            padding: 2px 8px;
            background-color: #E8F5E9;
            border-radius: 4px;
        """)
        storage_layout.addWidget(self.current_dtype_label)
        
        row3_layout.addWidget(storage_frame)
        row3_layout.addSpacing(20)
        
        # 性能信息面板
        perf_frame = QFrame()
        perf_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        perf_layout = QHBoxLayout(perf_frame)
        perf_layout.setContentsMargins(10, 6, 10, 6)
        
        self.performance_label = QLabel("⏱️ 性能: --")
        self.performance_label.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #F57C00;
            padding: 2px 8px;
            background-color: #FFF3E0;
            border-radius: 4px;
        """)
        self.performance_label.setToolTip("显示最近一次查询的性能指标\n点击查看详细性能报告")
        self.performance_label.mousePressEvent = self.on_performance_label_clicked
        perf_layout.addWidget(self.performance_label)
        
        # 缓存状态标签
        self.cache_status_label = QLabel("💾 缓存: 已启用")
        self.cache_status_label.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            color: #7B1FA2;
            padding: 2px 8px;
            background-color: #F3E5F5;
            border-radius: 4px;
        """)
        perf_layout.addWidget(self.cache_status_label)
        
        row3_layout.addWidget(perf_frame)
        row3_layout.addStretch()
        
        main_layout.addLayout(row3_layout)
        
        return group

    def create_stock_selection_panel(self):
        """创建股票选择面板"""
        group = QGroupBox("股票列表")
        layout = QVBoxLayout(group)

        # 搜索和筛选
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("🔍 搜索:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入代码全局搜索（如000001）...")
        self.search_edit.textChanged.connect(self.on_search_text_changed)
        filter_layout.addWidget(self.search_edit)

        self.filter_all_btn = QPushButton("全部")
        self.filter_all_btn.setCheckable(True)
        self.filter_all_btn.setChecked(True)
        self.filter_all_btn.clicked.connect(lambda: self.load_stock_list('all'))
        filter_layout.addWidget(self.filter_all_btn)

        self.filter_stock_btn = QPushButton("股票")
        self.filter_stock_btn.setCheckable(True)
        self.filter_stock_btn.clicked.connect(lambda: self.load_stock_list('stock'))
        filter_layout.addWidget(self.filter_stock_btn)

        self.filter_bond_btn = QPushButton("债券")
        self.filter_bond_btn.setCheckable(True)
        self.filter_bond_btn.clicked.connect(lambda: self.load_stock_list('bond'))
        filter_layout.addWidget(self.filter_bond_btn)

        layout.addLayout(filter_layout)

        # 股票表格
        self.stock_table = QTableWidget()
        self.stock_table.setColumnCount(5)  # 【修改】增加"数据类型"列
        self.stock_table.setHorizontalHeaderLabels(["股票代码", "类型", "数据类型", "记录数", "日期范围"])
        self.stock_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.stock_table.setSelectionMode(QTableWidget.SingleSelection)
        self.stock_table.setSortingEnabled(True)
        self.stock_table.setMaximumHeight(250)
        
        # 【新增】优化列宽设置（2026-04-12）- 根据内容合理分配
        header = self.stock_table.horizontalHeader()
        header.setStretchLastSection(False)  # 【修改】关闭自动拉伸，手动控制
        self.stock_table.setColumnWidth(0, 110)  # 股票代码（稍宽以容纳完整代码）
        self.stock_table.setColumnWidth(1, 45)   # 类型（股票/ETF）
        self.stock_table.setColumnWidth(2, 70)   # 数据类型（日线/1m等）
        self.stock_table.setColumnWidth(3, 65)   # 记录数
        self.stock_table.setColumnWidth(4, 280)  # 日期范围（适中宽度，不占用过多空间）
        
        self.stock_table.itemSelectionChanged.connect(self.on_stock_selection_changed)
        self.stock_table.itemDoubleClicked.connect(self.on_stock_double_clicked)
        layout.addWidget(self.stock_table)

        return group

    def create_data_table_panel(self):
        """创建数据表格面板"""
        group = QGroupBox("详细数据")
        layout = QVBoxLayout(group)

        # 标签页切换（行情数据 / 财务数据）
        self.data_tab_widget = QTabWidget()

        # 行情数据标签页
        market_data_widget = QWidget()
        market_layout = QVBoxLayout(market_data_widget)

        # 统计信息
        stats_layout = QHBoxLayout()
        self.data_stats_label = QLabel("共 0 条记录")
        self.data_stats_label.setStyleSheet("color: #757575;")
        stats_layout.addWidget(self.data_stats_label)
        stats_layout.addStretch()
        market_layout.addLayout(stats_layout)

        # 数据表格
        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSortingEnabled(True)
        self.data_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.data_table.setColumnCount(8)
        self.data_table.setHorizontalHeaderLabels([
            "日期", "开盘", "最高", "最低", "收盘", "涨跌幅", "成交量", "成交额"
        ])

        # 【优化】智能列宽设置（2026-04-12）
        # 根据数据类型动态调整日期列宽度
        header = self.data_table.horizontalHeader()
        header.setStretchLastSection(True)  # 最后一列自动拉伸
        
        # 默认列宽（会在加载数据时根据数据类型动态调整）
        self.data_table.setColumnWidth(0, 120)   # 日期/日期时间
        self.data_table.setColumnWidth(1, 75)    # 开盘
        self.data_table.setColumnWidth(2, 75)    # 最高
        self.data_table.setColumnWidth(3, 75)    # 最低
        self.data_table.setColumnWidth(4, 75)    # 收盘
        self.data_table.setColumnWidth(5, 70)    # 涨跌幅
        self.data_table.setColumnWidth(6, 130)    # 成交量
        # 成交额列会自动拉伸（stretchLastSection）

        market_layout.addWidget(self.data_table)
        self.data_tab_widget.addTab(market_data_widget, "📈 行情数据")

        # 财务数据标签页
        financial_data_widget = QWidget()
        financial_layout = QVBoxLayout(financial_data_widget)

        # 财务数据统计
        fin_stats_layout = QHBoxLayout()
        self.fin_stats_label = QLabel("点击上方「加载财务数据」按钮查看")
        self.fin_stats_label.setStyleSheet("color: #757575;")
        fin_stats_layout.addWidget(self.fin_stats_label)
        fin_stats_layout.addStretch()
        financial_layout.addLayout(fin_stats_layout)

        # 操作按钮
        fin_btn_layout = QHBoxLayout()
        self.load_fin_btn = QPushButton("💰 加载财务数据")
        self.load_fin_btn.clicked.connect(self.load_financial_data)
        fin_btn_layout.addWidget(self.load_fin_btn)

        fin_btn_layout.addStretch()
        financial_layout.addLayout(fin_btn_layout)

        # 财务数据表格
        self.financial_table = QTableWidget()
        self.financial_table.setAlternatingRowColors(True)
        self.financial_table.setSortingEnabled(True)
        self.financial_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.financial_table.setColumnCount(5)
        self.financial_table.setHorizontalHeaderLabels([
            "报告期", "净资产收益率", "毛利率", "净利率", "资产负债率"
        ])

        # 设置列宽
        self.financial_table.setColumnWidth(0, 100)
        for i in range(1, 5):
            self.financial_table.setColumnWidth(i, 100)

        financial_layout.addWidget(self.financial_table)
        self.data_tab_widget.addTab(financial_data_widget, "💰 财务数据")

        # Tick数据标签页
        tick_data_widget = QWidget()
        tick_layout = QVBoxLayout(tick_data_widget)

        # Tick数据统计
        tick_stats_layout = QHBoxLayout()
        self.tick_stats_label = QLabel("选择日期后点击「加载Tick数据」查看")
        self.tick_stats_label.setStyleSheet("color: #757575;")
        tick_stats_layout.addWidget(self.tick_stats_label)
        tick_stats_layout.addStretch()
        tick_layout.addLayout(tick_stats_layout)

        # Tick数据操作区域
        tick_ctrl_layout = QHBoxLayout()

        tick_ctrl_layout.addWidget(QLabel("选择日期:"))
        self.tick_date_edit = QDateEdit()
        self.tick_date_edit.setCalendarPopup(True)
        self.tick_date_edit.setDate(QDate.currentDate())
        self.tick_date_edit.setDisplayFormat("yyyy-MM-dd")
        tick_ctrl_layout.addWidget(self.tick_date_edit)

        tick_ctrl_layout.addWidget(QLabel("时间段:"))
        self.tick_time_combo = QComboBox()
        self.tick_time_combo.addItems(["全天", "9:15-11:30", "13:00-15:00", "9:30-10:00", "10:00-10:30", "14:00-14:30"])
        tick_ctrl_layout.addWidget(self.tick_time_combo)

        tick_ctrl_layout.addStretch()

        self.load_tick_btn = QPushButton("📊 加载Tick数据")
        self.load_tick_btn.clicked.connect(self.load_tick_data)
        tick_ctrl_layout.addWidget(self.load_tick_btn)

        tick_layout.addLayout(tick_ctrl_layout)

        # Tick数据表格
        self.tick_table = QTableWidget()
        self.tick_table.setAlternatingRowColors(True)
        self.tick_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.tick_table.setColumnCount(7)
        self.tick_table.setHorizontalHeaderLabels([
            "时间", "价格", "成交量", "成交额", "买卖方向", "持仓量", "数据类型"
        ])

        # 设置列宽
        self.tick_table.setColumnWidth(0, 120)
        self.tick_table.setColumnWidth(1, 80)
        self.tick_table.setColumnWidth(2, 100)
        self.tick_table.setColumnWidth(3, 100)
        self.tick_table.setColumnWidth(4, 80)
        self.tick_table.setColumnWidth(5, 100)
        self.tick_table.setColumnWidth(6, 80)

        tick_layout.addWidget(self.tick_table)
        self.data_tab_widget.addTab(tick_data_widget, "📊 Tick数据")

        layout.addWidget(self.data_tab_widget)

        return group

    def load_initial_data(self):
        """加载初始数据"""
        self.load_stock_list('all')
        
        # 【新增】初始化存储模式信息和查询方式（2026-04-12）
        self._init_storage_mode_info()
    
    def _init_storage_mode_info(self):
        """初始化存储模式信息显示 - 优化版（2026-04-12）"""
        try:
            # 获取存储模式配置
            storage_mode = self.config.get('storage', {}).get('data_source', {}).get('mode', 'parquet')
            
            # 【修复】支持新的 dual 双重存储模式（2026-04-12）
            if storage_mode == 'parquet':
                mode_text = "Parquet 文件模式"
                mode_color = "#1976D2"  # 蓝色
                mode_bg = "#E3F2FD"
            elif storage_mode == 'database':
                mode_text = "数据库表模式"
                mode_color = "#388E3C"  # 绿色
                mode_bg = "#E8F5E9"
            elif storage_mode == 'dual':
                mode_text = "双重存储模式（Parquet + DuckDB表）"
                mode_color = "#9C27B0"  # 紫色
                mode_bg = "#F3E5F5"
            else:
                mode_text = f"未知模式 ({storage_mode})"
                mode_color = "#F57C00"  # 橙色
                mode_bg = "#FFF3E0"
            
            if hasattr(self, 'storage_mode_label'):
                self.storage_mode_label.setText(f"📦 存储模式: {mode_text}")
                self.storage_mode_label.setStyleSheet(f"""
                    font-size: 13px;
                    font-weight: bold;
                    color: {mode_color};
                    padding: 2px 8px;
                    background-color: {mode_bg};
                    border-radius: 4px;
                """)
            
            # 【新增】从配置文件加载用户偏好设置（2026-04-12）
            try:
                from src.core.utils.config_manager import get_config_manager
                config_mgr = get_config_manager()
                
                # 加载查询方式偏好
                query_pref = config_mgr.get_query_preference()
                if hasattr(self, 'query_view_radio') and hasattr(self, 'query_table_radio'):
                    if query_pref == 'view':
                        self.query_view_radio.setChecked(True)
                        print(f"   🔍 查询方式: 视图查询（从配置文件加载）")
                    elif query_pref == 'table':
                        self.query_table_radio.setChecked(True)
                        print(f"   🔍 查询方式: 物理表查询（从配置文件加载）")
                    else:
                        print(f"   🔍 查询方式: 自动（默认）")
                
                # 加载缓存设置
                cache_enabled, cache_max_size, _ = config_mgr.get_cache_settings()
                self._cache_max_size = cache_max_size
                
                if hasattr(self, 'cache_toggle_btn'):
                    self.cache_toggle_btn.setChecked(cache_enabled)
                    
                    # 触发UI更新（模拟点击）
                    if cache_enabled:
                        self.cache_toggle_btn.click()  # 开启状态
                        self.cache_toggle_btn.click()  # 保持开启
                    else:
                        # 先确保是开启状态，再关闭
                        if not self.cache_toggle_btn.isChecked():
                            self.cache_toggle_btn.click()
                        self.cache_toggle_btn.click()
                    
                    print(f"   💾 缓存设置: enabled={cache_enabled}, max_size={cache_max_size}（从配置文件加载）")
                
                # 【新增】更新缓存容量SpinBox显示（2026-04-12）
                if hasattr(self, 'cache_size_spin'):
                    self.cache_size_spin.setValue(cache_max_size)
                    print(f"   📦 缓存容量UI已更新: {cache_max_size} 条")
                
            except Exception as e:
                print(f"   ⚠️ 加载用户偏好失败: {e}")
            
            # 【新增】数据库架构信息（2026-04-12）- 优化版
            if hasattr(self, 'db_arch_label'):
                has_dual_db = 'database' in self.config and \
                             'data_db' in self.config.get('database', {}) and \
                             'view_db' in self.config.get('database', {})
                
                if has_dual_db:
                    # 【优化】使用更清晰的架构描述
                    arch_text = "🔗 物理表+视图双库架构"
                    arch_color = "#388E3C"  # 绿色
                    
                    data_db_file = self.config['database'].get('data_db', {}).get('dbfile', 'N/A')
                    view_db_file = self.config['database'].get('view_db', {}).get('dbfile', 'N/A')
                    
                    # 【新增】保存视图数据库完整路径（2026-04-12）
                    if view_db_file and view_db_file != 'N/A':
                        from pathlib import Path
                        view_db_full_path = str(Path(self.db_path).parent / view_db_file)
                        self.view_db_path = view_db_full_path
                        
                        # 【诊断】检查视图数据库文件是否存在及大小（2026-04-12）
                        view_db_path_obj = Path(self.view_db_path)
                        if view_db_path_obj.exists():
                            view_size_kb = view_db_path_obj.stat().st_size / 1024
                            print(f"   🔗 视图数据库: {self.view_db_path} ({view_size_kb:.1f} KB) ✅")
                        else:
                            print(f"   ⚠️ 视图数据库: {self.view_db_path} (文件不存在！)")
                    else:
                        self.view_db_path = self.db_path  # 回退到主数据库
                        print(f"   ⚠️ 视图数据库未配置，回退到主数据库")
                    
                    # 【诊断】检查物理表数据库文件是否存在及大小（2026-04-12）
                    data_db_path_obj = Path(self.db_path)
                    if data_db_path_obj.exists():
                        data_size_kb = data_db_path_obj.stat().st_size / 1024
                        print(f"   📦 物理表数据库: {self.db_path} ({data_size_kb:.1f} KB) ✅")
                    else:
                        print(f"   ⚠️ 物理表数据库: {self.db_path} (文件不存在！)")
                    
                    self.db_arch_label.setToolTip(
                        f"📦 双数据库分离架构\n\n"
                        f"【物理表库】{data_db_file}\n"
                        f"   └─ 存储实际数据（DuckDB物理表）\n"
                        f"   └─ 支持快速查询、批量操作\n\n"
                        f"【视图库】{view_db_file}\n"
                        f"   └─ 仅包含视图定义\n"
                        f"   └─ 映射到 Parquet 文件\n\n"
                        f"💡 优势：查询灵活，可按需选择数据源"
                    )
                    
                    # 启用物理表查询选项
                    if hasattr(self, 'query_table_radio'):
                        self.query_table_radio.setEnabled(True)
                else:
                    arch_text = "⚪ 单库模式"
                    arch_color = "#F57C00"  # 橙色
                    self.db_arch_label.setToolTip(
                        "当前为单数据库模式\n\n"
                        "所有数据和视图存储在同一个数据库中"
                    )
                    
                    # 禁用物理表查询选项
                    if hasattr(self, 'query_table_radio'):
                        self.query_table_radio.setEnabled(False)
                
                self.db_arch_label.setText(arch_text)
                self.db_arch_label.setStyleSheet(f"""
                    font-size: 13px;
                    font-weight: bold;
                    color: {arch_color};
                    padding: 2px 8px;
                    background-color: {'#E8F5E9' if has_dual_db else '#FFF3E0'};
                    border-radius: 4px;
                """)
            
            # 【新增】初始化当前数据类型显示（2026-04-12）
            if hasattr(self, 'current_dtype_label') and hasattr(self, 'data_type_combo'):
                # 获取下拉框的当前选择
                current_text = self.data_type_combo.currentText()
                
                # 数据类型映射
                dtype_display_map = {
                    "日线": "日线数据(1d)",
                    "1分钟": "分钟线数据(1m)",
                    "5分钟": "分钟线数据(5m)",
                    "15分钟": "分钟线数据(15m)",
                    "30分钟": "分钟线数据(30m)",
                    "60分钟": "分钟线数据(60m)",
                    "周线": "周线数据(weekly)",
                    "月线": "月线数据(monthly)"
                }
                
                display_text = dtype_display_map.get(current_text, current_text)
                self.current_dtype_label.setText(f"📊 当前数据类型: {display_text}")
                
                print(f"   📊 当前数据类型已初始化: {display_text}")
            
            print(f"✅ 存储模式信息已初始化: {mode_text}")
            
            # 【新增】启动时自动检查并修复视图（2026-04-12）
            self._auto_check_and_fix_views()
            
        except Exception as e:
            print(f"⚠️ 初始化存储模式信息失败: {e}")
    
    def _auto_check_and_fix_views(self):
        """
        启动时自动检查视图状态，如有问题则自动修复
        
        检查项：
        1. 视图库文件是否存在
        2. 关键视图是否存在
        3. Tick 视图类型是否匹配
        4. 是否有可用的数据
        """
        try:
            import duckdb
            from pathlib import Path
            
            print("\n🔍 [自动检查] 开始检查数据库视图状态...")
            
            # 1. 检查视图库文件
            view_db_path = getattr(self, 'view_db_path', None) or self.db_path
            view_db_file = Path(view_db_path)
            
            if not view_db_file.exists():
                print(f"   ⚠️ 视图数据库文件不存在: {view_db_path}")
                print(f"   🔄 尝试创建视图数据库并重建视图...")
                self._rebuild_views_if_needed()
                return
            
            view_size = view_db_file.stat().st_size / 1024
            print(f"   ✅ 视图库文件存在: {view_db_path} ({view_size:.1f} KB)")
            
            # 2. 连接数据库检查视图
            conn = duckdb.connect(view_db_path, read_only=False)
            
            try:
                # 检查关键视图是否存在
                critical_views = ['stock_daily', 'stock_1m', 'stock_tick']
                missing_views = []
                broken_views = []
                
                for view_name in critical_views:
                    try:
                        # 测试查询能否执行
                        test_result = conn.execute(f"""
                            SELECT COUNT(*) FROM {view_name} LIMIT 1
                        """).fetchone()
                        
                        if test_result and test_result[0] is not None:
                            count = conn.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()[0]
                            print(f"   ✅ 视图 {view_name}: {count:,} 条记录")
                        else:
                            missing_views.append(view_name)
                            
                    except Exception as ve:
                        error_str = str(ve).lower()
                        if "does not exist" in error_str or "not found" in error_str:
                            missing_views.append(view_name)
                        elif "types don't match" in error_str or "altered" in error_str:
                            broken_views.append(view_name)
                            print(f"   ⚠️ 视图 {view_name}: 类型不匹配 → 需要重建")
                        else:
                            broken_views.append(view_name)
                            print(f"   ⚠️ 视图 {view_name}: {str(ve)[:60]}")
                
                # 3. 根据检查结果决定是否需要重建
                if missing_views or broken_views:
                    print(f"\n   🔄 发现问题:")
                    if missing_views:
                        print(f"      • 缺失视图: {missing_views}")
                    if broken_views:
                        print(f"      • 异常视图: {broken_views}")
                    print(f"   🔧 自动重建所有视图...")
                    
                    conn.close()
                    self._rebuild_views_if_needed()
                else:
                    total_stocks = conn.execute("""
                        SELECT COUNT(DISTINCT stock_code) FROM stock_daily WHERE stock_code IS NOT NULL
                    """).fetchone()[0] or 0
                    
                    print(f"\n   ✅ 所有视图检查通过！可用标的: {total_stocks} 只")
                    
            finally:
                conn.close()
                
        except Exception as e:
            print(f"   ❌ 自动检查视图失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _rebuild_views_if_needed(self):
        """重建视图（内部方法）"""
        try:
            from src.core.data.storage.view_manager import ViewManager
            
            view_db_path = getattr(self, 'view_db_path', None) or self.db_path
            
            print(f"   📝 正在重建视图: {view_db_path}")
            
            view_manager = ViewManager(view_db_path, self.config)
            
            if view_manager.refresh_all_views():
                print(f"   ✅ 视图重建成功！")
            else:
                print(f"   ⚠️ 视图重建返回失败")
                
        except Exception as e:
            print(f"   ❌ 重建视图异常: {e}")
    
    def on_cache_mode_changed(self):
        """缓存模式切换处理 - 完整实现（2026-04-12）"""
        try:
            is_enabled = self.cache_toggle_btn.isChecked()
            
            # 【核心】更新内部缓存状态
            self._cache_enabled = is_enabled
            
            # 【新增】保存到全局配置文件（2026-04-12）
            try:
                from src.core.utils.config_manager import get_config_manager
                config_mgr = get_config_manager()
                config_mgr.set_cache_settings(
                    enabled=is_enabled,
                    max_size=self._cache_max_size,
                    auto_save=True
                )
                print(f"💾 缓存设置已保存到配置文件")
            except Exception as e:
                print(f"⚠️ 保存缓存配置失败: {e}")
            
            if is_enabled:
                self.cache_toggle_btn.setText("💾 缓存: 开启")
                self.cache_toggle_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #E8F5E9;
                        border: 1px solid #4CAF50;
                        color: #2E7D32;
                        font-weight: bold;
                        padding: 4px 12px;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background-color: #C8E6C9;
                    }
                """)
                cache_status = "已启用"
                cache_color = "#7B1FA2"
                cache_bg = "#F3E5F5"
                
                print(f"✅ 缓存模式已启用 | 当前缓存: {len(self._data_cache)} 条")
                print(f"   📊 缓存统计: 命中={self._cache_hits}, 未命中={self._cache_misses}")
                
            else:
                self.cache_toggle_btn.setText("💾 缓存: 关闭")
                self.cache_toggle_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FFEBEE;
                        border: 1px solid #f44336;
                        color: #c62828;
                        font-weight: bold;
                        padding: 4px 12px;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background-color: #FFCDD2;
                    }
                """)
                cache_status = "已禁用"
                cache_color = "#757575"
                cache_bg = "#EEEEEE"
                
                # 【关键】关闭缓存时清空现有缓存
                cleared_count = len(self._data_cache)
                self._data_cache.clear()
                self._cache_hits = 0
                self._cache_misses = 0
                
                print(f"⚠️ 缓存模式已禁用 | 已清空 {cleared_count} 条缓存数据")
            
            # 更新缓存状态标签
            if hasattr(self, 'cache_status_label'):
                stats_text = f"💾 缓存: {cache_status}"
                if is_enabled and len(self._data_cache) > 0:
                    stats_text += f" ({len(self._data_cache)}条)"
                    
                self.cache_status_label.setText(stats_text)
                self.cache_status_label.setStyleSheet(f"""
                    font-size: 13px;
                    font-weight: bold;
                    color: {cache_color};
                    padding: 2px 8px;
                    background-color: {cache_bg};
                    border-radius: 4px;
                """)
                
                # 更新工具提示显示缓存统计
                if is_enabled:
                    hit_rate = (self._cache_hits / (self._cache_hits + self._cache_misses) * 100 
                              if (self._cache_hits + self._cache_misses) > 0 else 0)
                    self.cache_status_label.setToolTip(
                        f"📦 缓存状态详情\n\n"
                        f"• 状态: 已启用\n"
                        f"• 缓存条目: {len(self._data_cache)} / {self._cache_max_size}\n"
                        f"• 命中次数: {self._cache_hits}\n"
                        f"• 未命中次数: {self._cache_misses}\n"
                        f"• 命中率: {hit_rate:.1f}%\n\n"
                        f"💡 提示:\n"
                        f"• 开启后重复查询相同数据将从缓存读取\n"
                        f"• 关闭后将每次都从数据库查询\n"
                        f"• 性能测试期间建议关闭以确保准确"
                    )
                else:
                    self.cache_status_label.setToolTip(
                        "📦 缓存已禁用\n\n"
                        "所有数据查询将直接访问数据库\n"
                        "不会使用任何缓存数据"
                    )
            
            print(f"🔄 缓存模式已{'启用' if is_enabled else '禁用'}")
            
        except Exception as e:
            print(f"❌ 缓存模式切换失败: {e}")
    
    def on_cache_size_changed(self, value):
        """缓存大小变化处理 - 保存到全局配置（2026-04-12）"""
        try:
            # 更新内部缓存大小限制
            old_size = self._cache_max_size
            self._cache_max_size = value
            
            # 【新增】如果新值小于当前缓存数量，需要清理超出部分
            if len(self._data_cache) > value:
                # 按照FIFO顺序删除最早的条目
                while len(self._data_cache) > value:
                    self._data_cache.popitem(last=False)
                print(f"🗑️ 缓存已清理: {old_size} → {value} 条 (删除了 {old_size - value} 条)")
            
            # 【核心】保存到全局配置文件
            try:
                from src.core.utils.config_manager import get_config_manager
                config_mgr = get_config_manager()
                config_mgr.set_cache_settings(
                    enabled=self.cache_toggle_btn.isChecked(),
                    max_size=value,
                    auto_save=True
                )
                print(f"💾 缓存容量设置已保存: {value} 条")
            except Exception as e:
                print(f"⚠️ 保存缓存配置失败: {e}")
            
            # 更新工具提示
            if hasattr(self, 'cache_status_label'):
                self.cache_status_label.setToolTip(
                    f"📦 最大缓存容量: {value} 条\n"
                    f"• 当前缓存: {len(self._data_cache)} 条\n"
                    f"• 调整滑块或输入框可修改"
                )
            
            print(f"📏 缓存容量已调整: {old_size} → {value} 条 | 当前缓存: {len(self._data_cache)} 条")
            
        except Exception as e:
            print(f"❌ 缓存容量调整失败: {e}")
    
    def on_performance_label_clicked(self, event):
        """性能标签点击事件 - 显示详细报告"""
        try:
            from PyQt5.QtWidgets import QMessageBox
            
            if not hasattr(self, '_last_performance_data') or not self._last_performance_data:
                QMessageBox.information(
                    self,
                    "性能报告",
                    "暂无性能数据\n\n请先加载数据或运行批量性能测试",
                    QMessageBox.Ok
                )
                return
            
            data = self._last_performance_data
            
            report_text = f"""📊 查询性能详细报告

━━━━━━━━━━━━━━━━━━━━━━━━━━

【基本信息】
• 查询方式：{data.get('mode', '未知')}
• 数据类型：{data.get('data_type', '未知')}
• 股票代码：{data.get('stock_code', '未选择')}

【性能指标】
• ⏱️ 查询耗时：{data.get('elapsed', 0):.3f} 秒
• 📈 记录数量：{data.get('record_count', 0):,} 条
• 🚀 吞吐量：{data.get('throughput', 0):,.0f} 条/秒
• 🎯 性能评级：{data.get('level', '未知')}

【系统状态】
• 💾 缓存模式：{'启用' if self.cache_toggle_btn.isChecked() else '禁用'}
• 🔍 查询方式：{'视图查询' if self.query_view_radio.isChecked() else '物理表查询'}
• 📦 存储模式：{self.storage_mode_label.text().replace('📦 存储模式: ', '')}

━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 提示：
• 点击「⚡ 性能测试」按钮可进行批量测试
• 批量测试会对比多种数据类型和查询方式
• 测试期间将自动禁用缓存以确保结果准确"""
            
            QMessageBox.information(
                self,
                "📊 性能报告",
                report_text,
                QMessageBox.Ok
            )
            
        except Exception as e:
            print(f"⚠️ 显示性能报告失败: {e}")
    
    def on_query_mode_changed(self, button):
        """
        查询方式变更处理 - 支持配置持久化（2026-04-12）
        
        Args:
            button: 被选中的单选按钮
        """
        try:
            mode_id = self.query_mode_group.id(button)
            
            # 【新增】保存查询方式偏好到配置文件（2026-04-12）
            try:
                from src.core.utils.config_manager import get_config_manager
                config_mgr = get_config_manager()
                
                if mode_id == 0:
                    config_mgr.set_query_preference('view', auto_save=True)
                elif mode_id == 1:
                    config_mgr.set_query_preference('table', auto_save=True)
                    
                print(f"🔍 查询方式偏好已保存到配置文件")
                
            except Exception as e:
                print(f"⚠️ 保存查询偏好失败: {e}")
            
            if mode_id == 0:
                # 视图查询
                print("🔄 切换到【视图查询】模式")
                self.performance_label.setText("⏱️ 性能: --")
                self.performance_label.setStyleSheet("color: #666; font-size: 11px;")
            elif mode_id == 1:
                # 物理表查询
                print("🔄 切换到【物理表查询】模式")
                self.performance_label.setText("⏱️ 性能: --")
                self.performance_label.setStyleSheet("color: #666; font-size: 11px;")
            
            # 提示用户重新加载数据
            if self.current_stock:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, 
                    "提示", 
                    f"已切换到{'视图' if mode_id == 0 else '物理表'}查询模式\n\n请点击「加载数据」按钮重新查询",
                    QMessageBox.Ok
                )
                
        except Exception as e:
            print(f"❌ 查询方式变更处理失败: {e}")

    def load_stock_list(self, filter_type: str = 'all', search_text: str = ''):
        """加载股票列表（支持全局搜索）"""
        try:
            # 构建WHERE子句
            conditions = []

            # 类型筛选
            if filter_type != 'all':
                conditions.append(f"symbol_type = '{filter_type}'")

            # 搜索筛选
            if search_text:
                conditions.append(f"stock_code LIKE '%{search_text}%'")

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # 如果有搜索文本，显示所有匹配结果；否则限制显示数量
            limit_clause = "" if search_text else "LIMIT 5000"

            # 根据当前数据类型选择对应的表
            current_data_type = getattr(self, 'data_type', '1d')
            
            if current_data_type == 'weekly':
                source_table = 'stock_weekly'
                date_column = 'date'
            elif current_data_type == 'monthly':
                source_table = 'stock_monthly'
                date_column = 'date'
            elif current_data_type == 'tick':
                source_table = 'stock_tick'
                date_column = 'datetime'
            elif current_data_type in ['1m', '5m', '15m', '30m', '60m']:
                source_table = f'stock_{current_data_type}'
                date_column = 'datetime'
            else:
                source_table = 'stock_daily'
                date_column = 'date'

            print(f"📋 [load_stock_list] 当前数据类型: {current_data_type}, 查询表: {source_table}")

            # 构建查询语句
            query = f"""
                SELECT
                    stock_code,
                    symbol_type,
                    COUNT(*) as count,
                    MIN({date_column}) as min_date,
                    MAX({date_column}) as max_date
                FROM {source_table}
                {where_clause}
                GROUP BY stock_code, symbol_type
                ORDER BY stock_code
                {limit_clause}
            """

            if DB_MANAGER_AVAILABLE and self.db_path:
                manager = get_db_manager(self.db_path)
                df = manager.query_dataframe(query)
            else:
                # 不再使用直接的duckdb.connect，避免递归调用
                df = pd.DataFrame()  # 空DataFrame

            self.populate_stock_table(df)

            # 显示搜索结果统计
            if search_text:
                self.data_stats_label.setText(f"搜索 '{search_text}': 找到 {len(df)} 只股票")
            else:
                self.data_stats_label.setText(f"共 {len(df)} 只股票")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载股票列表失败: {e}")

    def populate_stock_table(self, df: pd.DataFrame):
        """填充股票表格"""
        self.stock_table.setRowCount(len(df))
        
        # 【新增】获取当前数据类型的显示名称（2026-04-12）
        current_data_type = getattr(self, 'data_type', '1d')
        data_type_display_map = {
            '1d': '日线', 'daily': '日线',
            '1m': '1分钟', '5m': '5分钟', '15m': '15分钟', 
            '30m': '30分钟', '60m': '60分钟',
            'weekly': '周线', '1w': '周线',
            'monthly': '月线', '1M': '月线',
            'tick': 'Tick'
        }
        data_type_display = data_type_display_map.get(current_data_type, current_data_type)

        for row_idx, (_, data_row) in enumerate(df.iterrows()):
            # 股票代码
            code_item = QTableWidgetItem(data_row['stock_code'])
            code_item.setFont(QFont("Consolas", 10))
            self.stock_table.setItem(row_idx, 0, code_item)

            # 类型
            type_map = {'stock': '股票', 'bond': '债券', 'etf': 'ETF'}
            type_item = QTableWidgetItem(type_map.get(data_row['symbol_type'], data_row['symbol_type']))
            self.stock_table.setItem(row_idx, 1, type_item)
            
            # 【新增】数据类型列（2026-04-12）
            dtype_item = QTableWidgetItem(data_type_display)
            dtype_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            dtype_item.setToolTip(f"当前查看的数据周期: {current_data_type}")
            self.stock_table.setItem(row_idx, 2, dtype_item)

            # 记录数（原索引2 → 现在是索引3）
            count_item = QTableWidgetItem(f"{data_row['count']:,}")
            count_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.stock_table.setItem(row_idx, 3, count_item)

            # 日期范围（原索引3 → 现在是索引4）
            min_date = str(data_row['min_date'])[:10]
            max_date = str(data_row['max_date'])[:10]
            date_item = QTableWidgetItem(f"{min_date} ~ {max_date}")
            self.stock_table.setItem(row_idx, 4, date_item)

        self.data_stats_label.setText(f"共 {len(df)} 只股票")

    def on_search_text_changed(self, text: str):
        """搜索文本改变（使用延迟避免频繁查询）"""
        # 停止之前的定时器
        if self.search_timer:
            self.search_timer.stop()
            self.search_timer = None

        # 如果文本为空，重新加载当前类型的所有股票
        if not text.strip():
            # 获取当前选中的筛选类型
            if self.filter_all_btn.isChecked():
                filter_type = 'all'
            elif self.filter_stock_btn.isChecked():
                filter_type = 'stock'
            elif self.filter_bond_btn.isChecked():
                filter_type = 'bond'
            else:
                filter_type = 'all'

            self.load_stock_list(filter_type, '')
            return

        # 延迟500ms后再搜索，避免输入时频繁查询
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(lambda: self.perform_global_search(text))
        self.search_timer.start(500)

    def perform_global_search(self, search_text: str):
        """执行全局搜索"""
        search_text = search_text.strip().upper()

        if not search_text:
            return

        # 获取当前选中的筛选类型
        if self.filter_all_btn.isChecked():
            filter_type = 'all'
        elif self.filter_stock_btn.isChecked():
            filter_type = 'stock'
        elif self.filter_bond_btn.isChecked():
            filter_type = 'bond'
        else:
            filter_type = 'all'

        # 执行搜索
        self.load_stock_list(filter_type, search_text)

    def filter_stocks(self):
        """筛选股票（保留用于兼容性，现在由全局搜索替代）"""
        pass

    def on_stock_selection_changed(self):
        """股票选择改变"""
        selected_items = self.stock_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            stock_code = self.stock_table.item(row, 0).text()
            record_count = self.stock_table.item(row, 2).text()
            self.current_stock = stock_code
            self.stock_label.setText(f"当前股票: {stock_code}")
            self.record_count_label.setText(f"记录数: {record_count}")

    def on_stock_double_clicked(self, item: QTableWidgetItem):
        """双击股票加载数据"""
        self.load_current_stock()

    def on_data_type_changed(self, text: str):
        """数据类型改变 - 增强版（2026-04-12）"""
        print(f"🔄 [on_data_type_changed] 数据类型改变为: {text}")
        
        # 数据类型映射
        data_type_map = {
            "日线": ("1d", "日线数据"),
            "1分钟": ("1m", "分钟线(1m)"),
            "5分钟": ("5m", "分钟线(5m)"),
            "15分钟": ("15m", "分钟线(15m)"),
            "30分钟": ("30m", "分钟线(30m)"),
            "60分钟": ("60m", "分钟线(60m)"),
            "周线": ("weekly", "周线数据"),
            "月线": ("monthly", "月线数据")
        }
        
        data_type_code, data_type_display = data_type_map.get(text, ("1d", "日线"))
        
        # 【新增】更新当前数据类型属性和显示标签（2026-04-12）
        self.data_type = data_type_code
        
        if hasattr(self, 'current_dtype_label'):
            self.current_dtype_label.setText(f"📊 当前数据类型: {data_type_display}")
            print(f"✅ 数据类型联动更新: {data_type_display} ({data_type_code})")
        
        # 重新加载股票列表（从对应的表中）
        if hasattr(self, 'filter_all_btn') and self.filter_all_btn.isChecked():
            filter_type = 'all'
        elif hasattr(self, 'filter_stock_btn') and self.filter_stock_btn.isChecked():
            filter_type = 'stock'
        elif hasattr(self, 'filter_bond_btn') and self.filter_bond_btn.isChecked():
            filter_type = 'bond'
        else:
            filter_type = 'all'
        
        self.load_stock_list(filter_type)
        
        # 【修改】如果已选择股票，提示用户是否自动加载数据
        if self.current_stock:
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "数据类型变更",
                f"检测到数据类型已变更为「{text}」\n\n"
                f"是否立即重新加载 {self.current_stock} 的{data_type_display}？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                self.load_current_stock()
            else:
                # 清空详细数据区域，避免数据不一致
                if hasattr(self, 'data_table'):
                    self.data_table.setRowCount(0)
                if hasattr(self, 'data_stats_label'):
                    self.data_stats_label.setText("⚠️ 数据类型已变更，请点击「加载数据」刷新")

    def on_adjust_changed(self, text: str):
        """复权类型改变"""
        if self.current_stock:
            self.load_current_stock()

    def load_current_stock(self):
        """加载当前股票数据 - 支持缓存（2026-04-12）"""
        if not self.current_stock:
            QMessageBox.warning(self, "提示", "请先选择股票")
            return

        start_date = self.start_date_edit.date().toString('yyyy-MM-dd')
        end_date = self.end_date_edit.date().toString('yyyy-MM-dd')

        # 数据类型映射
        data_type_map = {
            "日线": "1d",
            "1分钟": "1m",
            "5分钟": "5m",
            "15分钟": "15m",
            "30分钟": "30m",
            "60分钟": "60m",
            "周线": "weekly",
            "月线": "monthly"
        }
        data_type = data_type_map.get(self.data_type_combo.currentText(), "1d")
        # 存储当前数据类型
        self.data_type = data_type

        # 复权类型映射
        adjust_map = {"不复权": "none", "前复权": "front", "后复权": "back"}
        adjust_type = adjust_map.get(self.adjust_combo.currentText(), "none")

        self.load_btn.setEnabled(False)
        self.load_btn.setText("加载中...")
        
        # 【新增】记录查询开始时间（2026-04-12）
        import time
        self._query_start_time = time.time()

        # 【核心】检查缓存（2026-04-12）
        cache_key = (self.current_stock, data_type, start_date, end_date)
        
        if self._cache_enabled and cache_key in self._data_cache:
            # 缓存命中！直接使用缓存数据
            cached_df = self._data_cache[cache_key]
            self._cache_hits += 1
            
            print(f"🎯 缓存命中! | {self.current_stock} | {data_type} | {start_date} ~ {end_date}")
            print(f"   📊 记录数: {len(cached_df):,}")
            
            # 模拟调用 on_data_loaded
            load_end_time = time.time()
            self.on_data_loaded(cached_df.copy(), self.current_stock)
            
            # 更新性能信息（标记为从缓存加载）
            elapsed = load_end_time - self._query_start_time
            self._update_performance_info_with_cache(load_end_time, len(cached_df), elapsed)
            
            return
        
        # 缓存未命中或缓存已禁用
        if self._cache_enabled:
            self._cache_misses += 1
            print(f"⚠️ 缓存未命中 | 将从数据库查询...")
        
        # 在线程中加载数据
        self.load_thread = DataLoadThread(
            self.current_stock, 
            start_date, 
            end_date, 
            adjust_type, 
            data_type, 
            self.db_path
        )
        self.load_thread.data_ready.connect(self.on_data_loaded)
        self.load_thread.error_occurred.connect(self.on_load_error)
        self.load_thread.start()

    def on_data_loaded(self, df: pd.DataFrame, stock_code: str):
        """数据加载完成"""
        import time
        # 【新增】记录加载完成时间（2026-04-12）
        load_end_time = time.time()
        
        self.current_data = df
        self.load_btn.setEnabled(True)
        self.load_btn.setText("📥 加载数据")

        if not df.empty:
            # 填充数据表格
            self.data_table.setRowCount(len(df))

            # 动态调整列数，支持更多数据列
            # 【优化】列头显示单位（2026-04-12）- 根据数据库实际存储的原始数值单位
            columns = [
                '日期', 
                '开盘(元)', '最高(元)', '最低(元)', '收盘(元)',  # 价格单位：元
                '涨跌(元)', '涨跌幅(%)',                           # 涨跌单位：元和百分比
                '成交量(手)', '成交额(元)',                        # 成交量单位：手，成交额单位：元（原始值）
                '均价(元/股)',                                     # 均价单位：元/股
                '换手率(%)'                                         # 换手率单位：百分比
            ]
            self.data_table.setColumnCount(len(columns))
            self.data_table.setHorizontalHeaderLabels(columns)

            # 【优化】智能列宽设置（2026-04-12）- 根据数据类型动态调整
            if hasattr(self, 'data_type') and self.data_type in ['1m', '5m', '15m', '30m', '60m', 'tick']:
                # 分钟线和Tick数据需要更宽的时间列（显示完整日期时间）
                # 【修改】加宽成交量和成交额列以显示完整数值和单位
                column_widths = [175, 70, 70, 70, 70, 65, 65, 105, 115, 70, 70]
            else:
                # 日线、周线、月线使用标准宽度
                # 【修改】加宽成交量和成交额列
                column_widths = [100, 70, 70, 70, 70, 65, 65, 105, 115, 70, 70]
            
            # 应用列宽设置
            for i, width in enumerate(column_widths):
                if i < self.data_table.columnCount():
                    self.data_table.setColumnWidth(i, width)
            
            # 【新增】自动调整起始时间为数据的实际范围（2026-04-12）
            if not df.empty and len(df) > 0:
                try:
                    # 获取数据的第一条和最后一条记录的日期
                    first_date = df.index[0] if isinstance(df.index, pd.DatetimeIndex) else df.iloc[0].name
                    last_date = df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else df.iloc[-1].name
                    
                    # 转换为 QDate
                    if hasattr(first_date, 'date'):
                        first_date = first_date.date()
                    if hasattr(last_date, 'date'):
                        last_date = last_date.date()
                    
                    from PyQt5.QtCore import QDate
                    q_first = QDate(first_date.year, first_date.month, first_date.day)
                    q_last = QDate(last_date.year, last_date.month, last_date.day)
                    
                    # 只在起始时间晚于数据开始时间时才调整（避免覆盖用户手动设置）
                    current_start = self.start_date_edit.date()
                    if q_first < current_start:
                        self.start_date_edit.setDate(q_first)
                        print(f"📅 自动调整起始时间: {q_first.toString('yyyy-MM-dd')}")
                    
                    # 确保结束时间不早于数据结束时间
                    current_end = self.end_date_edit.date()
                    if q_last > current_end:
                        self.end_date_edit.setDate(q_last)
                        
                except Exception as e:
                    print(f"⚠️ 自动调整日期范围失败: {e}")

            for row_idx, (date, row_data) in enumerate(df.iterrows()):
                # 日期/时间显示
                if hasattr(self, 'data_type') and self.data_type in ['1m', '5m', '15m', '30m', '60m', 'tick']:
                    # 分钟线和Tick数据显示完整的时间
                    date_item = QTableWidgetItem(str(date))
                else:
                    # 日线、周线、月线只显示日期
                    date_item = QTableWidgetItem(str(date)[:10])
                self.data_table.setItem(row_idx, 0, date_item)

                # OHLC
                for col_idx, col_name in enumerate(['open', 'high', 'low', 'close'], 1):
                    if col_name in row_data:
                        value = row_data[col_name]
                        item = QTableWidgetItem(f"{value:.2f}")

                        # 涨跌颜色（红涨绿跌）
                        if col_name == 'close':
                            if row_idx > 0:
                                prev_close = df.iloc[row_idx - 1]['close']
                                if value > prev_close:
                                    item.setForeground(QColor("#f44336"))  # 红涨
                                elif value < prev_close:
                                    item.setForeground(QColor("#4CAF50"))  # 绿跌
                    else:
                        item = QTableWidgetItem("-")
                    self.data_table.setItem(row_idx, col_idx, item)

                # 涨跌
                if 'change' in row_data:
                    change = row_data['change']
                    if pd.notna(change):
                        change_item = QTableWidgetItem(f"{change:+.2f}")
                        if change > 0:
                            change_item.setForeground(QColor("#f44336"))
                        elif change < 0:
                            change_item.setForeground(QColor("#4CAF50"))
                    else:
                        change_item = QTableWidgetItem("-")
                else:
                    change_item = QTableWidgetItem("-")
                self.data_table.setItem(row_idx, 5, change_item)

                # 涨跌幅
                if 'change_pct' in row_data:
                    pct_change = row_data['change_pct']
                    if pd.notna(pct_change):
                        pct_item = QTableWidgetItem(f"{pct_change:+.2f}%")
                        if pct_change > 0:
                            pct_item.setForeground(QColor("#f44336"))
                        elif pct_change < 0:
                            pct_item.setForeground(QColor("#4CAF50"))
                    else:
                        pct_item = QTableWidgetItem("-")
                else:
                    pct_item = QTableWidgetItem("-")
                self.data_table.setItem(row_idx, 6, pct_item)

                # 成交量（原始数值显示，不转换单位）
                if 'volume' in row_data:
                    volume = row_data['volume']
                    if pd.notna(volume) and volume > 0:
                        # 【修复】按原始数据库数值展示（2026-04-12）
                        # 不转换为"万手"、"手"等单位，直接显示原始数值
                        if isinstance(volume, (int, np.integer)):
                            volume_text = f"{volume:,}"
                        else:
                            volume_text = f"{volume:,.2f}"
                        volume_item = QTableWidgetItem(volume_text)
                    else:
                        volume_item = QTableWidgetItem("-")
                else:
                    volume_item = QTableWidgetItem("-")
                self.data_table.setItem(row_idx, 7, volume_item)

                # 成交额（原始数值显示，不转换单位）
                if 'amount' in row_data:
                    amount = row_data['amount']
                    if pd.notna(amount) and amount > 0:
                        # 【修复】按原始数据库数值展示（2026-04-12）
                        # 不转换为"亿元"、"万元"等单位，直接显示原始数值
                        if isinstance(amount, (int, np.integer)):
                            amount_text = f"{amount:,}"
                        else:
                            amount_text = f"{amount:,.2f}"
                        amount_item = QTableWidgetItem(amount_text)
                    else:
                        amount_item = QTableWidgetItem("-")
                else:
                    amount_item = QTableWidgetItem("-")
                self.data_table.setItem(row_idx, 8, amount_item)

                # 均价
                if 'avg_price' in row_data:
                    avg_price = row_data['avg_price']
                    if pd.notna(avg_price) and avg_price > 0:
                        avg_item = QTableWidgetItem(f"{avg_price:.2f}")
                    else:
                        avg_item = QTableWidgetItem("-")
                else:
                    avg_item = QTableWidgetItem("-")
                self.data_table.setItem(row_idx, 9, avg_item)

                # 换手率
                if 'turnover' in row_data:
                    turnover = row_data['turnover']
                    if pd.notna(turnover):
                        turnover_item = QTableWidgetItem(f"{turnover:.2f}%")
                    else:
                        turnover_item = QTableWidgetItem("-")
                else:
                    turnover_item = QTableWidgetItem("-")
                self.data_table.setItem(row_idx, 10, turnover_item)

            self.data_stats_label.setText(f"共 {len(df)} 条记录 - {stock_code}")
            
            # 【新增】将数据写入缓存（2026-04-12）
            if self._cache_enabled and not df.empty:
                cache_key = (stock_code, getattr(self, 'data_type', '1d'), 
                            self.start_date_edit.date().toString('yyyy-MM-dd'),
                            self.end_date_edit.date().toString('yyyy-MM-dd'))
                
                # 如果缓存已满，删除最旧的条目
                if len(self._data_cache) >= self._cache_max_size:
                    oldest_key = next(iter(self._data_cache))
                    del self._data_cache[oldest_key]
                    print(f"🗑️ 缓存已满，移除最旧条目: {oldest_key}")
                
                # 写入缓存
                self._data_cache[cache_key] = df.copy()
                
                # 更新缓存状态标签显示
                if hasattr(self, 'cache_status_label'):
                    current_text = self.cache_status_label.text()
                    if '已启用' in current_text:
                        self.cache_status_label.setText(f"💾 缓存: 已启用 ({len(self._data_cache)}条)")
                
                print(f"💾 数据已缓存 | Key: {cache_key} | 总缓存: {len(self._data_cache)}/{self._cache_max_size}")
            
            # 【新增】显示性能对比信息（2026-04-12）
            self._update_performance_info(load_end_time, len(df))
        else:
            self.data_table.setRowCount(0)
            self.data_stats_label.setText(f"{stock_code} 该时间段无数据")

    def _update_performance_info(self, load_end_time: float, record_count: int):
        """
        更新性能对比信息显示 - 增强版（2026-04-12）
        
        Args:
            load_end_time: 数据加载完成的时间戳
            record_count: 加载的记录数
        """
        try:
            import time
            
            # 计算查询耗时
            query_time = getattr(self, '_query_start_time', load_end_time - 0.5)
            elapsed = max(load_end_time - query_time, 0.001)  # 至少1ms
            
            # 获取当前查询模式
            is_table_query = self.query_table_radio.isChecked()
            mode_text = "物理表(DuckDB)" if is_table_query else "视图(Parquet)"
            
            # 性能评估（基于记录数和耗时）
            records_per_sec = record_count / elapsed if elapsed > 0 else 0
            
            # 性能等级评定
            if elapsed < 0.5:
                performance_level = "⚡ 极快"
                perf_color = "#388E3C"  # 深绿色
                perf_bg = "#E8F5E9"  # 浅绿背景
            elif elapsed < 2.0:
                performance_level = "✅ 快速"
                perf_color = "#689F38"  # 绿色
                perf_bg = "#F1F8E9"
            elif elapsed < 5.0:
                performance_level = "🔄 正常"
                perf_color = "#F57C00"  # 橙色
                perf_bg = "#FFF3E0"
            else:
                performance_level = "␡ 较慢"
                perf_color = "#D32F2F"  # 红色
                perf_bg = "#FFEBEE"
            
            # 构建性能信息文本
            info_text = f"{performance_level} | {mode_text} | {elapsed:.2f}s | {record_count:,}条 | {records_per_sec:,.0f}/s"
            
            # 更新性能标签（使用新的样式）
            if hasattr(self, 'performance_label'):
                self.performance_label.setText(f"⏱️ {info_text}")
                self.performance_label.setStyleSheet(f"""
                    font-size: 13px;
                    font-weight: bold;
                    color: {perf_color};
                    padding: 2px 8px;
                    background-color: {perf_bg};
                    border-radius: 4px;
                """)
                
                # 设置详细的工具提示
                tooltip = f"""📊 查询性能详情

━━━━━━━━━━━━━━━━━━━━

【基本信息】
• 查询方式：{mode_text}
• 数据类型：{getattr(self, 'data_type', '1d')}
• 股票代码：{self.current_stock or '未选择'}

【性能指标】
• ⏱️ 查询耗时：{elapsed:.3f} 秒
• 📈 记录数量：{record_count:,} 条
• 🚀 吞吐量：{records_per_sec:,.0f} 条/秒
• 🎯 性能评级：{performance_level}

【系统状态】
• 💾 缓存模式：{'启用' if self.cache_toggle_btn.isChecked() else '禁用'}
• 📦 存储模式：{self.storage_mode_label.text().replace('📦 存储模式: ', '')}

💡 提示：点击此处查看详细报告，或点击「⚡ 性能测试」进行批量测试"""
                
                self.performance_label.setToolTip(tooltip)
            
            # 【新增】保存性能数据供后续查看（2026-04-12）
            self._last_performance_data = {
                'mode': mode_text,
                'data_type': getattr(self, 'data_type', '1d'),
                'stock_code': self.current_stock,
                'elapsed': elapsed,
                'record_count': record_count,
                'throughput': records_per_sec,
                'level': performance_level,
                'cache_enabled': self.cache_toggle_btn.isChecked(),
                'timestamp': __import__('datetime').datetime.now()
            }
            
            print(f"⏱️ 性能信息已更新: {info_text}")
            
        except Exception as e:
            print(f"⚠️ 更新性能信息失败: {e}")

    def _update_performance_info_with_cache(self, load_end_time: float, record_count: int, elapsed: float):
        """
        更新性能信息（缓存命中版本）- 标记为从缓存加载（2026-04-12）
        
        Args:
            load_end_time: 加载完成时间
            record_count: 记录数
            elapsed: 耗时（秒）
        """
        try:
            # 获取当前查询模式
            is_table_query = self.query_table_radio.isChecked()
            mode_text = "物理表(DuckDB)" if is_table_query else "视图(Parquet)"
            
            # 性能等级评定（缓存命中通常极快）
            if elapsed < 0.01:
                performance_level = "⚡ 缓存命中"
                perf_color = "#9C27B0"  # 紫色
                perf_bg = "#F3E5F5"
            elif elapsed < 0.1:
                performance_level = "🎯 缓存命中"
                perf_color = "#673AB7"
                perf_bg = "#EDE7F6"
            else:
                performance_level = "✅ 快速"
                perf_color = "#388E3C"
                perf_bg = "#E8F5E9"
            
            records_per_sec = record_count / elapsed if elapsed > 0 else 0
            
            info_text = f"{performance_level} | {mode_text} | {elapsed:.3f}s | {record_count:,}条 | 💾缓存"
            
            if hasattr(self, 'performance_label'):
                self.performance_label.setText(f"⏱️ {info_text}")
                self.performance_label.setStyleSheet(f"""
                    font-size: 13px;
                    font-weight: bold;
                    color: {perf_color};
                    padding: 2px 8px;
                    background-color: {perf_bg};
                    border-radius: 4px;
                """)
                
                self.performance_label.setToolTip(
                    f"📊 查询性能详情（缓存模式）\n\n"
                    f"━━━━━━━━━━━━━━━━━━\n\n"
                    f"【基本信息】\n"
                    f"• 查询方式：{mode_text}\n"
                    f"• 数据类型：{getattr(self, 'data_type', '1d')}\n"
                    f"• 股票代码：{self.current_stock or '未选择'}\n\n"
                    f"【性能指标】\n"
                    f"• ⏱️ 查询耗时：{elapsed:.4f} 秒\n"
                    f"• 📈 记录数量：{record_count:,} 条\n"
                    f"• 🚀 吞吐量：{records_per_sec:,.0f} 条/秒\n"
                    f"• 🎯 性能评级：{performance_level}\n\n"
                    f"【缓存状态】\n"
                    f"• 💾 模式：已启用\n"
                    f"• 📊 命中次数：{self._cache_hits}\n"
                    f"• 📊 未命中次数：{self._cache_misses}\n\n"
                    f"💡 提示：数据从内存缓存直接读取，无需查询数据库"
                )
            
            # 保存性能数据
            self._last_performance_data = {
                'mode': f'{mode_text}(缓存)',
                'data_type': getattr(self, 'data_type', '1d'),
                'stock_code': self.current_stock,
                'elapsed': elapsed,
                'record_count': record_count,
                'throughput': records_per_sec,
                'level': performance_level,
                'cache_enabled': True,
                'cache_hit': True,
                'timestamp': __import__('datetime').datetime.now()
            }
            
            print(f"⏱️ [缓存] 性能信息更新: {info_text}")
            
        except Exception as e:
            print(f"⚠️ 更新缓存性能信息失败: {e}")

    def on_load_error(self, error_msg: str):
        """加载错误"""
        self.load_btn.setEnabled(True)
        self.load_btn.setText("📥 加载数据")
        QMessageBox.critical(self, "错误", f"数据加载失败: {error_msg}")

    # ==================== 批量性能测试功能（2026-04-12）====================
    
    def _get_max_available_stocks_for_testing(self) -> int:
        """
        获取数据库中实际可用的最大标的数量（2026-04-12）
        
        用于设置测试对话框中标的数量选择框的上限
        
        Returns:
            可用标的数量，如果查询失败返回0
        """
        try:
            # 【关键修复】根据存储模式选择正确的数据库（2026-04-12）
            storage_mode = self.config.get('storage', {}).get('data_source', {}).get('mode', 'parquet')
            
            if storage_mode == 'parquet' or storage_mode == 'dual':
                query_db = getattr(self, 'view_db_path', None) or self.db_path
            else:
                query_db = self.db_path
            
            if DB_MANAGER_AVAILABLE and query_db:
                manager = get_db_manager(query_db)
                
                print(f"🔍 [初始化] 正在查询可用标的数量...")
                print(f"   📁 数据库路径: {query_db} (模式: {storage_mode})")
                
                # 查询日线表中的标的数量（作为基准）
                try:
                    df = manager.query_dataframe("""
                        SELECT COUNT(DISTINCT stock_code) as cnt
                        FROM stock_daily
                        WHERE stock_code IS NOT NULL AND stock_code != ''
                    """)
                    
                    if df is not None and not df.empty:
                        count = int(df.iloc[0]['cnt'])
                        print(f"✅ [初始化] 查询到 {count} 只可用标的")
                        return count
                    else:
                        print(f"⚠️ [初始化] 查询返回空结果")
                        return 0
                        
                except Exception as e:
                    print(f"❌ [初始化] 查询失败: {e}")
                    return 0
                    
            return 0
            
        except Exception as e:
            print(f"⚠️ [初始化] 获取标的数量失败: {e}")
            return 0
    
    def show_performance_test_dialog(self):
        """显示批量性能测试对话框"""
        try:
            from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                                          QGridLayout, QSpinBox, QListWidget,
                                          QPushButton, QLabel, QProgressBar,
                                          QTextEdit, QCheckBox, QGroupBox)
            
            dialog = QDialog(self)
            dialog.setWindowTitle("⚡ 批量性能测试")
            dialog.setMinimumSize(700, 600)
            
            layout = QVBoxLayout(dialog)
            
            # ===== 测试配置区域 =====
            config_group = QGroupBox("测试配置")
            config_layout = QGridLayout(config_group)
            
            # 【新增】先查询实际可用的标的数量（2026-04-12）
            max_available_stocks = self._get_max_available_stocks_for_testing()
            
            # 标的数量 - 根据实际可用数量动态设置上限
            config_layout.addWidget(QLabel("📊 测试标的数量:"), 0, 0)
            self.test_stock_count_spin = QSpinBox()
            
            # 【关键】根据实际可用标的数设置范围
            if max_available_stocks > 0:
                self.test_stock_count_spin.setRange(1, max_available_stocks)
                self.test_stock_count_spin.setValue(min(10, max_available_stocks))  # 默认10个或全部
                self.test_stock_count_spin.setToolTip(
                    f"随机选择指定数量的股票进行测试\n"
                    f"• 当前数据库可用: {max_available_stocks} 只标的\n"
                    f"• 建议选择 5-20 只以获得代表性结果"
                )
            else:
                self.test_stock_count_spin.setRange(1, 8)  # 使用默认列表
                self.test_stock_count_spin.setValue(8)
                self.test_stock_count_spin.setToolTip(
                    "使用预定义的8只股票进行测试\n"
                    "（数据库中暂无数据或连接失败）"
                )
                
            config_layout.addWidget(self.test_stock_count_spin, 0, 1)
            
            # 查询方式选择
            config_layout.addWidget(QLabel("🔍 测试查询方式:"), 1, 0)
            query_mode_layout = QHBoxLayout()
            self.test_view_check = QCheckBox("视图查询(Parquet)")
            self.test_view_check.setChecked(True)
            self.test_table_check = QCheckBox("物理表查询(DuckDB)")
            self.test_table_check.setChecked(True)
            query_mode_layout.addWidget(self.test_view_check)
            query_mode_layout.addWidget(self.test_table_check)
            query_mode_layout.addStretch()
            config_layout.addLayout(query_mode_layout, 1, 1)
            
            # 【优化】数据类型选择 - 改为下拉框+所有类型选项（2026-04-12）
            config_layout.addWidget(QLabel("📈 测试数据类型:"), 2, 0)
            
            dtype_combo = QComboBox()
            dtype_combo.setToolTip("选择要测试的数据类型\n• 所有类型: 测试全部8种数据类型\n• 单一类型: 只测试选中的类型")
            
            # 添加选项：所有类型在前，然后是各个具体类型
            test_types = [
                "📊 所有类型(8种)",
                "日线(1d)", "1分钟(1m)", "5分钟(5m)", "15分钟(15m)", 
                "30分钟(30m)", "60分钟(60m)", "周线(weekly)", "月线(monthly)"
            ]
            for t in test_types:
                dtype_combo.addItem(t)
            
            # 默认选择"所有类型"
            dtype_combo.setCurrentIndex(0)
            config_layout.addWidget(dtype_combo, 2, 1)
            
            self.test_dtype_combo = dtype_combo  # 改用combo替代list
            
            # 强制关闭缓存选项
            config_layout.addWidget(QLabel("💾 缓存设置:"), 3, 0)
            self.force_no_cache_check = QCheckBox("强制关闭缓存（推荐，确保测试准确）")
            self.force_no_cache_check.setChecked(True)
            self.force_no_cache_check.setToolTip(
                "性能测试期间强制关闭缓存\n避免缓存影响测试结果的准确性"
            )
            config_layout.addWidget(self.force_no_cache_check, 3, 1)
            
            layout.addWidget(config_group)
            
            # ===== 测试进度区域 =====
            progress_group = QGroupBox("测试进度")
            progress_layout = QVBoxLayout(progress_group)
            
            self.test_progress_bar = QProgressBar()
            self.test_progress_bar.setValue(0)
            progress_layout.addWidget(self.test_progress_bar)
            
            self.test_status_label = QLabel("准备就绪，点击「开始测试」按钮启动...")
            self.test_status_label.setStyleSheet("color: #666;")
            progress_layout.addWidget(self.test_status_label)
            
            layout.addWidget(progress_group)
            
            # ===== 测试结果区域 =====
            result_group = QGroupBox("测试结果详情")
            result_layout = QVBoxLayout(result_group)
            
            self.test_result_text = QTextEdit()
            self.test_result_text.setReadOnly(True)
            self.test_result_text.setFont(QFont("Consolas", 9))
            self.test_result_text.setMaximumHeight(200)
            result_layout.addWidget(self.test_result_text)
            
            layout.addWidget(result_group)
            
            # ===== 操作按钮 =====
            btn_layout = QHBoxLayout()
            
            start_btn = QPushButton("🚀 开始测试")
            start_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    padding: 8px 20px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            start_btn.clicked.connect(lambda: self.run_batch_performance_test(dialog))
            btn_layout.addWidget(start_btn)
            
            export_btn = QPushButton("📄 导出报告")
            export_btn.clicked.connect(lambda: self.export_performance_report())
            btn_layout.addWidget(export_btn)
            
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.close)
            btn_layout.addWidget(close_btn)
            
            btn_layout.addStretch()
            layout.addLayout(btn_layout)
            
            dialog.exec_()
            
        except Exception as e:
            print(f"❌ 显示性能测试对话框失败: {e}")
            import traceback
            traceback.print_exc()
    
    def run_batch_performance_test(self, dialog):
        """执行批量性能测试"""
        try:
            import time
            from datetime import datetime
            
            # 获取配置
            stock_count = self.test_stock_count_spin.value()
            use_view_query = self.test_view_check.isChecked()
            use_table_query = self.test_table_check.isChecked()
            force_no_cache = self.force_no_cache_check.isChecked()
            
            # 【优化】从下拉框获取选中的数据类型（2026-04-12）
            dtype_selection = self.test_dtype_combo.currentText()
            
            if "所有类型" in dtype_selection:
                # 选择了"所有类型"，使用全部8种类型
                selected_types = [
                    "日线(1d)", "1分钟(1m)", "5分钟(5m)", "15分钟(15m)", 
                    "30分钟(30m)", "60分钟(60m)", "周线(weekly)", "月线(monthly)"
                ]
                print(f"📊 已选择: 所有数据类型（共{len(selected_types)}种）")
            else:
                # 选择了单一类型
                selected_types = [dtype_selection]
                print(f"📊 已选择: 单一数据类型 - {dtype_selection}")
            
            if not selected_types:
                QMessageBox.warning(dialog, "提示", "请至少选择一种数据类型进行测试")
                return
            
            if not (use_view_query or use_table_query):
                QMessageBox.warning(dialog, "提示", "请至少选择一种查询方式进行测试")
                return
            
            # 【关键】性能测试时强制关闭缓存
            original_cache_state = self.cache_toggle_btn.isChecked()
            if force_no_cache and original_cache_state:
                self.cache_toggle_btn.click()
            
            # 禁用开始按钮防止重复运行
            dialog.findChildren(QPushButton)[0].setEnabled(False)
            
            results = []
            total_tests = len(selected_types) * (1 if use_view_query else 0 + 1 if use_table_query else 0) * stock_count
            current_test = 0
            
            self.test_result_text.clear()
            self.test_result_text.append("=" * 80)
            self.test_result_text.append(f"⚡ 批量性能测试报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.test_result_text.append("=" * 80)
            self.test_result_text.append("")
            
            # 【修复】数据类型映射定义移到使用之前（2026-04-12）
            data_type_map = {
                "日线(1d)": "1d",
                "1分钟(1m)": "1m",
                "5分钟(5m)": "5m",
                "15分钟(15m)": "15m",
                "30分钟(30m)": "30m",
                "60分钟(60m)": "60m",
                "周线(weekly)": "weekly",
                "月线(monthly)": "monthly"
            }
            
            # 获取可用的股票列表
            self.test_status_label.setText("正在获取可用股票列表...")
            # 【优化】传入数据类型以从对应表获取有数据的标的（2026-04-12）
            first_type_code = data_type_map.get(selected_types[0], '1d') if selected_types else '1d'
            available_stocks = self._get_available_stocks_for_testing(stock_count, first_type_code)
            
            if not available_stocks:
                self.test_result_text.append("❌ 错误：无法获取可用股票列表")
                self.cache_toggle_btn.setChecked(original_cache_state)  # 恢复缓存状态
                return
            
            self.test_result_text.append(f"📋 测试配置:")
            self.test_result_text.append(f"   • 标的数量: {len(available_stocks)} 只")
            
            # 【新增】显示标的数量调整警告（2026-04-12）
            if hasattr(self, '_test_warning_msg') and self._test_warning_msg:
                self.test_result_text.append(f"\n{self._test_warning_msg}")
                self._test_warning_msg = ""  # 清除已显示的警告
            
            self.test_result_text.append(f"   • 数据类型: {', '.join(selected_types)}")
            self.test_result_text.append(f"   • 视图查询: {'✅' if use_view_query else '❌'}")
            self.test_result_text.append(f"   • 物理表查询: {'✅' if use_table_query else '❌'}")
            self.test_result_text.append(f"   • 缓存状态: {'已禁用（测试模式）' if force_no_cache else '启用'}")
            
            self.test_result_text.append(f"   📅 查询时间范围: 全部数据（查询各标的实际数据范围）")
            
            self.test_result_text.append("")
            self.test_result_text.append("-" * 80)
            
            # 遍历每种数据类型
            for type_display in selected_types:
                data_type_code = data_type_map.get(type_display, "1d")
                
                self.test_result_text.append(f"\n📊 数据类型: {type_display} ({data_type_code})")
                self.test_result_text.append("-" * 40)
                
                # 遍历每个股票
                for idx, stock_code in enumerate(available_stocks[:stock_count]):
                    current_test += 1
                    progress_pct = int((current_test / total_tests) * 100)
                    self.test_progress_bar.setValue(progress_pct)
                    
                    self.test_status_label.setText(
                        f"正在测试 [{idx+1}/{min(len(available_stocks), stock_count)}] "
                        f"{stock_code} - {type_display} ({progress_pct}%)"
                    )
                    
                    # 视图查询测试
                    if use_view_query:
                        view_result = self._single_query_test(
                            stock_code, data_type_code, "视图查询"
                        )
                        results.append(view_result)
                        # 【新增】显示错误信息（2026-04-12）
                        error_suffix = f" | ⚠️{view_result['error']}" if view_result.get('error') else ""
                        self.test_result_text.append(
                            f"   {stock_code} | 视图 | {view_result['elapsed']:.3f}s | "
                            f"{view_result['records']:,}条 | {view_result['throughput']:,.0f}/s{error_suffix}"
                        )
                    
                    # 物理表查询测试
                    if use_table_query:
                        table_result = self._single_query_test(
                            stock_code, data_type_code, "物理表"
                        )
                        results.append(table_result)
                        # 【新增】显示错误信息（2026-04-12）
                        error_suffix = f" | ⚠️{table_result['error']}" if table_result.get('error') else ""
                        self.test_result_text.append(
                            f"   {stock_code} | 物理表 | {table_result['elapsed']:.3f}s | "
                            f"{table_result['records']:,}条 | {table_result['throughput']:,.0f}/s{error_suffix}"
                        )
                    
                    # 让UI有机会更新
                    QApplication.processEvents()
                    time.sleep(0.05)  # 避免过快导致界面卡顿
            
            # ===== 生成汇总统计 =====
            self.test_result_text.append("\n")
            self.test_result_text.append("=" * 80)
            self.test_result_text.append("📈 测试结果汇总统计")
            self.test_result_text.append("=" * 80)
            
            # 按查询方式分组统计
            view_results = [r for r in results if r['mode'] == '视图查询']
            table_results = [r for r in results if r['mode'] == '物理表']
            
            if view_results:
                avg_time_v = sum(r['elapsed'] for r in view_results) / len(view_results)
                avg_throughput_v = sum(r['throughput'] for r in view_results) / len(view_results)
                total_records_v = sum(r['records'] for r in view_results)
                
                self.test_result_text.append(f"\n【视图查询(Parquet)】共 {len(view_results)} 次测试:")
                self.test_result_text.append(f"   ⏱️ 平均耗时: {avg_time_v:.3f} 秒")
                self.test_result_text.append(f"   🚀 平均吞吐量: {avg_throughput_v:,.0f} 条/秒")
                self.test_result_text.append(f"   📈 总记录数: {total_records_v:,} 条")
            
            if table_results:
                avg_time_t = sum(r['elapsed'] for r in table_results) / len(table_results)
                avg_throughput_t = sum(r['throughput'] for r in table_results) / len(table_results)
                total_records_t = sum(r['records'] for r in table_results)
                
                self.test_result_text.append(f"\n【物理表查询(DuckDB)】共 {len(table_results)} 次测试:")
                self.test_result_text.append(f"   ⏱️ 平均耗时: {avg_time_t:.3f} 秒")
                self.test_result_text.append(f"   🚀 平均吞吐量: {avg_throughput_t:,.0f} 条/秒")
                self.test_result_text.append(f"   📈 总记录数: {total_records_t:,} 条")
            
            # 对比分析
            if view_results and table_results:
                speed_ratio = avg_time_t / avg_time_v if avg_time_v > 0 else 0
                throughput_ratio = avg_throughput_v / avg_throughput_t if avg_throughput_t > 0 else 0
                
                self.test_result_text.append("\n" + "-" * 40)
                self.test_result_text.append("⚖️ 对比分析:")
                
                if speed_ratio < 1.0:
                    faster = "物理表查询"
                    ratio_text = f"{1/speed_ratio:.2f}x"
                else:
                    faster = "视图查询"
                    ratio_text = f"{speed_ratio:.2f}x"
                
                self.test_result_text.append(f"   🏆 速度更快: {faster} ({ratio_text})")
                self.test_result_text.append(f"   📊 吞吐量对比: 视图/物理表 = {throughput_ratio:.2f}x")
            
            # ===== 【新增】缓存性能对比测试（2026-04-12）=====
            self.test_result_text.append("\n")
            self.test_result_text.append("=" * 80)
            self.test_result_text.append("💾 缓存性能对比测试")
            self.test_result_text.append("=" * 80)
            
            cache_comparison_results = []
            
            try:
                # 选择第一只股票和第一种数据类型进行缓存对比
                test_stock = available_stocks[0] if available_stocks else '000001.SZ'
                test_type_code = data_type_map.get(selected_types[0], '1d') if selected_types else '1d'
                
                self.test_status_label.setText("正在执行缓存性能对比...")
                
                # 1️⃣ 无缓存查询（确保缓存已清空）
                if self._cache_enabled:
                    original_cache_data = self._data_cache.copy()
                    self._data_cache.clear()
                
                no_cache_start = time.time()
                no_cache_result = self._single_query_test(test_stock, test_type_code, "无缓存-视图")
                no_cache_elapsed = time.time() - no_cache_start
                
                cache_comparison_results.append(no_cache_result)
                self.test_result_text.append(f"\n📊 无缓存测试:")
                self.test_result_text.append(f"   ⏱️ 耗时: {no_cache_elapsed:.4f}s | 📈 {no_cache_result['records']:,}条")
                
                # 2️⃣ 有缓存查询（先填充缓存）
                cache_fill_start = time.time()
                cache_fill_result = self._single_query_test(test_stock, test_type_code, "填充缓存")
                cache_fill_elapsed = time.time() - cache_fill_start
                
                # 3️⃣ 从缓存读取
                cache_hit_start = time.time()
                if self._cache_enabled:
                    # 模拟从缓存读取（直接返回已缓存的数据）
                    cache_key = (test_stock, test_type_code, 
                               self.start_date_edit.date().toString('yyyy-MM-dd'),
                               self.end_date_edit.date().toString('yyyy-MM-dd'))
                    
                    if cache_key in self._data_cache:
                        cached_df = self._data_cache[cache_key]
                        cache_hit_elapsed = time.time() - cache_hit_start
                        
                        cache_hit_result = {
                            'stock_code': test_stock,
                            'data_type': test_type_code,
                            'mode': '缓存命中',
                            'elapsed': cache_hit_elapsed,
                            'records': len(cached_df) if hasattr(cached_df, '__len__') else 0,
                            'throughput': (len(cached_df) / cache_hit_elapsed) if cache_hit_elapsed > 0 else 0,
                            'level': '⚡ 极快' if cache_hit_elapsed < 0.01 else '🎯 快速',
                            'error': None
                        }
                        
                        cache_comparison_results.append(cache_hit_result)
                        
                        self.test_result_text.append(f"\n💾 缓存命中测试:")
                        self.test_result_text.append(f"   ⏱️ 耗时: {cache_hit_elapsed:.6f}s | 📈 {cache_hit_result['records']:,}条")
                        
                        # 计算加速比
                        speedup = no_cache_elapsed / cache_hit_elapsed if cache_hit_elapsed > 0 else 0
                        self.test_result_text.append(f"\n🚀 缓存加速比: {speedup:.1f}x")
                        self.test_result_text.append(f"   （缓存比无缓存快 {speedup:.1f} 倍）")
                    else:
                        self.test_result_text.append(f"\n⚠️ 缓存未命中（可能缓存被禁用）")
                
                # 恢复原始缓存数据
                if self._cache_enabled and 'original_cache_data' in dir():
                    self._data_cache = original_cache_data
                
            except Exception as e:
                self.test_result_text.append(f"\n❌ 缓存对比测试失败: {e}")
            
            # ===== 【新增】生成独立报告文件（2026-04-12）=====
            report_filename = None
            
            try:
                from pathlib import Path
                from datetime import datetime
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                report_dir = Path(__file__).parent.parent.parent / 'logs' / 'performance_reports'
                report_dir.mkdir(parents=True, exist_ok=True)
                
                report_filename = report_dir / f'performance_report_{timestamp}.txt'
                
                with open(report_filename, 'w', encoding='utf-8') as f:
                    f.write(self.test_result_text.toPlainText())
                
                self.test_result_text.append(f"\n\n{'=' * 80}")
                self.test_result_text.append(f"📄 独立报告已生成")
                self.test_result_text.append(f"{'=' * 80}")
                self.test_result_text.append(f"   📁 文件路径: {report_filename}")
                self.test_result_text.append(f"   📅 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                print(f"✅ 性能测试报告已保存: {report_filename}")
                
            except Exception as e:
                self.test_result_text.append(f"\n⚠️ 生成独立报告失败: {e}")
            
            # 保存测试数据供后续查看（包含缓存对比结果）
            self._last_perf_test_data = {
                'timestamp': datetime.now(),
                'config': {
                    'stock_count': stock_count,
                    'data_types': selected_types,
                    'use_view': use_view_query,
                    'use_table': use_table_query,
                    'force_no_cache': force_no_cache,
                    'report_file': str(report_filename) if report_filename else None
                },
                'results': results,
                'cache_comparison': cache_comparison_results,
                'summary': {
                    'view_avg_time': sum(r['elapsed'] for r in view_results) / len(view_results) if view_results else 0,
                    'table_avg_time': sum(r['elapsed'] for r in table_results) / len(table_results) if table_results else 0,
                    'cache_speedup': (no_cache_elapsed / cache_hit_elapsed) if ('cache_hit_elapsed' in dir() and cache_hit_elapsed > 0) else 0
                }
            }
            
            # 完成
            self.test_progress_bar.setValue(100)
            self.test_status_label.setText(f"✅ 测试完成！共执行 {total_tests} 次查询")
            self.test_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            
            dialog.findChildren(QPushButton)[0].setEnabled(True)
            
            # 恢复缓存状态
            if force_no_cache and original_cache_state:
                self.cache_toggle_btn.click()
            
            print(f"✅ 批量性能测试完成: {total_tests} 次查询")
            
        except Exception as e:
            print(f"❌ 批量性能测试失败: {e}")
            import traceback
            traceback.print_exc()
            self.test_result_text.append(f"\n❌ 测试出错: {str(e)}")
    
    def _get_available_stocks_for_testing(self, count: int, data_type: str = '1d') -> list:
        """
        获取用于测试的股票列表 - 优化版（2026-04-12）
        
        改进：
        1. 过滤掉无数据的标的
        2. 优先选择数据量大的标的（确保测试有效）
        3. 根据数据类型动态查询对应表
        4. 【新增】自动限制不超过实际有数据的标的数
        
        Args:
            count: 需要的标的数量
            data_type: 数据类型（用于确定查询哪张表）
            
        Returns:
            有数据的股票代码列表
        """
        try:
            # 【关键修复】根据数据存储模式选择正确的数据库（2026-04-12）
            # 数据在Parquet中，通过视图库访问 → 应该从视图库获取股票列表
            storage_mode = self.config.get('storage', {}).get('data_source', {}).get('mode', 'parquet')
            
            if storage_mode == 'parquet' or storage_mode == 'dual':
                # Parquet/Dual模式：数据通过视图访问，从视图库获取
                query_db = getattr(self, 'view_db_path', None) or self.db_path
                print(f"🔍 [测试] 查询模式: {storage_mode} → 使用视图库")
            else:
                # 纯数据库模式：直接查物理表
                query_db = self.db_path
                print(f"🔍 [测试] 查询模式: {storage_mode} → 使用物理表库")
            
            if DB_MANAGER_AVAILABLE and query_db:
                manager = get_db_manager(query_db)
                
                print(f"🔍 [测试] 正在从数据库获取股票列表...")
                print(f"   📁 数据库路径: {query_db}")
                print(f"   📊 数据类型: {data_type}")
                
                # 【优化】根据数据类型确定查询的表和日期列（与DataLoadThread一致）
                if data_type == '1d':
                    source_table = 'stock_daily'
                    date_col = 'date'
                elif data_type == 'weekly':
                    source_table = 'stock_weekly'
                    date_col = 'date'
                elif data_type == 'monthly':
                    source_table = 'stock_monthly'
                    date_col = 'date'
                elif data_type == 'tick':
                    source_table = 'stock_tick'
                    date_col = 'datetime'
                else:
                    source_table = f'stock_{data_type}'
                    date_col = 'datetime'
                
                print(f"   📋 查询表: {source_table}")
                
                # 【核心】获取有数据的标的及其记录数（过滤无数据标的）
                try:
                    df = manager.query_dataframe(f"""
                        SELECT 
                            stock_code,
                            COUNT(*) as record_count,
                            MIN({('date' if data_type in ['daily', 'weekly', 'monthly'] else 'datetime')}) as min_date,
                            MAX({('date' if data_type in ['daily', 'weekly', 'monthly'] else 'datetime')}) as max_date
                        FROM {source_table}
                        WHERE stock_code IS NOT NULL AND stock_code != ''
                        GROUP BY stock_code
                        HAVING COUNT(*) > 0  # 【关键】确保有数据
                        ORDER BY record_count DESC  # 按数据量降序排列
                    """)
                    
                    if df is None:
                        print(f"⚠️ [测试] 查询返回None，表 {source_table} 可能不存在")
                        df = pd.DataFrame()
                        
                except Exception as query_err:
                    print(f"❌ [测试] 查询失败: {query_err}")
                    df = pd.DataFrame()
                
                if df is not None and not df.empty:
                    total_available = len(df)  # 实际有数据的标的总数
                    
                    # 【关键】限制数量不超过实际有数据的标的数
                    actual_count = min(count, total_available)
                    stocks = df['stock_code'].tolist()[:actual_count]
                    
                    # 输出详细信息
                    print(f"✅ 获取到 {len(stocks)} 只测试用股票（从 {source_table} 表）")
                    
                    # 【诊断】显示实际stock_code格式（2026-04-12）
                    if len(stocks) > 0:
                        sample_codes = stocks[:5]
                        print(f"   📝 stock_code 格式示例: {sample_codes}")
                        print(f"   💡 提示: 这些是数据库中存储的原始格式，将直接用于查询")
                    
                    # 【新增】警告信息：如果请求的数量超过实际可用数量
                    if count > total_available:
                        print(f"⚠️ 警告: 请求测试 {count} 只标的，但该表实际只有 {total_available} 只有数据")
                        print(f"   📊 已自动调整为使用全部 {total_available} 只标的")
                        
                        # 【新增】存储警告信息供调用方使用
                        if not hasattr(self, '_test_warning_msg'):
                            self._test_warning_msg = ""
                        self._test_warning_msg = (
                            f"⚠️ 测试标的数量已自动调整\n"
                            f"• 请求: {count} 只\n"
                            f"• 实际有数据: {total_available} 只\n"
                            f"• 已使用: {actual_count} 只\n\n"
                            f"建议: 减少测试标的数量或下载更多 {data_type} 数据"
                        )
                    
                    # 显示前几只的数据情况
                    for idx, row in df.head(min(5, len(df))).iterrows():
                        print(f"   {row['stock_code']}: {row['record_count']:,}条 | "
                              f"{str(row['min_date'])[:10]} ~ {str(row['max_date'])[:10]}")
                    
                    return stocks
                
            # 如果数据库不可用或表为空，使用预定义列表
            default_stocks = [
                '000001.SZ', '000002.SZ', '600000.SH', '600036.SH',
                '601398.SH', '000858.SZ', '002594.SZ', '300750.SZ'
            ]
            print(f"⚠️ 使用默认股票列表: {len(default_stocks)} 只（数据库可能无 {data_type} 数据）")
            return default_stocks[:count]
            
        except Exception as e:
            print(f"⚠️ 获取测试股票失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _single_query_test(self, stock_code: str, data_type: str, mode: str) -> dict:
        """
        执行单次查询测试（2026-04-12 重构）
        
        【关键】使用与 DataLoadThread 完全相同的查询逻辑，
        确保数据查看器能加载的数据这里也能查到
        """
        import time
        
        result = {
            'stock_code': stock_code,
            'data_type': data_type,
            'mode': mode,
            'elapsed': 0,
            'records': 0,
            'throughput': 0,
            'level': '未知',
            'error': None
        }
        
        try:
            # ===== 【核心】表名映射 - 与 DataLoadThread 完全一致 =====
            if data_type == '1d':
                table_name = 'stock_daily'
                date_col = 'date'
            elif data_type == 'weekly':
                table_name = 'stock_weekly'
                date_col = 'date'
            elif data_type == 'monthly':
                table_name = 'stock_monthly'
                date_col = 'date'
            elif data_type == 'tick':
                table_name = 'stock_tick'
                date_col = 'datetime'
            else:
                table_name = f'stock_{data_type}'
                date_col = 'datetime'
            
            # ===== 【核心】根据查询模式选择正确的数据库（2026-04-12 修复）=====
            # 双库架构：视图查询走视图库，物理表查询走物理表库
            if mode == '视图查询':
                # 视图查询：使用视图数据库（stock_views.duckdb）
                db_to_use = getattr(self, 'view_db_path', None) or self.db_path
                mode_label = "视图(Parquet)"
            elif mode == '物理表':
                # 物理表查询：使用物理表数据库（stock_data.duckdb/.ddb）
                db_to_use = self.db_path
                mode_label = "物理表(DuckDB)"
            else:
                # 兼容其他模式，默认使用主数据库
                db_to_use = self.db_path
                mode_label = mode
            
            print(f"   🔍 [{mode_label}] {stock_code} | 表: {table_name} | 类型: {data_type}")
            print(f"   📁 数据库: {db_to_use}")
            
            start_time = time.time()
            
            if DB_MANAGER_AVAILABLE and db_to_use:
                manager = get_db_manager(db_to_use)
                
                try:
                    # 查询该标的的总记录数和实际日期范围（不限制时间范围）
                    range_sql = f"""
                        SELECT 
                            COUNT(*) as cnt,
                            MIN({date_col}) as min_date,
                            MAX({date_col}) as max_date
                        FROM {table_name}
                        WHERE stock_code = '{stock_code}'
                    """
                    range_df = manager.query_dataframe(range_sql)
                    
                    if range_df is not None and not range_df.empty:
                        total_for_stock = int(range_df.iloc[0]['cnt'])
                        actual_min = range_df.iloc[0]['min_date']
                        actual_max = range_df.iloc[0]['max_date']
                        
                        result['records'] = total_for_stock
                        
                        if total_for_stock > 0:
                            min_str = str(actual_min)[:19] if pd.notna(actual_min) else 'N/A'
                            max_str = str(actual_max)[:19] if pd.notna(actual_max) else 'N/A'
                            print(f"   ✅ {total_for_stock:,} 条 | 📅 {min_str} ~ {max_str}")
                            result['level'] = '✅ 有数据'
                        else:
                            print(f"   ⚠️ 表 {table_name} 中无 {stock_code} 的数据")
                            result['error'] = f'无 {stock_code} 数据'
                            result['level'] = '⚠️ 无数据'
                    else:
                        result['error'] = '查询返回空'
                        
                except Exception as query_err:
                    error_msg = str(query_err)
                    print(f"   ❌ 失败: {error_msg}")
                    result['error'] = error_msg
                    result['level'] = '❌ 失败'
            else:
                result['error'] = '数据库不可用'
            
            result['elapsed'] = time.time() - start_time
            
            if result['elapsed'] > 0 and result['records'] > 0:
                result['throughput'] = result['records'] / result['elapsed']
            
            if not result.get('level') or result['level'] == '未知':
                if result['elapsed'] < 0.05:
                    result['level'] = '⚡ 极快'
                elif result['elapsed'] < 0.2:
                    result['level'] = '✅ 快速'
                elif result['elapsed'] < 1.0:
                    result['level'] = '🔄 正常'
                else:
                    result['level'] = '🐢 较慢'
                    
        except Exception as e:
            result['error'] = str(e)
            result['level'] = '❌ 异常'
        
        return result
    
    def export_performance_report(self):
        """导出性能测试报告"""
        try:
            if not hasattr(self, '_last_perf_test_data') or not self._last_perf_test_data:
                QMessageBox.information(self, "提示", "暂无测试数据可导出\n请先运行批量性能测试")
                return
            
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"performance_report_{timestamp}.txt"
            
            filepath, _ = QFileDialog.getSaveFileName(
                self, "保存性能报告", filename, "文本文件 (*.txt)"
            )
            
            if not filepath:
                return
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.test_result_text.toPlainText())
            
            QMessageBox.information(
                self, "成功",
                f"性能测试报告已保存至:\n{filepath}",
                QMessageBox.Ok
            )
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出报告失败: {str(e)}")

    def load_financial_data(self):
        """加载财务数据"""
        if not self.current_stock:
            QMessageBox.warning(self, "提示", "请先选择股票")
            return

        self.load_fin_btn.setEnabled(False)
        self.load_fin_btn.setText("加载中...")

        # 使用线程加载财务数据（传递完整股票代码）
        self.fin_thread = FinancialDataLoadThread(self.current_stock)
        self.fin_thread.data_ready.connect(self.on_financial_data_loaded)
        self.fin_thread.error_occurred.connect(self.on_financial_load_error)
        self.fin_thread.start()

    def on_financial_data_loaded(self, df: pd.DataFrame):
        """财务数据加载完成"""
        self.load_fin_btn.setEnabled(True)
        self.load_fin_btn.setText("💰 加载财务数据")

        if not df.empty:
            # 填充财务数据表格
            self.financial_table.setRowCount(len(df))

            for row_idx, (_, row_data) in enumerate(df.iterrows()):
                # 报告期
                report_value = row_data.get('报告期', '')
                report_item = QTableWidgetItem(str(report_value)[:10])
                self.financial_table.setItem(row_idx, 0, report_item)

                # 财务指标
                for col_idx, (key, format_fn) in enumerate([
                    ('净资产收益率', lambda x: f"{x:.2f}%" if pd.notna(x) else "-"),
                    ('毛利率', lambda x: f"{x:.2f}%" if pd.notna(x) else "-"),
                    ('净利率', lambda x: f"{x:.2f}%" if pd.notna(x) else "-"),
                    ('资产负债率', lambda x: f"{x:.2f}%" if pd.notna(x) else "-"),
                ], 1):
                    value = row_data.get(key)
                    if pd.notna(value):
                        item = QTableWidgetItem(format_fn(value))
                        # 根据指标好坏着色
                        if key == '净资产收益率':
                            if value > 15:
                                item.setForeground(QColor("#4CAF50"))  # 好 - 绿
                            elif value < 5:
                                item.setForeground(QColor("#f44336"))  # 差 - 红
                        elif key == '资产负债率':
                            if value > 70:
                                item.setForeground(QColor("#f44336"))  # 高风险 - 红
                            elif value < 30:
                                item.setForeground(QColor("#4CAF50"))  # 低风险 - 绿
                    else:
                        item = QTableWidgetItem("-")
                    self.financial_table.setItem(row_idx, col_idx, item)

            self.fin_stats_label.setText(f"共 {len(df)} 期财务数据")
        else:
            self.financial_table.setRowCount(0)
            self.fin_stats_label.setText("该股票暂无财务数据")

    def load_tick_data(self):
        """加载Tick数据"""
        if not self.current_stock:
            QMessageBox.warning(self, "提示", "请先选择股票")
            return

        tick_date = self.tick_date_edit.date().toString('yyyy-MM-dd')
        time_range = self.tick_time_combo.currentText()

        self.load_tick_btn.setEnabled(False)
        self.load_tick_btn.setText("加载中...")

        # 使用线程加载tick数据
        self.tick_thread = TickDataLoadThread(self.current_stock, tick_date, time_range)
        self.tick_thread.data_ready.connect(self.on_tick_data_loaded)
        self.tick_thread.error_occurred.connect(self.on_tick_load_error)
        self.tick_thread.start()

    def on_tick_data_loaded(self, df: pd.DataFrame):
        """Tick数据加载完成"""
        self.load_tick_btn.setEnabled(True)
        self.load_tick_btn.setText("📊 加载Tick数据")

        if not df.empty:
            # 填充tick数据表格
            self.tick_table.setRowCount(len(df))
            
            # 更新表格列
            columns = ['时间', '开盘', '最高', '最低', '收盘', '最新价', '前收盘价', '成交量', '原始成交量', '成交额', 
                       '成交笔数', '买卖方向', '持仓量', '前结算', '证券状态', '委买价', '委买量', '委卖价', '委卖量']
            self.tick_table.setColumnCount(len(columns))
            self.tick_table.setHorizontalHeaderLabels(columns)
            
            # 设置列宽
            column_widths = [180, 80, 80, 80, 80, 80, 80, 100, 100, 100, 
                           100, 80, 100, 80, 80, 100, 100, 100, 100]
            for i, width in enumerate(column_widths):
                self.tick_table.setColumnWidth(i, width)

            for row_idx, (_, row_data) in enumerate(df.iterrows()):
                # 时间
                time_value = row_data.get('datetime', row_data.get('time', ''))
                if isinstance(time_value, pd.Timestamp):
                    time_str = time_value.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                else:
                    time_str = str(time_value)
                time_item = QTableWidgetItem(time_str)
                self.tick_table.setItem(row_idx, 0, time_item)

                # 开盘价
                open_price = row_data.get('open', 0)
                open_item = QTableWidgetItem(f"{open_price:.2f}" if pd.notna(open_price) else "-")
                self.tick_table.setItem(row_idx, 1, open_item)

                # 最高价
                high_price = row_data.get('high', 0)
                high_item = QTableWidgetItem(f"{high_price:.2f}" if pd.notna(high_price) else "-")
                self.tick_table.setItem(row_idx, 2, high_item)

                # 最低价
                low_price = row_data.get('low', 0)
                low_item = QTableWidgetItem(f"{low_price:.2f}" if pd.notna(low_price) else "-")
                self.tick_table.setItem(row_idx, 3, low_item)

                # 收盘价
                close_price = row_data.get('close', 0)
                close_item = QTableWidgetItem(f"{close_price:.2f}" if pd.notna(close_price) else "-")
                self.tick_table.setItem(row_idx, 4, close_item)

                # 最新价
                last_price = row_data.get('lastPrice', row_data.get('price', 0))
                last_item = QTableWidgetItem(f"{last_price:.2f}" if pd.notna(last_price) else "-")
                self.tick_table.setItem(row_idx, 5, last_item)
                
                # 前收盘价 - 直接使用API返回的原始值
                last_close = row_data.get('lastClose', 0)
                last_close_item = QTableWidgetItem(f"{last_close:.2f}" if pd.notna(last_close) else "-")
                self.tick_table.setItem(row_idx, 6, last_close_item)

                # 成交量
                volume = row_data.get('volume', row_data.get('vol', 0))
                if pd.notna(volume) and volume >= 0:
                    volume_item = QTableWidgetItem(f"{int(volume):,}")
                else:
                    volume_item = QTableWidgetItem("-")
                self.tick_table.setItem(row_idx, 7, volume_item)
                
                # 原始成交量
                pvolume = row_data.get('pvolume', 0)
                if pd.notna(pvolume) and pvolume >= 0:
                    pvolume_item = QTableWidgetItem(f"{int(pvolume):,}")
                else:
                    pvolume_item = QTableWidgetItem("-")
                self.tick_table.setItem(row_idx, 8, pvolume_item)

                # 成交额
                amount = row_data.get('amount', row_data.get('money', 0))
                if pd.notna(amount) and amount > 0:
                    amount_item = QTableWidgetItem(f"{amount:,.0f}")
                else:
                    amount_item = QTableWidgetItem("-")
                self.tick_table.setItem(row_idx, 9, amount_item)
                
                # 成交笔数
                transaction_num = row_data.get('transactionNum', 0)
                if pd.notna(transaction_num) and transaction_num >= 0:
                    transaction_item = QTableWidgetItem(f"{int(transaction_num):,}")
                else:
                    transaction_item = QTableWidgetItem("-")
                self.tick_table.setItem(row_idx, 10, transaction_item)

                # 买卖方向
                bid_ask = row_data.get('func_type', row_data.get('type', ''))
                if bid_ask == 1:
                    bid_ask_str = "买入"
                    bid_ask_item = QTableWidgetItem(bid_ask_str)
                    bid_ask_item.setForeground(QColor("#f44336"))
                elif bid_ask == 2:
                    bid_ask_str = "卖出"
                    bid_ask_item = QTableWidgetItem(bid_ask_str)
                    bid_ask_item.setForeground(QColor("#4CAF50"))
                else:
                    bid_ask_str = "-"
                    bid_ask_item = QTableWidgetItem(bid_ask_str)
                self.tick_table.setItem(row_idx, 11, bid_ask_item)

                # 持仓量
                open_interest = row_data.get('openInt', row_data.get('oi', 0))
                if pd.notna(open_interest) and open_interest > 0:
                    oi_item = QTableWidgetItem(f"{int(open_interest):,}")
                else:
                    oi_item = QTableWidgetItem("-")
                self.tick_table.setItem(row_idx, 12, oi_item)
                
                # 前结算
                last_settlement = row_data.get('lastSettlementPrice', 0)
                last_settlement_item = QTableWidgetItem(f"{last_settlement:.2f}" if pd.notna(last_settlement) else "-")
                self.tick_table.setItem(row_idx, 13, last_settlement_item)
                
                # 证券状态
                stock_status = row_data.get('stockStatus', 0)
                stock_status_item = QTableWidgetItem(str(stock_status) if pd.notna(stock_status) else "-")
                self.tick_table.setItem(row_idx, 14, stock_status_item)
                
                # 委买价
                bid_price = row_data.get('bidPrice', [])
                # 处理 numpy array 或 list 类型
                if hasattr(bid_price, '__len__') and len(bid_price) > 0:
                    first_elem = bid_price[0] if not pd.isna(bid_price[0]) else 0
                    bid_price_str = f"{first_elem:.2f}" if first_elem > 0 else "-"
                else:
                    bid_price_str = "-"
                bid_price_item = QTableWidgetItem(bid_price_str)
                self.tick_table.setItem(row_idx, 15, bid_price_item)
                
                # 委买量
                bid_vol = row_data.get('bidVol', [])
                # 处理 numpy array 或 list 类型
                if hasattr(bid_vol, '__len__') and len(bid_vol) > 0:
                    first_elem = bid_vol[0] if not pd.isna(bid_vol[0]) else 0
                    bid_vol_str = f"{int(first_elem):,}" if first_elem > 0 else "-"
                else:
                    bid_vol_str = "-"
                bid_vol_item = QTableWidgetItem(bid_vol_str)
                self.tick_table.setItem(row_idx, 16, bid_vol_item)
                
                # 委卖价
                ask_price = row_data.get('askPrice', [])
                # 处理 numpy array 或 list 类型
                if hasattr(ask_price, '__len__') and len(ask_price) > 0:
                    first_elem = ask_price[0] if not pd.isna(ask_price[0]) else 0
                    ask_price_str = f"{first_elem:.2f}" if first_elem > 0 else "-"
                else:
                    ask_price_str = "-"
                ask_price_item = QTableWidgetItem(ask_price_str)
                self.tick_table.setItem(row_idx, 17, ask_price_item)
                
                # 委卖量
                ask_vol = row_data.get('askVol', [])
                # 处理 numpy array 或 list 类型
                if hasattr(ask_vol, '__len__') and len(ask_vol) > 0:
                    first_elem = ask_vol[0] if not pd.isna(ask_vol[0]) else 0
                    ask_vol_str = f"{int(first_elem):,}" if first_elem > 0 else "-"
                else:
                    ask_vol_str = "-"
                ask_vol_item = QTableWidgetItem(ask_vol_str)
                self.tick_table.setItem(row_idx, 18, ask_vol_item)

            self.tick_stats_label.setText(f"共 {len(df)} 条Tick数据")
        else:
            self.tick_table.setRowCount(0)
            self.tick_stats_label.setText("该日期暂无Tick数据")

    def on_tick_load_error(self, error_msg: str):
        """Tick数据加载错误"""
        self.load_tick_btn.setEnabled(True)
        self.load_tick_btn.setText("📊 加载Tick数据")
        QMessageBox.warning(self, "提示", f"Tick数据加载失败\n\n{error_msg}")

    def on_financial_load_error(self, error_msg: str):
        """财务数据加载错误"""
        self.load_fin_btn.setEnabled(True)
        self.load_fin_btn.setText("💰 加载财务数据")
        QMessageBox.warning(self, "提示", f"财务数据加载失败\n\n{error_msg}\n\n数据来源: QMT迅投xtdata接口")

    def export_to_excel(self):
        """导出到Excel"""
        current_tab = self.data_tab_widget.currentIndex()

        if current_tab == 0:
            # 导出行情数据
            table = self.data_table
            prefix = "market"
        else:
            # 导出财务数据
            table = self.financial_table
            prefix = "financial"

        if table.rowCount() == 0:
            QMessageBox.warning(self, "提示", "没有数据可导出")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出Excel",
            f"{self.current_stock or 'stock'}_{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx);;CSV Files (*.csv)"
        )

        if file_path:
            try:
                # 收集表格数据
                data = []
                headers = [table.horizontalHeaderItem(col).text()
                          for col in range(table.columnCount())]

                for row in range(table.rowCount()):
                    row_data = []
                    for col in range(table.columnCount()):
                        item = table.item(row, col)
                        row_data.append(item.text() if item else "")
                    data.append(row_data)

                df_export = pd.DataFrame(data, columns=headers)

                if file_path.endswith('.csv'):
                    df_export.to_csv(file_path, index=False, encoding='utf-8-sig')
                else:
                    df_export.to_excel(file_path, index=False)

                QMessageBox.information(self, "成功", f"数据已导出到:\n{file_path}")

            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {e}")


class FinancialDataLoadThread(QThread):
    """财务数据加载线程 - 使用QMT数据源"""
    data_ready = pyqtSignal(pd.DataFrame)
    error_occurred = pyqtSignal(str)

    def __init__(self, stock_code: str):
        super().__init__()
        self.stock_code = stock_code

    def run(self):
        try:
            # 尝试从QMT获取财务数据
            try:
                from xtquant import xtdata
            except ImportError:
                self.error_occurred.emit("QMT xtdata 不可用")
                return

            # 获取财务数据（使用QMT接口）
            try:
                # 获取资产负债表、利润表、现金流量表
                tables = ['Balance', 'Income', 'CashFlow']

                # 使用动态结束日期（当前日期）
                from datetime import datetime
                end_date = datetime.now().strftime('%Y%m%d')

                result = xtdata.get_financial_data(
                    stock_list=[self.stock_code],
                    table_list=tables,
                    start_time="20200101",
                    end_time=end_date,
                    report_type='report_time'
                )

                if not isinstance(result, dict):
                    self.error_occurred.emit(f"QMT返回数据格式错误: 期望dict, 实际{type(result)}")
                    return

                if self.stock_code not in result:
                    self.error_occurred.emit(f"QMT返回数据中不包含股票: {self.stock_code}")
                    return

                stock_data = result[self.stock_code]

                # 检查是否有利润表数据
                if 'Income' not in stock_data:
                    self.error_occurred.emit("QMT返回数据中不包含利润表(Income)")
                    return

                income_df = stock_data['Income']

                # 检查Income是否为DataFrame
                if not isinstance(income_df, pd.DataFrame):
                    self.error_occurred.emit(f"利润表数据格式错误: 期望DataFrame, 实际{type(income_df)}")
                    return

                if income_df.empty:
                    self.error_occurred.emit("利润表数据为空")
                    return

                # 获取资产负债表数据（用于计算资产负债率）
                balance_df = stock_data.get('Balance', pd.DataFrame())

                # 提取并计算财务指标
                # QMT列名映射：
                # m_timetag -> 报告期时间戳
                # net_profit_incl_min_int_inc -> 归属母公司所有者的净利润
                # revenue -> 营业收入
                # total_operating_cost -> 营业总成本
                # tot_assets -> 总资产
                # tot_liab -> 总负债

                records = []

                for idx, row in income_df.iterrows():
                    # 获取报告期时间戳并转换为日期字符串
                    timetag = row.get('m_timetag')
                    if pd.isna(timetag):
                        continue

                    # 将时间戳转换为日期字符串 (格式: YYYYMMDD -> YYYY-MM-DD)
                    if isinstance(timetag, (int, float)):
                        report_date = str(int(timetag))
                        if len(report_date) == 8:
                            report_date_formatted = f"{report_date[0:4]}-{report_date[4:6]}-{report_date[6:8]}"
                        else:
                            report_date_formatted = report_date
                    else:
                        report_date_formatted = str(timetag)[:10]

                    # 提取净利润（万元）
                    net_profit = row.get('net_profit_incl_min_int_inc', 0)
                    if pd.isna(net_profit):
                        net_profit = 0

                    # 提取营业收入（万元）
                    revenue = row.get('revenue', 0)
                    if pd.isna(revenue):
                        revenue = 0
                    # 如果revenue为0，尝试operating_revenue
                    if revenue == 0:
                        revenue = row.get('operating_revenue', 0)
                        if pd.isna(revenue):
                            revenue = 0

                    # 提取营业成本（万元）
                    cost = row.get('total_operating_cost', 0)
                    if pd.isna(cost):
                        cost = 0

                    # 计算净利率 (%)
                    net_margin = (net_profit / revenue * 100) if revenue > 0 else 0

                    # 计算毛利率 (%)
                    gross_margin = ((revenue - cost) / revenue * 100) if revenue > 0 else 0

                    # 尝试从资产负债表获取数据计算ROE和资产负债率
                    roe = 0
                    debt_ratio = 0

                    if isinstance(balance_df, pd.DataFrame) and not balance_df.empty:
                        # 查找同一报告期的资产负债表数据
                        balance_row = balance_df[balance_df['m_timetag'] == timetag]
                        if not balance_row.empty:
                            bal_row = balance_row.iloc[0]

                            # 总资产（万元）
                            total_assets = bal_row.get('tot_assets', 0)
                            if pd.isna(total_assets):
                                total_assets = 0

                            # 总负债（万元）
                            total_liabilities = bal_row.get('tot_liab', 0)
                            if pd.isna(total_liabilities):
                                total_liabilities = 0

                            # 股东权益（万元）
                            total_equity = bal_row.get('total_equity', 0)
                            if pd.isna(total_equity):
                                total_equity = 0

                            # 如果股东权益为0，尝试用总资产减总负债计算
                            if total_equity == 0 and total_assets > 0:
                                total_equity = total_assets - total_liabilities

                            # 计算净资产收益率ROE (%)
                            if total_equity > 0:
                                roe = (net_profit / total_equity * 100)

                            # 计算资产负债率 (%)
                            if total_assets > 0:
                                debt_ratio = (total_liabilities / total_assets * 100)

                    records.append({
                        '报告期': report_date_formatted,
                        '净资产收益率': roe,
                        '毛利率': gross_margin,
                        '净利率': net_margin,
                        '资产负债率': debt_ratio
                    })

                if records:
                    df = pd.DataFrame(records)
                    # 按报告期降序排列（最新的在前面）
                    df = df.sort_values('报告期', ascending=False)
                    self.data_ready.emit(df)
                else:
                    self.error_occurred.emit("无法从QMT财务数据中提取有效记录")

            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                self.error_occurred.emit(f"从QMT获取财务数据失败: {str(e)}\n\n详细信息:\n{error_detail}")

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.error_occurred.emit(f"发生错误: {str(e)}\n\n详细信息:\n{error_detail}")


class FinancialDataSaveThread(QThread):
    """财务数据保存线程 - 保存QMT数据到DuckDB"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str, int)  # message, percentage
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, stock_code: str):
        super().__init__()
        self.stock_code = stock_code

    def run(self):
        """运行保存任务"""
        try:
            self.log_signal.emit(f"开始保存 {self.stock_code} 的财务数据到DuckDB...")
            self.progress_signal.emit("连接数据库...", 10)

            # 获取数据库管理器
            if not DB_MANAGER_AVAILABLE:
                self.error_signal.emit("数据库管理器不可用")
                return

            # 使用 AdvancedDataViewerWidget 的 db_path
            from src.widgets.advanced_data_viewer_widget import AdvancedDataViewerWidget
            viewer = AdvancedDataViewerWidget()
            manager = get_db_manager(viewer.db_path)

            # 创建财务数据保存器
            if not FINANCIAL_SAVER_AVAILABLE:
                self.error_signal.emit("财务数据保存器不可用")
                return

            saver = FinancialDataSaver(manager)

            self.progress_signal.emit("从QMT获取数据...", 30)

            # 从QMT获取财务数据
            from xtquant import xtdata

            tables = ['Balance', 'Income', 'CashFlow', 'Dividend']
            result = xtdata.get_financial_data(
                stock_list=[self.stock_code],
                table_list=tables,
                start_time="20200101",
                end_time="20260130",
                report_type='report_time'
            )

            if not isinstance(result, dict) or self.stock_code not in result:
                self.error_signal.emit(f"QMT返回数据格式错误")
                return

            stock_data = result[self.stock_code]

            self.progress_signal.emit("准备数据...", 50)

            # 提取各个表的数据
            income_df = stock_data.get('Income', pd.DataFrame())
            balance_df = stock_data.get('Balance', pd.DataFrame())
            cashflow_df = stock_data.get('CashFlow', pd.DataFrame())
            dividend_df = stock_data.get('Dividend', pd.DataFrame())

            self.progress_signal.emit("保存到DuckDB...", 70)

            # 保存到DuckDB
            save_result = saver.save_from_qmt(
                self.stock_code,
                income_df,
                balance_df,
                cashflow_df,
                dividend_df
            )

            self.progress_signal.emit("完成...", 100)

            if save_result['success']:
                summary = f"""
财务数据保存成功！

股票代码: {save_result['stock_code']}
- 利润表: {save_result['income_count']} 条记录
- 资产负债表: {save_result['balance_count']} 条记录
- 现金流量表: {save_result['cashflow_count']} 条记录
- 分红数据: {save_result.get('dividend_count', 0)} 条记录
"""
                self.log_signal.emit(summary)
                self.finished_signal.emit(save_result)
            else:
                self.error_signal.emit(f"保存失败: {save_result.get('error', '未知错误')}")

        except ImportError:
            self.error_signal.emit("无法导入xtquant，请确保QMT已安装并运行")
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.error_signal.emit(f"保存失败: {str(e)}\n\n详细信息:\n{error_detail}")


class BatchFinancialSaveThread(QThread):
    """批量保存财务数据线程"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str, int, int)  # message, current, total
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, stock_list: list):
        super().__init__()
        self.stock_list = stock_list
        self._is_running = True

    def run(self):
        """批量保存财务数据"""
        try:
            if not DB_MANAGER_AVAILABLE or not FINANCIAL_SAVER_AVAILABLE:
                self.error_signal.emit("数据库模块不可用")
                return

            # 使用 AdvancedDataViewerWidget 的 db_path
            from src.widgets.advanced_data_viewer_widget import AdvancedDataViewerWidget
            viewer = AdvancedDataViewerWidget()
            manager = get_db_manager(viewer.db_path)
            saver = FinancialDataSaver(manager)

            from xtquant import xtdata

            total = len(self.stock_list)
            success_count = 0
            failed_count = 0
            failed_list = []

            self.log_signal.emit(f"开始批量保存 {total} 只股票的财务数据...")
            self.log_signal.emit("=" * 60)

            for idx, stock_code in enumerate(self.stock_list):
                if not self._is_running:
                    self.log_signal.emit("\n用户中断操作")
                    break

                current = idx + 1
                self.progress_signal.emit(f"正在处理 {stock_code}...", current, total)

                try:
                    # 获取财务数据
                    tables = ['Balance', 'Income', 'CashFlow', 'Dividend']
                    result = xtdata.get_financial_data(
                        stock_list=[stock_code],
                        table_list=tables,
                        start_time="20200101",
                        end_time="20260130",
                        report_type='report_time'
                    )

                    if isinstance(result, dict) and stock_code in result:
                        stock_data = result[stock_code]

                        income_df = stock_data.get('Income', pd.DataFrame())
                        balance_df = stock_data.get('Balance', pd.DataFrame())
                        cashflow_df = stock_data.get('CashFlow', pd.DataFrame())
                        dividend_df = stock_data.get('Dividend', pd.DataFrame())

                        # 保存到DuckDB
                        save_result = saver.save_from_qmt(
                            stock_code,
                            income_df,
                            balance_df,
                            cashflow_df,
                            dividend_df
                        )

                        if save_result['success']:
                            total_records = (save_result['income_count'] +
                                          save_result['balance_count'] +
                                          save_result['cashflow_count'] +
                                          save_result.get('dividend_count', 0))
                            self.log_signal.emit(
                                f"[{current}/{total}] {stock_code}: OK ({total_records}条记录)"
                            )
                            success_count += 1
                        else:
                            self.log_signal.emit(
                                f"[{current}/{total}] {stock_code}: 失败 - {save_result.get('error', '')}"
                            )
                            failed_count += 1
                            failed_list.append(stock_code)
                    else:
                        self.log_signal.emit(f"[{current}/{total}] {stock_code}: 无数据（可能是ETF/指数）")
                        failed_count += 1

                except Exception as e:
                    self.log_signal.emit(f"[{current}/{total}] {stock_code}: 异常 - {str(e)}")
                    failed_count += 1
                    failed_list.append(stock_code)

            # 输出汇总
            self.log_signal.emit("\n" + "=" * 60)
            self.log_signal.emit("批量保存完成！")
            self.log_signal.emit(f"总计: {total} 只股票")
            self.log_signal.emit(f"成功: {success_count} 只")
            self.log_signal.emit(f"失败: {failed_count} 只")

            if failed_list:
                self.log_signal.emit(f"\n失败的股票: {', '.join(failed_list[:10])}")
                if len(failed_list) > 10:
                    self.log_signal.emit(f"  ... 还有 {len(failed_list) - 10} 只")

            self.finished_signal.emit({
                'total': total,
                'success': success_count,
                'failed': failed_count,
                'failed_list': failed_list
            })

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.error_signal.emit(f"批量保存失败: {str(e)}\n\n{error_detail}")

    def stop(self):
        """停止保存"""
        self._is_running = False


class TickDataLoadThread(QThread):
    """Tick数据加载线程"""
    data_ready = pyqtSignal(pd.DataFrame)
    error_occurred = pyqtSignal(str)

    def __init__(self, stock_code: str, tick_date: str, time_range: str):
        super().__init__()
        self.stock_code = stock_code
        self.tick_date = tick_date
        self.time_range = time_range

    def run(self):
        try:
            # 首先尝试从DuckDB加载tick数据
            if DB_MANAGER_AVAILABLE:
                # 使用 AdvancedDataViewerWidget 的 db_path
                from src.widgets.advanced_data_viewer_widget import AdvancedDataViewerWidget
                viewer = AdvancedDataViewerWidget()
                manager = get_db_manager(viewer.db_path)

                # 解析日期
                date_obj = datetime.strptime(self.tick_date, '%Y-%m-%d')

                # 构建时间范围过滤
                time_filter = ""
                if self.time_range == "9:15-11:30":
                    time_filter = "AND ((EXTRACT(HOUR FROM datetime) = 9 AND EXTRACT(MINUTE FROM datetime) >= 15) OR (EXTRACT(HOUR FROM datetime) = 10) OR (EXTRACT(HOUR FROM datetime) = 11 AND EXTRACT(MINUTE FROM datetime) < 30))"
                elif self.time_range == "13:00-15:00":
                    time_filter = "AND ((EXTRACT(HOUR FROM datetime) = 13) OR (EXTRACT(HOUR FROM datetime) = 14 AND EXTRACT(MINUTE FROM datetime) < 30))"
                elif self.time_range == "9:30-10:00":
                    time_filter = "AND ((EXTRACT(HOUR FROM datetime) = 9 AND EXTRACT(MINUTE FROM datetime) >= 30) OR (EXTRACT(HOUR FROM datetime) = 10 AND EXTRACT(MINUTE FROM datetime) < 30))"
                elif self.time_range == "10:00-10:30":
                    time_filter = "AND EXTRACT(HOUR FROM datetime) = 10 AND EXTRACT(MINUTE FROM datetime) >= 0 AND EXTRACT(MINUTE FROM datetime) < 30"
                elif self.time_range == "14:00-14:30":
                    time_filter = "AND EXTRACT(HOUR FROM datetime) = 14 AND EXTRACT(MINUTE FROM datetime) >= 0 AND EXTRACT(MINUTE FROM datetime) < 30"

                # 尝试从stock_tick视图查询
                # 检查视图是否存在（同时检查表和视图）
                check_query = """
                    SELECT count(*) FROM (
                        SELECT table_name FROM information_schema.views 
                        WHERE table_name = 'stock_tick'
                        UNION ALL
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_name = 'stock_tick'
                    ) AS combined
                """
                table_exists = manager.query_dataframe(check_query)
                if table_exists is None or table_exists.empty or table_exists.iloc[0, 0] == 0:
                    self.error_occurred.emit("stock_tick 视图不存在，请先在「数据管理」页面点击「🔄 重新生成数据库视图」按钮")
                    return
                
                query = f"""
                    SELECT
                        datetime,
                        open,
                        high,
                        low,
                        close,
                        lastPrice,
                        lastClose,
                        volume,
                        pvolume,
                        amount,
                        transactionNum,
                        func_type,
                        openInt,
                        lastSettlementPrice,
                        stockStatus,
                        askPrice,
                        bidPrice,
                        askVol,
                        bidVol
                    FROM "stock_tick"
                    WHERE stock_code = '{self.stock_code}'
                      AND DATE_TRUNC('day', datetime) = '{self.tick_date}'
                      {time_filter}
                    ORDER BY datetime
                    LIMIT 100000
                """

                try:
                    df = manager.query_dataframe(query)

                    if df is not None and not df.empty:
                        # 确保所有需要的字段存在
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
                        
                        self.data_ready.emit(df)
                        return
                    else:
                        # 如果DuckDB中没有数据，尝试从QMT实时获取
                        pass
                except Exception as e:
                    # 如果查询失败，尝试从QMT获取
                    self.error_occurred.emit(f"从数据库获取Tick数据失败: {str(e)}")
            else:
                # 如果数据库不可用，尝试从QMT获取
                pass

            # 尝试从QMT获取tick数据
            try:
                from xtquant import xtdata

                # 转换日期格式
                date_str = datetime.strptime(self.tick_date, '%Y-%m-%d').strftime('%Y%m%d')

                # 获取tick数据，指定所有需要的字段
                tick_data = xtdata.get_market_data_ex(
                    field_list=['time', 'lastPrice', 'open', 'high', 'low', 'lastClose', 
                               'amount', 'volume', 'pvolume', 'stockStatus', 'openInt', 
                               'lastSettlementPrice', 'askPrice', 'bidPrice', 'askVol', 
                               'bidVol', 'transactionNum'],
                    stock_list=[self.stock_code],
                    period='tick',
                    start_time=date_str,
                    end_time=date_str
                )

                if isinstance(tick_data, dict) and self.stock_code in tick_data:
                    df = tick_data[self.stock_code]

                    if not df.empty:
                        # 确保必要的列存在
                        if 'datetime' not in df.columns and 'time' in df.columns:
                            # 转换为北京时间（UTC+8）
                            df['datetime'] = pd.to_datetime(df['time'], unit='ms', utc=True).dt.tz_convert('Asia/Shanghai')
                            # 移除时区信息，只保留本地时间
                            df['datetime'] = df['datetime'].dt.tz_localize(None)
                        
                        # 重命名列以匹配数据库结构
                        if 'price' in df.columns and 'lastPrice' not in df.columns:
                            df['lastPrice'] = df['price']
                        if 'type' in df.columns and 'func_type' not in df.columns:
                            df['func_type'] = df['type']
                        if 'oi' in df.columns and 'openInt' not in df.columns:
                            df['openInt'] = df['oi']
                        
                        # 确保价格列存在
                        for col in ['open', 'high', 'low', 'close']:
                            if col not in df.columns:
                                df[col] = df.get('lastPrice', 0)
                        
                        # 确保成交笔数字段有正确的值
                        if 'transactionNum' in df.columns:
                            # 填充NaN值为0
                            df['transactionNum'] = df['transactionNum'].fillna(0)
                        
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

                        # 应用时间范围过滤
                        if self.time_range != "全天":
                            if 'datetime' not in df.columns:
                                df['datetime'] = pd.to_datetime(df['time'], unit='ms')

                            if self.time_range == "9:15-11:30":
                                df = df[(df['datetime'].dt.hour >= 9) & (df['datetime'].dt.hour < 12)]
                            elif self.time_range == "13:00-15:00":
                                df = df[(df['datetime'].dt.hour >= 13) & (df['datetime'].dt.hour < 15)]
                            elif self.time_range == "9:30-10:00":
                                df = df[((df['datetime'].dt.hour == 9) & (df['datetime'].dt.minute >= 30)) |
                                       ((df['datetime'].dt.hour == 10) & (df['datetime'].dt.minute < 30))]
                            elif self.time_range == "10:00-10:30":
                                df = df[(df['datetime'].dt.hour == 10) & (df['datetime'].dt.minute >= 0) & (df['datetime'].dt.minute < 30)]
                            elif self.time_range == "14:00-14:30":
                                df = df[(df['datetime'].dt.hour == 14) & (df['datetime'].dt.minute >= 0) & (df['datetime'].dt.minute < 30)]

                        # 限制返回的行数
                        if len(df) > 100000:
                            df = df.head(100000)

                        self.data_ready.emit(df)
                        return

            except ImportError:
                self.error_occurred.emit("QMT xtdata不可用，且数据库中无tick数据")
                return
            except Exception as e:
                import traceback
                self.error_occurred.emit(f"从QMT获取tick数据失败: {str(e)}")
                return

            # 如果没有任何数据
            self.error_occurred.emit(f"{self.tick_date} 无tick数据，请先在「数据管理」中下载")

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.error_occurred.emit(f"加载tick数据出错: {str(e)}\n\n{error_detail}")
