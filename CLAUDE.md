# CLAUDE.md — StarGazer 项目规范

> 本文件是 Claude Code 的项目说明书。每次启动时请先阅读本文件、PRD 与设计规范，再开始任何开发工作。

## 项目概述

**StarGazer · 观象指北** 是一个面向城市天文爱好者的观测规划工具。用户选择天文事件、输入所在位置和约束条件，系统通过多 Agent 编排自动聚合天象数据、光污染、天气预测、交通路线等信息，输出综合推荐的观测地点和出行方案。

MVP 阶段仅支持 C/2025 R3 彗星，地点覆盖长三角地区。

## 核心文档

- `PRD_StarGazer.md`（v1.9）：完整产品需求文档，包含功能定义、Agent 编排架构、数据 Schema、API 契约、评分权重等所有产品细节。**开发任何功能前必须先查阅 PRD 中对应章节。**
- `frontend_v2/DESIGN_SPEC.md`：第二版前端的设计规范，包含色板、字体、视图布局、过渡动效、组件设计、TypeScript 类型与 mock 数据。**前端 v2 的所有视觉与交互决策以此文件为准。**

## 项目阶段与目录现状

项目当前处于 **第二版前端重设计** 阶段：

- `backend/`：完整后端脚本，已通过数据源验证。
- `frontend/`：**第一版前端（已冻结）**。保留作为参考与回退，**不再修改**。
- `frontend_v2/`：**第二版前端（当前开发目标）**。所有新前端代码与设计实现都写入此目录。

修改前端时只动 `frontend_v2/`，不要改动 `frontend/`。

## 技术栈

| 层级 | 选型 |
|------|------|
| 前端 v2 | React + **TypeScript** + **Tailwind**，**Three.js**（背景星点 + noise depth 层），**Framer Motion**（过渡动效，含 `layoutId` 共享元素动画） |
| 视口范围 | **桌面优先（1280px+）**，MVP 不处理移动端/平板断点 |
| 后端 Agent 编排 | Dify workflow（含 LLM tool calling 与 LLM 文案生成节点） |
| RAG 知识库 | Dify 内置知识库模块 |
| 彗星亮度预测 | Python（scipy curve_fit） |
| 天文星历 | JPL Horizons API（双查询架构 + 地点级并行 topocentric 查询） |
| 晨昏时刻计算 | Python（skyfield）— `backend/tools/twilight_calculator.py`，本地计算无 API 调用 |
| 彗星观测数据 | COBS API（**ICQ 固定宽度文本**，非 JSON） |
| 天气 | 7Timer（ASTRO 优先，CIVIL 降级） |
| 交通路线 + 地理编码 | 高德地图 API |
| 部署 | 前端 Vercel，后端 Dify 云端 |

## 前端开发规范（frontend_v2）

> **所有视觉细节、色值、字号、布局比例、过渡时长以 `frontend_v2/DESIGN_SPEC.md` 为准。** 本节是项目级别的硬约束与高频参考。

### 设计基调

**关键词：Neo-minimalism · Approachable Sophistication · 神秘 · 优雅 · 克制的浪漫 · 精密仪器感**

核心原则（详见 DESIGN_SPEC.md §2）：

- **不是「极简到只剩文字」，而是「留下来的一切都是设计」**。深色基底上要有可见的层次：装饰细线、低不透明度纹理、版面节奏、字号张力。
- **数据即视觉**。数字、坐标、星等本身就是排版材料，像排一页古典星历表。
- **每个视图至少有一处「值得多看一眼」的视觉锚点**——视图一是 ~5.1 mag 的英雄数字，视图二是共享元素动画的落位瞬间，视图三是弧形导航 + 晨昏渐变 / 高度角复合图。
- **One accent, used with intention**：`#5b8dd9` 仅用于当前最重要的交互元素或数据点；`--accent-muted` 可作为氛围色更自由地使用。
- **The risk of austerity is as real as the risk of excess**——「Dark mode nothing」（一个近黑屏 + 几行字）也是失败。当不确定时，倾向于多加一条 hairline、一个排版细节，而非留空。

