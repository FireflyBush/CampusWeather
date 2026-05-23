# “校园晴雨表”桌面插件

## ❓ 这是什么
“校园晴雨表”是深圳市高级中学气象社设计的一款基于 Python 数据获取与 Rainmeter 渲染界面的轻量级桌面天气插件，可实现显示实时天气、3日预报、预警信号与2小时短时降雨预报等功能。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Rainmeter](https://img.shields.io/badge/Rainmeter-4.5.0+-blue.svg)
![Python](https://img.shields.io/badge/Python-3.x-green.svg)

## 📸 效果展示
![主界面截图](https://github.com/user-attachments/assets/6d1d7dff-0369-4bdb-bf2c-aada121b4207)

## ✨ 核心功能

- **🌡️ 实时天气**：显示我校实时气温，数据时效性强
- **🧠 体感温度**：根据风速和湿度计算得到，对主观感受反映更准
- **📅 三日预报**：展示未来3天的天气情况图示、最高/最低温及天气简述。
- **⚠️ 预警信号**：自动解析官方预警，最多支持6个图标并列展示，悬停可查看详细信息。
- **🌧️ 短时降雨**：以柱状图形式呈现未来120分钟的降雨强度预测。
- **🔄 智能刷新**：默认每5分钟自动更新数据，也支持点击刷新按钮手动触发。
- **🛡️ 断网适配**：无联网时段将预警数量置零，防止过时信息导致误解。


## 📋 运行要求

- **Rainmeter**: 4.5.0 或以上版本
- **Python**: 3.x (**.rmskin安装版已经嵌入好相关文件，无需另行安装**)

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
   - *首次运行约需点击右上角“刷新”按钮等待7秒完成数据获取与界面刷新。*

## 🔍 工作原理

1. **定时触发**: Rainmeter 内置计时器每5分钟触发一次。
2. **数据获取**: 异步调用 `update_weather.pyw` 和 `getrain.pyw` 两个 Python 脚本。
3. **数据处理**: 脚本从深圳市气象局公开接口获取数据，经过解析、计算、容错处理后，分别写入 `data/weather_vars.inc` 和 `data/rain.inc` 文件。
4. **界面渲染**: `szw.ini` 通过 `@include` 指令引入这两个变量文件。
5. **延迟刷新**: 脚本执行完毕后通过 `[!Delay 7000][!Refresh]` 指令延迟刷新界面，确保读取到完整的新数据。
6. **异常处理**: 当网络异常或接口失效时，Python 脚本会捕获异常并写入全零默认值或保留上一次有效缓存，保证皮肤不会崩溃或显示错误信息。

## ❓ 注意事项

- **免责声明**  
  本项目仅用于桌面美化与学习研究，不作为官方气象信息发布渠道。数据精度与时效性以深圳市气象局官网为准，防灾减灾综合信息请以深圳市政府官方通报为准。

## 🙏 致谢

- **数据来源**: [深圳市气象局](http://weather.sz.gov.cn/)
- **体感温度算法**: 基于 Steadman 表观温度公式本地化改良

---
*Made with ❤️ for Shenzhen Weather*
