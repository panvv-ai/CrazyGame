# PanWatchDIY v2

私有部署的长期投资观察站。聚焦 A 股、港股、美股、A 股场内 ETF 与场外基金的自选、加权组合、轻量持仓、价格提醒和每日持仓健康简报。

默认简体中文，可切换英文；默认深色界面。

## 功能

- A 股、港股、美股股票搜索与自选。
- A 股场内 ETF、开放式基金/ETF 联接自选。
- 按相对权重创建混合 Group，权重自动归一。
- Group 当日加权涨跌、覆盖率与历史归一曲线。
- 单账户轻量持仓：数量、平均成本、市值、浮动盈亏。
- 价格与当日涨跌幅提醒。
- 飞书机器人和阿里云短信通知。
- 每个交易日 15:20 生成持仓健康简报，15:28 自动重试一次。
- 中文与英文界面，提醒和 AI 简报跟随界面语言。
- Docker Compose 单服务部署。
- 全部历史行情使用折线/面积图，不包含 K 线图。

## 数据来源

行情通过 `packages/marketdata` 的主备引擎获取：

| 标的 | 主源 | 备用源 | 历史曲线 |
|---|---|---|---|
| A 股 | 腾讯 | 东方财富 | 腾讯、东方财富 |
| 港股 | 腾讯 | 新浪、东方财富 | 腾讯、东方财富 |
| 美股 | 腾讯 | 新浪 | 腾讯、Stooq |
| A 股 ETF | 腾讯/东方财富 | — | 交易价格日线 |
| 场外基金 | 天天基金估值 | 东方财富净值 | 东方财富正式净值 |

这些是公开网页数据接口，不是交易所授权行情。数据可能延迟、限流或改变格式。场外基金盘中数据是估值，正式收益以基金净值为准。

本项目仅供私有、单用户研究和长期投资观察，不构成投资建议。不要把行情接口转发给第三方，也不要将未认证的服务直接暴露到公网。

## 技术栈

- Python 3.11
- FastAPI、SQLAlchemy、SQLite、APScheduler
- React 18、TypeScript、Vite
- i18next、react-i18next
- lightweight-charts
- 腾讯/新浪/东方财富公开行情接口

## 本地开发

```bash
make setup
make dev-api
```

另一个终端：

```bash
make dev-web
```

- 后端：<http://localhost:8000>
- 前端开发服务器：<http://localhost:5183>

首次启动会创建 `data/panwatch-v2.db`。v2 不迁移旧版 `panwatch.db`，也不会删除旧数据库。

## Docker Compose

```bash
cp .env.example .env
# 修改 AUTH_USERNAME、AUTH_PASSWORD、JWT_SECRET
docker compose up -d --build
```

打开 <http://localhost:8000>。

数据持久化在 `panwatch_data` volume。升级或重建容器不会删除数据库。

## 环境变量

| 变量 | 说明 |
|---|---|
| `AUTH_USERNAME` | 首次启动创建的用户名 |
| `AUTH_PASSWORD` | 首次启动创建的密码，至少 8 位 |
| `JWT_SECRET` | JWT 签名密钥，建议至少 32 个随机字符 |
| `DATA_DIR` | SQLite 数据目录 |
| `TZ` | 应用时区，默认 `Asia/Shanghai` |
| `AI_BASE_URL` | OpenAI 兼容 API 地址 |
| `AI_API_KEY` | AI API Key，也可在设置页填写 |
| `AI_MODEL` | 模型标识 |
| `HTTP_PROXY` / `HTTPS_PROXY` | 可选出站代理 |

## 通知配置

### 飞书

1. 在飞书群中添加“自定义机器人”。
2. 复制 Webhook URL。
3. 如机器人开启签名校验，同时填写签名密钥。
4. 在设置页添加渠道并发送测试消息。

### 阿里云短信

需要自行准备：

- AccessKey ID / Secret
- 已审核通过的短信签名
- 中文模板 Code
- 英文模板 Code
- 接收手机号

提醒模板变量为：

```text
${rule} ${name} ${price} ${change}
```

短信由阿里云按发送量收费。

## 每日持仓健康简报

- 仅 A 股交易日运行。
- 默认 `15:20 Asia/Shanghai`。
- 失败后 `15:28` 重试一次。
- 已有成功结果时不会重复调用 AI。
- 简报读取持仓、当日行情、120 日趋势和资产分布。
- 只提供个人研究辅助，不执行交易。

## 测试

```bash
make test
```

或分别运行：

```bash
.venv/bin/python -m pytest tests/v2 -q
cd frontend && pnpm test
cd frontend && pnpm check:i18n
cd frontend && pnpm build
```

## 归档

改版前的完整功能保存在 annotated tag：

```text
archive/full-feature-2026-11
```

需要恢复旧功能时，从该 tag 查看或按需移植。不要在当前分支重新引入整套多 Agent、交易研究或 MCP 模块。

## 许可

MIT。详见 [LICENSE](LICENSE)。
