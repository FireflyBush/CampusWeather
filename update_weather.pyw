#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深圳天气数据更新脚本（整合版）
- 断网保护：获取失败时保留原有天气数据，仅预警数量置0
- 新增：风速获取与体感温度计算
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
#URL_ALARM = "http://127.0.0.1/szAlarmWinter.js"

WARNING_MAX_AGE_MINUTES = 30

WARNING_LEVEL_PRIORITY = {
    'hongse': 5, 'chengse': 4, 'huangse': 3, 'leidian': 3, 'ganhan': 3, 'lanse': 2, 'baise': 1,
}

os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'http://weather.sz.gov.cn/',
}

AUTO_STATION_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
    'Accept': 'application/json',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}


# ========== 体感温度计算 ==========

def apparent_temperature(T, RH, v):
    """
    分段表观温度（优化版 Steadman，低温斜率更大、湿冷效应更强）
    T: 气温 (℃)
    RH: 相对湿度 (%)
    v: 风速 (m/s)
    返回: 体感温度 AT (℃)
    """
    # ===================== 水汽压计算（和截图公式完全一致）=====================
    gamma = (17.27 * T) / (237.7 + T) + math.log(RH / 100.0)
    Td = (237.7 * gamma) / (17.27 - gamma)
    vp = 6.11 * math.exp(5417.7530 * (1/273.16 - 1/(Td + 273.16)))

    # ===================== 新分段公式（低温斜率大 + 湿度反转）=====================
    if T >= 24:
        # 高温区：和截图原版一致
        AT = T + 0.33 * vp - 0.7 * v - 4
    elif T <= 14:
        # 低温湿冷区：斜率大幅增强 + 湿度反转
        AT = T - 0.50 * vp - 0.80 * v + 3.0
    else:
        # 过渡区：平滑衔接
        AT = T + 0.10 * vp - 0.60 * v - 1.0

    return round(AT, 1)


# ========== 工具函数 ==========

def strip_units(value, extract_wind=False):
    """
    去除单位，返回数值字符串
    extract_wind=True: 从风速字符串如"1.2m/s(1级)"提取数值
    """
    if value is None or value == 'N/A':
        return 'N/A'
    value_str = str(value).strip()
    
    # 特殊处理：提取风速数值（如 "1.2m/s(1级)" -> "1.2"）
    if extract_wind:
        match = re.search(r"[\d.]+", value_str)
        if match:
            return match.group()
        return 'N/A'
    
    # 常规处理：移除单位
    for unit in ['℃', '°C', '°c', '°', '%', '％', 'mm', 'hPa', 'km', 'm/s', 'Pa']:
        value_str = value_str.replace(unit, '')
    return value_str.strip()


def remove_temperature_desc(desc):
    if not desc or desc == 'N/A':
        return desc
    cleaned = re.sub(r'气温[^；]*；', '', desc)
    cleaned = re.sub(r'；+', '；', cleaned)
    cleaned = cleaned.replace('；。', '。')
    return cleaned.strip('；')


def convert_weekday(date_str):
    if not date_str or date_str == 'N/A':
        return date_str
    return re.sub(r'星期([一二三四五六日])', r'周\1', date_str)


def extract_observe_time(describe_str):
    if not describe_str:
        return 'N/A'
    match = re.search(r'(\d{2}:\d{2})', describe_str)
    return match.group(0) if match else 'N/A'


def extract_cdate_from_js(js_content):
    match = re.search(r'/\*@cdate:(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', js_content)
    if match:
        return match.group(1)
    match = re.search(r'/\*@cdate:(\d{4}-\d{2}-\d{2})', js_content)
    if match:
        return f"{match.group(1)} {datetime.now().strftime('%H:%M:%S')}"
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_json_string(js_str):
    try:
        js_str = re.sub(r'/\*.*?\*/', '', js_str, flags=re.DOTALL)
        js_str = re.sub(r'try\{\s*', '', js_str)
        js_str = re.sub(r'\s*\}catch\(e\)\{\s*\}', '', js_str)
        js_str = js_str.strip().strip(';').lstrip('\ufeff')
        js_str = re.sub(r"(?<!\\)'", '"', js_str)
        js_str = js_str.replace('\\x', '\\\\x')
        js_str = re.sub(r',\s*}', '}', js_str)
        js_str = re.sub(r',\s*]', ']', js_str)
        js_str = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', js_str)
        return js_str
    except Exception:
        return None


