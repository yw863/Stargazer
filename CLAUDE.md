# CLAUDE.md — StarGazer 项目规范

> 本文件是 Claude Code 的项目说明书。每次启动时请先阅读本文件和 PRD，再开始任何开发工作。

## 项目概述

StarGazer 是一个面向城市天文爱好者的观测规划工具。用户选择天文事件、输入所在位置和约束条件，系统通过多 Agent 编排自动聚合天象数据、光污染、天气预测、交通路线等信息，输出综合推荐的观测地点和出行方案。

MVP 阶段仅支持 C/2025 R3 彗星，地点覆盖长三角地区。

## 核心文档

- `PRD_StarGazer.md`：完整产品需求文档，包含功能定义、Agent 编排架构、数据 Schema、API 契约、评分权重等所有产品细节。**开发任何功能前必须先查阅 PRD 中对应章节。**

## 技术栈

| 层级 | 选型 |
|------|------|
| 前端 | React（单页应用） |
| 后端 Agent 编排 | Dify workflow |
| RAG 知识库 | Dify 内置知识库模块 |
| 彗星亮度预测 | Python（scipy curve_fit） |
| 天文星历 | JPL Horizons API |
| 彗星观测数据 | COBS API（JSON 格式） |
| 天气 | 7Timer（ASTRO 优先，CIVIL 降级） |
| 交通路线 + 地理编码 | 高德地图 API |
| 部署 | 前端 Vercel，后端 Dify 云端 |

## 前端开发规范

### 设计原则

本项目有明确的设计基调，前端开发必须遵循：

**基调关键词**：神秘、简约、优雅、呼吸感；克制的浪漫、精密工具感。

**具体要求**：
- 深色系为主，呼应夜空。不要用明亮的白色背景或高饱和度色彩。
- 排版留白充分，信息密度适中。数据呈现优先于装饰元素。
- 文案风格为「仪表盘读数式」：用中点「·」分隔结构化短语，不用完整叙述句。
- 不使用感叹号、语气词、emoji。语气克制、陈述性。
- 天文术语保持专业表达（Bortle 等级、星等、高度角），不做通俗化降级。
- 字体选择应体现科学感和优雅感，避免过于随意的字体。

**关键文案（已确定，不可更改）**：
- 视图一副标题：「Do Look Up——」
- 视图一主标题：「近日可见：」
- 视图二不设引导语，直接展示表单
- 视图三观测条件摘要使用读数式排列

### 设计 Skills 参照

本项目使用 **Impeccable**（`pbakaus/impeccable`）作为前端设计 skill，它构建在 Anthropic 官方 frontend-design skill 之上，提供更深度的设计控制和反模式检测。

**安装方式**：在项目根目录执行 `npx skills add pbakaus/impeccable`，会自动在 `.claude/skills/` 下安装 skill 文件。

**初始化（必须执行一次）**：安装后运行 `/impeccable teach`，按引导填写项目设计上下文。以下是本项目的设计上下文，供 teach 流程参考：

- **Target audience**：城市天文爱好者（入门至中级），懂基础天文术语，追求高效决策工具
- **Tone / Aesthetic direction**：refined minimalism + dark observatory aesthetic。深色系为主，呼应夜空。克制的浪漫——安静的期待感而非社交媒体式兴奋。精密工具感而非内容社区感
- **Differentiation**：仪表盘读数式的数据呈现（中点分隔短语），让用户感觉在操作一个精密天文仪器而非浏览一个网站
- **Constraints**：React SPA，深色主题，不使用白色背景，术语保持专业不降级

生成的 `.impeccable.md` 文件会被 Impeccable 的所有后续命令自动读取。

**可选的 Impeccable 命令**（开发过程中按需使用）：
- `/impeccable craft`：基于设计上下文生成组件
- `/impeccable typeset`：排查和修复排版问题
- `/impeccable audit`：运行可访问性和性能检查
- `/impeccable critique`：对现有界面给出设计反馈
- `/impeccable polish`：改进布局、间距和视觉节奏

### 视图结构

本项目是单页应用（SPA），通过状态切换实现三个视图：

1. **视图一（事件总览）**：展示近期天文事件卡片。MVP 仅 3 个事件（1 个可交互 + 2 个占位）。
2. **视图二（观测规划输入）**：视图一点击事件后原地过渡展开，不跳转新页面。顶部保留事件标识和返回箭头。包含 4 个输入字段。
3. **视图三（推荐结果）**：包含观测条件摘要、地图、对比表格、观测方案卡片。

视图一 → 视图二的过渡方式是**原地展开**，不是分栏布局，不是页面跳转。

### 数据对接

前端开发阶段使用 mock 数据，JSON 结构严格遵循 PRD 第 7 节的 API 契约定义。后端完成后只需切换数据源。

mock 数据文件放在 `/src/mocks/` 目录下。

### 地图组件

结果页需要展示交互式地图（候选地点分布）。MVP 阶段使用高德地图 JS API。

