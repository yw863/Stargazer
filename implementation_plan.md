# StarGazer 工程实施计划

## Context

StarGazer 是面向城市天文爱好者的观测规划工具。MVP 仅支持 C/2025 R3 彗星，覆盖长三角。系统由 React 前端 + Dify 多 Agent 编排 + 若干 Python 辅助脚本组成。目前仓库仅含 `CLAUDE.md`、`PRD_StarGazer.md`、`data/horizons_sample.json`、`data/cobs_sample.json` 四个文件，尚无任何代码。本计划给出从 0 到可演示 MVP 的工程路径，不包含实际编码动作。

---

## 一、模块清单与职责边界

### A. 后端 Python 辅助工具（Dify 自定义工具，`backend/tools/`）

| 模块 | 输入 | 输出 | 依赖 |
|------|------|------|------|
| `cobs_parser.py` | COBS API 原始响应（JSON 格式，`format=json`） | `list[{date, magnitude, obs_method, aperture}]`，按日聚合的中位星等 | 无 |
| `horizons_parser.py` | Horizons API JSON 响应（`result` 字段纯文本） | 结构化 ephemeris：`list[{date, T_mag, r, delta, S_O_T, leading_trailing, T_O_M, moon_illu}]` | 无 |
| `comet_model.py` | COBS 日均 m + Horizons 对应日的 r/Δ | 拟合出的 `{H, n, rmse}`；给定未来日期的预测星等 | `cobs_parser`、`horizons_parser`、scipy |
| `weather_processor.py` | 7Timer ASTRO/CIVIL JSON + 目标日期 + best_window | 夜间时段聚合数据 + 一票否决结果 + weather_score；source 标签 | 无 |
| `haversine.py` | 两组经纬度 | 直线距离（km） | 无 |
| `amap_client.py`（可选封装） | 出发/到达经纬度 + 交通模式 | transit_options 列表 | 高德 Web 服务 Key |

### B. 每日定时任务（`backend/daily_job/`）

| 模块 | 输入 | 输出 | 依赖 |
|------|------|------|------|
| `daily_fit.py` | `data/events.json` 中的 event_id | 写入缓存 `data/cache/{event_id}_fit.json`，结构见 PRD 6.3 | 以上 A 组全部工具、COBS/Horizons API |

### C. Dify Workflow（云端配置，非代码）

| Agent | 输入 | 输出 | 依赖 |
|-------|------|------|------|
| Agent 1 天象分析 | 用户经纬度+日期+设备+event_id | 观测需求单（PRD 5.4） | 缓存、`horizons_parser`（实时 topocentric 查询 B） |
| Agent 2 地点筛选（RAG） | 用户经纬度+交通方式+max_bortle | 候选地点列表 | `haversine`、Dify 知识库 |
| Agent 3 环境评估 | 候选地点+日期范围 | weather_by_date + 一票否决过滤后列表 | `weather_processor`、7Timer |
| Agent 4 交通规划 | 出发地+候选地点+交通偏好 | transit_options | `amap_client`、高德 API |
| 编排层 | 四 Agent 输出 | `/api/plan` 响应 JSON | 综合评分公式 |

### D. 数据资产（`data/`）

| 文件 | 内容 |
|------|------|
| `events.json` | 事件元数据（PRD 6.2），MVP 含 1 个彗星 + 2 个流星雨占位 |
| `locations.json` | 观测地点知识库（PRD 6.1），长三角 15-20 条，上传至 Dify 知识库 |
| `cache/{event_id}_fit.json` | 每日拟合结果（PRD 6.3），由 `daily_fit.py` 生成 |

### E. 前端模块（`frontend/src/`）

