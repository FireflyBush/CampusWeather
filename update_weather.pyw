#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深圳天气数据更新脚本（精简版）
- 断网保护：获取失败时保留原有天气数据，仅预警数量置0
- 包含：风速获取与体感温度计算
"""
import requests
import re
import os
import sys
import json
import argparse
import urllib3
import math
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== 配置 ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DEFAULT_OBT_ID = "G3634"
DEFAULT_CITY_ID = "28060159493"

URL_FORECAST = "http://weather.121.com.cn/data_cache/szWeather/sz10day_new.js"
URL_ALARM = "http://weather.121.com.cn/data_cache/szWeather/alarm/szAlarm.js"
WARNING_MAX_AGE_MINUTES = 30

WARNING_LEVEL_PRIORITY = {
    'hongse': 5, 'chengse': 4, 'huangse': 3, 'leidian': 3, 
    'ganhan': 3, 'lanse': 2, 'baise': 1
}

os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'http://weather.sz.gov.cn/',
}
AUTO_STATION_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
    'Accept': 'application/json',
}

# ========== 体感温度计算 ==========
def apparent_temperature(T, RH, v):
    gamma = (17.27 * T) / (237.7 + T) + math.log(RH / 100.0)
    Td = (237.7 * gamma) / (17.27 - gamma)
    vp = 6.11 * math.exp(5417.7530 * (1/273.16 - 1/(Td + 273.16)))
    
    if T >= 24:
        AT = T + 0.33 * vp - 0.7 * v - 4
    elif T <= 14:
        AT = T - 0.50 * vp - 0.80 * v + 3.0
    else:
        AT = T + 0.10 * vp - 0.60 * v - 1.0
    return round(AT, 1)

# ========== 工具函数 ==========
def strip_units(value):
    """从包含单位的字符串中提取纯数字"""
    if not value or value == 'N/A': return 'N/A'
    match = re.search(r"[\d.]+", str(value).strip())
    return match.group() if match else 'N/A'

def extract_observe_time(describe_str):
    if not describe_str: return 'N/A'
    match = re.search(r'(\d{2}:\d{2})', describe_str)
    return match.group(0) if match else 'N/A'

def extract_js_variable(js_content, var_name):
    """直接从JS中提取JSON对象并解析（去除复杂清洗）"""
    if not js_content: return None
    try:
        cdate_match = re.search(r'@cdate:(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', js_content)
        cdate = cdate_match.group(1) if cdate_match else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        pattern = rf'var\s+{var_name}\s*=\s*(\{{.*\}})\s*;'
        match = re.search(pattern, js_content, re.DOTALL)
        if not match: return None
        
        json_str = re.sub(r'/\*.*?\*/', '', match.group(1), flags=re.DOTALL)
        data = json.loads(json_str)
        if isinstance(data, dict):
            data['_cdate'] = cdate
        return data
    except Exception as e:
        print(f" -> 解析JS变量失败: {e}")
        return None

def check_data_freshness(data_time_str):
    try:
        data_time = datetime.strptime(data_time_str, "%Y-%m-%d %H:%M:%S")
        return abs((datetime.now() - data_time).total_seconds()) / 60
    except ValueError:
        return None

def get_warning_type(icon_name):
    if not icon_name: return "unknown"
    icon_lower = icon_name.lower()
    for level in WARNING_LEVEL_PRIORITY.keys():
        if icon_lower.endswith(level):
            return icon_lower[:-len(level)]
    return icon_lower

def deduplicate_alarms(alarms):
    if not alarms: return []
    type_best_alarm = {}
    for alarm in alarms:
        icon = alarm.get('icon', '')
        alarm_type = get_warning_type(icon)
        level = WARNING_LEVEL_PRIORITY.get(icon.split('_')[-1], 0) if icon else 0
        for k, v in WARNING_LEVEL_PRIORITY.items():
            if k in icon: level = v; break
        
        if alarm_type not in type_best_alarm or level > type_best_alarm[alarm_type].get('_level', 0):
            alarm['_level'] = level
            type_best_alarm[alarm_type] = alarm
            
    result = sorted(type_best_alarm.values(), key=lambda x: x['_level'], reverse=True)
    for alarm in result: del alarm['_level']
    return result

# ========== 数据获取 ==========
class AutoStationAPI:
    BASE_URL = "https://szqxapp1.121.com.cn/sztq-app/v6/v7"
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(AUTO_STATION_HEADERS)

    def get_realtime_data(self, obt_id=DEFAULT_OBT_ID, city_id=DEFAULT_CITY_ID):
        try:
            url = f"{self.BASE_URL}/meteorologicalObt/topics"
            response = self.session.get(url, params={"obtId": obt_id, "cityId": city_id}, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == 200:
                result = data.get("result", {})
                temp_str = strip_units(result.get("t"))
                hum_str = strip_units(result.get("rh"))
                wind_str = strip_units(result.get("ws"))
                
                apparent_temp = 'N/A'
                try:
                    if 'N/A' not in [temp_str, hum_str, wind_str]:
                        apparent_temp = str(apparent_temperature(float(temp_str), float(hum_str), float(wind_str)))
                except: pass
                
                return {
                    "t": temp_str, "u": hum_str, "ws": wind_str,
                    "apparentTemp": apparent_temp,
                    "obtName": result.get("obtName", "未知"),
                    "observeTime": extract_observe_time(result.get("describe", "")),
                    "_success": True
                }
            return {"_success": False}
        except Exception as e:
            print(f" -> 实时数据请求失败: {e}")
            return {"_success": False}

class WeatherDataFetcher:
    @staticmethod
    def get_forecast_data():
        try:
            response = requests.get(URL_FORECAST, timeout=10, headers=HEADERS, verify=False)
            response.encoding = 'utf-8'
            data = extract_js_variable(response.text, "SZ121_10dayWeather")
            if data: data["_success"] = True
            return data or {"_success": False}
        except Exception as e:
            print(f" -> 预报请求失败: {e}")
            return {"_success": False}

    @staticmethod
    def get_alarm_data():
        try:
            response = requests.get(URL_ALARM, timeout=10, headers=HEADERS, verify=False)
            response.encoding = 'utf-8'
            text = response.text
            return text if text and 'SZ121_AlarmInfo' in text else None
        except Exception as e:
            print(f" -> 预警请求失败: {e}")
            return None

def parse_alarm_data(js_content):
    data = extract_js_variable(js_content, "SZ121_AlarmInfo")
    if not data: return None
    
    update_time = data.pop('_cdate', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    time_diff = check_data_freshness(update_time)
    is_fresh = time_diff is not None and time_diff <= WARNING_MAX_AGE_MINUTES
    
    if not is_fresh:
        return {'update_time': update_time, 'count': 0, 'alarms': [], 'expired': True, '_success': True}
    
    deduped = deduplicate_alarms(data.get("subAlarm", []))
    return {'update_time': update_time, 'count': len(deduped), 'alarms': deduped[:6], 'expired': False, 'raw_count': len(data.get("subAlarm", [])), '_success': True}

# ========== 文件读写 ==========
def read_existing_vars():
    vars_path = os.path.join(DATA_DIR, 'weather_vars.inc')
    existing_data = {}
    if not os.path.exists(vars_path): return existing_data
    try:
        with open(vars_path, 'r', encoding='gbk') as f:
            for line in f.read().split('\n'):
                line = line.strip()
                if line and not line.startswith((';', '[')) and '=' in line:
                    k, v = line.split('=', 1)
                    existing_data[k.strip()] = v.strip()
        return existing_data
    except: return {}

def generate_vars_file(forecast_data, realtime_data, alarm_data, existing_data):
    forecast_success = forecast_data and forecast_data.pop('_success', False)
    realtime_success = realtime_data and realtime_data.pop('_success', False)
    alarm_success = alarm_data and alarm_data.pop('_success', False)

    # 断网保护逻辑
    if not forecast_success and existing_data:
        print(" -> [保护] 预报数据获取失败，保留原有数据")
        forecast_data = {'pubDate': existing_data.get('PublishTime', 'N/A'), 'today': {'icon': existing_data.get('TodayIcon', '02'), 'minT': existing_data.get('TodayMin', 'N/A'), 'maxT': existing_data.get('TodayMax', 'N/A'), 'report': existing_data.get('TodayDesc', 'N/A')}, 'day10': [[existing_data.get(f'Day{i}Date', 'N/A'), existing_data.get(f'Day{i}Desc', 'N/A'), existing_data.get(f'Day{i}Max', 'N/A'), existing_data.get(f'Day{i}Min', 'N/A'), existing_data.get(f'Day{i}Icon', '02')] for i in range(1, 4)]}
    if not realtime_success and existing_data:
        print(" -> [保护] 实时数据获取失败，保留原有数据")
        realtime_data = {'t': existing_data.get('RealtimeTemp', 'N/A'), 'u': existing_data.get('RealtimeHum', 'N/A'), 'ws': existing_data.get('RealtimeWindSpeed', 'N/A'), 'apparentTemp': existing_data.get('RealtimeApparentTemp', 'N/A'), 'obtName': existing_data.get('obtName', '未知'), 'observeTime': existing_data.get('ObserveTime', 'N/A')}
    if not alarm_success or (alarm_data and alarm_data.get('expired', False)):
        print(" -> [保护] 预警数据获取失败或过期，数量置0")
        alarm_data = {'update_time': 'N/A', 'count': 0, 'alarms': []}

    try:
        today = forecast_data.get('today', {})
        day10 = forecast_data.get('day10', [])
        
        # 新增 is_int 参数处理取整需求
        def safe_get(d, k, default='N/A', is_num=False, is_int=False):
            v = d.get(k, default) if isinstance(d, dict) else default
            if is_num and v not in [None, 'N/A']:
                try: 
                    return str(int(float(v))) if is_int else str(round(float(v), 1))
                except: pass
            return str(v).replace('\n', ' ').strip() if v else 'N/A'

        def safe_list(lst, idx, k_idx, is_int=False):
            if isinstance(lst, list) and len(lst) > idx and isinstance(lst[idx], list) and len(lst[idx]) > k_idx:
                v = str(lst[idx][k_idx]).strip()
                if is_int:
                    try: return str(int(float(v)))
                    except: pass
                return v
            return 'N/A'

        raw_desc = today.get('report', 'N/A')
        cleaned_desc = re.sub(r'气温[^；]*；', '', raw_desc).replace('；。', '。').strip('；')
        
        def convert_weekday(s):
            return re.sub(r'星期([一二三四五六日])', r'周\1', s) if s and s != 'N/A' else s

        lines = [
            "[Variables]",
            f"; 天气数据 - 站点:{realtime_data.get('obtName', 'N/A')}",
            f"; 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"PublishTime={safe_get(forecast_data, 'pubDate')}",
            f"ObserveTime={realtime_data.get('observeTime', 'N/A')}",
            f"RealtimeTemp={safe_get(realtime_data, 't', is_num=True)}",
            f"RealtimeHum={safe_get(realtime_data, 'u', is_num=True, is_int=True)}",
            f"RealtimeWindSpeed={safe_get(realtime_data, 'ws', is_num=True)}",
            f"RealtimeApparentTemp={safe_get(realtime_data, 'apparentTemp', is_num=True)}",
            f"TodayIcon={safe_get(today, 'icon', '02')}",
            f"TodayMin={safe_get(today, 'minT', is_num=True, is_int=True)}",  # 强制取整
            f"TodayMax={safe_get(today, 'maxT', is_num=True, is_int=True)}",  # 强制取整
            f"TodayDesc={cleaned_desc}",
            f"Day1Date={convert_weekday(safe_list(day10, 0, 0))}",
            f"Day1Icon={safe_list(day10, 0, 4) or '02'}",
            f"Day1Min={safe_list(day10, 0, 3, is_int=True)}",
            f"Day1Max={safe_list(day10, 0, 2, is_int=True)}",
            f"Day1Desc={safe_list(day10, 0, 1)}",
            f"Day2Date={convert_weekday(safe_list(day10, 1, 0))}",
            f"Day2Icon={safe_list(day10, 1, 4) or '02'}",
            f"Day2Min={safe_list(day10, 1, 3, is_int=True)}",
            f"Day2Max={safe_list(day10, 1, 2, is_int=True)}",
            f"Day2Desc={safe_list(day10, 1, 1)}",
            f"Day3Date={convert_weekday(safe_list(day10, 2, 0))}",
            f"Day3Icon={safe_list(day10, 2, 4) or '02'}",
            f"Day3Min={safe_list(day10, 2, 3, is_int=True)}",
            f"Day3Max={safe_list(day10, 2, 2, is_int=True)}",
            f"Day3Desc={safe_list(day10, 2, 1)}",
            "",
            "; 预警数据",
            f"WarningUpdateTime={alarm_data.get('update_time', 'N/A')}",
            f"WarningCount={alarm_data.get('count', 0)}",
        ]

        if alarm_data and alarm_data.get('count', 0) > 0:
            for i, alarm in enumerate(alarm_data.get('alarms', []), 1):
                lines.append(f"WarningIcon{i}={alarm.get('icon', '')}")
                lines.append(f"WarningInfo{i}={alarm.get('str', '').replace(chr(10), ' ').strip()}")

        with open(os.path.join(DATA_DIR, 'weather_vars.inc'), 'w', encoding='gbk') as f:
            f.write('\n'.join(lines) + '\n')
        print(f"[OK] 变量文件已生成")
        return True
    except Exception as e:
        print(f"[FAIL] 生成失败: {e}")
        return False

# ========== 主函数 ==========
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--station', '-s', default=DEFAULT_OBT_ID)
    args = parser.parse_args()

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 更新天气数据...")
    existing_data = read_existing_vars()
    fetcher = WeatherDataFetcher()
    
    forecast = fetcher.get_forecast_data()
    realtime = AutoStationAPI().get_realtime_data(args.station)
    
    alarm_js = fetcher.get_alarm_data()
    alarm = parse_alarm_data(alarm_js) if alarm_js else None
    if alarm and not alarm.get('_success'): alarm = None

    success = generate_vars_file(forecast, realtime, alarm, existing_data)
    if success:
        status = lambda x: "缓存" if not x or not x.get('_success') else "最新"
        print(f" 预报: {status(forecast)} | 实时: {status(realtime)} | 预警: {alarm.get('count',0) if alarm else 0}条")
    return success

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