**注意：高德有两个独立的 Key，走不同路径**：
- **JS API Key**：前端使用，加载地图组件。通过环境变量 `VITE_AMAP_JS_KEY` 引用，不得硬编码。
- **Web 服务 Key**：后端使用（Dify），调用路径规划和地理编码 API。

前端代码中通过 `import.meta.env.VITE_AMAP_JS_KEY` 获取 Key 初始化高德地图 SDK。
安全密钥通过 `import.meta.env.VITE_AMAP_SECURITY_CODE` 获取，用于高德 JS API 2.0 安全校验。

## 后端开发规范

### Dify Workflow 编排

后端在 Dify 中搭建，共 4 个 Agent + 1 个编排层，详见 PRD 第 5 节。

Claude Code 在后端开发中的角色是编写以下辅助代码：

1. **COBS 数据解析器**：解析 COBS JSON 格式（`format=json`），提取日期和表观星等。
2. **彗星光变拟合脚本**：用 scipy curve_fit 拟合 H 和 n，输入 COBS 观测数据 + Horizons 星历数据。
3. **Horizons API 响应解析器**：解析嵌在 JSON `result` 字段中的纯文本表格，提取 r、Δ、S-O-T、T-O-M 等字段。
4. **7Timer 数据处理器**：解析 JSON，按 timepoint 计算实际时间，提取夜间时段数据，实现 ASTRO → CIVIL 降级逻辑。
5. **Haversine 距离计算工具**：输入两组经纬度，输出直线距离（km），用于 Agent 2 的 600km 预筛。

这些脚本将部署为 Dify 自定义工具。

### 每日定时任务

需要配置一个每日凌晨运行的定时任务，流程：
1. 调用 COBS API 拉取最新观测数据
2. 调用 Horizons API（地心，Quantities 9,19,20,23,25）获取历史和未来 30 天的 r、Δ 等
3. 运行拟合脚本，更新 H 和 n
4. 将拟合结果和星历数据写入缓存

### API Key 管理

所有 API Key 通过环境变量注入，不得硬编码在代码中。

**前端环境变量**（`.env` 文件，已加入 `.gitignore`）：
- `VITE_AMAP_JS_KEY`：高德地图 JS API Key（地图展示用）
- `VITE_AMAP_SECURITY_CODE`：高德地图安全密钥（JS API 2.0 安全校验）

**后端环境变量**（Dify 环境配置）：
- `AMAP_WEB_SERVICE_KEY`：高德地图 Web 服务 Key（路径规划 + 地理编码用）

Horizons、COBS、7Timer 均为免费开放 API，不需要 Key。

## 项目目录结构（建议）

```
stargazer/
├── CLAUDE.md                    # 本文件
├── PRD_StarGazer.md             # 产品需求文档
├── .impeccable.md               # Impeccable 设计上下文（/impeccable teach 生成）
├── .env                         # 环境变量（不提交到 git）
├── .gitignore
├── .claude/                     # Impeccable skill 文件（npx skills add 安装）
│   └── skills/
├── frontend/                    # React 前端
│   ├── src/
│   │   ├── components/          # UI 组件
│   │   ├── views/               # 三个视图
│   │   ├── mocks/               # Mock 数据
│   │   ├── hooks/               # 自定义 hooks
│   │   ├── utils/               # 工具函数
│   │   └── styles/              # 全局样式和主题
│   ├── public/
│   └── package.json
├── backend/                     # Dify 辅助脚本
│   ├── tools/                   # Dify 自定义工具
│   │   ├── cobs_parser.py       # COBS JSON 格式解析
│   │   ├── comet_model.py       # 彗星光变拟合
│   │   ├── horizons_parser.py   # Horizons 响应解析
│   │   ├── weather_processor.py # 7Timer 数据处理 + 降级逻辑
│   │   └── haversine.py         # 距离计算
│   ├── daily_job/               # 每日定时任务
│   │   └── daily_fit.py         # 拉取数据 + 拟合 + 缓存
│   └── requirements.txt
└── data/
    ├── locations.json            # 观测地点知识库
    └── events.json               # 天文事件配置
```

## 编码规范

- Python：遵循 PEP 8，使用 type hints
- React：函数式组件 + Hooks，不使用 class 组件
- 命名：组件用 PascalCase，文件名用 kebab-case，变量和函数用 camelCase
- 所有外部 API 调用都需要 try-catch 错误处理和超时设置
- 注释用中文，代码和变量名用英文

## 工作方式

**你是这个项目的技术 Lead，不是逐行编码的工具。** 你应该：

1. 收到任务后，先查阅 PRD 对应章节理解完整上下文。
2. 自主决策技术细节（组件拆分、状态管理、库选型等），不需要逐项请示。
3. 如果 PRD 中有矛盾或遗漏，指出问题并给出建议方案，不要猜测或跳过。
4. 交付时说明你做了什么技术决策以及为什么，而不是解释每行代码。

**不要做的事**：
- 不要在没有查阅 PRD 的情况下凭假设开发
- 不要在前端使用明亮的白色主题或默认 UI 框架样式
- 不要把 API Key 硬编码到代码里
- 不要用 class 组件
- 不要在文案中使用感叹号、emoji 或口语化表达
