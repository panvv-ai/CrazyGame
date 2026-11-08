# CrazyGame

**本地优先的多市场长期投资观察工具。**

<p align="center">
  <img alt="Python 3.11" src="https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white">
  <img alt="Node.js 22+" src="https://img.shields.io/badge/Node.js-22%2B-339933?logo=node.js&logoColor=white">
  <img alt="React 18" src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white">
  <img alt="MIT License" src="https://img.shields.io/badge/License-MIT-yellow.svg">
</p>

<p align="center">
  <a href="README.md">简体中文</a> | <a href="docs/README.en.md">English</a>
</p>

CrazyGame 把股票、ETF 和场外基金收束到同一个本地观察站。你可以维护自选清单、用权重组合观察整体趋势、记录轻量持仓，并在价格或涨跌幅达到条件时通过飞书、短信收到提醒。

应用采用本地单用户架构，没有账号、登录、注册或权限系统。SQLite 保存配置和业务状态，AI Key 与通知凭据加密存储。

> [!IMPORTANT]
> 行情来自公开网页接口，不是交易所正式授权行情。数据可能延迟、限流或改变格式。场外基金盘中值为估算，正式收益以基金净值为准。本项目仅供个人研究，不构成投资建议。

## 产品功能

<p align="center">
  <img src="docs/images/dashboard.png" alt="CrazyGame 首页，展示加权组合、自选行情与每日持仓简报" width="100%">
</p>

- **分区自选**：股票按 A 股、港股、美股分开查看；基金按场内 ETF、场外基金分开查看。
- **场外基金**：支持基金搜索、盘中估值、正式净值与历史净值曲线。
- **分类组合**：用目标权重组织同一分类的观察篮，权重自动归一，并展示当日加权涨跌、覆盖率和归一曲线。
- **长期曲线**：支持 1 月、3 月、1 年、3 年、全部，组合可叠加最多 5 条成分线。
- **轻量持仓**：单账户记录数量、平均成本、市值和浮动盈亏，并按币种汇总。
- **智能提醒**：价格或当日涨跌幅阈值，支持每日一次、冷却时间和交易时段门控。
- **飞书与短信**：每个提醒可独立选择通知渠道，支持重试和投递状态追踪。
- **每日持仓健康**：A 股交易日 15:20 自动生成，15:28 失败重试；简报按 Markdown 渲染。
- **双语界面**：默认中文，可随时切换英文；AI 简报和提醒跟随界面语言。
- **本地部署**：Docker Compose 一条命令启动，默认仅监听 `127.0.0.1`。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 API | Python 3.11、FastAPI、Pydantic、SQLAlchemy |
| 调度与存储 | APScheduler、SQLite、WAL |
| 行情层 | Tencent、Sina、Eastmoney、Stooq |
| 场外基金 | 天天基金估值、东方财富净值 |
| 前端 | React 18、TypeScript、Vite、i18next |
| 图表 | lightweight-charts |
| 通知 | 飞书自定义机器人、阿里云短信 |
| 测试 | pytest、Vitest |
| 部署 | Docker Compose |

## 快速开始

### 环境要求

- Python 3.11
- Node.js 22+
- pnpm 10+
- Docker Desktop（可选）

### 方式一：Docker Compose（推荐）

```bash
git clone https://github.com/panvv-ai/CrazyGame.git
cd CrazyGame

cp config/env.example .env
# 可选：在 .env 中填写 AI 服务配置

docker compose up -d --build
docker compose ps
```

打开 <http://127.0.0.1:8000>。

默认构建 `crazygame:latest`。需要固定 tag 时：

```bash
CRAZYGAME_TAG=v1 docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f crazygame
```

停止服务：

```bash
docker compose down
```

容器只映射到本机回环地址，SQLite 与凭据密钥保存在 `crazygame_data` volume。根目录 `.env` 已被 Git 忽略，不要把真实 API Key 写进 `config/env.example`。

### 方式二：本地开发

```bash
git clone https://github.com/panvv-ai/CrazyGame.git
cd CrazyGame

make setup
make dev-api
```

另开一个终端：

```bash
make dev-web
```

打开 <http://127.0.0.1:5183>。Vite 会把 `/api` 代理到本地 FastAPI。

生产式本地运行：

```bash
cd frontend && pnpm build
cd ..
mkdir -p backend/static
cp -R frontend/dist/. backend/static/
cd backend && ../.venv/bin/python main.py
```

打开 <http://127.0.0.1:8000>。

### 手动构建 Docker 镜像

```bash
cp config/env.example .env
docker build --build-arg CRAZYGAME_TAG=v1 -t crazygame:v1 .
docker run -d \
  --name crazygame \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -v crazygame_data:/app/data \
  --env-file .env \
  crazygame:v1
```

打开 <http://127.0.0.1:8000>。

也可以使用统一构建脚本：

