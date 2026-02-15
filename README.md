# ClaudeDevKit

**Claude Code 开发模板套件** — 极简设计，为 Claude Code CLI 提供项目治理和标准化工作流。

---

## 目录

- [项目概述](#项目概述)
- [核心特性](#核心特性)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [核心文件](#核心文件)
- [文件等级保护](#文件等级保护)
- [命令系统](#命令系统)
- [Skills 系统](#skills-系统)
- [目标管理](#目标管理)
- [自动检测规则](#自动检测规则)

---

## 项目概述

### 是什么？

ClaudeDevKit 是一个用于 **Claude Code CLI** 的极简项目模板，通过 **8 个核心文件** 提供 AI 辅助开发的治理能力。

### 解决什么问题？

| 问题 | ClaudeDevKit 解决方案 |
|------|----------------------|
| AI 随意修改核心代码 | 文件等级保护（active/stable/core） |
| 提交信息不规范 | `/commit` 命令 + Conventional Commits |
| 项目状态不透明 | PROJECT.md 统一管理模块和历史 |
| API 被无意破坏 | API 变更检测 + 提示更新文档 |
| 开发焦点分散 | 目标管理 + 单一焦点模式 |

### 核心理念

> **极简但可控** — 8 个文件完成治理，Git 提交后自动更新状态。

---

## 核心特性

- **8 个核心文件** — PROJECT.md + 4 commands + 3 skills
- **文件等级保护** — active / stable / core 三级保护
- **Skills 治理系统** — workspace-governor + api-governor + goal-tracker
- **目标管理** — 单一焦点模式，追踪开发进度
- **自动状态更新** — 提交后自动追加历史、建议升级
- **标准化工作流** — Conventional Commits + 自动检测
- **只读问答模式** — `/ask` 命令安全分析代码

---

## 目录结构

```
ClaudeDevKit/
│
├── .claude/                      # AI 控制层（核心）
│   ├── PROJECT.md                # 唯一配置文档
│   ├── commands/
│   │   ├── ask.md                # /ask - 只读问答
│   │   ├── commit.md             # /commit - 提交流程
│   │   ├── goal.md               # /goal - 目标管理
│   │   └── readproject.md        # /readproject - 项目概览
│   └── skills/
│       ├── api-governor.md       # API 契约治理
│       ├── workspace-governor.md # 工作区治理
│       └── goal-tracker.md       # 目标追踪
│
├── backend/                      # 后端代码目录
├── frontend/                     # 前端代码目录
├── deploy/                       # 部署配置
│
├── docs/
│   ├── CURRENT_GOAL.md           # 当前开发目标
│   └── api/
│       └── API.md                # API 文档（可选）
│
└── README.md                     # 项目说明
```

---

## 快速开始

### 1. 使用模板

```bash
# 克隆或复制
git clone <repo-url> my-project
cd my-project
```

### 2. 配置项目

编辑 `.claude/PROJECT.md`：

```markdown
## 项目信息

| 字段 | 值 |
|------|-----|
| **名称** | my-project |
| **类型** | fullstack |
| **描述** | 我的项目描述 |
```

### 3. 定义模块

在 PROJECT.md 中添加模块：

```markdown
| 模块 | 路径 | Status | Level |
|------|------|--------|-------|
| my-module | `src/my-module/**` | dev | active |
```

### 4. 新会话时使用 /readproject

```bash
# 每次 Claude Code 新会话开始时执行
/readproject
```

这会输出项目信息、模块状态、当前目标、最近历史，帮助 AI 快速建立项目认知。

### 5. 开始开发

使用 Claude Code 正常开发，AI 会自动遵守治理规则。

---

## 核心文件

### 1. PROJECT.md

**唯一配置文档**，包含：

- 项目信息（名称、类型、描述）
- 模块定义（路径、状态、等级）
- 保护规则（文件保护、API保护）
- 当前目标（任务、状态、进度）
- 开发历史（自动追加）

### 2. commands/commit.md

**Git 提交流程**：

1. Pre-commit 检查（lint）
2. 检查保护文件（stable/core）
3. 生成 Commit Message（Conventional Commits）
4. 执行 Commit
5. **自动更新 PROJECT.md**
6. Push

### 3. commands/ask.md

**只读问答模式**：

- 禁止修改、创建、删除文件
- 用于代码分析、架构理解、Bug 分析

### 4. commands/goal.md

**目标管理模式**：

- 设置、查看、完成目标
- 单一焦点模式（一次一个主目标）
- 提交时自动询问目标进度

### 5. commands/readproject.md

**项目概览模式**：

- 新会话时快速建立项目认知
- 输出项目信息、模块状态、当前目标、最近历史
- 严格只读，不修改任何文件

---

## 文件等级保护

| 等级 | 含义 | 修改规则 |
|------|------|----------|
| `active` | 活跃开发 | 自由修改 |
| `stable` | 已稳定 | 需确认 |
| `core` | 核心保护 | 禁止自动修改 |

### 保护机制

```
修改 core 文件
    │
    ▼
⛔ Core Protection Warning
    │
    └─→ 操作阻止，需手动降级

修改 stable 文件
    │
    ▼
⚠️ Stability Modification Proposal
    │
    ├─→ 确认 → 允许修改
    │
    └─→ 拒绝 → 停止操作
```

---

## 命令系统

### /readproject — 项目概览

```bash
/readproject
```

**用途：** 新会话时执行，快速建立项目认知

**输出：**
- 项目信息（名称、类型、描述）
- 模块状态（路径、状态、保护等级）
- 当前目标（任务、状态、进度）
- 最近历史（最近 3 条提交）

**特性：**
- 严格只读
- 不修改任何文件
- 建议每次新会话先执行

---

### /ask — 只读问答

```bash
/ask <问题>
```

**示例：**
```bash
/ask 这个项目的认证流程是怎样的？
/ask 为什么这个函数会报错？
/ask 帮我分析这个模块的架构
```

**特性：**
- 严格只读
- 不生成补丁
- 联网需授权

### /commit — Git 提交

```bash
/commit
```

**流程：**
1. Lint 检查
2. 保护文件检测
3. API 变更检测
4. 目标进度检查
5. 生成 Conventional Commit
6. 提交
7. 自动更新 PROJECT.md
8. Push

### /goal — 目标管理

```bash
/goal                    # 查看当前目标
/goal set <任务描述>      # 设置新目标
/goal done               # 标记当前目标完成
/goal block <原因>       # 标记目标阻塞
/goal unblock            # 解除阻塞状态
```

**特性：**
- 单一焦点模式（一次一个主目标）
- 提交时自动询问目标完成状态
- 完成后提示设置新目标

---

## Skills 系统

Skills 是可复用的治理模块，被 `/commit` 命令调用执行保护逻辑。

### workspace-governor

**功能**：文件等级保护

| Level | 动作 |
|-------|------|
| `core` | 阻止修改，输出警告 |
| `stable` | 输出提案，等待确认 |
| `active` | 允许修改 |

**触发**：所有写操作前

### api-governor

**功能**：API 契约保护

| 变更类型 | 判定 |
|----------|------|
| 删除 API / 参数 | Breaking Change |
| 修改参数类型 | Breaking Change |
| 新增 optional 参数 | Non-Breaking |

**触发**：API 相关文件变更

### goal-tracker

**功能**：目标进度追踪

| 目标状态 | 动作 |
|----------|------|
| `in_progress` | 输出目标完成询问 |
| `completed` | 提示设置新目标 |
| `blocked` | 输出阻塞原因 |

**触发**：/commit 执行时

### Skills 与 Commands 关系

```
/commit
   │
   ├──→ workspace-governor (检查文件保护)
   │
   ├──→ api-governor (检查 API 变更)
   │
   ├──→ goal-tracker (检查目标进度)
   │
   └──→ 执行提交 + 更新 PROJECT.md
```

---

## 目标管理

ClaudeDevKit 提供目标管理能力，帮助你保持单一焦点。

### 核心理念

> **单一焦点** — 一次只关注一个核心任务

### 目标状态

| 状态 | 含义 |
|------|------|
| `in_progress` | 进行中 |
| `completed` | 已完成 |
| `blocked` | 阻塞中 |

### 使用示例

```
# 设置目标
/goal set 实现用户登录 API

# 查看目标
/goal

# 提交时检查
/commit
📌 Goal Progress Check
Current Goal: 实现用户登录 API
Is this goal completed? [y/N]

# 标记完成
/goal done
✅ Goal Completed!
What's your next goal?
```

### CURRENT_GOAL.md 文件格式

```markdown
## 目标信息

| 字段 | 值 |
|------|-----|
| **任务** | 实现用户登录 API |
| **状态** | in_progress |
| **优先级** | high |
| **创建日期** | 2026-02-15 |

## 完成标准

登录 API 通过测试，返回正确 token

## 进度记录

| 时间 | 进展 |
|------|------|
| 2026-02-15 | 开始实现登录逻辑 |
```

---

## 自动检测规则

### 提交后自动执行

1. **模块状态升级建议**
   - 条件：模块 `dev` + 最近 3 次提交无变动
   - 动作：建议升级为 `done` + `stable`

2. **API 变更检测**
   - 条件：检测到 API 文件变更
   - 动作：提示更新 `docs/api/API.md`

3. **保护文件警告**
   - 条件：修改 `stable` 或 `core` 文件
   - 动作：输出提示，等待确认

4. **目标进度检查**
   - 条件：执行 /commit 时
   - 动作：输出目标完成询问，更新进度记录

---

## 复杂度对比

| 指标 | 原框架 | 新框架 |
|------|--------|--------|
| 核心文件数 | 12+ | **8** |
| 配置行数 | ~800 行 | ~200 行 |
| 治理层级 | 4 层 | 1 层 |
| 文档同步 | 4 个文件 | 1 个文件 |
| Skills 支持 | 无 | **3 个** |
| 目标管理 | 无 | **支持** |

---

## 设计原则

| 原则 | 说明 |
|------|------|
| **极简** | 8 个文件完成核心治理 |
| **自动化** | Git 提交后自动更新状态 |
| **可保护** | 三级文件等级保护核心代码 |
| **可追溯** | PROJECT.md 统一记录历史 |
| **可聚焦** | 目标管理保持单一焦点 |

---

## License

MIT License
