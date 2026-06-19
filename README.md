# “校园晴雨表”桌面插件

## ❓ 这是什么

“校园晴雨表”是深圳市高级中学气象社设计的一款基于 Python 数据获取与 Rainmeter 渲染界面的轻量级桌面天气插件，可实现显示实时天气、3日预报、预警信号与2小时短时降雨预报等功能。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Rainmeter](https://img.shields.io/badge/Rainmeter-4.5.0+-blue.svg)
![Python](https://img.shields.io/badge/Python-3.x-green.svg)

## 📸 效果展示

![主界面截图](https://github.com/user-attachments/assets/6d1d7dff-0369-4bdb-bf2c-aada121b4207)

## ✨ 核心功能

- **🌡️ 实时天气**：显示我校实时气温，数据现地性时效性强。
- **🧠 体感温度**：根据风速和湿度计算得到，对主观感受反映更准。
- **📅 三日预报**：展示未来3天的天气情况图示、最高/最低温及天气简述。
- **⚠️ 预警信号**：自动解析官方预警，最多支持6个图标并列展示，悬停可查看详细信息。
- **🌧️ 短时降雨**：以柱状图形式呈现未来120分钟的降雨强度预测。
- **🔄 智能刷新**：默认每5分钟自动更新数据，也支持点击刷新按钮手动触发。
- **🛡️ 断网适配**：无联网时段将预警数量置零，防止过时信息导致误解。

## 🚀 安装步骤


1. **安装Rainmeter桌面美化软件**

	✅️可在[Rainmeter网站官网](https://www.rainmeter.net/)或[其Github仓库](https://github.com/rainmeter/rainmeter/releases)下载最新版，这是一款能够在桌面上显示各种可自定义“皮肤”的软件，本插件目前亦依赖其进行显示。
	安装完成后该软件会显示自带的欢迎界面和系统性能看板皮肤，右键其并点击“关闭皮肤”可以关闭。
	
	![软件自带皮肤](https://github.com/user-attachments/assets/f0bd48a6-8882-42ae-bd2b-d7f38c96b415)

2. **部署/安装皮肤**

	将本项目所有文件复制至 Rainmeter 皮肤目录的一个子文件夹下，比如：
	```
	%USERPROFILE%\Documents（*注：即为当前用户的“文档”文件夹）\Rainmeter\Skins\CampusWeather\
	```
	当然也可以通过双击“.rmskin”皮肤包直接安装，如果采取本方法，完成当前步骤后插件就可以正常加载了。
	.rmskin皮肤包可以在本仓库的Releases下载。
	
	![通过.rmskin文件安装](https://github.com/user-attachments/assets/428159f1-b5b9-494e-98c8-3f9515fc5fdb)

3. **加载皮肤**

	- 打开 Rainmeter 管理器。(任务栏托盘雨滴图标右键>管理)
	- 找到 `CampusWeather` 文件夹下的 `szw.ini`。
	- 点击右侧窗口中的"加载"按钮。
	- *首次运行需点击右上角“刷新”按钮等待7秒左右完成数据获取与界面刷新。*
	- 建议使用下面截图中的皮肤设置（右键插件打开菜单进行设置）
	
	![推荐设置](https://github.com/user-attachments/assets/4f86ede1-43b9-4bb1-920c-694fcf17d69a)

## 🔍 工作原理

1. **定时触发**: Rainmeter 内置计时器每5分钟触发一次下列活动。
2. **数据获取**: 运行 `update_weather.pyw` 和 `getrain.pyw` 两个数据获取脚本。
3. **数据处理**: 脚本从公开接口获取数据，经过解析、计算、容错处理后，分别写入 `data/weather_vars.inc` 和 `data/rain.inc` 文件。
4. **界面渲染**: `szw.ini` 通过 `@include` 指令读取这两个文件中的数据。
5. **延迟刷新**: 脚本执行完毕后通过 `[!Delay 7000][!Refresh]` 指令延迟刷新界面，确保读取到完整的新数据。
6. **异常处理**: 当网络异常或接口失效时，脚本会写入全零默认值（预警、2h降雨）或保留上一次有效缓存（实况、预报），保证皮肤不会崩溃或显示错误信息。

## ❓ 注意事项

- **免责声明**  
❗️  本项目仅用于桌面美化与学习研究，不作为官方气象信息发布渠道。数据精度与时效性以深圳市气象局官网为准，防灾减灾综合信息请以深圳市政府官方通报为准。
❗️  本项目数据来源于市气象局官网等处的网络接口，其数据均对社会公开可查，下载使用本项目者应遵循相关法律法规，不得滥用。

## 🙏 致谢

- **数据来源**: [深圳市气象局](http://weather.sz.gov.cn/)
- **界面字体**: [GWM Sans 中文](https://www.gwm.com.cn/gwmsans/fontdownload.html)

---
*Made with ❤️ for Shenzhen Weather*
