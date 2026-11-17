# CrazyGame Android 独立应用与移动 UI 分阶段施工计划

> 更新日期：2026-11-16
>
> 执行状态：Phase 0–4 已实施。Phase 0 的兼容性门禁触发 Kotlin 本地回退，
> Phase 1–3 完成共享 UI 与交互基础设施，Phase 4 完成 Android 本地运行和
> 签名发布链。
>
> Phase 0 结果：现有 Pydantic 2 依赖链无法通过 Chaquopy 打包，Phase 4 使用已批准的
> Kotlin 本地业务层回退。详见 `docs/mobile-phase0-report.md`。

## 已确认的边界

- PC Web 与 Android 完全独立运行。两端各自拥有 FastAPI、SQLite 和业务数据，不连接同一后端，不使用云端，不做局域网自动同步。
- 跨设备数据迁移只通过手动导入/导出完成。
- React/CSS 是同一份源码，分别构建为 PC Web 资源和 APK 内的 WebView 资源；运行时不共享任何数据。
- Android 优先采用 Kotlin WebView + React + Chaquopy 17.2 + 手机内 FastAPI + SQLite。
- Chaquopy 只负责在手机进程内携带 Python 运行时，不连接电脑或云端。
- Phase 0 必须先用最小 APK 验证 Python 依赖和本地 HTTP 服务。若关键依赖不兼容，则回退为 Kotlin 本地数据、行情和提醒层，继续保留同一套 React UI。
- 最终范围为分阶段实现 Web/Android 功能同构；不交付 Windows 桌面壳。
- UI 保持纯深色 Aurora Workbench，不增加浅色主题。
- Android 底栏：总览、自选、组合、持仓、提醒；AI 和设置位于顶部工具区。
- 提醒检查：App 前台约 30 秒，后台 WorkManager 约 15 分钟。
- Android 通知同时覆盖系统本地通知、飞书和阿里云短信。

## Phase 0：仓库分析与技术门禁

### 当前结构

- `App.tsx`：极光背景、顶部工具栏、路由和移动底栏。
- 页面：Overview、Watchlist、Groups、Holdings、Alerts、AI、Settings。
- 公共组件：按钮、玻璃面板、弹窗、空状态、加载、字段、图表、Markdown 和行情状态。
- 样式：`styles.css` 保存旧组件规则；`workbench.css` 保存 Aurora token、布局和兼容层。
- 后端：FastAPI、SQLAlchemy、SQLite、APScheduler、公开行情聚合、AI 和通知服务。

### 390px 移动视口发现

- 底栏缺少组合入口，却把尚未纳入当前核心闭环的 AI 放在一级导航。
- 多个页面同时出现页头主按钮和空状态按钮。
- 空状态占用空间过大，首屏操作密度偏低。
- 设置页仍是桌面长表单纵向堆叠。
- 弹窗是桌面中心 Modal，缺少移动端拖动关闭、Android 返回键和键盘协议。
- 页面以路径 key 强制重建，并通过页面级定时器重复拉取数据。
- 两份 CSS 存在重复的导航、弹窗和断点定义。
- 元数据偏小，部分点击目标低于 44px。

### Chaquopy 探针

在 Android 产品 UI 继续扩展前，建立最小 Android 工程并验证：

1. Python 3.11、`minSdk 26`、`arm64-v8a + x86_64`。
2. FastAPI、Pydantic 2、cryptography、SQLAlchemy、APScheduler、httpx、python-multipart 和 uvicorn 可导入。
3. SQLite 可初始化。
4. 外网 HTTPS 请求可用。
5. uvicorn 可绑定手机 `127.0.0.1`。
6. WebView 可请求 `/api/health`。
7. 记录 APK 大小、冷启动、Python 初始化和内存。

结果通过则保留 Chaquopy；结果失败则记录具体依赖并切换 Kotlin 本地业务层。

## Phase 1：设计系统、动效与通用交互基础

Phase 1 只处理公共基础设施、导航壳层和样式 token，不逐页重写业务页面。

### 设计系统

- 保留现有颜色、极光背景、字体、玻璃表面、圆角和图表视觉。
- 建立颜色、文字、间距、圆角、阴影、触控尺寸和动效的语义 token。
- 移动正文不小于 14px，主要触控目标不小于 44px。
- 保留旧 CSS 兼容别名，只删除已确认重复的移动导航规则。