参照对象（DESIGN_SPEC.md §2）：✅ Dieter Rams / Cartier Santos / Bloomberg Terminal best moments；❌ 太空屏保、通用 SaaS、shadcn 默认样式、纯黑屏 + 文字。

### 色板（CSS 变量，硬约束）

```css
--bg-base: #080c14;        /* 视口基底 */
--bg-elevated: #0d1220;    /* 浮层、卡片 */
--hairline: rgba(91, 141, 217, 0.12);
--text-primary: rgba(255, 255, 255, 0.87);
--text-secondary: rgba(255, 255, 255, 0.55);
--text-tertiary: rgba(255, 255, 255, 0.32);
--accent: #5b8dd9;          /* 唯一强调色 */
--accent-muted: rgba(91, 141, 217, 0.15);
--warning: #c9954a;
--positive: #5a9e6f;
```

不得引入其他色相。功能色（warning/positive）保持低饱和。

### 字体（硬约束）

| 用途 | 字体 |
|------|------|
| 品牌 wordmark「StarGazer」 | **Cinzel** 400/700（Google Fonts），letter-spacing ~0.15em |
| 标题 / 文学性中文 | **Cormorant Garamond** 300/400/600（英文）+ **Noto Serif SC** 300/400/600（中文） |
| 正文 / UI 标签 | **DM Sans** 300/400/500 |
| **所有数字读数**（星等、坐标、时间、距离） | **Geist Mono**（CDN: `https://cdn.jsdelivr.net/npm/geist@1.2.0/dist/fonts/geist-mono/GeistMono-Variable.woff2`） |

**禁止**使用 Inter、Roboto、Arial、系统 sans-serif 作为正文或展示字体。所有数值必须 Geist Mono。

### 品牌标识

每个视图左上角固定渲染品牌 wordmark：

- 「StarGazer」（Cinzel，~24–28px，混合大小写呈现 small-caps 效果）
- 旁边或下方「观象指北」（Noto Serif SC，~12px，`--text-tertiary`）

视图切换时品牌不变。

### 文案规范（仪表盘读数式）

- **中文为主**，天文术语保持专业（Bortle 等级、星等、高度角、方位角），不通俗化降级。
- **结构化短语用中点「·」分隔**：「目视星等 ~5.1 · 肉眼极限附近 · 昏星」，不写成完整叙述句。
- **不使用感叹号、语气词、emoji**。陈述性、克制。
- 不使用「最佳」「最适合」等主观评价词，用「条件最优」或直接以数据呈现。

**关键文案锚点（已确定，不可更改）**：

- 视图一副标题：「Do Look Up ——」（Cormorant Garamond，small-caps letter-spaced）
- 视图一主标题：「近日可见：」
- 视图一左栏定锚引文：Chet Raymo *The Soul of the Night* 的诗段（详见 DESIGN_SPEC.md §4，挂角引号 + raised cap 处理）
- 视图二顶部右侧标签：「观测请求 · REQUEST FORM」
- 视图二字段标签为双语：「所在位置 LOCATION」「观测日期 DATE RANGE」「交通方式 TRANSPORT」「观测设备 EQUIPMENT」
- 视图二加载文案为分阶段读数：「正在查询星历数据…」「正在评估天气条件…」「正在规划交通路线…」「正在综合排序…」
- 视图三顶部右侧标签：「观测结果 · RESULTS」
- 全局页脚签名：`STARGAZER · 观象指北 · 生成于 YYYY.MM.DD · 数据源 JPL Horizons / COBS / 7Timer`

### 视图结构（SPA，状态切换）