def extract_js_variable(js_content, var_name):
    try:
        cdate = extract_cdate_from_js(js_content)
        pattern = rf'var\s+{var_name}\s*=\s*(\{{.*?\}})\s*;'
        match = re.search(pattern, js_content, re.DOTALL)
        if not match:
            return None
        json_str = match.group(1)
        cleaned = clean_json_string(json_str)
        if not cleaned:
            return None
        data = json.loads(cleaned)
        if isinstance(data, dict):
            data['_cdate'] = cdate
        return data
    except Exception:
        return None


def check_data_freshness(data_time_str):
    try:
        data_time = datetime.strptime(data_time_str, "%Y-%m-%d %H:%M:%S")
        local_time = datetime.now()
        diff = abs(local_time - data_time)
        return diff.total_seconds() / 60
    except ValueError:
        return None


def extract_warning_level(icon_name):
    if not icon_name:
        return 0
    icon_lower = icon_name.lower()
    for level, priority in sorted(WARNING_LEVEL_PRIORITY.items(), key=lambda x: x[1], reverse=True):
        if level in icon_lower:
            return priority
    return 0


def get_warning_type(icon_name):
    if not icon_name:
        return "unknown"
    icon_lower = icon_name.lower()
    for level in WARNING_LEVEL_PRIORITY.keys():
        if icon_lower.endswith(level):
            return icon_lower[:-len(level)]
    return icon_lower


def deduplicate_alarms(alarms):
    if not alarms:
        return []
    type_best_alarm = {}
    for alarm in alarms:
        icon = alarm.get('icon', '')
        alarm_type = get_warning_type(icon)
        level = extract_warning_level(icon)
        if alarm_type in type_best_alarm:
            existing_level = type_best_alarm[alarm_type]['_level']
            if level > existing_level:
                alarm['_level'] = level
                type_best_alarm[alarm_type] = alarm
            else:
                pass
        else:
            alarm['_level'] = level
            type_best_alarm[alarm_type] = alarm
    result = list(type_best_alarm.values())
    result.sort(key=lambda x: x['_level'], reverse=True)
    for alarm in result:
        if '_level' in alarm:
            del alarm['_level']
    return result


# ========== 数据类 ==========

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
                raw_desc = result.get("describe", "")
                
                # 获取基础数据
                temp_str = strip_units(result.get("t"))
                hum_str = strip_units(result.get("rh"))
                wind_str = strip_units(result.get("ws"), extract_wind=True)
                
                # 计算体感温度
                apparent_temp = 'N/A'
                try:
                    if temp_str != 'N/A' and hum_str != 'N/A' and wind_str != 'N/A':
                        T = float(temp_str)
                        RH = float(hum_str)
                        v = float(wind_str)
                        apparent_temp = str(apparent_temperature(T, RH, v))
                except Exception as calc_err:
                    print(f"  -> 体感温度计算失败: {calc_err}")
                
                return {
                    "t": temp_str,
                    "u": hum_str,
                    "ws": wind_str,
                    "apparentTemp": apparent_temp,
                    "obtName": result.get("obtName", "未知"),
                    "observeTime": extract_observe_time(raw_desc),
                    "raw_t": result.get("t"),
                    "raw_u": result.get("rh"),
                    "raw_ws": result.get("ws"),
                    "_success": True
                }
            return {"_success": False}
        except Exception as e:
            print(f"  -> 实时数据请求失败: {e}")
            return {"_success": False}


class WeatherDataFetcher:
    @staticmethod
    def get_forecast_data():
        try:
            response = requests.get(URL_FORECAST, timeout=10, headers=HEADERS, verify=False)
            response.encoding = 'utf-8'
            data = extract_js_variable(response.text, "SZ121_10dayWeather")
            if data:
                data["_success"] = True
                return data
            return {"_success": False}
        except Exception as e:
            print(f"  -> 预报请求失败: {e}")
            return {"_success": False}
    
    @staticmethod
    def get_alarm_data():
        try:
            response = requests.get(URL_ALARM, timeout=10, headers=HEADERS, verify=False)
            response.encoding = 'utf-8'
            text = response.text
            if not text or len(text) < 100 or 'SZ121_AlarmInfo' not in text:
                return None
            return text
        except Exception as e:
            print(f"  -> 预警请求失败: {e}")
            return None