### 动效

- 使用 `motion@14.14.0` 和 `motion/react`。
- 通过 `LazyMotion` 延迟加载动画特性，避免完整运行时进入首屏主包。
- 页面切换使用约 220–280ms 的短距离位移和透明度。
- 卡片按压约 `0.98`；列表只对首批项目做 20–30ms 错峰。
- 所有位移动画服从 `prefers-reduced-motion`。

### 通用组件

- `PageTransition`：方向感知的路由进入和退出。
- `StaggerList`：限制首批项目的错峰反馈。
- `AnimatedNumber`：数值动画同时保留最终可访问文本。
- `Pressable`：统一按压和无障碍行为，并向 Android 发送有意义的触觉事件。
- `BottomSheet`：拖动关闭、遮罩关闭、Escape、Android 返回、焦点管理、键盘和安全区适配。
- `Toast`：统一成功、错误和中性反馈。
- `Skeleton`：稳定局部加载布局。
- `EmptyState`：提供紧凑模式供 Phase 2 使用。

### 导航

- 底栏固定五个核心业务页面。
- AI 和设置继续使用顶部工具入口。
- 底栏选中状态使用共享 layout indicator。
- 页面切换不再通过 `key={location.pathname}` 重建整个 `main`。
- 前进时滚动到顶部；浏览器/Android 返回时恢复该路径的滚动位置。
- Android 原生返回键通过统一 `crazygame:back` 事件先关闭可关闭层，再交给路由。

### Phase 1 停止条件

- 前端测试、i18n 检查、TypeScript 和生产构建通过。
- 320、375、390、414 和 768px 无横向溢出。
- 1440px 桌面导航和核心首屏保持正常。
- 输出修改文件、依赖、验证结果、遗留问题和 Phase 2 建议。

## Phase 2–3：页面与复杂交互

Phase 2 逐页推进：Overview → Watchlist → Groups → Holdings → Alerts。

- Overview：首屏优先显示真实持仓/组合状态和图表；压缩空状态；消除重复 CTA。
- Watchlist：紧凑行情列表、可触达筛选与搜索、保留详情和提醒。
- Groups：横向组合选择，先摘要与曲线，再成员权重。
- Holdings：币种摘要横向滑动，移动列表替代宽表，编辑进入 Bottom Sheet。
- Alerts：优先显示监听状态、当前值、阈值和冷却；本地与远程通知分组明确。

Phase 3 处理 AI、Settings、图表和复杂表单：

- AI 聊天输入区跟随键盘，保持可见；长 Markdown 独立滚动。
- Settings 改为分组入口和二级页面。
- 图表支持触摸拖动、缩放、十字线、区间切换和刷新时视口保持。
- 所有表单处理键盘、错误聚焦、取消确认和状态恢复。

## Phase 4：Android 本地运行与发布

Phase 0 已验证现有 Python 依赖无法通过 Chaquopy 打包，因此本阶段执行已批准的
Kotlin 本地回退：

- Kotlin 工程负责 WebView、本地数据服务、SQLite/Room、行情访问、生命周期和异常恢复。
- React 继续通过明确的平台适配接口使用 Android 本地数据层，不连接 PC。
- Android Keystore 加密 LLM 和通知凭据。
- WorkManager 直接调用 Kotlin 提醒扫描逻辑，不运行长期 APScheduler。
- Kotlin 发布系统通知，同时执行飞书/SMS 投递。
- WebView 配置深色系统栏、安全区、键盘 resize、返回键、文件选择和外部导航限制。
- 支持 `.crazygame` 数据包导入/导出；凭据使用用户密码单独加密。
- 建立签名 release keystore、GitHub Actions、`CrazyGame_1.apk` 和后续 `mobile-v*` 发布流程。

## 验证要求

- 前端单元测试：动效 token、导航、滚动记忆、路由过渡、Bottom Sheet、Toast、Skeleton、Pressable、数值动画。
- 后端：现有测试必须持续通过。
- 视觉：320、375、390、414、768 和 1440px。
- 后续 Android：依赖探针、SQLite migration、Keystore、WorkManager、通知权限和本地 API 启动。
- 契约：桌面 Python 与 Android 本地运行层的组合和提醒用例保持一致。
- 无法在真机或目标环境中验证的内容必须明确标记，不以推断代替验证。
