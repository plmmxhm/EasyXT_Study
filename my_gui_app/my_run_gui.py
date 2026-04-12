#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI应用快速启动脚本
用于启动EasyXT量化交易策略管理平台
"""

import sys
import os
import logging
from datetime import datetime

def setup_logger():
    """设置日志记录器"""
    # 确保日志目录存在
    project_root = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(project_root, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 生成日志文件名
    log_filename = f"run_gui_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path = os.path.join(log_dir, log_filename)
    
    # 创建logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    # 清除现有的handlers
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)
    
    # 创建file handler
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # 创建stream handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    
    # 设置格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    
    # 添加handlers
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    
    return logger

def main():
    # 【关键】抑制第三方库的 datetime KeyError 警告
    # 周线/月线数据使用 date 列而非 datetime 列，某些库会尝试访问不存在的 datetime 列
    import warnings
    warnings.filterwarnings('ignore', message=".*'datetime'.*", category=Warning)
    
    # 【增强】配置日志系统，过滤掉所有包含 'datetime' 的 WARNING 级别日志
    import logging
    
    class DateTimeWarningFilter(logging.Filter):
        """自定义过滤器：过滤包含 'datetime' KeyError 的警告"""
        def filter(self, record):
            # 如果是WARNING级别且消息包含 'datetime' 和 '缓存操作失败' 或类似模式，则过滤掉
            if record.levelno == logging.WARNING:
                msg = str(record.getMessage())
                if "'datetime'" in msg and ("缓存" in msg or "操作失败" in msg or "KeyError" in msg):
                    return False  # 过滤掉这条日志
            return True  # 保留其他日志
    
    # 获取root logger并添加过滤器
    root_logger = logging.getLogger()
    root_logger.addFilter(DateTimeWarningFilter())
    
    # 同时设置基本配置，确保WARNING级别以上的日志能被正确处理
    logging.basicConfig(
        level=logging.INFO,  # 默认级别
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # 禁用日志文件，只输出到控制台
    def print_log(message):
        print(message)
    
    # 获取项目根目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    # 获取父目录（项目总根目录）
    parent_root = os.path.dirname(project_root)
    
    # 添加项目路径到sys.path
    sys.path.insert(0, project_root)
    sys.path.insert(0, parent_root)
    
    print_log("=" * 70)
    print_log("EasyXT量化交易策略管理平台 - 启动器")
    print_log("=" * 70)
    
    # 检查依赖
    print_log("\n[*] 检查依赖...")

    dependencies = {
        'PyQt5': 'PyQt5基础库',
        'pandas': 'DataFrame数据处理',
        'numpy': '数值计算库',
    }

    missing_deps = []
    for package, description in dependencies.items():
        try:
            __import__(package)
            print_log(f"  [OK] {package:<15} - {description}")
        except ImportError:
            print_log(f"  [FAIL] {package:<15} - {description} (未安装)")
            missing_deps.append(package)

    if missing_deps:
        print_log(f"\n[WARNING] 缺少以下依赖: {', '.join(missing_deps)}")
        print_log("请运行以下命令安装:")
        print_log(f"  pip install {' '.join(missing_deps)}")
        return False

    # 检查转换器
    print_log("\n[*] 检查转换器...")
    try:
        # 尝试从本地路径导入转换器
        converter_path = os.path.join(project_root, 'src', 'widgets', 'jq_to_ptrade_widget.py')
        if os.path.exists(converter_path):
            print_log(f"  [OK] 本地转换器文件存在")
        else:
            print_log(f"  [WARNING] 转换器文件不存在，但继续运行")
    except Exception as e:
        print_log(f"  [WARNING] 检查转换器时出错: {e}")
        # 继续运行，不因为转换器问题而停止

    # 检查GUI组件
    print_log("\n[*] 检查GUI组件...")
    required_files = [
        'main_window.py',
        'src/widgets/jq_to_ptrade_widget.py',
    ]

    for file_path in required_files:
        full_path = os.path.join(project_root, file_path)
        if os.path.exists(full_path):
            print_log(f"  [OK] {file_path}")
        else:
            print_log(f"  [FAIL] {file_path} (不存在)")
            return False

    # 所有检查通过，启动应用
    print_log("\n[OK] 所有检查通过，正在启动应用...\n")
    print_log("=" * 70)
    print_log("")
    
    # 动态导入并启动应用
    try:
        from main_window import main as gui_main
        print_log("启动应用主窗口...")
        gui_main()
    except Exception as e:
        print_log(f"[ERROR] 启动应用失败: {e}")
        import traceback
        print_log(traceback.format_exc())
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
