#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EasyXT量化交易策略管理平台
基于PyQt5的专业量化交易策略参数设置和管理界面
用于策略开发、参数配置、实时监控和交易执行
"""

import sys
import os
import json
import traceback
import importlib.util
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QTextEdit, QLabel, QPushButton, QComboBox,
    QSpinBox, QDoubleSpinBox, QSlider, QGroupBox, QGridLayout,
    QListWidget, QListWidgetItem, QProgressBar, QStatusBar,
    QMenuBar, QAction, QMessageBox, QFileDialog, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QLineEdit, QFormLayout, QTreeWidget, QTreeWidgetItem,
    QDockWidget, QToolBar, QFrame, QSizePolicy, QDateTimeEdit,
    QTimeEdit, QDateEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings, QSize, QDateTime
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor, QPixmap

import pandas as pd
import numpy as np

try:
    import pyqtgraph as pg
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False

try:
    # 修复导入错误
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# 添加项目路径
project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_path)

# 尝试导入easy_xt
try:
    import easy_xt
    EASYXT_AVAILABLE = True
except ImportError:
    EASYXT_AVAILABLE = False
    print("警告: easy_xt未安装，部分功能将不可用")

def setup_logger():
    """设置日志记录器 - 只输出到控制台"""
    # 创建 logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    # 清除现有的 handlers
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)
    
    # 只创建 stream handler，不再生成日志文件
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    
    # 设置格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    stream_handler.setFormatter(formatter)
    
    # 添加 handlers
    logger.addHandler(stream_handler)
    
    return logger

# 导入各个功能组件
from src.widgets.backtest_widget import BacktestWidget
from src.widgets.jq2qmt_widget import JQ2QMTWidget
from src.widgets.jq_to_ptrade_widget import JQToPtradeWidget
from src.widgets.grid_trading_widget import GridTradingWidget
from src.widgets.conditional_order_widget import ConditionalOrderWidget
from src.widgets.local_data_manager_widget import LocalDataManagerWidget
from src.widgets.advanced_data_viewer_widget import AdvancedDataViewerWidget
from src.widgets.tushare_data_widget import TushareDataWidget


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.logger = setup_logger()
        self.executor_thread = None
        self.logger.info("初始化主窗口...")
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        self.logger.info("开始初始化界面...")
        self.setWindowTitle("EasyXT量化交易策略管理平台")
        self.setGeometry(100, 100, 1600, 1000)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # 创建各个功能标签页
        self.create_tabs()
        
        # 创建状态栏
        self.create_status_bar()
        
        # 设置窗口属性
        self.setWindowTitle("EasyXT量化交易策略管理平台")
        self.setGeometry(100, 100, 1400, 1100)
        self.setMinimumSize(900, 900)
        
        # 设置默认标签页
        self.tab_widget.setCurrentIndex(0)
        self.logger.info("界面初始化完成")
        
    def create_tabs(self):
        """创建各个功能标签页"""
        self.logger.info("开始创建功能标签页...")
        
        # 回测分析标签页
        self.logger.info("创建回测分析标签页...")
        backtest_tab = QWidget()
        backtest_layout = QVBoxLayout(backtest_tab)
        self.backtest_widget = BacktestWidget()
        backtest_layout.addWidget(self.backtest_widget)
        self.tab_widget.addTab(backtest_tab, "回测分析")
        self.logger.info("回测分析标签页创建完成")

        # 聚宽到Ptrade转换标签页
        self.logger.info("创建JQ转Ptrade标签页...")
        jq_to_ptrade_tab = QWidget()
        jq_to_ptrade_layout = QVBoxLayout(jq_to_ptrade_tab)
        self.jq_to_ptrade_widget = JQToPtradeWidget()
        jq_to_ptrade_layout.addWidget(self.jq_to_ptrade_widget)
        self.tab_widget.addTab(jq_to_ptrade_tab, "JQ转Ptrade")
        self.logger.info("JQ转Ptrade标签页创建完成")

        # 网格交易标签页
        self.logger.info("创建网格交易标签页...")
        grid_trading_tab = QWidget()
        grid_trading_layout = QVBoxLayout(grid_trading_tab)
        self.grid_trading_widget = GridTradingWidget()
        grid_trading_layout.addWidget(self.grid_trading_widget)
        self.tab_widget.addTab(grid_trading_tab, "网格交易")
        self.logger.info("网格交易标签页创建完成")

        # 条件单标签页
        self.logger.info("创建条件单标签页...")
        conditional_order_tab = QWidget()
        conditional_order_layout = QVBoxLayout(conditional_order_tab)
        self.conditional_order_widget = ConditionalOrderWidget()
        conditional_order_layout.addWidget(self.conditional_order_widget)
        self.tab_widget.addTab(conditional_order_tab, "条件单")
        self.logger.info("条件单标签页创建完成")

        # 本地数据管理标签页
        self.logger.info("创建数据管理标签页...")
        data_manager_tab = QWidget()
        data_manager_layout = QVBoxLayout(data_manager_tab)
        self.data_manager_widget = LocalDataManagerWidget()
        data_manager_layout.addWidget(self.data_manager_widget)
        self.tab_widget.addTab(data_manager_tab, "📊 数据管理")
        self.logger.info("数据管理标签页创建完成")

        # 高级数据查看器标签页
        self.logger.info("创建数据查看器标签页...")
        advanced_viewer_tab = QWidget()
        advanced_viewer_layout = QVBoxLayout(advanced_viewer_tab)
        self.advanced_data_viewer_widget = AdvancedDataViewerWidget()
        advanced_viewer_layout.addWidget(self.advanced_data_viewer_widget)
        self.tab_widget.addTab(advanced_viewer_tab, "📈 数据查看器")
        self.logger.info("数据查看器标签页创建完成")

        # Tushare数据下载标签页
        self.logger.info("创建Tushare下载标签页...")
        tushare_data_tab = QWidget()
        tushare_data_layout = QVBoxLayout(tushare_data_tab)
        self.tushare_data_widget = TushareDataWidget()
        tushare_data_layout.addWidget(self.tushare_data_widget)
        self.tab_widget.addTab(tushare_data_tab, "📥 Tushare下载")
        self.logger.info("Tushare下载标签页创建完成")
        self.logger.info("所有功能标签页创建完成")
        
    def create_status_bar(self):
        """创建状态栏"""
        self.logger.info("创建状态栏...")
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 添加连接状态指示器
        self.connection_status = QLabel("🔴 MiniQMT未连接")
        self.connection_status.setStyleSheet("""
            QLabel {
                background-color: #ff4444;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QLabel:hover {
                background-color: #ff6666;
                cursor: pointer;
            }
        """)
        # 添加提示文本
        self.connection_status.setToolTip("点击刷新连接状态")
        # 连接鼠标点击事件
        self.connection_status.mousePressEvent = self.on_connection_status_clicked
        
        self.status_bar.addPermanentWidget(self.connection_status)
        self.status_bar.showMessage("就绪")

        # 检查MiniQMT连接状态（启动时延迟1秒检查）
        self.logger.info("设置连接状态检查定时器...")
        QTimer.singleShot(1000, self.check_connection_status)

        # 定期检查连接状态（每30秒检查一次）
        self.connection_check_timer = QTimer()
        self.connection_check_timer.timeout.connect(self.check_connection_status)
        self.connection_check_timer.start(30000)  # 30秒
        self.logger.info("状态栏创建完成")

    def on_connection_status_clicked(self, event):
        """连接状态标签被点击事件"""
        self.logger.info("手动刷新连接状态...")
        self.check_connection_status()

    def check_connection_status(self):
        """检查MiniQMT连接状态"""
        self.logger.info("\n" + "="*60)
        self.logger.info("开始检查MiniQMT连接状态...")
        self.logger.info("="*60)

        api = None
        try:
            # 检查easy_xt是否可用
            if not EASYXT_AVAILABLE:
                self.logger.error("❌ EasyXT不可用")
                self.update_connection_status(False)
                return

            self.logger.info("✓ EasyXT可用")

            try:
                api = easy_xt.get_api()
                self.logger.info("✓ 成功获取API实例")
            except Exception as e:
                self.logger.error(f"❌ 获取API失败: {str(e)}")
                self.update_connection_status(False)
                return

            # 检查data服务
            if not hasattr(api, 'data'):
                self.logger.error("❌ API没有data属性")
                self.update_connection_status(False)
                return

            self.logger.info("✓ API有data属性")

            # 尝试初始化数据服务
            self.logger.info("\n尝试初始化数据服务...")
            init_success = False
            try:
                if hasattr(api, 'init_data'):
                    self.logger.info("  尝试调用 api.init_data()...")
                    init_result = api.init_data()
                    self.logger.info(f"  api.init_data() 返回: {init_result}")

                    if init_result:
                        self.logger.info("✓ 数据服务初始化成功")
                        init_success = True
                    else:
                        self.logger.warning("⚠ 数据服务初始化返回False")
                
                # 如果第一次初始化失败，尝试在data对象上初始化
                if not init_success and hasattr(api.data, 'init_data'):
                    self.logger.info("  尝试调用 api.data.init_data()...")
                    init_result = api.data.init_data()
                    self.logger.info(f"  api.data.init_data() 返回: {init_result}")
                    
                    if init_result:
                        self.logger.info("✓ 数据服务初始化成功")
                        init_success = True
                    else:
                        self.logger.warning("⚠ 数据服务初始化返回False")
                
                if not init_success:
                    self.logger.warning("⚠ 数据服务初始化失败，尝试获取数据可能会失败")
            except Exception as e:
                self.logger.warning(f"⚠ 初始化数据服务时出现异常: {str(e)}")

            # 尝试获取行情数据来验证连接
            test_codes = ['511090.SH', '000001.SZ']
            connected = False

            for code in test_codes:
                try:
                    self.logger.info(f"\n尝试获取 {code} 的行情数据...")
                    # 确保数据服务已初始化
                    if not init_success:
                        self.logger.warning("  数据服务未初始化，尝试再次初始化...")
                        try:
                            if hasattr(api, 'init_data'):
                                init_result = api.init_data()
                                if init_result:
                                    self.logger.info("  ✓ 数据服务初始化成功")
                                    init_success = True
                        except Exception as init_e:
                            self.logger.warning(f"  ⚠ 再次初始化失败: {init_e}")
                    
                    # 只有在初始化成功后才尝试获取数据
                    if init_success:
                        price_df = api.data.get_current_price([code])

                        self.logger.info(f"  返回类型: {type(price_df)}")
                        self.logger.info(f"  是否为None: {price_df is None}")

                        if price_df is not None:
                            self.logger.info(f"  是否为空: {price_df.empty if hasattr(price_df, 'empty') else 'N/A'}")
                            self.logger.info(f"  长度: {len(price_df) if hasattr(price_df, '__len__') else 'N/A'}")

                            if hasattr(price_df, 'empty') and not price_df.empty:
                                connected = True
                                self.logger.info(f"✓ 连接验证成功：通过{code}获取到行情数据")
                                self.logger.info(f"  数据预览:\n{price_df.head()}")
                                break
                            else:
                                self.logger.info(f"  返回为空DataFrame")
                        else:
                            self.logger.info(f"  返回为None")
                    else:
                        self.logger.warning("  数据服务未初始化，跳过数据获取")
                        break

                except Exception as e:
                    error_msg = str(e)
                    self.logger.error(f"  ❌ 获取{code}行情异常: {error_msg}")
                    # 如果是数据服务未连接的错误，尝试重新初始化
                    if "数据服务未连接" in error_msg:
                        self.logger.warning("  尝试重新初始化数据服务...")
                        try:
                            if hasattr(api, 'init_data'):
                                init_result = api.init_data()
                                if init_result:
                                    self.logger.info("  ✓ 重新初始化成功")
                                    init_success = True
                                    # 再次尝试获取数据
                                    price_df = api.data.get_current_price([code])
                                    if price_df is not None and hasattr(price_df, 'empty') and not price_df.empty:
                                        connected = True
                                        self.logger.info(f"✓ 重新尝试成功：通过{code}获取到行情数据")
                                        break
                        except Exception as reinit_e:
                            self.logger.warning(f"  ⚠ 重新初始化失败: {reinit_e}")
                    continue

            self.logger.info("\n" + "="*60)
            if connected:
                self.logger.info("✅ 最终结果: MiniQMT已连接")
            else:
                self.logger.error("❌ 最终结果: MiniQMT未连接")
            self.logger.info("="*60 + "\n")

            self.update_connection_status(connected)

        except Exception as e:
            self.logger.error(f"\n❌ 检查连接状态异常: {str(e)}")
            import traceback
            self.logger.error(f"详细错误堆栈:\n{traceback.format_exc()}")
            self.logger.info("="*60 + "\n")
            self.update_connection_status(False)
        finally:
            # 清理资源，避免MiniRacer异常
            if api and hasattr(api, 'close'):
                try:
                    api.close()
                    self.logger.info("✓ 成功关闭API连接")
                except Exception as close_e:
                    self.logger.warning(f"⚠ 关闭API连接时出现异常: {close_e}")

    def update_connection_status(self, connected: bool):
        """更新连接状态显示

        Args:
            connected: 是否已连接
        """
        if connected:
            self.logger.info("更新连接状态: MiniQMT已连接")
            self.connection_status.setText("🟢 MiniQMT已连接")
            self.connection_status.setStyleSheet("""
                QLabel {
                    background-color: #00cc00;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                }
            """)
            self.status_bar.showMessage("MiniQMT已连接")
        else:
            self.logger.warning("更新连接状态: MiniQMT未连接")
            self.connection_status.setText("🔴 MiniQMT未连接")
            self.connection_status.setStyleSheet("""
                QLabel {
                    background-color: #ff4444;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                }
            """)
            self.status_bar.showMessage("MiniQMT未连接，请检查QMT客户端是否启动")

    def closeEvent(self, a0):
        """关闭事件"""
        self.logger.info("正在关闭应用窗口...")
        # 停止连接检查定时器
        if hasattr(self, 'connection_check_timer'):
            self.logger.info("停止连接检查定时器...")
            self.connection_check_timer.stop()
        self.logger.info("应用窗口已关闭")
        a0.accept()


def main():
    """主函数"""
    # 设置日志
    logger = setup_logger()
    logger.info("=" * 70)
    logger.info("EasyXT量化交易策略管理平台 - 主函数")
    logger.info("=" * 70)
    
    try:
        logger.info("初始化应用程序...")
        app = QApplication(sys.argv)
        
        # 设置应用程序信息
        app.setApplicationName("EasyXT量化交易策略管理平台")
        app.setApplicationVersion("3.0")
        app.setOrganizationName("EasyXT")
        logger.info("应用程序信息设置完成")
        
        # 设置应用程序字体
        font = QFont("Microsoft YaHei", 9)
        app.setFont(font)
        logger.info("应用程序字体设置完成")
        
        # 设置样式
        app.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #2196F3;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #ccc;
                background-color: #f0f0f0;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        logger.info("应用程序样式设置完成")
        
        # 创建并显示主窗口
        logger.info("创建主窗口...")
        window = MainWindow()
        logger.info("显示主窗口...")
        window.show()
        
        # 运行应用程序
        logger.info("运行应用程序...")
        sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"应用程序运行异常: {e}")
        import traceback
        logger.error(f"详细错误堆栈:\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()