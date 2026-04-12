#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局配置管理器 - 统一管理应用配置（2026-04-12）

功能：
1. 提供统一的配置读取/写入接口
2. 支持配置持久化到 YAML 文件
3. 支持运行时配置修改和保存
4. 提供其他模块可调用的通用方法

使用示例：
    from src.core.utils.config_manager import get_config_manager
    
    config_mgr = get_config_manager()
    
    # 读取查询方式偏好
    query_mode = config_mgr.get_query_preference()
    
    # 读取缓存设置
    cache_enabled, cache_size = config_mgr.get_cache_settings()
    
    # 保存用户偏好
    config_mgr.save_user_preference('query_mode', 'table')
"""

import os
import sys
import yaml
from pathlib import Path
from typing import Any, Optional, Dict, Tuple
from datetime import datetime

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CONFIG_FILE = PROJECT_ROOT / 'config' / 'data_config.yaml'


class GlobalConfigManager:
    """全局配置管理器 - 单例模式"""
    
    _instance = None
    _config = {}
    _config_file = CONFIG_FILE
    _last_modified = None
    
    def __new__(cls):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._load_config()
        
        print(f"✅ 全局配置管理器初始化完成")
        print(f"   📁 配置文件: {self._config_file}")
    
    def _load_config(self):
        """加载配置文件"""
        try:
            if self._config_file.exists():
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f) or {}
                
                self._last_modified = datetime.fromtimestamp(
                    self._config_file.stat().st_mtime
                )
                print(f"   ✅ 配置加载成功")
            else:
                print(f"   ⚠️ 配置文件不存在: {self._config_file}")
                self._config = {}
                
        except Exception as e:
            print(f"   ❌ 配置加载失败: {e}")
            self._config = {}
    
    def reload(self):
        """重新加载配置文件（当外部修改后调用）"""
        self._load_config()
    
    def save(self):
        """保存当前配置到文件"""
        try:
            with open(self._config_file, 'w', encoding='utf-8') as f:
                yaml.dump(
                    self._config, 
                    f, 
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False
                )
            
            self._last_modified = datetime.now()
            print(f"✅ 配置已保存到: {self._config_file}")
            return True
            
        except Exception as e:
            print(f"❌ 保存配置失败: {e}")
            return False
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值（支持点号路径）
        
        Args:
            key_path: 配置键路径，如 'storage.data_source.mode'
            default: 默认值
            
        Returns:
            配置值
            
        示例:
            mode = config_mgr.get('storage.data_source.mode', 'parquet')
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any, auto_save: bool = True):
        """
        设置配置值（支持点号路径）
        
        Args:
            key_path: 配置键路径
            value: 要设置的值
            auto_save: 是否自动保存到文件
        """
        keys = key_path.split('.')
        target = self._config
        
        # 导航到目标位置
        for key in keys[:-1]:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            target = target[key]
        
        # 设置值
        target[keys[-1]] = value
        
        print(f"📝 配置已更新: {key_path} = {value}")
        
        if auto_save:
            self.save()
    
    # ==================== 用户偏好设置接口 ====================
    
    def get_query_preference(self) -> str:
        """
        获取查询方式偏好
        
        Returns:
            'view' | 'table' | 'auto'
        """
        preference = self.get('user_preference.query_mode', 'auto')
        
        # 验证有效性
        valid_modes = ['view', 'table', 'auto']
        if preference not in valid_modes:
            preference = 'auto'
        
        return preference
    
    def set_query_preference(self, mode: str, auto_save: bool = True):
        """
        设置查询方式偏好
        
        Args:
            mode: 'view'(视图查询) | 'table'(物理表查询) | 'auto'(自动)
        """
        valid_modes = ['view', 'table', 'auto']
        if mode not in valid_modes:
            raise ValueError(f"无效的查询模式: {mode}，有效值: {valid_modes}")
        
        self.set('user_preference.query_mode', mode, auto_save)
    
    def get_cache_settings(self) -> Tuple[bool, int, bool]:
        """
        获取缓存设置
        
        Returns:
            (是否启用, 最大条目数, 性能测试时强制关闭)
        """
        enabled = self.get('user_preference.cache.enabled', True)
        max_size = self.get('user_preference.cache.max_size', 50)
        force_disable_on_test = self.get('user_preference.cache.force_disable_on_test', True)
        
        return (enabled, max_size, force_disable_on_test)
    
    def set_cache_settings(self, enabled: bool = True, max_size: int = 50, 
                          force_disable_on_test: bool = True, auto_save: bool = True):
        """
        设置缓存配置
        
        Args:
            enabled: 是否启用缓存
            max_size: 最大缓存条目数
            force_disable_on_test: 性能测试时是否强制关闭缓存
        """
        # 确保 user_preference.cache 存在
        if 'user_preference' not in self._config:
            self._config['user_preference'] = {}
        if 'cache' not in self._config['user_preference']:
            self._config['user_preference']['cache'] = {}
        
        self._config['user_preference']['cache']['enabled'] = enabled
        self._config['user_preference']['cache']['max_size'] = max_size
        self._config['user_preference']['cache']['force_disable_on_test'] = force_disable_on_test
        
        print(f"💾 缓存配置更新: enabled={enabled}, max_size={max_size}, force_disable={force_disable_on_test}")
        
        if auto_save:
            self.save()
    
    def get_storage_mode(self) -> str:
        """
        获取存储模式
        
        Returns:
            'parquet' | 'database' | 'dual'
        """
        return self.get('storage.data_source.mode', 'parquet')
    
    def get_database_paths(self) -> Tuple[Optional[str], Optional[str]]:
        """
        获取数据库路径
        
        Returns:
            (数据表库路径, 视图库路径)
        """
        root_dir = self.get('data_paths.root_dir', 'D:/MyStockData')
        
        data_db = None
        view_db = None
        
        db_config = self.get('database', {})
        if 'data_db' in db_config and 'dbfile' in db_config['data_db']:
            data_db = str(Path(root_dir) / db_config['data_db']['dbfile'])
        
        if 'view_db' in db_config and 'dbfile' in db_config['view_db']:
            view_db = str(Path(root_dir) / db_config['view_db']['dbfile'])
        
        return (data_db, view_db)
    
    def is_dual_database_architecture(self) -> bool:
        """检查是否为双数据库架构"""
        db_config = self.get('database', {})
        return ('data_db' in db_config and 'view_db' in db_config)
    
    def get_available_data_types(self) -> list:
        """
        获取可用的数据类型列表（根据实际配置动态生成）
        
        Returns:
            数据类型列表，如 ['1d', '1m', '5m', ..., 'weekly', 'monthly']
        """
        types = []
        
        # 从 parquet.structure 获取
        structure = self.get('parquet.structure.kline', {})
        if structure:
            types.extend(structure.keys())
        
        # 添加 tick
        types.append('tick')
        
        return types
    
    def get_performance_test_config(self) -> Dict:
        """
        获取性能测试配置
        
        Returns:
            包含测试参数的字典
        """
        return {
            'default_stock_count': self.get('test.daily_stock_count', 10),
            'default_types': ['1d', '1m', '5m'],  # 默认测试的数据类型
            'output_dir': PROJECT_ROOT / 'logs' / 'performance_reports',
            'report_format': 'txt',
            'include_cache_comparison': True  # 是否包含缓存对比测试
        }
    
    # ==================== 配置变更通知系统 ====================
    
    def register_callback(self, key_path: str, callback):
        """
        注册配置变更回调函数（预留接口）
        
        Args:
            key_path: 要监听的配置键
            callback: 回调函数 callback(old_value, new_value)
        """
        # TODO: 实现观察者模式
        pass


# ==================== 全局单例访问点 ====================

_config_manager_instance = None


def get_config_manager() -> GlobalConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager_instance
    
    if _config_manager_instance is None:
        _config_manager_instance = GlobalConfigManager()
    
    return _config_manager_instance


def reload_config():
    """重新加载配置文件"""
    mgr = get_config_manager()
    mgr.reload()


def get_query_mode() -> str:
    """快捷方法：获取查询方式偏好"""
    return get_config_manager().get_query_preference()


def get_cache_config() -> Tuple[bool, int]:
    """快捷方法：获取缓存配置 (enabled, max_size)"""
    enabled, max_size, _ = get_config_manager().get_cache_settings()
    return (enabled, max_size)


def is_cache_enabled() -> bool:
    """快捷方法：检查缓存是否启用"""
    enabled, _, _ = get_config_manager().get_cache_settings()
    return enabled


if __name__ == '__main__':
    # 测试代码
    print("=" * 60)
    print("🧪 全局配置管理器测试")
    print("=" * 60)
    
    mgr = get_config_manager()
    
    # 测试基本功能
    print(f"\n📊 存储模式: {mgr.get_storage_mode()}")
    print(f"🔍 查询偏好: {mgr.get_query_preference()}")
    print(f"💾 缓存设置: {mgr.get_cache_settings()}")
    print(f"🗂️ 数据库路径: {mgr.get_database_paths()}")
    print(f"🔗 双库架构: {mgr.is_dual_database_architecture()}")
    print(f"📈 可用数据类型: {mgr.get_available_data_types()}")
    
    # 测试配置修改
    print("\n📝 测试配置修改...")
    mgr.set_query_preference('table')
    print(f"   修改后查询偏好: {mgr.get_query_preference()}")
    
    # 恢复默认
    mgr.set_query_preference('auto')
    
    print("\n✅ 测试完成！")