1. **视图一 · 天象概览**：两栏布局。左栏（~35–38%）为文学引文 + raised cap 排版氛围区；右栏（~62–65%）为副标题 / 主标题 / 事件垂直时间轴 + 节点。MVP 含 1 个可点击事件（C/2025 R3）+ 2 个「即将上线」占位。
2. **视图二 · 观测请求**：两栏布局，左右内容相对视图一互换——左栏是从视图一共享元素动画飞落的事件上下文（只读），右栏是 4 个输入字段表单 + 提交按钮。
3. **视图三 · 观测结果**：「天地分栏」——左栏（~40–42%）为「天」（天象上下文 + 当晚晨昏渐变 / 高度角复合图 + 选中地点的观测细节），右栏（~58–60%）为「地」（弧形导航 floating over 暗色地图，地图边缘 feather 进 `--bg-base`）。**没有传统对比表格**，所有地点对比通过弧形导航 + 关键指标读数完成。

### 过渡动效（Framer Motion）

- **视图一 → 视图二：共享元素动画（layoutId）**——事件名、类型 tag、参数读数、~5.1 hero 数字从视图一右栏飞落至视图二左栏，hero 数字尺寸明显收缩；非共享元素 fade-out 后表单字段错峰 fade-in。整体感觉为单一连贯姿态，非三段离散动画。背景星点跨视图连续，不重置。
- 兜底方案：若共享元素动画实现成本过高，整页 slide + fade 也可接受，但事件摘要必须已就位于左栏。
- **视图二 → 视图三**：clean cross-fade，左栏事件上下文持续，右栏由表单切换为弧形导航 + 地图。
- 微交互 150–250ms，布局位移 400–500ms，ease-out。必须支持 `prefers-reduced-motion`。

### Three.js 背景层

跨所有视图持续渲染、不在过渡时重置：

- **星点粒子**：30–50 个，三档大小，3–5 个最大粒子带光晕和缓慢呼吸。极慢漂移。最大档粒子加载时应肉眼可辨。
- **可选 noise depth 层**：fragment shader + simplex noise，低不透明度，在深蓝范围内提供「活的暗」纹理。校准方法：截图 200% 放大应能看到颗粒结构。

### 视图三特别说明：晨昏渐变 / 高度角复合图

DESIGN_SPEC.md §7 中定义的核心可视化。要点：

- 横轴：日落前 1 小时 → 日出后 1 小时（白天部分不渲染）。
- 渐变带：暮光暖色 → 民昏 → 天昏 → 深夜 → 天曙 → 日出，**连续渐变非硬色阶**，肩部必须可见暖色。
- 闲置态（未选地点）：仅渲染渐变带 + 下方晨昏刻度。
- 激活态（选中地点）：高度角曲线 fade-in（半正弦插值，基于该地点的 `target_passage`），上方添加目标升 / 落 / 峰值刻度，观测窗口区段以 `--accent-muted` 高亮。
- **晨昏值与曲线均使用「选中地点」的 `twilight` 与 `target_passage`**，未选时使用 `observation_summary` 基准值。切换时 cross-fade。

### 视图三特别说明：弧形导航

- 静态 SVG 弧段（凸面朝右、朝向地图），不旋转、不拖拽、不物理化。
- 6 个节点等角分布在双线轨道上，外加刻度小线条与稀疏装饰粒子。
- 节点 hover/选中影响地图标记（双向联动）。所有标签水平排版，不沿弧线旋转。
- 选中后：地图缩放至该地点 + 显示交通卡片浮层 + 左栏下区淡入观测建议。

### 数据对接

前端开发阶段使用 mock 数据，文件放在 `frontend_v2/src/mocks/`，结构严格遵循 DESIGN_SPEC.md §9 的 TypeScript 类型与 PRD 第 7 节的 API 契约。从一开始就按这些类型定义组件 props，后端完成后只需切换数据源。

### 地图组件

视图三右栏底层地图。MVP 阶段使用高德地图 JS API（深色样式），通过 feathered gradient mask 让边缘溶进 `--bg-base`。

**注意：高德有两个独立的 Key**：