```bash
./scripts/build.sh v1
# 产物：crazygame:v1
```

## 使用方式

### 添加自选

在“自选”页先选择“股票”或“基金”，再切换 A 股、港股、美股、场内 ETF、场外基金分类。搜索代码或名称后添加；港股代码会自动补足 5 位，场外基金代码补足 6 位。拖动卡片抓手可以调整当前分类内的显示顺序。

### 添加分类组合

在“组合”页选择与组合相同的分类后，从该分类的自选标的中填写相对权重。例如 `30 / 25 / 20 / 15 / 10` 会被归一为 `30% / 25% / 20% / 15% / 10%`。不同市场或不同基金类型不能混在同一个组合中。

### 记录持仓

在“持仓”页选择已有自选标的，填写数量和平均成本。多币种分别汇总，不进行隐含汇率换算。

### 组合与持仓怎么区分

“持仓”记录你实际持有的数量、平均成本和浮盈亏，是每日健康简报的唯一分析来源。

“组合”不记录真实仓位，只用于把几只关注标的按目标权重组成一个观察篮，查看假设配置下的共同涨跌和长期曲线。如果只需要分析真实资产，可以不使用组合功能。

### 设置提醒

在提醒表单中选择价格或涨跌幅条件、方向和阈值。飞书和阿里云短信需要在设置页先完成配置。

阿里云提醒模板变量为：

```text
${rule} ${name} ${price} ${change}
```

### 查看每日健康简报

服务在 A 股交易日 15:20 生成持仓健康简报。需要先在设置页配置 OpenAI 兼容的 AI 服务和模型。

## 配置

复制 [`config/env.example`](config/env.example) 为根目录 `.env`，或直接使用环境变量：

`config/env.example` 只包含安全占位符；真实 API Key 请写入被 Git 忽略的 `.env`，或直接在设置页填写。应用会将凭据加密后保存到本地数据库。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATA_DIR` | `./data` | SQLite 与本地密钥目录 |
| `TZ` | `Asia/Shanghai` | 应用与调度时区 |
| `CRAZYGAME_TAG` | `latest` | Compose 构建和使用的镜像 tag |
| `CRAZYGAME_HOST` | `127.0.0.1` | 本地服务监听地址 |
| `CRAZYGAME_PORT` | `8000` | 本地服务端口 |
| `APP_SECRET_KEY` | 自动生成 | 加密 AI Key 和通知凭据 |
| `AI_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容 API |
| `AI_API_KEY` | 空 | AI API Key，也可在设置页填写 |
| `AI_MODEL` | `gpt-4.1-mini` | 模型标识 |
| `HTTP_PROXY` / `HTTPS_PROXY` | 空 | 可选行情代理 |

## 项目结构

```text
.
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pyproject.toml
│   ├── src/crazygame/
│   │   ├── api/          # FastAPI、依赖和路由
│   │   ├── core/         # 配置、数据库、密钥、日历
│   │   ├── domain/       # ORM、schema 和确定性业务规则
│   │   ├── providers/    # 场外基金数据适配
│   │   └── services/     # 行情、提醒、通知、AI、调度
│   └── tests/
├── frontend/
│   ├── src/crazygame/     # React 页面、组件、i18n 和设计系统
│   └── public/
├── marketdata/           # 可复用股票/ETF 行情包
├── config/env.example
├── docs/                 # 架构、设计和英文 README
├── scripts/build.sh
├── compose.yaml
├── Dockerfile
└── Makefile
```

更详细的数据流和模块职责见 [架构文档](docs/architecture.md)，视觉规则见 [设计语言](docs/design-language.md)。

## 数据与隐私

- 默认数据库：`DATA_DIR/crazygame.sqlite3`。
- 默认本地密钥：`DATA_DIR/.app-secret`，权限为 `0600`。
- AI Key、飞书签名和阿里云 AccessKey 加密后写入 SQLite。
- API 不会返回完整凭据，只返回掩码。
- 本项目不会上传持仓、自选或提醒到第三方；只有配置的 AI 服务和通知渠道会接收对应内容。
- 不要把无认证服务直接暴露到公网。Compose 默认只发布到 `127.0.0.1`。

## 开发与测试

```bash
make test

cd frontend
pnpm check:i18n
pnpm test
pnpm build
```

单独运行：

```bash
cd backend && ../.venv/bin/python -m pytest tests -q
.venv/bin/python -m pytest marketdata/tests -q
```

## 已知限制

- 只支持 A 股场内 ETF，不包含港股和美股 ETF。
- 场外基金无法提供连续交易价格，估值与正式净值必须区分。
- 公开行情源没有 SLA，可能临时不可用。
- 目前只有深色主题。
- AI 输出只作为个人研究辅助，不会自动交易。

## 开源协议

Copyright © 2026 CrazyGame contributors.

本项目采用 [MIT License](LICENSE)。