| 模块 | 职责 | 依赖 |
|------|------|------|
| `views/EventsView` | 视图一，事件总览卡片 | `mocks/events.json` 或 `/api/events` |
| `views/PlanInputView` | 视图二，输入表单（原地展开过渡） | 浏览器 Geolocation、高德 JS SDK（地理编码） |
| `views/ResultView` | 视图三，摘要+地图+对比表格+方案卡片 | `/api/plan` |
| `components/EventCard` / `SummaryBar` / `LocationMap` / `CompareTable` / `PlanCard` | 原子组件 | Impeccable 生成 |
| `hooks/useGeolocation` / `useAmapGeocode` | 定位与地理编码 | 高德 JS API Key（`VITE_AMAP_JS_KEY`） |
| `mocks/` | 前端联调 mock，详见第五节 | 无 |
| `styles/theme.css` | 深色主题、仪表盘读数排版规范 | 参照 `.impeccable.md` |

---

## 二、开发顺序与阶段划分

### 阶段 0 · 基础设施（串行，先行）✅
1. 初始化仓库骨架（`frontend/`、`backend/`、`data/`、`.env`、`.gitignore`）。
2. 创建 `data/events.json` 与 `data/locations.json`（events 3 条种子，locations 空数组等用户录入）。
3. Vite + React 初始化，深色主题 CSS 变量落地，默认内容清空。
4. 执行 `npx skills add pbakaus/impeccable` 与 `/impeccable teach`（前端开发前执行）。

### 阶段 1 · 后端数据层（可多数并行）
以下模块无相互依赖，可**并行**开发：
- `haversine.py`
- `cobs_parser.py`（JSON 格式）
- `horizons_parser.py`（基于 `data/horizons_sample.json` 开发与单测）
- `weather_processor.py`（需先取一份真实 7Timer 样本）

完成上述后，**串行**：
- `comet_model.py`（依赖 cobs_parser + horizons_parser）
- `daily_fit.py`（依赖以上全部 + 缓存写入约定）
- `amap_client.py`（独立，可并行，需要 Web 服务 Key）

### 阶段 2 · 前端骨架（与阶段 1 并行）
- 全局主题、字体、排版规范落地（深色、读数式）
- 视图一 → 视图二 → 视图三 三态切换（基于 mock）
- 地图组件接入高德 JS API

### 阶段 3 · Dify 编排（依赖阶段 1 产出与缓存格式）
- 上传 `locations.json` 至 Dify 知识库
- 按顺序搭建 Agent 1 → Agent 2 → Agent 3 / 4（3 与 4 并行）→ 编排层
- 将 Python 工具注册为 Dify 自定义工具

### 阶段 4 · 前后端联调
- 前端从 mock 切换到真实 `/api/plan`
- 端到端走通 C/2025 R3 的一个上海用户场景

---

## 三、数据流验证节点

在以下节点**必须人工验证**后再推进：

1. **COBS 解析后**：抽查 5 条记录，确认 `obs_date`、`magnitude`、`obs_method` 提取无误；按日聚合的中位星等与原始观测分布吻合。
2. **Horizons 解析后**：用 `horizons_sample.json` 核对 2026-04-01 行：r≈0.6698、Δ≈1.2487、T-mag≈10.424、S-O-T=32.31/L、MN_Illu≈98.7。字段对齐即通过。
3. **拟合结果 H、n**：参考 C/2025 R3 Horizons 给定 M1=11.9、k1=11.25。自建拟合的 H 应落在 5-13 区间，n 应落在 2-8 区间。若严重偏离（如 n<0 或 H>20），停下排查再继续 `daily_fit`。
4. **缓存文件生成后**：比对 `data/cache/{event_id}_fit.json` 与 PRD 6.3 字段一一对应，ephemeris 覆盖未来 30 天逐日。
5. **Agent 1 输出**：对 2026-04-25（PRD 示例中 S-O-T=3.7° 的日期）验证 `observable:false` 并带 reason。
6. **Agent 3 降级路径**：构造超出 ASTRO 72h 的日期，验证降级至 CIVIL，`transparency:null` 且前端对比表格列显示「—」。
7. **编排层 JSON**：与 PRD 7.2 Response 字段逐一比对后再交付前端联调。
8. **前端视图一→二过渡**：确认是**原地展开**而非页面跳转或分栏布局（PRD 明确点名）。