- **JS API Key**：前端使用，加载地图组件。`import.meta.env.VITE_AMAP_JS_KEY`，不得硬编码。
- **JS API 安全密钥**：`import.meta.env.VITE_AMAP_SECURITY_CODE`，用于 JS API 2.0 安全校验。
- **Web 服务 Key**：后端使用（Dify），调用路径规划与地理编码 API。

### 实现校准（Screenshot Test）

DESIGN_SPEC.md §2 定义了三项截图自检，每完成一个视图都跑一次：

1. **「这是设计过的吗」**：拿给无上下文的人看，若回答「就是黑底加文字」，则视觉素材不足。
2. **「我该看哪里」**：眯眼看，是否能立刻识别视觉锚点。
3. **「它活吗」**：是否有渐变、粒子、字体张力、空间节奏，还是像终端窗口。

**最常见的失败模式是欠设计而非过度设计**。不确定时往「更显眼」的方向调，再回退。

## 后端开发规范

### Dify Workflow 编排

后端在 Dify 中搭建。架构详见 PRD §5：

- **Agent 1**：天象分析（Horizons 双查询架构、skyfield 晨昏、亮度预测）
- **Agent 2**：地点筛选（Haversine 距离 + 交通方式 + Bortle 三层过滤，唯一筛选环节）
- **Agent 3**：环境评估（7Timer ASTRO → CIVIL 降级，含一票否决与天气评分）
- **Agent 4**：交通规划（高德路径规划，不筛选只提供数据）
- **步骤 5.5**：地点星历与晨昏计算（per-location 并行 Horizons topocentric + skyfield twilight）
- **步骤 5.6**：地形 × 方位冲突检测（**LLM tool calling**，输出 terrain_compatibility）
- **编排层**：综合排序（天气 50% / 光污染 25% / 交通 15% / 地形方位兼容性 10%，top 6）
- **步骤 5.7**：观测指导生成（**LLM**，针对当晚条件生成个性化 notes，失败回退到知识库静态文本）

Claude Code 在后端开发中负责编写以下辅助代码：

1. **COBS 数据解析器**（`backend/tools/cobs_parser.py`）：解析 COBS **ICQ 固定宽度文本**（非 JSON），提取日期和表观星等。
2. **彗星光变拟合脚本**（`backend/tools/comet_model.py`）：用 scipy curve_fit 拟合 H 和 n。
3. **Horizons API 响应解析器**（`backend/tools/horizons_parser.py`）：解析嵌在 JSON `result` 字段中的纯文本表格（地心查询字段 + topocentric AZ/EL），含 `target_passage` 提取。
4. **7Timer 数据处理器**（`backend/tools/weather_processor.py`）：解析 JSON，按 timepoint 计算实际时间，提取夜间数据，实现 ASTRO → CIVIL 降级与一票否决逻辑。
5. **Haversine 距离计算工具**（`backend/tools/haversine.py`）：用于 Agent 2 的 600km 预筛。
6. **晨昏时刻计算工具**（`backend/tools/twilight_calculator.py`）：基于 skyfield，输入经纬度 + 日期，输出 `twilight` 对象（日落 / 民昏 / 天昏 / 天曙 / 民曙 / 日出 / 月落）。纯本地计算，不调外部 API。

这些脚本部署为 Dify 自定义工具。

### 每日定时任务

每日凌晨自动执行：

1. 调用 COBS API 拉取最新观测（ICQ 文本）
2. 调用 Horizons API（地心，Quantities 9,19,20,23,25，STEP 1d）覆盖历史起始日 → 未来 30 天
3. 运行拟合脚本，更新 H 和 n
4. 写缓存：拟合结果 + 未来 30 天逐日 r、Δ、S-O-T、/L或/T、T-O-M、MN_Illu%、Horizons T-mag

### API Key 管理

所有 API Key 通过环境变量注入，**不得硬编码**。

**前端环境变量**（`frontend_v2/.env`，加入 `.gitignore`）：

