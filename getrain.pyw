#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深圳未来2小时降雨预报获取脚本
- 每4分钟一个数据点，共30个点（120分钟）
- 输出：雨量值 + 柱形高度（0-40px）+ 关键时间点
"""

import requests
import os
import sys
import json
from datetime import datetime, timedelta

# ========== 配置 ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
#RAIN_API_URL = "http://127.0.0.1/raintest.json"
# 本地调试（保留）
RAIN_API_URL = "https://wx.121.com.cn/Mobile/LdService/position"

DEFAULT_PARAMS = {
    "latitude": "22.552188",
    "longitude": "114.025106",
    "sign": "1e86faea84f8574f155c9e485ed4710e"
}
MAX_BAR_HEIGHT = 90      # 像素高度
MAX_RAIN_VALUE = 40     # 满格阈值（mm/hr）

os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
    'Accept': 'application/json',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}


def calc_height(rain_mm):
    """计算柱形高度：线性映射 0-40 → 0-90px，超过40按90px"""
    if rain_mm <= 0:
        return 0
    if rain_mm >= MAX_RAIN_VALUE:
        return MAX_BAR_HEIGHT
    return round((rain_mm / MAX_RAIN_VALUE) * MAX_BAR_HEIGHT)


def parse_rain(rain_str):
    """解析逗号分隔的降雨数据为浮点数列表"""
    if not rain_str:
        return [0.0] * 30
    try:
        values = [float(x) if x else 0.0 for x in rain_str.split(',')]
        return (values + [0.0] * 30)[:30]
    except:
        return [0.0] * 30


def get_times(start_str):
    """生成30个时间点（每4分钟）和4个关键时间点"""
    try:
        dt = datetime.strptime(start_str, "%Y/%m/%d %H:%M:%S")
    except:
        dt = datetime.now()
    
    # 30个详细时间点
    detail_times = [(dt + timedelta(minutes=i * 4)).strftime("%H:%M") for i in range(30)]
    
    # 4个关键时间点：+30分, +1小时, +1.5小时, +2小时
    key_times = {
        '30min': (dt + timedelta(minutes=30)).strftime("%H:%M"),
        '1h': (dt + timedelta(hours=1)).strftime("%H:%M"),
        '1h30': (dt + timedelta(minutes=90)).strftime("%H:%M"),
        '2h': (dt + timedelta(hours=2)).strftime("%H:%M"),
    }
    
    return detail_times, key_times


def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 更新降雨预报...")
    
    try:
        # 获取数据
        response = requests.get(RAIN_API_URL, params=DEFAULT_PARAMS, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        rain_values = parse_rain(data.get('rain', ''))
        detail_times, key_times = get_times(data.get('dataTimeFormat', ''))
        has_rain = any(r > 0 for r in rain_values)
        
        # 生成变量文件
        lines = [
            "[Variables]",
            f"RainHasRain={1 if has_rain else 0}",
            f"RainStartTime={detail_times[0]}",
            f"RainDesc={data.get('wlrain', '无降雨预报')}",
            "",
            "; 时间轴关键节点",
            f"RainTime30min={key_times['30min']}",
            f"RainTime1h={key_times['1h']}",
            f"RainTime1h30={key_times['1h30']}",
            f"RainTime2h={key_times['2h']}",
        ]
        
        # 30个数据点：雨量 + 高度
        for i, (t, rv) in enumerate(zip(detail_times, rain_values), 1):
            h = calc_height(rv)
            lines.append(f"Rain{i:02d}={rv}")
            lines.append(f"RainH{i:02d}={h}")
        
        # 写入
        with open(os.path.join(DATA_DIR, 'rain.inc'), 'w', encoding='gbk') as f:
            f.write('\n'.join(lines) + '\n')
        
        max_r = max(rain_values)
        print(f"  OK 最大雨量:{max_r}mm 柱高:{calc_height(max_r)}px")
        print(f"     时间轴: {key_times['30min']} | {key_times['1h']} | {key_times['1h30']} | {key_times['2h']}")
        return True
        
    except Exception as e:
        print(f"  FAIL {e}")
        # 生成空数据
        lines = [
            "[Variables]",
            "RainHasRain=0",
            "RainStartTime=--:--",
            "RainDesc=获取失败",
            "RainTime30min=--:--",
            "RainTime1h=--:--",
            "RainTime1h30=--:--",
            "RainTime2h=--:--",
        ]
        for i in range(1, 31):
            lines.extend([f"Rain{i:02d}=0", f"RainH{i:02d}=0"])
        with open(os.path.join(DATA_DIR, 'rain.inc'), 'w', encoding='gbk') as f:
            f.write('\n'.join(lines) + '\n')
        return False


if __name__ == '__main__':
    sys.exit(0 if main() else 1)