---

## 四、已确认的技术决策

1. **COBS 格式**：采用 `format=json`，`cobs_parser.py` 按 JSON 结构（`objects` 数组）解析。
2. **光变拟合公式**：经典形式 `m = H + 5·log10(Δ) + 2.5·n·log10(r)`，scipy curve_fit 求 H、n。
3. **COBS 观测筛选**：保留所有有效目视星等观测，不按方法/口径过滤。同日多条取中位数；剔除偏离当日中位数 > 1.5 mag 的异常值。
4. **每日定时任务载体**：GitHub Actions（`schedule: cron`），在 runner 上执行 `daily_fit.py`，结果自动 commit 回仓库。
5. **缓存存储**：MVP 阶段使用仓库内 `data/cache/*.json`。Dify 自定义工具通过 raw file URL 读取。后续视并发迁移至对象存储。
6. **`locations.json`**：用户手动录入 15-20 条长三角地点（沪/杭/宁周边），同时覆盖公共交通与仅自驾两类。
7. **高德 Key**：前端用 `VITE_AMAP_JS_KEY`（Vite 环境变量前缀），后端用 `AMAP_WEB_SERVICE_KEY`，均通过环境变量注入。
8. **前端脚手架**：Vite + React。

---

## 五、Mock 数据策略

前端开发阶段所有网络请求走 mock。mock 文件放 `frontend/src/mocks/`，与 PRD 第 7 节一一对应：

| Mock 文件 | 对应端点 | 备注 |
|-----------|----------|------|
| `events.json` | `GET /api/events`（PRD 7.1） | 3 条：1 个 active 彗星 + 2 个 coming_soon 流星雨 |
| `plan.response.shanghai.json` | `POST /api/plan`（PRD 7.2） | 上海出发、3 日范围、无车、双筒的典型返回；含 best_date、date_notes、6 条 recommendations |
| `plan.response.edge-nodata.json` | `POST /api/plan` 边界 | 日期范围全部超 7 天 → 触发「天气预测暂不可用」分支 |
| `plan.response.edge-unobservable.json` | `POST /api/plan` 边界 | 所有日期 S-O-T<15° → 前端展示「所选日期全部不可观测，建议调整」 |
| `plan.response.edge-civil-fallback.json` | `POST /api/plan` 边界 | 降级 CIVIL，`transparency:null`，对比表格该列「—」 |
| `amap.geocode.sample.json` | 高德地理编码前端调用 | 用于 `useAmapGeocode` 离线调试 |

所有 mock 字段严格匹配 PRD 7 节 schema，后端就绪后仅需切换 fetch 的 base URL 即可。

---

## 六、外部 API 地址

| API | URL |
|-----|-----|
| COBS（JSON 格式） | `https://cobs.si/api/obs_list.api?format=json&des=C/2025%20R3` |
| JPL Horizons（地心，Quantities 9,19,20,23,25） | `https://ssd.jpl.nasa.gov/api/horizons.api?format=json&COMMAND=%27C/2025%20R3%27&CENTER=%27500@399%27&MAKE_EPHEM=YES&TABLE_TYPE=OBSERVER&START_TIME=%272026-04-01%27&STOP_TIME=%272026-04-05%27&STEP_SIZE=%271d%27&QUANTITIES=%279,19,20,23,25%27` |

---

## 验证与交付

- **端到端验证**：上海（31.23, 121.47）用户、2026-04-22 至 2026-04-24、无车、双筒，最终返回与 PRD 7.2 示例形状一致的 JSON，前端能正确渲染三个视图。
- **降级验证**：人为把日期推到 14 天外，验证 CIVIL 降级；再推到超 7 天，验证「暂不可用」。
- **不可观测验证**：模拟 S-O-T<15° 的日期（构造 mock 或等自然窗口），验证提示文案。
