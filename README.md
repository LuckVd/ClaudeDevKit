# ClaudeDevKit

**Claude Code 项目治理框架** — 让 AI 在帮你写代码时，不会乱改核心代码、不会破坏 API、不会忘记当前任务。

---

## 核心价值

| 痛点 | 解决方案 |
|------|----------|
| AI 乱改核心代码 | 三级文件保护（active / stable / core） |
| API 被无意破坏 | Breaking Change 自动检测 |
| 每次会话重新解释项目 | PROJECT.md 统一状态管理 |
| 提交信息不规范 | Conventional Commits 自动生成 |
| AI 改着改着跑偏了 | 目标追踪 + 单一焦点模式 |

---

## 失败场景：没有 ClaudeDevKit 会怎样

```
用户：帮我优化一下用户模块的性能
  │
  ▼
AI：好的，我优化了数据库查询...
    顺便重构了认证逻辑...
    还清理了一些"冗余"代码...
  │
  ▼
结果：
  • 用户模块确实快了 20%
  • 但认证系统崩了（那不是冗余代码）
  • API 参数被改了，前端全挂
  • commit message: "optimize user module"
```

**使用 ClaudeDevKit 后**：核心模块被保护、API 变更需要确认、目标进度自动追踪。

---

## 项目结构

```
.claude/
├── PROJECT.md              # 唯一配置文档（模块定义、保护规则、开发历史）
├── commands/
│   ├── readproject.md      # /readproject - 项目概览
│   ├── ask.md              # /ask - 只读问答
│   ├── goal.md             # /goal - 目标管理
│   └── commit.md           # /commit - 提交流程
└── skills/
    ├── workspace-governor.md   # 文件等级保护
    ├── api-governor.md         # API 契约保护
    └── goal-tracker.md         # 目标进度追踪

docs/
├── ROADMAP.md              # 项目路线图
├── CURRENT_GOAL.md         # 当前目标
├── api/API.md              # API 文档
└── git/
    ├── history.md          # 提交历史摘要
    └── logs/               # 详细提交日志
```

---

## 快速开始

### 1. 复制模板

```bash
cp -r ClaudeDevKit/.claude your-project/
cp -r ClaudeDevKit/docs your-project/
cd your-project
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

## 模块列表

| 模块 | 路径 | Status | Level |
|------|------|--------|-------|
| auth | `src/auth/**` | dev | active |
| core | `src/core/**` | done | core |
```

### 3. 新会话开始

```bash
# 每次 Claude Code 新会话执行
/readproject
```

### 4. 开发工作流

```bash
/readproject    # 了解项目状态
/goal           # 查看/设置当前目标
# ... 开发 ...
/commit         # 提交 + 自动检查 + 更新状态
```

---

## 命令系统

### `/readproject` — 项目概览

新会话时执行，快速建立项目认知。

```bash
/readproject
```

**输出**：项目信息、模块状态、当前目标、最近历史

---

### `/ask` — 只读问答

安全分析代码，只读不写。

```bash
/ask 这个项目的认证流程是怎样的？
/ask 为什么这个函数会报错？
```

**特性**：禁止修改、创建、删除文件

---

### `/goal` — 目标管理

单一焦点模式，追踪开发进度。

```bash
/goal                      # 查看当前目标
/goal set 实现用户登录 API   # 设置新目标
/goal done                 # 标记完成
/goal block 等待数据库配置   # 标记阻塞
/goal unblock              # 解除阻塞
```

---

### `/commit` — 提交流程

核心命令，执行完整治理流程：

```
1. Pre-commit 检查（lint）
2. 清理临时文件
3. 文件保护检查（workspace-governor）
4. API 变更检测（api-governor）
5. 目标进度检查（goal-tracker）
6. 生成 Conventional Commit
7. 执行提交
8. 更新状态文件（PROJECT.md / CURRENT_GOAL.md / ROADMAP.md）
9. 更新 Git 历史（history.md + logs/）
10. Push
```

---

## 三级文件保护

| Level | 含义 | 修改规则 |
|-------|------|----------|
| `active` | 活跃开发 | 自由修改 |
| `stable` | 已稳定 | 需确认 |
| `core` | 核心保护 | 禁止 AI 自动修改 |

**工作原理**：`/commit` 时自动检测变更文件所属模块等级，根据等级决定放行、询问或阻止。

---

## Skills 系统

Skills 是可复用的治理模块，被 `/commit` 命令调用：

| Skill | 职责 | 触发条件 |
|-------|------|----------|
| `workspace-governor` | 文件等级保护 | 所有文件变更 |
| `api-governor` | API 契约保护 | API 相关文件变更 |
| `goal-tracker` | 目标进度追踪 | 所有提交 |

---

## 典型工作流

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
    │               自动记录历史
    ▼
/goal done  ──────→ 标记目标完成，设置下一个
```

---

## 文件清单

| 文件 | 用途 |
|------|------|
| `.claude/PROJECT.md` | 唯一配置文档 |
| `.claude/commands/readproject.md` | 项目概览命令 |
| `.claude/commands/ask.md` | 只读问答命令 |
| `.claude/commands/goal.md` | 目标管理命令 |
| `.claude/commands/commit.md` | 提交流程命令 |
| `.claude/skills/workspace-governor.md` | 文件保护 Skill |
| `.claude/skills/api-governor.md` | API 保护 Skill |
| `.claude/skills/goal-tracker.md` | 目标追踪 Skill |

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
