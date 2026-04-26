# x 架构设计文档

本文面向 `x` 的贡献者和维护者，说明项目定位、系统边界、核心流程和代码组织。它是架构导览，不替代 `skill/SKILL.md` 或 `skill/references/` 中的执行协议。

## 1. 项目定位

`x` 是一个面向 Codex 的本地 architect-to-code 工作流。它关注的不是“让模型写代码”，而是让 agent 在长任务、多角色、并行 lane 和集成审查中保持可控。

它解决的核心问题包括：

- 长任务中方向漂移和上下文丢失。
- 多 agent 并行后缺少统一控制面。
- reviewer ready 被误当成 merge 许可。
- 架构决策、实现证据和验证结果散落在聊天记录中。
- lane 之间有依赖或共享文件，但普通 agent 工具不强制集成顺序。

`x` 不是通用 agent runtime、云平台、任务系统或产品操作系统。它是一套本地 workflow 协议，加上状态脚本、角色 prompt、Markdown 模板和测试。

## 2. 设计原则

### 可审计

关键状态写入 Markdown 文件，包括 run、brief、contract、plan、lane、attempt、review、architect review、directive、risk 和 ledger。状态文件应能支持 main agent 在长会话后恢复上下文。

### 本地优先

运行时状态默认放在：

```text
~/.x/projects/<project-key>/
```

产品仓库只保存项目上下文：`PROJECT_CONSTRAINTS.md`、`AGENTS.md` 和 `.x/project/profile.md`。这样 `x` 保持可复用，产品仓库不会默认写入运行态 state。

### 职责分离

engineer 只实现一个 lane attempt；reviewer 只审查 attempt；architect 负责方向、plan、directive 和 integration review。reviewer 的 `ready` 只是代码评审证据，集成前仍需要 architect `merge-ok`。

### Gate 优先

没有 accepted Architecture Brief，就不能创建 Technical Contract 或 materialize integration worktree。没有 materialized worktree 和通过 readiness gate 的 Architect Execution Plan，就不能启动 lane work。

## 3. 角色模型

- `root`：用户，拥有方向决策、不可逆决策和最终 merge 授权。
- `main agent`：编排者，负责读上下文、写状态、生成 package、启动 worktree、运行 gate 和汇报。
- `interaction participants`：执行前的方向视角，例如 `founder`、`cto`、`product-lead`、`market-intelligence`、`gtm`、`challenger` 或自定义参与者。
- `architect`：把 root intent 转成 Architecture Brief、Technical Contract、Architect Execution Plan，并在执行中通过 directive 和 architect review 控制方向。
- `engineer`：在 lane worktree 内实现一个 attempt 或 fix attempt。
- `reviewer`：独立审查 attempt diff、verification、scope 和项目约束。

interaction 输出只是 advisory。只有 root 记录 accepted decision，并生成 accepted Architect Intake 后，方向才进入 architect execution。

## 4. 核心流程

整体流程：

```text
interaction
-> root decision
-> architect intake
-> run
-> Architecture Brief
-> materialized integration worktree
-> Technical Contract
-> Architect Execution Plan
-> architect readiness gate
-> lane worktrees
-> attempt
-> code review
-> architect directive/review
-> integrate
-> final verification
-> merge-ready gate
-> close / merge-back recommendation
```

执行层的关键边界：

- Architect Execution Plan 必须通过 readiness gate 后才能开始 lane。
- Plan 必须说明 lane scope、依赖、risk level、concurrent group、serial-only、shared files 和 integration order。
- high-risk lane 需要两个不同的 `merge-ok` architect review，且都必须链接最新 attempt。
- `integrate` 只集成 architect-approved lane diff 到 integration worktree。
- `close --status accepted` 前必须通过 merge-ready gate。
- merge-back recommendation 不是 merge；merge、push、PR 必须由 root 显式授权。

## 5. 状态模型

`x_state.py` 使用 Markdown 状态文件。主要状态目录包括 `interactions/`、`participant-briefs/`、`participants/`、`runs/`、`briefs/`、`contracts/`、`execution-plans/`、`lanes/`、`tasks/`、`attempts/`、`reviews/`、`architect-reviews/`、`directives/`、`packages/`、`decisions/`、`risks/`、`messages/`、`ledger/` 和 `boards/`。

