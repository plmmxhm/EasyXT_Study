#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
周期数据完整性验证器

功能描述：
- 验证周期数据（周线、月线等）的完整性
- 判断当前时间是否处于周期内，数据是否完整
- 提供数据更新建议
- 支持断点续传时的数据完整性检查

版本：v1.0.0
创建时间：2026-04-04
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import pandas as pd


class CycleDataValidator:
    """周期数据完整性验证器
    
    支持的数据类型：
    - 日线 (1d): 当日收盘后数据才完整
    - 分钟线 (1m/5m/15m/30m/60m): 当日16:00后数据才完整
    - 周线 (1w): 周日收盘后数据才完整
    - 月线 (1mon): 月末收盘后数据才完整
    """
    
    def __init__(self):
        """初始化验证器"""
        self.trading_hours = {
            'morning_start': (9, 30),
            'morning_end': (11, 30),
            'afternoon_start': (13, 0),
            'afternoon_end': (15, 0)
        }
        
        # 分钟线数据完整性判断时间（收盘后1小时，确保数据已同步）
        self.minute_data_complete_time = (16, 0)  # 16:00
        
        # 各数据类型的完整性配置
        self.data_type_config = {
            '1d': {'name': '日线', 'complete_after_close': True},
            '1m': {'name': '1分钟线', 'complete_after_close': True, 'complete_time': (16, 0)},
            '5m': {'name': '5分钟线', 'complete_after_close': True, 'complete_time': (16, 0)},
            '15m': {'name': '15分钟线', 'complete_after_close': True, 'complete_time': (16, 0)},
            '30m': {'name': '30分钟线', 'complete_after_close': True, 'complete_time': (16, 0)},
            '60m': {'name': '60分钟线', 'complete_after_close': True, 'complete_time': (16, 0)},
            '1w': {'name': '周线', 'complete_after_close': False},  # 特殊处理
            '1mon': {'name': '月线', 'complete_after_close': False},  # 特殊处理
        }
    
    def is_trading_day(self, date: datetime) -> bool:
        """
        判断是否为交易日（周一到周五）
        
        Args:
            date: 日期
            
        Returns:
            是否为交易日
        """
        return date.weekday() < 5  # 0-4 表示周一到周五
    
    def is_after_market_close(self, dt: datetime) -> bool:
        """
        判断是否在收盘后
        
        Args:
            dt: 日期时间
            
        Returns:
            是否在收盘后
        """
        if not self.is_trading_day(dt):
            return True  # 非交易日视为收盘后
        
        hour, minute = dt.hour, dt.minute
        close_hour, close_minute = self.trading_hours['afternoon_end']
        
        return hour > close_hour or (hour == close_hour and minute >= close_minute)
    
    def get_week_boundaries(self, date: datetime) -> Tuple[datetime, datetime]:
        """
        获取日期所在周的边界（周一到周五）
        
        Args:
            date: 日期
            
        Returns:
            (周一开始, 周五结束)
        """
        weekday = date.weekday()  # 0=周一, 4=周五, 6=周日
        week_start = date - timedelta(days=weekday)
        week_end = week_start + timedelta(days=4)  # 周五
        
        # 设置为当天开始和结束时间
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return week_start, week_end
    
    def get_month_boundaries(self, date: datetime) -> Tuple[datetime, datetime]:
        """
        获取日期所在月的边界（月初到月末）
        
        Args:
            date: 日期
            
        Returns:
            (月初开始, 月末结束)
        """
        # 月初
        month_start = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # 月末：下个月第一天减一秒
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        
        month_end = next_month - timedelta(seconds=1)
        
        return month_start, month_end
    
    def is_week_complete(self, week_end: datetime, current_time: Optional[datetime] = None) -> bool:
        """
        判断周线数据是否完整
        
        条件：
        1. 当前时间已经过了该周的周五收盘时间
        2. 或者该周不是当前周，且数据已经存在
        
        Args:
            week_end: 该周结束时间（周五）
            current_time: 当前时间，默认为现在
            
        Returns:
            数据是否完整
        """
        if current_time is None:
            current_time = datetime.now()
        
        # 如果当前时间已经超过了该周的周五收盘时间，数据完整
        if current_time > week_end:
            return True
        
        # 如果当前时间在该周五，检查是否已收盘
        if current_time.date() == week_end.date():
            return self.is_after_market_close(current_time)
        
        return False
    
    def is_month_complete(self, month_end: datetime, current_time: Optional[datetime] = None) -> bool:
        """
        判断月线数据是否完整
        
        条件：
        1. 当前时间已经过了该月的最后一天收盘时间
        2. 或者该月不是当前月
        
        Args:
            month_end: 该月结束时间
            current_time: 当前时间，默认为现在
            
        Returns:
            数据是否完整
        """
        if current_time is None:
            current_time = datetime.now()
        
        # 如果当前时间已经超过了该月的最后一天收盘时间，数据完整
        if current_time > month_end:
            return True
        
        # 如果当前时间在该月内，检查是否已收盘
        if current_time.date() == month_end.date():
            return self.is_after_market_close(current_time)
        
        return False
    
    def check_weekly_data_integrity(self, data_date: datetime, 
                                   current_time: Optional[datetime] = None) -> Dict:
        """
        检查周线数据完整性
        
        注意：QMT API返回的周线数据日期是周日，但实际周期是周一到周五
        
        Args:
            data_date: 数据日期（可能是周日）
            current_time: 当前时间
            
        Returns:
            完整性检查结果
        """
        if current_time is None:
            current_time = datetime.now()
        
        # 特殊处理：如果数据日期是周日，调整为前一个周五
        if data_date.weekday() == 6:  # 周日
            adjusted_date = data_date - timedelta(days=2)  # 调整到周五
        else:
            adjusted_date = data_date
        
        week_start, week_end = self.get_week_boundaries(adjusted_date)
        is_complete = self.is_week_complete(week_end, current_time)
        
        # 计算数据新鲜度
        if is_complete:
            freshness = "complete"
        elif current_time.date() == week_end.date():
            freshness = "in_progress"
        else:
            freshness = "incomplete"
        
        return {
            'period_type': 'weekly',
            'period_start': week_start,
            'period_end': week_end,
            'data_date': data_date,  # 原始数据日期（可能是周日）
            'adjusted_date': adjusted_date,  # 调整后的实际周期结束日期（周五）
            'is_complete': is_complete,
            'freshness': freshness,
            'should_update': not is_complete,
            'next_update_time': week_end if not is_complete else None
        }
    
    def check_monthly_data_integrity(self, data_date: datetime,
                                    current_time: Optional[datetime] = None) -> Dict:
        """
        检查月线数据完整性
        
        Args:
            data_date: 数据日期
            current_time: 当前时间
            
        Returns:
            完整性检查结果
        """
        if current_time is None:
            current_time = datetime.now()
        
        month_start, month_end = self.get_month_boundaries(data_date)
        is_complete = self.is_month_complete(month_end, current_time)
        
        # 计算数据新鲜度
        if is_complete:
            freshness = "complete"
        elif current_time.date() == month_end.date():
            freshness = "in_progress"
        else:
            freshness = "incomplete"
        
        return {
            'period_type': 'monthly',
            'period_start': month_start,
            'period_end': month_end,
            'is_complete': is_complete,
            'freshness': freshness,
            'should_update': not is_complete,
            'next_update_time': month_end if not is_complete else None
        }
    
    def get_recommended_download_range(self, period: str, 
                                      start_date: str, 
                                      end_date: str,
                                      current_time: Optional[datetime] = None) -> Tuple[str, str]:
        """
        获取推荐的下载日期范围
        
        策略：
        1. 如果结束日期在当前周期内且周期未结束，建议下载到上一周期结束
        2. 如果结束日期在当前周期内且周期已结束，可以下载到当前周期结束
        
        Args:
            period: 周期类型（1w/1mon）
            start_date: 开始日期字符串
            end_date: 结束日期字符串
            current_time: 当前时间
            
        Returns:
            (推荐开始日期, 推荐结束日期)
        """
        if current_time is None:
            current_time = datetime.now()
        
        end_dt = pd.to_datetime(end_date)
        
        if period in ['1w', 'weekly']:
            week_start, week_end = self.get_week_boundaries(end_dt)
            
            # 如果结束日期在当前周内且本周未结束
            if end_dt.date() == week_end.date() or end_dt.date() >= week_start.date():
                if not self.is_week_complete(week_end, current_time):
                    # 建议下载到上周五
                    last_week_end = week_start - timedelta(days=1)
                    return start_date, last_week_end.strftime('%Y-%m-%d')
        
        elif period in ['1mon', 'monthly']:
            month_start, month_end = self.get_month_boundaries(end_dt)
            
            # 如果结束日期在当前月内且本月未结束
            if end_dt.date() == month_end.date() or end_dt.date() >= month_start.date():
                if not self.is_month_complete(month_end, current_time):
                    # 建议下载到上月末
                    last_month_end = month_start - timedelta(days=1)
                    return start_date, last_month_end.strftime('%Y-%m-%d')
        
        return start_date, end_date
    
    def is_daily_data_complete(self, data_date: datetime,
                              current_time: Optional[datetime] = None) -> bool:
        """
        判断日线数据是否完整
        
        条件：
        1. 数据日期不是今天，或者
        2. 数据日期是今天且已收盘
        
        Args:
            data_date: 数据日期
            current_time: 当前时间
            
        Returns:
            数据是否完整
        """
        if current_time is None:
            current_time = datetime.now()
        
        # 如果数据日期不是今天，数据完整
        if data_date.date() < current_time.date():
            return True
        
        # 如果数据日期是今天，检查是否已收盘
        if data_date.date() == current_time.date():
            return self.is_after_market_close(current_time)
        
        # 数据日期是未来，数据不完整
        return False
    
    def is_minute_data_complete(self, data_date: datetime,
                               current_time: Optional[datetime] = None) -> bool:
        """
        判断分钟线数据是否完整
        
        条件：
        1. 数据日期不是今天，或者
        2. 数据日期是今天且已过16:00（收盘后1小时，确保数据同步）
        
        Args:
            data_date: 数据日期
            current_time: 当前时间
            
        Returns:
            数据是否完整
        """
        if current_time is None:
            current_time = datetime.now()
        
        # 如果数据日期不是今天，数据完整
        if data_date.date() < current_time.date():
            return True
        
        # 如果数据日期是今天，检查是否已过16:00
        if data_date.date() == current_time.date():
            complete_hour, complete_minute = self.minute_data_complete_time
            current_hour, current_minute = current_time.hour, current_time.minute
            
            return (current_hour > complete_hour or 
                   (current_hour == complete_hour and current_minute >= complete_minute))
        
        # 数据日期是未来，数据不完整
        return False
    
    def check_daily_data_integrity(self, data_date: datetime,
                                  current_time: Optional[datetime] = None) -> Dict:
        """
        检查日线数据完整性
        
        Args:
            data_date: 数据日期
            current_time: 当前时间
            
        Returns:
            完整性检查结果
        """
        if current_time is None:
            current_time = datetime.now()
        
        is_complete = self.is_daily_data_complete(data_date, current_time)
        
        # 计算数据新鲜度
        if is_complete:
            freshness = "complete"
        elif data_date.date() == current_time.date():
            if self.is_after_market_close(current_time):
                freshness = "complete"
            else:
                freshness = "in_progress"
        else:
            freshness = "incomplete"
        
        return {
            'period_type': 'daily',
            'data_date': data_date,
            'is_complete': is_complete,
            'freshness': freshness,
            'should_update': not is_complete,
            'next_update_time': data_date.replace(hour=15, minute=30) if not is_complete else None
        }
    
    def check_minute_data_integrity(self, data_date: datetime,
                                   period: str = '1m',
                                   current_time: Optional[datetime] = None) -> Dict:
        """
        检查分钟线数据完整性
        
        Args:
            data_date: 数据日期
            period: 分钟线周期
            current_time: 当前时间
            
        Returns:
            完整性检查结果
        """
        if current_time is None:
            current_time = datetime.now()
        
        is_complete = self.is_minute_data_complete(data_date, current_time)
        
        # 计算数据新鲜度
        if is_complete:
            freshness = "complete"
        elif data_date.date() == current_time.date():
            complete_hour, complete_minute = self.minute_data_complete_time
            current_hour, current_minute = current_time.hour, current_time.minute
            
            if (current_hour > complete_hour or 
                (current_hour == complete_hour and current_minute >= complete_minute)):
                freshness = "complete"
            else:
                freshness = "in_progress"
        else:
            freshness = "incomplete"
        
        return {
            'period_type': period,
            'data_date': data_date,
            'is_complete': is_complete,
            'freshness': freshness,
            'should_update': not is_complete,
            'next_update_time': data_date.replace(hour=16, minute=0) if not is_complete else None
        }
    
    def should_refresh_data(self, data_date: datetime, 
                           period: str,
                           current_time: Optional[datetime] = None) -> bool:
        """
        判断是否需要刷新数据
        
        用于断点续传时判断已存在的数据是否需要更新
        
        Args:
            data_date: 数据日期
            period: 周期类型（1d, 1m, 5m, 15m, 30m, 60m, 1w, 1mon）
            current_time: 当前时间
            
        Returns:
            是否需要刷新
        """
        if current_time is None:
            current_time = datetime.now()
        
        # 根据周期类型选择对应的检查方法
        if period == '1d':
            result = self.check_daily_data_integrity(data_date, current_time)
        elif period in ['1m', '5m', '15m', '30m', '60m']:
            result = self.check_minute_data_integrity(data_date, period, current_time)
        elif period in ['1w', 'weekly']:
            # 特殊处理：如果数据日期是周日，调整为前一个周五
            if data_date.weekday() == 6:  # 周日
                adjusted_date = data_date - timedelta(days=2)  # 调整到周五
                result = self.check_weekly_data_integrity(adjusted_date, current_time)
            else:
                result = self.check_weekly_data_integrity(data_date, current_time)
        elif period in ['1mon', 'monthly']:
            result = self.check_monthly_data_integrity(data_date, current_time)
        else:
            # 对于其他类型，默认不需要刷新
            return False
        
        return result['should_update']


# 全局验证器实例
cycle_validator = CycleDataValidator()


def get_cycle_validator() -> CycleDataValidator:
    """获取周期数据验证器实例"""
    return cycle_validator