# ========== 预警解析 ==========

def parse_alarm_data(js_content):
    if not js_content:
        return None
    data = extract_js_variable(js_content, "SZ121_AlarmInfo")
    if not data:
        return None
    update_time = data.pop('_cdate', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    time_diff = check_data_freshness(update_time)
    is_fresh = time_diff is not None and time_diff <= WARNING_MAX_AGE_MINUTES
    if not is_fresh:
        return {
            'update_time': update_time,
            'count': 0,
            'alarms': [],
            'expired': True,
            'time_diff': time_diff,
            '_success': True
        }
    raw_alarms = data.get("subAlarm", [])
    deduped = deduplicate_alarms(raw_alarms)
    return {
        'update_time': update_time,
        'count': len(deduped),
        'alarms': deduped[:6],
        'expired': False,
        'time_diff': time_diff,
        'raw_count': len(raw_alarms),
        '_success': True
    }


# ========== 文件读写 ==========

def read_existing_vars():
    """读取现有的weather_vars.inc文件，返回解析后的字典"""
    vars_path = os.path.join(DATA_DIR, 'weather_vars.inc')
    existing_data = {}
    
    if not os.path.exists(vars_path):
        return existing_data
    
    try:
        with open(vars_path, 'r', encoding='gbk') as f:
            content = f.read()
        
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith(';') and not line.startswith('['):
                if '=' in line:
                    key, value = line.split('=', 1)
                    existing_data[key.strip()] = value.strip()
        
        print(f"  -> 已读取现有数据: {len(existing_data)}个变量")
        return existing_data
    except Exception as e:
        print(f"  -> 读取现有文件失败: {e}")
        return {}


def generate_vars_file(forecast_data, realtime_data, alarm_data, existing_data=None):
    """生成变量文件，支持断网保护"""
    
    if existing_data is None:
        existing_data = {}
    
    forecast_success = forecast_data and forecast_data.pop('_success', False)
    realtime_success = realtime_data and realtime_data.pop('_success', False)
    alarm_success = alarm_data and alarm_data.pop('_success', False)
    
    if not forecast_success and existing_data:
        print(f"  -> [保护] 预报数据获取失败，保留原有数据")
        forecast_data = {
            'pubDate': existing_data.get('PublishTime', 'N/A'),
            'today': {
                'icon': existing_data.get('TodayIcon', '02'),
                'minT': existing_data.get('TodayMin', 'N/A'),
                'maxT': existing_data.get('TodayMax', 'N/A'),
                'report': existing_data.get('TodayDesc', 'N/A'),
            },
            'day10': [
                [existing_data.get('Day1Date', 'N/A'), existing_data.get('Day1Desc', 'N/A'),
                 existing_data.get('Day1Max', 'N/A'), existing_data.get('Day1Min', 'N/A'),
                 existing_data.get('Day1Icon', '02')],
                [existing_data.get('Day2Date', 'N/A'), existing_data.get('Day2Desc', 'N/A'),
                 existing_data.get('Day2Max', 'N/A'), existing_data.get('Day2Min', 'N/A'),
                 existing_data.get('Day2Icon', '02')],
                [existing_data.get('Day3Date', 'N/A'), existing_data.get('Day3Desc', 'N/A'),
                 existing_data.get('Day3Max', 'N/A'), existing_data.get('Day3Min', 'N/A'),
                 existing_data.get('Day3Icon', '02')],
            ]
        }
    
    if not realtime_success and existing_data:
        print(f"  -> [保护] 实时数据获取失败，保留原有数据")
        realtime_data = {
            't': existing_data.get('RealtimeTemp', 'N/A'),
            'u': existing_data.get('RealtimeHum', 'N/A'),
            'ws': existing_data.get('RealtimeWindSpeed', 'N/A'),
            'apparentTemp': existing_data.get('RealtimeApparentTemp', 'N/A'),
            'obtName': existing_data.get('obtName', '未知'),
            'observeTime': existing_data.get('ObserveTime', 'N/A'),
        }
    
    if not alarm_success:
        print(f"  -> [保护] 预警数据获取失败，数量置0")
        alarm_data = {
            'update_time': existing_data.get('WarningUpdateTime', 'N/A') + ' (数据获取失败)',
            'count': 0,
            'alarms': [],
            'expired': False,
        }
    elif alarm_data.get('expired', False):
        print(f"  -> [保护] 预警数据过期，数量置0")
    
    try:
        today = forecast_data.get('today', {})
        day10 = forecast_data.get('day10', [])
        
        def safe_get(data, key, default='N/A'):
            value = data.get(key, default) if isinstance(data, dict) else default
            if key in ['minT', 'maxT', 't', 'u', 'ws', 'apparentTemp'] and value not in [None, 'N/A']:
                try:
                    num = float(value)
                    # 温度、风速、体感温度保留1位小数，其他取整
                    return str(round(num, 1)) if key in ['t', 'ws', 'apparentTemp'] else str(int(num))
                except:
                    pass
            return str(value).replace('\n', ' ').replace('\r', '').strip() if value else 'N/A'
        
        def safe_list(lst, idx, key_idx, default='N/A'):
            if isinstance(lst, list) and len(lst) > idx:
                item = lst[idx]
                if isinstance(item, list) and len(item) > key_idx:
                    val = str(item[key_idx]).strip()
                    if key_idx in [2, 3] and val.replace('.', '').replace('-', '').isdigit():
                        try:
                            return str(int(float(val)))
                        except:
                            pass
                    return val
            return default
        
        raw_desc = today.get('report', 'N/A')
        cleaned_desc = remove_temperature_desc(raw_desc)
        
        day1 = convert_weekday(safe_list(day10, 0, 0))
        day2 = convert_weekday(safe_list(day10, 1, 0))
        day3 = convert_weekday(safe_list(day10, 2, 0))
        
        alarm_count = alarm_data.get('count', 0) if alarm_data else 0
        alarm_time = alarm_data.get('update_time', 'N/A') if alarm_data else 'N/A'
        raw_count = alarm_data.get('raw_count', 0) if alarm_data else 0
        
        lines = [
            "[Variables]",
            f"; 天气数据 - 站点:{realtime_data.get('obtName', 'N/A')}",
            f"; 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"PublishTime={safe_get(forecast_data, 'pubDate')}",
            f"ObserveTime={realtime_data.get('observeTime', 'N/A')}",
            f"RealtimeTemp={safe_get(realtime_data, 't')}",
            f"RealtimeHum={safe_get(realtime_data, 'u')}",
            f"RealtimeWindSpeed={safe_get(realtime_data, 'ws')}",
            f"RealtimeApparentTemp={safe_get(realtime_data, 'apparentTemp')}",
            f"TodayIcon={safe_get(today, 'icon', '02')}",
            f"TodayMin={safe_get(today, 'minT')}",
            f"TodayMax={safe_get(today, 'maxT')}",
            f"TodayDesc={cleaned_desc}",
            f"Day1Date={day1}",
            f"Day1Icon={safe_list(day10, 0, 4, '02')}",
            f"Day1Min={safe_list(day10, 0, 3)}",
            f"Day1Max={safe_list(day10, 0, 2)}",
            f"Day1Desc={safe_list(day10, 0, 1)}",
            f"Day2Date={day2}",
            f"Day2Icon={safe_list(day10, 1, 4, '02')}",
            f"Day2Min={safe_list(day10, 1, 3)}",
            f"Day2Max={safe_list(day10, 1, 2)}",
            f"Day2Desc={safe_list(day10, 1, 1)}",
            f"Day3Date={day3}",
            f"Day3Icon={safe_list(day10, 2, 4, '02')}",
            f"Day3Min={safe_list(day10, 2, 3)}",
            f"Day3Max={safe_list(day10, 2, 2)}",
            f"Day3Desc={safe_list(day10, 2, 1)}",
            "",
            "; 预警数据",
            f"WarningUpdateTime={alarm_time}",
            f"WarningCount={alarm_count}",
        ]
        
        if alarm_data and alarm_count > 0 and not alarm_data.get('expired', False):
            for i, alarm in enumerate(alarm_data.get('alarms', []), 1):
                lines.append(f"WarningIcon{i}={alarm.get('icon', '')}")
                info = alarm.get('str', '').replace('\n', ' ').replace('\r', '').strip()
                lines.append(f"WarningInfo{i}={info}")
        
        vars_path = os.path.join(DATA_DIR, 'weather_vars.inc')
        with open(vars_path, 'w', encoding='gbk') as f:
            f.write('\n'.join(lines) + '\n')
        
        print(f"[OK] 变量文件已生成: {vars_path}")
        
        if not forecast_success and existing_data:
            print(f"     [断网保护] 预报: 使用缓存")
        if not realtime_success and existing_data:
            print(f"     [断网保护] 实时: 使用缓存")
        if not alarm_success or (alarm_data and alarm_data.get('expired', False)):
            print(f"     [安全机制] 预警: 已清空 (数量=0)")
        elif raw_count > alarm_count:
            print(f"     [去重] 预警: {raw_count}条 -> {alarm_count}条")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# ========== 主函数 ==========

def main():
    parser = argparse.ArgumentParser(description='深圳天气数据更新')
    parser.add_argument('--station', '-s', default=DEFAULT_OBT_ID, help='自动站编号')
    args = parser.parse_args()
    
    print("="*60)
    print(f"深圳天气数据更新 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"实时站点: {args.station}")
    print(f"断网保护: 保留天气数据，预警置0")
    print("="*60)
    
    print("\n[0/4] 读取现有数据...")
    existing_data = read_existing_vars()
    
    fetcher = WeatherDataFetcher()
    
    print("\n[1/4] 获取预报数据...")
    forecast = fetcher.get_forecast_data()
    if forecast and forecast.get('_success'):
        print(f"  -> 成功")
    else:
        print(f"  -> 失败")
    
    print(f"\n[2/4] 获取实时数据...")
    api = AutoStationAPI()
    realtime = api.get_realtime_data(args.station)
    if realtime and realtime.get('_success'):
        print(f"  -> {realtime.get('obtName', '成功')}")
        if realtime.get('apparentTemp') != 'N/A':
            print(f"     体感温度: {realtime.get('apparentTemp')}℃ (风速:{realtime.get('ws')}m/s)")
    else:
        print(f"  -> 失败")
    
    print(f"\n[3/4] 获取预警数据...")
    alarm_js = fetcher.get_alarm_data()
    alarm = None
    if alarm_js:
        alarm = parse_alarm_data(alarm_js)
        if alarm and alarm.get('_success'):
            if alarm.get('expired', False):
                print(f"  -> 成功但已过期")
            else:
                print(f"  -> 成功，{alarm.get('count', 0)}条预警")
        else:
            print(f"  -> 解析失败")
            alarm = None
    else:
        print(f"  -> 请求失败")
    
    print("\n[4/4] 生成变量文件...")
    success = generate_vars_file(forecast, realtime, alarm, existing_data)
    
    if success:
        print("\n" + "="*60)
        print("[OK] 更新完成")
        
        f_status = "缓存" if not forecast or not forecast.get('_success') else "最新"
        r_status = "缓存" if not realtime or not realtime.get('_success') else "最新"
        
        if not alarm or not alarm.get('_success') or alarm.get('expired', False):
            a_status = "已清空"
        elif alarm.get('raw_count', 0) > alarm.get('count', 0):
            a_status = f"{alarm.get('count', 0)}条(去重)"
        else:
            a_status = f"{alarm.get('count', 0)}条"
        
        at_info = ""
        if realtime and realtime.get('_success') and realtime.get('apparentTemp') != 'N/A':
            at_info = f" | 体感:{realtime.get('apparentTemp')}℃"
        
        print(f"  预报: {f_status} | 实时: {r_status} | 预警: {a_status}{at_info}")
        print("="*60)
    
    return success


if __name__ == '__main__':
    try:
        sys.exit(0 if main() else 1)
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)