这些目录分别记录 interaction、participant brief、participant card、run、Architecture Brief、Technical Contract、Architect Execution Plan、lane heartbeat、Engineer Task、attempt evidence、code review、architect integration review、control directive、input package、root decision、risk、mailbox、ledger 和 root board。

Markdown state 的优点是可读、可 diff、可恢复、可由 agent 直接引用。代价是 header、section 和 table 格式必须稳定；修改模板时要同步修改 parser、package 和测试。

## 6. Worktree 模型

root control root 通常是产品仓库的 `main` 或 `master` 分支。

accepted Architecture Brief 之后，`materialize` 创建 integration worktree：

```text
.dev/<scope>
```

`lane-start` 再创建 lane worktree：

```text
.dev/<scope>-<lane-id>
```

engineer 和 reviewer package 只能在 lane worktree 内工作。integration worktree 只用于串行集成经过 architect approval 的 lane diff。

## 7. Gate 和 Directive

Architect readiness gate 检查 plan 是否足够完整。`Parallel Lanes` 表必须包含：

```text
Lane ID, Task ID, Allowed Scope, Forbidden Scope, Worktree Scope,
Verification, Done Evidence, Risk Level, Concurrent Group,
Serial Only, Shared Files
```

`Risk Level` 是 `standard` 或 `high`。包含 shared files 的 lane 必须是 `high`。serial-only lane 的 concurrent group 必须是 `none`。

architect directive 是执行期控制面，支持：

- `continue`
- `parallelism-adjustment`
- `verification-adjustment`
- `pause-lane`
- `resume-lane`
- `replan`
- `root-decision`
- `request-more-evidence`

open `pause-lane` 阻塞对应 lane 的 lower work。open `replan` 阻塞 lower lane work。open `root-decision` 阻塞 accepted close。

## 8. 代码组织

- `skill/`：Codex skill 主体。
- `skill/SKILL.md`：`$x ...` 协议入口。
- `skill/references/`：按场景拆分的 workflow policy。
- `skill/assets/`：Markdown state 模板。
- `skill/scripts/`：`x_state.py` CLI 和状态命令实现。
- `agents/`：architect、engineer、reviewer 通用角色 prompt。
- `tests/`：基于 `unittest` 的 workflow 行为测试。
- `scripts/install-local.sh`：把 checkout 链接到本机 Codex home。

脚本按职责拆分：`x_state_common.py` 放共享 helper；`x_state_commands.py` 放 run、contract、task、attempt、gate、decision、close 等基础命令；`x_state_execution.py` 和 `x_state_integration.py` 管 execution plan、lane、architect review、diff 和 integration；`x_state_discussion.py`、`x_state_directives.py`、`x_state_packages.py`、`x_state_reviews.py`、`x_state_mailbox.py`、`x_state_cleanup.py` 分别管理 interaction、directive、package、review、mailbox 和 worktree cleanup。

## 9. 维护规则

修改 workflow 行为时，应同步考虑：

- `skill/SKILL.md` 是否需要更新。
- `skill/references/*.md` 是否需要更新。
- `skill/assets/*.md` 模板是否需要新字段。
- `skill/scripts/*.py` 是否需要读写或 gate 校验。
- input package 是否需要暴露新状态。
- 是否需要迁移或清理旧状态文件。
- tests 是否覆盖正向和失败路径。

脚本改动后运行：

```bash
python -m py_compile skill/scripts/*.py
```

prompt 改动后解析 `agents/*.toml`。package 行为变化时，smoke package generation for `architect`、`engineer` 和 `reviewer`。

## 10. 非目标

当前架构刻意不做 Web UI、数据库、云端任务调度、外部服务依赖、GitHub/PR 自动化、自动 merge/push/release，也不把产品特定约束内置到 `x` 仓库。

这些限制让 `x` 保持轻量、可检查、可移植，也降低 agent 自动化误操作的风险。
