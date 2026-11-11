# CrazyGame

**个人持仓观察与 AI 决策辅助工具。**

<p align="center">
  <img alt="Python 3.11" src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white">
  <img alt="Node.js 22+" src="https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white">
  <img alt="React 18" src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white">
  <img alt="MIT License" src="https://img.shields.io/badge/License-MIT-yellow.svg">
</p>

<p align="center">
  <a href="README.md">简体中文</a> | <a href="docs/README.en.md">English</a>
</p>

CrazyGame 帮你只关注少数真正认可的股票与基金，看清真实持仓结构和风险，并借助 AI 整理调仓与买入思路。数据、提醒和配置都保存在本地。

应用采用本地单用户架构，没有账号、登录、注册或权限系统。SQLite 保存配置和业务状态，AI Key 与通知凭据加密存储。

> [!IMPORTANT]
> 行情来自公开网页接口，不是交易所正式授权行情。数据可能延迟、限流或改变格式；场外基金盘中值为估算，正式收益以基金净值为准。

## 产品功能

<table>
  <tr>
    <td width="50%">
      <img src="docs/images/dashboard.png" alt="CrazyGame 总览页面" width="100%">
    </td>
    <td width="50%">
      <img src="docs/images/ai-workspace.png" alt="AI 诊股工作台" width="100%">
    </td>
  </tr>
  <tr>
    <td align="center">总览与自选行情</td>
    <td align="center">AI 诊股与多轮问股</td>
  </tr>
  <tr>
    <td width="50%">
      <img src="docs/images/groups.png" alt="加权组合页面" width="100%">
    </td>
    <td width="50%">
      <img src="docs/images/llm-config.png" alt="LLM Config 设置页面" width="100%">
    </td>
  </tr>
  <tr>
    <td align="center">加权组合与长期曲线</td>
    <td align="center">LLM Config 与能力测试</td>
  </tr>
</table>

> [!IMPORTANT]
> **使用提醒：** 使用 AI 功能前，请先进入“设置”页面完成 LLM Config：填写 Base URL、API Key 和模型，并运行一次能力测试。

| 模块 | 功能 | 说明 |
| --- | --- | --- |
| **AI 诊股** | 结构化决策报告 | 生成趋势、评分、支撑压力、风险、催化剂、仓位建议和操作清单。 |
| **AI 问股** | 工具驱动多轮对话 | 基于行情、技术指标、热点和持仓上下文流式回答，支持会话恢复与追问。 |
| **多模态识别** | 截图找股票 | 从股票截图识别 A 股、港股、美股或场内 ETF，确认后加入自选或开始诊断。 |
| **AI 简报** | 每日持仓健康 | A 股交易日 15:20 自动生成，15:28 失败重试，支持 Markdown 展示。 |
| **行情观察** | 分区自选 | 股票按 A 股、港股、美股分区；基金按场内 ETF、场外基金分区。 |
| **持仓管理** | 轻量持仓与盈亏 | 记录数量、平均成本和备注，按币种汇总市值与浮动盈亏。 |
| **分类组合** | 加权观察篮 | 同分类标的按相对权重归一，展示加权涨跌、覆盖率和长期曲线。 |
| **行情曲线** | 多周期趋势 | 支持 1 月、3 月、1 年、3 年、全部，组合可叠加最多 5 条成分线。 |
| **智能提醒** | 价格与涨跌幅 | 支持每日一次、冷却时间、交易时段门控，以及飞书和短信投递。 |
| **热点证据** | 新闻与公告 | 默认使用东方财富公开数据，按相关性与时效排序，可配置 Tavily/Bocha。 |
| **本地部署** | 一键启动 | Docker Compose 构建运行，默认仅监听 `127.0.0.1`。 |

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 API | Python 3.11、FastAPI、Pydantic、SQLAlchemy |
| 调度与存储 | APScheduler、SQLite、WAL |
| 行情层 | Tencent、Sina、Eastmoney、Stooq |
| 场外基金 | 天天基金估值、东方财富净值 |
| 前端 | React 18、TypeScript、Vite、i18next |
| 图表 | lightweight-charts |
| AI | OpenAI 兼容 Chat Completions、Tool Calls、流式输出、图片输入 |
| 通知 | 飞书自定义机器人、阿里云短信 |
| 部署 | Docker Compose |

## 快速开始

### 一键脚本

```bash
git clone https://github.com/panvv-ai/CrazyGame.git
cd CrazyGame
./docker-start.sh v2
```

脚本会自动构建并启动容器，完成后访问 <http://127.0.0.1:8000>。

## 配置

CrazyGame 不提供环境配置文件。语言、LLM Config、新闻检索和通知渠道均在设置页完成，凭据加密后保存在本地 SQLite。

填写服务商提供的 Base URL、API Key 和模型 ID；视觉模型可留空继承主模型。先运行能力测试，通过后再保存配置。

## 项目结构

```text
.
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── src/crazygame/
│   │   ├── api/          # FastAPI、依赖和路由
│   │   ├── core/         # 配置、数据库、密钥、日历
│   │   ├── domain/       # ORM、schema 和确定性业务规则
│   │   ├── providers/    # 场外基金数据适配
│   │   └── services/     # 行情、提醒、通知、AI、调度
├── frontend/
│   ├── src/crazygame/     # React 页面、组件、i18n 和设计系统
│   └── public/
├── marketdata/           # 可复用股票/ETF 行情包
├── docs/                 # 架构、设计和英文 README
├── docker-start.sh       # 一键构建与部署
├── compose.yaml
├── Dockerfile
└── Makefile
```

更详细的数据流和模块职责见 [架构文档](docs/architecture.md)，视觉规则见 [设计语言](docs/design-language.md)。

## 数据与隐私

CrazyGame 是一个纯本地、纯个人、极轻量的项目：没有云端服务器，也不存在远端数据存储。SQLite 数据库、配置和加密密钥均保存在本机；使用 AI 或新闻功能时，请求会按你的配置发送至相应第三方服务。

## 免责声明

本项目仅供学习和研究使用，不构成任何投资建议。股市有风险，投资需谨慎。作者不对使用本项目产生的任何损失负责。

## 开源协议

Copyright © 2026 CrazyGame contributors.

本项目采用 [MIT License](LICENSE)。

参考项目的架构与交互设计归属见 [第三方声明](docs/third-party-notices.md)。
