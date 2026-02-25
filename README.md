# ClaudeDevKit

Claude Code 项目治理框架 — 三级文件保护、API 变更检测、目标追踪。

## Features

- **三级文件保护** — active / stable / core，防止 AI 乱改核心代码
- **API 契约保护** — 自动检测 Breaking Change
- **目标追踪** — 单一焦点模式，保持开发专注
- **自动状态管理** — 提交后自动更新项目文档
- **规范化提交** — Conventional Commits 自动生成

## Installation

```bash
cp -r ClaudeDevKit/.claude your-project/
cp -r ClaudeDevKit/docs your-project/
```

## Quick Start

### 0. 填写项目方案

将你的项目方案文档按照 `docs/ROADMAP.md` 的格式填写，替换原始内容：

```markdown
## 项目概览

| 字段 | 值 |
|------|-----|
| **名称** | your-project |
| **类型** | fullstack |
| **描述** | 项目描述 |
| **技术栈** | Node.js + React + PostgreSQL |

## 开发阶段

| 阶段 | 目标 | 状态 | 预计完成 |
|------|------|------|----------|
| Phase 1 | 用户认证系统 | in_progress | 2026-03-01 |
| Phase 2 | 核心功能开发 | todo | 2026-04-01 |

## 里程碑

| 里程碑 | 交付物 | 状态 | 日期 |
|--------|--------|------|------|
| v0.1 | MVP | in_progress | 2026-03-01 |
| v1.0 | 正式发布 | todo | 2026-06-01 |
```

### 1. 配置项目

编辑 `.claude/PROJECT.md`：

```markdown
## 项目信息

| 字段 | 值 |
|------|-----|
| **名称** | my-project |
| **类型** | fullstack |

## 模块列表

| 模块 | 路径 | Status | Level |
|------|------|--------|-------|
| auth | `src/auth/**` | dev | active |
| core | `src/core/**` | done | core |
```

### 2. 新会话开始

```bash
/readproject
```

### 3. 开发流程

```bash
/goal set 实现用户登录    # 设置目标
# ... 开发 ...
/commit                   # 提交（自动执行保护检查）
```

## Commands

| 命令 | 说明 |
|------|------|
| `/readproject` | 项目概览，新会话时执行 |
| `/ask <问题>` | 只读问答，安全分析代码 |
| `/goal` | 目标管理 |
| `/commit` | 提交流程，触发完整治理检查 |

### `/readproject`

新会话时执行，输出项目信息、模块状态、当前目标、最近历史。

### `/ask`

只读问答模式，用于代码分析、架构理解、Bug 分析。禁止修改任何文件。

```bash
/ask 这个项目的认证流程是怎样的？
/ask 为什么这个函数会报错？
```

### `/goal`

目标管理命令：

```bash
/goal                      # 查看当前目标
/goal set 实现用户登录 API   # 设置新目标
/goal done                 # 标记完成
/goal block 等待数据库配置   # 标记阻塞
/goal unblock              # 解除阻塞
```

### `/commit`

核心命令，执行完整治理流程：

1. Pre-commit 检查（lint）
2. 清理临时文件
3. 文件保护检查
4. API 变更检测
5. 目标进度检查
6. 生成 Conventional Commit
7. 执行提交
8. 更新状态文件
9. 更新 Git 历史
10. Push

## File Protection

| Level | 说明 | 修改规则 |
|-------|------|----------|
| `active` | 活跃开发 | 自由修改 |
| `stable` | 已稳定 | 需确认 |
| `core` | 核心保护 | 禁止 AI 自动修改 |

修改 `core` 模块时会被阻止，需手动降级后才能提交。

## Skills

Skills 是可复用的治理模块，被 `/commit` 命令调用：

| Skill | 职责 |
|-------|------|
| `workspace-governor` | 文件等级保护 |
| `api-governor` | API 契约保护，检测 Breaking Change |
| `goal-tracker` | 目标进度追踪 |

## Project Structure

```
.claude/
├── PROJECT.md              # 配置文档
├── commands/               # 命令定义
│   ├── readproject.md
│   ├── ask.md
│   ├── goal.md
│   └── commit.md
└── skills/                 # 治理模块
    ├── workspace-governor.md
    ├── api-governor.md
    └── goal-tracker.md

docs/
├── ROADMAP.md              # 项目路线图
├── CURRENT_GOAL.md         # 当前目标
├── api/API.md              # API 文档
└── git/
    ├── history.md          # 提交历史摘要
    └── logs/               # 详细日志
```

## Workflow

```
新会话开始
    │
    ▼
/readproject  ────→ AI 了解项目全貌
    │
    ▼
/goal  ───────────→ 确认当前目标
    │
    ▼
[开发工作...]
    │
    ▼
/commit  ─────────→ 自动执行保护检查
    │               自动生成规范提交
    │               自动更新项目状态
    ▼
/goal done  ──────→ 标记目标完成
```

## License

MIT