- `VITE_AMAP_JS_KEY`：高德 JS API Key（地图展示）
- `VITE_AMAP_SECURITY_CODE`：高德 JS API 2.0 安全密钥

**后端环境变量**（Dify 环境配置）：

- `AMAP_WEB_SERVICE_KEY`：高德 Web 服务 Key（路径规划 + 地理编码）

Horizons、COBS、7Timer 均为免费开放 API，不需要 Key。

## 项目目录结构

```
stargazer/
├── CLAUDE.md                       # 本文件
├── PRD_StarGazer.md                # 产品需求文档（v1.9）
├── implementation_plan.md          # 实施计划
├── .env                            # 环境变量（不提交到 git）
├── .gitignore
├── frontend/                       # 第一版前端（已冻结，不再修改）
│   └── ...
├── frontend_v2/                    # 第二版前端（当前开发目标）
│   ├── DESIGN_SPEC.md              # 设计规范（前端 v2 视觉与交互的唯一真源）
│   ├── src/
│   │   ├── components/             # UI 组件（PascalCase）
│   │   ├── views/                  # ViewOne / ViewTwo / ViewThree
│   │   ├── mocks/                  # events.mock.json / plan.response.json
│   │   ├── hooks/
│   │   ├── utils/
│   │   ├── styles/                 # 全局 CSS 变量、Tailwind 配置
│   │   └── types/                  # TypeScript 类型定义（与 DESIGN_SPEC §9 对齐）
│   ├── public/
│   └── package.json
├── backend/                        # Dify 辅助脚本
│   ├── tools/
│   │   ├── cobs_parser.py
│   │   ├── comet_model.py
│   │   ├── horizons_parser.py
│   │   ├── weather_processor.py
│   │   ├── haversine.py
│   │   └── twilight_calculator.py  # 基于 skyfield 的晨昏计算
│   ├── daily_job/
│   │   └── daily_fit.py
│   └── requirements.txt
└── data/
    ├── locations.json               # 观测地点知识库
    └── events.json                  # 天文事件配置
```

## 编码规范

- **Python**：遵循 PEP 8，使用 type hints
- **React**：函数式组件 + Hooks，**不使用 class 组件**；前端 v2 全部使用 **TypeScript**
- **样式**：Tailwind 工具类 + 全局 CSS 变量定义色板，不允许在组件中硬编码色值
- **命名**：组件用 PascalCase，文件名用 kebab-case，变量和函数用 camelCase
- 所有外部 API 调用都需要 try-catch 错误处理和超时设置
- 注释用中文，代码和变量名用英文

## 工作方式

**你是这个项目的技术 Lead，不是逐行编码的工具。**

1. 收到任务后，先查阅 PRD 与 DESIGN_SPEC.md 对应章节理解完整上下文。
2. 自主决策技术细节（组件拆分、状态管理、库选型等），不需要逐项请示。
3. 如果 PRD / DESIGN_SPEC 中有矛盾或遗漏，指出问题并给出建议方案，不要猜测或跳过。
4. 交付时说明你做了什么技术决策以及为什么，而不是解释每行代码。

**不要做的事**：

- 不要在没有查阅 PRD 与 DESIGN_SPEC 的情况下凭假设开发
- 不要修改 `frontend/`（第一版已冻结），所有新前端代码都写入 `frontend_v2/`
- 不要在前端使用明亮的白色主题、shadcn 默认样式或任何饱和高的颜色
- 不要使用 Inter / Roboto / Arial / 系统 sans-serif 作为展示或正文字体；数字必须 Geist Mono
- 不要让视图退化成「Dark mode nothing」（黑底 + 几行字 + 没有任何视觉层次）
- 不要把 API Key 硬编码到代码里
- 不要用 class 组件
- 不要在文案中使用感叹号、emoji 或口语化表达
- 不要为视图三构建传统对比表格——地点对比通过弧形导航 + 节点旁的关键读数完成
