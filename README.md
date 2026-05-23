# 深圳天气监控 Rainmeter 皮肤

一款基于 Python 脚本抓取数据 + Rainmeter 渲染界面的轻量级桌面天气插件，专为深圳市气象局公开数据源设计。集成实时气象、3日预报、官方预警信号与2小时短时降雨预报功能，内置断网保护与智能容错机制，确保桌面显示稳定可靠。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Rainmeter](https://img.shields.io/badge/Rainmeter-4.5.0+-blue.svg)
![Python](https://img.shields.io/badge/Python-3.x-green.svg)

## ✨ 核心功能

- **🌡️ 实时天气**：显示当前温度、湿度、风速、观测时间及体感温度。
- **📅 三日预报**：展示未来3天的日期、天气图标、最高/最低温及天气简述。
- **⚠️ 预警信号**：自动解析官方预警，按颜色级别去重（红>橙>黄>蓝>白），最多支持6个图标并列展示，悬停可查看详细信息。
- **🌧️ 短时降雨**：提供未来120分钟（每4分钟1个点，共30个点）的降雨强度预测，以垂直柱状图形式动态渲染，并标注关键时间节点。
- **🧠 体感温度**：采用分段 Steadman 公式计算，针对深圳气候特征优化了低温湿冷效应。
- **🛡️ 断网保护**：API请求失败时自动读取本地缓存复用天气数据，同时将预警数量强制清零，防止过期警报误导用户。
- **🔄 智能刷新**：默认每5分钟自动执行数据更新脚本，也支持点击界面刷新按钮手动触发。

## 📋 环境要求

- **Rainmeter**: 4.5.0 或以上版本
- **Python**: 3.x (需配置好环境变量，确保 Rainmeter 能调用 `python` 命令)

## 🚀 安装步骤

1. **部署皮肤**  
   将本项目所有文件复制至 Rainmeter 皮肤目录，例如：
   ```
   %USERPROFILE%\Documents\Rainmeter\Skins\ShenzhenWeather\
   ```

2. **加载皮肤**  
   - 打开 Rainmeter 管理器。
   - 找到 `ShenzhenWeather` 分类下的 `szw.ini`。
   - 点击"加载"。
   - *首次运行约需等待7秒完成数据获取与界面刷新。*

## 📂 目录结构

```text
ShenzhenWeather/
├── szw.ini             # Rainmeter 主皮肤配置文件
├── update_weather.pyw  # 综合天气数据获取脚本（实时/预报/预警/体感）
├── getrain.pyw         # 2小时短时降雨预报获取脚本
├── data/
│   ├── icons/          # 天气图标资源目录
│   ├── warnings/       # 预警图标资源目录
│   ├── weather_vars.inc# [自动生成] 天气变量输出文件
│   └── rain.inc        # [自动生成] 降雨数据输出文件
└── README.md           # 本说明文件
```

## ⚙️ 自定义配置

| 配置项 | 修改方法 | 说明 |
| :--- | :--- | :--- |
| **监控位置** | 编辑 `getrain.pyw` 中的 `DEFAULT_PARAMS` | 修改 `latitude` 和 `longitude` 参数即可切换至深圳其他区域。 |
| **刷新间隔** | 编辑 `szw.ini` 中 `[MeasureRefreshTimer]` 区块 | 修改 `Formula=(Counter + 1) % 301` 中的数值 `301` (单位:秒)。 |
| **主题配色** | 编辑 `szw.ini` 中 `[Variables]` 区块 | 修改 `BgColor`, `TextColor`, `TitleColor` 等变量值。 |
| **预警时效** | 编辑 `update_weather.pyw` | 修改 `WARNING_MAX_AGE_MINUTES` 变量 (默认30分钟)，超出该时限的预警将被视为过期。 |

## 🔍 工作原理

1. **定时触发**: Rainmeter 内置计时器每5分钟触发一次。
2. **数据获取**: 异步调用 `update_weather.pyw` 和 `getrain.pyw` 两个 Python 脚本。
3. **数据处理**: 脚本从深圳市气象局公开接口获取数据，经过解析、计算、容错处理后，分别写入 `data/weather_vars.inc` 和 `data/rain.inc` 文件。
4. **界面渲染**: `szw.ini` 通过 `@include` 指令引入这两个变量文件。
5. **延迟刷新**: 脚本执行完毕后通过 `[!Delay 7000][!Refresh]` 指令延迟刷新界面，确保读取到完整的新数据。
6. **异常处理**: 当网络异常或接口失效时，Python 脚本会捕获异常并写入全零默认值或保留上一次有效缓存，保证皮肤不会崩溃或显示错误信息。

## ❓ 常见问题与注意事项

- **图标不显示**  
  皮肤通过变量动态拼接图标路径，请确保 `data/icons/` 和 `data/warnings/` 目录中存在与变量值对应的 `.png` 文件。

- **接口失效**  
  API 可能不定期更新 `sign` 参数或调整数据结构。若脚本持续报错 `FAIL`，请检查网络连接或联系作者更新解析逻辑。

- **免责声明**  
  本项目仅用于个人桌面美化与学习研究，不作为官方气象信息发布渠道。数据精度与时效性以深圳市气象局官网为准，防灾减灾请以政府官方通报为准。

## 🙏 致谢

- **数据来源**: [深圳市气象局](http://weather.sz.gov.cn/)
- **体感温度算法**: 基于 Steadman 表观温度公式本地化改良

---
*Made with ❤️ for Shenzhen Weather*
