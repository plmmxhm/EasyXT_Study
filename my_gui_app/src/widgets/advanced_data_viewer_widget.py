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
    QTabWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDate, QTimer
from PyQt5.QtGui import QFont, QColor

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
                    # 计算均价
                    if 'amount' in df.columns and 'volume' in df.columns:
                        df['avg_price'] = df['amount'] / df['volume'] if 'volume' in df.columns and df['volume'].sum() > 0 else 0
                    
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
            self.db_path = 'D:/MyStockData/stock_data.ddb'
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
                'dbfile': 'stock_data.ddb',
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
        """解析数据库路径"""
        # 检查 self.config 是否为 None
        if self.config is None:
            print("⚠️ self.config 为 None，使用默认数据库路径")
            db_path = 'D:/MyStockData/stock_data.ddb'
            print(f"⚠️ 使用默认数据库路径: {db_path}")
            return db_path
        
        # 1. 从合并后的配置中获取数据库路径
        if 'database' in self.config and 'path' in self.config['database']:
            db_path = self.config['database']['path']
            print(f"✅ 从配置文件读取数据库路径: {db_path}")
            return db_path
        
        # 2. 尝试组合生成路径
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
        
        # 4. 如果没有配置，使用默认路径，与local_data_manager_widget.py保持一致
        else:
            db_path = 'D:/MyStockData/stock_data.ddb'
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
        """创建控制面板"""
        group = QGroupBox("控制面板")
        layout = QHBoxLayout(group)

        # 左侧：股票信息
        info_layout = QVBoxLayout()
        self.stock_label = QLabel("当前股票: 未选择")
        self.stock_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.stock_label.setStyleSheet("color: #2196F3;")
        info_layout.addWidget(self.stock_label)

        self.record_count_label = QLabel("记录数: 0")
        self.record_count_label.setStyleSheet("color: #757575;")
        info_layout.addWidget(self.record_count_label)

        layout.addLayout(info_layout)

        # 中间：数据类型、复权和日期
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

        control_layout.addWidget(QLabel("起始日期:"), 1, 0)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-3))
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        control_layout.addWidget(self.start_date_edit, 1, 1)

        control_layout.addWidget(QLabel("结束日期:"), 1, 2)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        control_layout.addWidget(self.end_date_edit, 1, 3)

        layout.addLayout(control_layout)

        # 右侧：操作按钮
        btn_layout = QHBoxLayout()

        self.load_btn = QPushButton("📥 加载数据")
        self.load_btn.clicked.connect(self.load_current_stock)
        btn_layout.addWidget(self.load_btn)

        self.export_btn = QPushButton("📤 导出Excel")
        self.export_btn.clicked.connect(self.export_to_excel)
        btn_layout.addWidget(self.export_btn)

        layout.addLayout(btn_layout)

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
        self.stock_table.setColumnCount(4)
        self.stock_table.setHorizontalHeaderLabels(["股票代码", "类型", "记录数", "日期范围"])
        self.stock_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.stock_table.setSelectionMode(QTableWidget.SingleSelection)
        self.stock_table.setSortingEnabled(True)
        self.stock_table.setMaximumHeight(250)
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

        # 设置列宽
        self.data_table.setColumnWidth(0, 100)
        for i in range(1, 5):
            self.data_table.setColumnWidth(i, 80)
        self.data_table.setColumnWidth(5, 70)
        self.data_table.setColumnWidth(6, 100)
        self.data_table.setColumnWidth(7, 100)

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

        for row_idx, (_, data_row) in enumerate(df.iterrows()):
            # 股票代码
            code_item = QTableWidgetItem(data_row['stock_code'])
            code_item.setFont(QFont("Consolas", 10))
            self.stock_table.setItem(row_idx, 0, code_item)

            # 类型
            type_map = {'stock': '股票', 'bond': '债券', 'etf': 'ETF'}
            type_item = QTableWidgetItem(type_map.get(data_row['symbol_type'], data_row['symbol_type']))
            self.stock_table.setItem(row_idx, 1, type_item)

            # 记录数
            count_item = QTableWidgetItem(f"{data_row['count']:,}")
            count_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.stock_table.setItem(row_idx, 2, count_item)

            # 日期范围
            min_date = str(data_row['min_date'])[:10]
            max_date = str(data_row['max_date'])[:10]
            date_item = QTableWidgetItem(f"{min_date} ~ {max_date}")
            self.stock_table.setItem(row_idx, 3, date_item)

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
        """数据类型改变"""
        print(f"🔄 [on_data_type_changed] 数据类型改变为: {text}")
        
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
        
        # 如果已选择股票，自动加载数据
        if self.current_stock:
            self.load_current_stock()

    def on_adjust_changed(self, text: str):
        """复权类型改变"""
        if self.current_stock:
            self.load_current_stock()

    def load_current_stock(self):
        """加载当前股票数据"""
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
        self.current_data = df
        self.load_btn.setEnabled(True)
        self.load_btn.setText("📥 加载数据")

        if not df.empty:
            # 填充数据表格
            self.data_table.setRowCount(len(df))

            # 动态调整列数，支持更多数据列
            columns = ['日期', '开盘', '最高', '最低', '收盘', '涨跌', '涨跌幅', '成交量', '成交额', '均价', '换手率']
            self.data_table.setColumnCount(len(columns))
            self.data_table.setHorizontalHeaderLabels(columns)

            # 设置列宽
            if hasattr(self, 'data_type') and self.data_type in ['1m', '5m', '15m', '30m', '60m', 'tick']:
                # 分钟线和Tick数据需要更宽的时间列
                column_widths = [180, 80, 80, 80, 80, 80, 80, 100, 100, 80, 80]
            else:
                # 日线、周线、月线使用默认宽度
                column_widths = [100, 80, 80, 80, 80, 80, 80, 100, 100, 80, 80]
            for i, width in enumerate(column_widths):
                self.data_table.setColumnWidth(i, width)

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

                # 成交量
                if 'volume' in row_data:
                    volume = row_data['volume']
                    if pd.notna(volume) and volume > 0:
                        volume_item = QTableWidgetItem(f"{int(volume):,}")
                    else:
                        volume_item = QTableWidgetItem("-")
                else:
                    volume_item = QTableWidgetItem("-")
                self.data_table.setItem(row_idx, 7, volume_item)

                # 成交额
                if 'amount' in row_data:
                    amount = row_data['amount']
                    if pd.notna(amount) and amount > 0:
                        amount_item = QTableWidgetItem(f"{amount:,.0f}")
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
        else:
            self.data_table.setRowCount(0)
            self.data_stats_label.setText(f"{stock_code} 该时间段无数据")

    def on_load_error(self, error_msg: str):
        """加载错误"""
        self.load_btn.setEnabled(True)
        self.load_btn.setText("📥 加载数据")
        QMessageBox.critical(self, "错误", f"数据加载失败: {error_msg}")

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
