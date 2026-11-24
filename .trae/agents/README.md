# .trae/agents 使用说明

本目录是 `community-correction` 项目的子智能体（Subagent）配置，共 8 个。它们只能被内置主智能体（SOLO Agent / Agent）调用，不能互相调用。

## 目录位置

必须放在**项目根目录**下：

```
community-correction/
└── .trae/
    └── agents/
        ├── capture-engineer.md
        ├── analysis-engineer.md
        ├── grading-engineer.md
        ├── backend-engineer.md
        ├── fe-user.md
        ├── fe-admin.md
        ├── qa-guard.md
        └── privacy-check.md
```

项目级 Subagent 跟随仓库，换台电脑也在；如果想让所有项目都能用，改放到 `~/.trae-cn/agents/`（Windows 为 `%userprofile%/.trae-cn/agents/`）。同名时项目级覆盖用户级。

## 启用步骤

1. Trae 打开 `community-correction` 项目根目录。
2. 进入 `设置 > Beta`，确认 **启用 Subagents 目录** 开关已打开（一般默认开启）。
3. 重启或重载窗口，让 `.trae/agents/` 被扫描到。
4. 验证：在 AI 对话输入框点 `@`，自定义智能体列表里应能看到这 8 个名字。

## 推荐使用顺序

### 第 1 步：先让主智能体产出契约（还不用子智能体）

SOLO 模式下输入 `/` 选 **Plan**，然后发：

```
目标：社区矫正智能辅助系统原型，先做单对象纵切，不做全量功能。
技术栈：Python 3.11 + FastAPI + SQLAlchemy + SQLite；前端 React + Vite。
模型全部走 Provider 抽象，先接 mock。
本轮只产出文档到 docs/，不写业务代码：
1. docs/prd.md
2. docs/architecture.md
3. docs/contracts/（capture.md、db.md、api.md、analysis.schema.json、grading.md、ui.md）
4. docs/grading.md（五色规则表 + 一致性规则 + 复核触发条件）
计划先给我确认，确认后再执行。
```

**这一步不能省。** 8 个子智能体全部以 `docs/contracts/` 为准开工，契约不存在时它们会被规则要求停下来报告，而不是自己猜字段。

### 第 2 步：按顺序点名，一次一个

```
使用 capture-engineer，按 docs/contracts/capture.md 实现抓拍 + 人脸裁剪 + 录音，只改 app/capture/。
```

```
使用 backend-engineer，按 docs/contracts/db.md 建 subjects / sessions / reviews / review_tickets / audit_logs 五张表，并实现 POST /api/sessions。
```

```
使用 analysis-engineer，先接 mock provider 把四路管线跑通，输出要能通过 docs/contracts/analysis.schema.json 校验。
```

```
使用 grading-engineer，按 docs/grading.md 实现规则表，每条规则一个函数并配 pytest。
```

```
使用 qa-guard，做一次契约校验和边界用例回归，输出报告到 docs/reports/。
```

### 第 3 步：前端与并行

跑通纵切后再开前端。此时可以用 SOLO 的多任务面板并行两个前端任务，因为目录不重叠：

```
使用 fe-user，实现采集引导页与知情同意页，只改 web/src/user/。
使用 fe-admin，实现复核队列页，色码必须与证据链同屏。
```

## 调用规则（重要）

- **子智能体看不到主对话历史**。每次点名都要带：目标文件路径、要遵守的契约文件、禁止改动的目录、验收标准。
- **自动调用靠 description 匹配**。你的措辞里出现 "抓拍 / 录音 / 人脸裁剪" 会命中 `capture-engineer`，出现 "五色 / 分级 / 复盘" 会命中 `grading-engineer`。写得太泛（"帮我改一下项目"）不会被调度。
- **只挂当前要用的智能体**。在 SOLO Agent 的配置图标 → 编辑工具里勾选，工具和智能体配太多会让执行路径变模糊。
- **子智能体不能改契约**。发现字段缺口会在输出里列出来，需要回到主对话统一改 `docs/contracts/`。
- **每轮结束跑一次 qa-guard**，主对话只看总结和 diff 摘要，细节在报告里。

## 目录所有权（避免冲突）

| Subagent | 可写目录 |
|---|---|
| capture-engineer | `app/capture/`, `tests/test_capture/` |
| analysis-engineer | `app/analysis/`, `tests/test_analysis/` |
| grading-engineer | `app/grading/`, `tests/test_grading/` |
| backend-engineer | `app/api/`, `app/db/`, `tests/test_api/`, `tests/test_db/` |
| fe-user | `web/src/user/` |
| fe-admin | `web/src/admin/` |
| qa-guard | `tests/`, `docs/reports/` |
| privacy-check | 无（只读） |

`docs/contracts/` 只允许主智能体改。

## 自定义模型（可选）

如果想让某个 Subagent 用不同模型，在 frontmatter 加一行 `model:`，取值必须是 Trae 内置模型标识（如 `gpt-5.4`、`kimi-k2.5`、`deepseek-v3.2`）。不写则默认用主智能体当前选的模型。检索类任务可以放轻量模型，`grading-engineer` 建议用强模型。

## 排查：没有被调用

1. `设置 > Beta > Subagents` 开关是否打开。
2. 文件是否在项目根 `.trae/agents/`。
3. `name` 是否字母开头、只含字母数字连字符、≤50 字符。
4. frontmatter 是否以 `---` 开头和结尾，`description` 是否非空、无 BOM。
5. 换个措辞，用 description 里的关键词再说一遍。

## 三条不能破的线

1. 只存裁剪后的人脸，原帧不落盘。
2. 分级结果只出口到人工复核工单，不接任何自动处置。
3. 色码只在管理端显示，且必须与证据链同屏。

