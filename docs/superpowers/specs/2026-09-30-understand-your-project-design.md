# UnderstandYourProject 设计文档

日期：2026-09-30
状态：待审阅

## 1. 背景与目标

vibe coding 让没有编程经验的人也能让 AI 做出能跑的项目，但他们无法判断代码结构是否健康，只知道"能不能用"。结构决定项目能不能持续演进，坏结构（"屎山"）会让后续每一次修改都更难、更容易出错，最终 AI 也改不动。

本项目提供一个 Claude Code skill：`understand-your-project`。它让用户的 agent 分析当前项目的架构，结合项目需求判断结构是否合理，并给出具体、可执行的修改建议。目标用户不需要任何编程知识就能读懂输出。

### 成功标准

- 非程序员读完报告后能说出"我的项目由哪几块组成、哪里有问题、先改哪条"。
- 报告里每个问题都有脚本给出的具体证据（文件路径、数字），没有凭印象的判断。
- 同一个项目在不同需求画像下得到不同的严重程度排序。
- 脚本在 3 个 fixture 项目上输出符合预期的事实。

### 非目标（第一版明确不做）

- 不自动修改代码。
- 不处理超大项目（源文件超过 800 个或代码超过 8 万行）的逐文件分析。
- 不提供 JS/TS 和 Python 以外语言的参考架构。
- 不做跨次分析的历史对比。
- 不做 CI 集成。
- 不做跨 agent 格式（Cursor、Codex 等）的移植；这是第二阶段，本设计只要求脚本零依赖以便将来移植。

## 2. 已确定的决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 载体 | Claude Code skill（SKILL.md + 脚本 + 参考文档） | 核心价值是 LLM 的判断和建议，先在一个平台把方法论做扎实 |
| 需求来源 | 先扫项目文档做草稿，再用业务问题跟用户确认 | "最优"是相对需求的；vibe coder 项目常无可靠文档 |
| 输出 | 项目根目录下的 `ARCHITECTURE_REVIEW.md`，语言跟用户对话语言一致 | 可保存、可回看；用户决定要不要改 |
| 判断标准 | 固定问题清单为骨架，项目类型与需求画像调整严重程度和建议形态 | 稳定、可解释，同时"相对需求" |
| 范围 | JS/TS 与 Python，几千到几万行 | 覆盖目标用户绝大多数项目 |
| 实现方式 | 零依赖 Python 脚本收集事实，agent 做判断 | 数得清的交给脚本，判得准的交给 LLM |

## 3. 文件布局

```
understand-your-project/
├── SKILL.md                       # 入口：触发条件、五步流程、给 agent 的规则
├── scripts/
│   └── collect_facts.py           # 事实收集脚本，仅标准库，输出 JSON
├── references/
│   ├── checklist.md               # 架构问题清单（16 条）
│   ├── reference-architectures.md # JS/TS 与 Python 各类项目的参考结构
│   ├── interview.md               # 需求访谈的问题模板和合成规则
│   └── report-template.md         # 报告的固定章节和写法规范
├── tests/
│   ├── fixtures/                  # 3 个小型 fixture 项目
│   └── test_collect_facts.py      # unittest
└── EVALS.md                       # 每个 fixture 的预期分析结果，人工对照
```

安装方式：整个目录复制到 `~/.claude/skills/understand-your-project/`，或打包为 plugin。

## 4. 工作流程

agent 严格按五步执行，每步产物是下一步输入。

### 触发条件

用户说"分析我的项目结构"、"这个架构好不好"、"代码是不是屎山"、"understand my project"、"review my architecture"、"is my code structure ok" 等，或直接 `/understand-your-project`。

### 第 1 步：收集事实

运行 `python3 scripts/collect_facts.py <项目根目录>`，得到 JSON。若 `out_of_scope` 为 true，agent 只做顶层分析并在报告和对话里明确告知。若脚本失败，agent 不得自行数文件替代，直接把脚本错误原因告诉用户并停止。

### 第 2 步：理解需求

1. 读取 JSON 里 `docs` 列出的文件（README、CLAUDE.md、docs/、PRD 等）。
2. 写一段"我理解你的项目是……"的草稿。若无文档，草稿改为"从代码看，这个项目像是……"。
3. 按 `interview.md` 问 4 个问题，一次一个，选择题优先。
4. 合成"需求画像"，含两个档位（见第 6 节）。
5. 用户拒绝回答时使用默认档位，并在报告里标注"以下判断基于默认假设"。

### 第 3 步：对照清单

按 `checklist.md` 逐条对照 JSON 证据，结合项目类型和需求画像定严重程度。若能识别项目类型，按 `reference-architectures.md` 生成"建议的目标结构"，只包含当前项目已暴露问题的部分。

### 第 4 步：写报告

按 `report-template.md` 生成 `ARCHITECTURE_REVIEW.md`，写到项目根目录。已存在则覆盖并在顶部标注生成时间。写完后在对话里用不超过 5 句话总结结论，并说明报告位置。

### 第 5 步：停止

不修改任何代码。报告里每条建议附一段可直接复制给 agent 的任务描述，由用户决定何时、是否执行。

## 5. 事实收集脚本 `collect_facts.py`

### 约束

- 仅使用 Python 标准库，Python 3.8 以上可运行。
- 用法：`python3 collect_facts.py <项目路径>`，JSON 输出到标准输出，错误输出到标准错误并以非零退出。
- 不做好坏判断，不给建议，不把文件内容放进 JSON（只有路径、统计数字和位置）。

### 忽略规则

忽略目录：`node_modules`、`.git`、`.venv`、`venv`、`env`、`__pycache__`、`dist`、`build`、`.next`、`out`、`coverage`、`.cache`、`.turbo`、`.pytest_cache`、`.mypy_cache`。同时读取项目 `.gitignore`，忽略其中列出的顶层目录。

源文件扩展名：`.js .jsx .ts .tsx .mjs .cjs .py`。其他文件计入总文件数但不计入代码行数和依赖分析。

### 输出结构

```json
{
  "root": "/abs/path",
  "project_type": {
    "name": "my-app",
    "languages": ["typescript", "python"],
    "frameworks": ["next", "react", "fastapi"],
    "package_managers": ["npm", "pip"],
    "monorepo": false,
    "detected_from": ["package.json", "pyproject.toml"]
  },
  "scale": {
    "total_files": 142,
    "source_files": 98,
    "source_lines": 18400,
    "lines_by_language": {"typescript": 15000, "python": 3400},
    "out_of_scope": false
  },
  "tree": [
    {"path": "src", "depth": 1, "files": 80, "lines": 15000},
    {"path": "src/app", "depth": 2, "files": 30, "lines": 9000}
  ],
  "largest_files": [
    {"path": "src/app/page.tsx", "lines": 1870, "language": "typescript"}
  ],
  "dependency": {
    "edge_count": 1,
    "most_imported": [{"path": "src/lib/utils.ts", "imported_by": 61}],
    "cycles": [["src/a.ts", "src/b.ts", "src/a.ts"]],
    "orphans": ["src/old/legacy.ts"],
    "unresolved_imports": 12,
    "edges": [{"from": "src/a.ts", "to": "src/b.ts"}]
  },
  "layer_mixing": [
    {"path": "src/app/page.tsx", "categories": ["ui", "network", "data"], "signals": ["jsx", "fetch(", "SELECT"]}
  ],
  "duplication": {
    "similar_filenames": [["src/utils.ts", "src/utils2.ts", "src/lib/helpers.ts"]],
    "repeated_function_names": [{"name": "formatDate", "files": ["src/a.ts", "src/b.ts"]}]
  },
  "naming": {
    "file_case_styles": {"camelCase": 40, "snake_case": 12, "kebab-case": 30},
    "dir_case_styles": {"camelCase": 3, "kebab-case": 8}
  },
  "hygiene": {
    "has_tests": false,
    "test_paths": [],
    "has_env_example": false,
    "has_gitignore": true,
    "has_lint_config": true,
    "has_format_config": false,
    "suspected_secrets": ["src/config.ts:12"],
    "config_files": ["src/config.ts", "src/constants.ts", "lib/settings.py"],
    "committed_env_files": [".env"]
  },
  "docs": ["README.md", "CLAUDE.md", "docs/prd.md"]
}
```

### 各字段的采集方法

**project_type**：读 `package.json` 的 dependencies 和 devDependencies 识别 next、react、vue、express、fastify、nest、electron 等；读 `pyproject.toml`、`requirements.txt`、`setup.py`、`Pipfile` 识别 fastapi、django、flask、streamlit 等。`monorepo` 判定为存在 `workspaces` 字段、`pnpm-workspace.yaml`、`lerna.json`、`turbo.json` 之一。

**scale**：遍历时累计。`out_of_scope` 为 `source_files > 800 or source_lines > 80000`。

**tree**：深度限制 4 层，每个目录汇总其子树的文件数和行数。

**largest_files**：所有行数超过 300 的源文件按行数降序排列；不足 15 个时补齐到前 15。这样 A1、A3 不会漏掉排名靠后的大文件。

**dependency**：正则匹配四种 import 形式：

- JS/TS：`import ... from '<spec>'`、`require('<spec>')`、`import('<spec>')`
- Python：`from <mod> import ...`、`import <mod>`

只解析项目内引用：JS/TS 中以 `.` 或 `/` 开头的路径，或匹配 `tsconfig.json` / `jsconfig.json` 中 `compilerOptions.paths` 的别名；Python 中相对导入和以项目内顶层包名开头的绝对导入。解析时尝试补全扩展名和 `index` 文件。无法解析的引用计入 `unresolved_imports`，不报错。

`cycles` 用 Tarjan 强连通分量算法找出所有大小大于 1 的分量，每个分量输出一个环路径。`orphans` 是没有被任何项目内文件引用、且不是入口文件（`main.*`、`index.*`、`app.*`、`page.*`、`layout.*`、`route.*`、`manage.py`、`__main__.py`、测试文件、配置文件）的源文件。`most_imported` 取被引用数前 10。

**layer_mixing**：对每个源文件扫描三类信号，同一文件命中两类以上就记录：

- UI 信号：JSX 语法、`useState`、`useEffect`、`document.`、`window.`、`streamlit`、`tkinter`
- 网络信号：`fetch(`、`axios`、`requests.`、`httpx`、`urllib`
- 数据信号：`SELECT `、`INSERT `、`prisma.`、`sqlite3`、`sqlalchemy`、`mongoose`、`.query(`

**duplication**：`similar_filenames` 把文件名去掉扩展名、去掉尾部数字、转小写后，同名或互为前缀（如 `util`/`utils`/`helpers` 归一为同一组，通过一个小同义词表）的文件分组。`repeated_function_names` 用正则抓 `function <name>`、`const <name> = (`、`def <name>(`，同名出现在 3 个以上文件的记录。

**naming**：统计源文件名和目录名的命名风格。

**hygiene**：

- `has_tests`：存在 `test`、`tests`、`__tests__`、`spec` 目录或 `*.test.*`、`*.spec.*`、`test_*.py` 文件。
- `has_env_example`：存在 `.env.example`、`.env.sample`、`.env.template`。
- `has_lint_config`：存在 `.eslintrc*`、`eslint.config.*`、`biome.json`、`ruff.toml`、`.flake8`、`.pylintrc`，或 `pyproject.toml` 含 `[tool.ruff]`。
- `has_format_config`：存在 `.prettierrc*`、`prettier.config.*`、`biome.json`，或 `pyproject.toml` 含 `[tool.black]`。
- `suspected_secrets`：正则匹配 `(api[_-]?key|secret|token|password)\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}['"]`，以及 `sk-`、`ghp_`、`AKIA` 开头的长字符串。只输出 `路径:行号`，绝不输出匹配内容。跳过 `.env.example` 和测试文件。
- `config_files`：文件名含 `config`、`settings`、`constants`、`env` 的源文件。

**docs**：`README*`、`CLAUDE.md`、`AGENTS.md`、`docs/` 下的 `.md`、文件名含 `prd`、`spec`、`requirements`、`design` 的 `.md`。

### 测试

`tests/fixtures/` 下三个项目：

1. `clean-next`：结构干净的 Next.js 项目，预期无循环、无层混合、有测试。
2. `monolith-py`：所有逻辑在一个 800 行 `main.py` 里的 Python 项目，含硬编码密钥和内联 SQL，预期 `largest_files[0]` 是它、`layer_mixing` 命中、`suspected_secrets` 非空。
3. `cyclic-node`：三个文件互相 require 的 Node 项目，预期 `cycles` 非空。

`test_collect_facts.py` 用 `unittest` 对每个 fixture 断言上述字段。

## 6. 需求访谈 `interview.md`

### 流程

1. 读 `docs` 列出的文件，写草稿"我理解你的项目是……"。
2. 依次问 4 个问题，一次一个，等用户回答再问下一个。
3. 合成需求画像。

### 四个问题

1. **项目是干什么的？** agent 先陈述自己的理解，请用户确认或纠正。开放式。
2. **给谁用？** 选项：只有我自己 / 少数几个人（家人、同事、朋友） / 公开给很多人。
3. **接下来半年打算怎么发展？** 选项：基本就这样了 / 会持续加功能 / 准备正式上线或收费 / 会有其他人一起改代码（可多选）。
4. **现在最头疼的是什么？** 选项：改一处坏一片 / AI 越来越改不动 / 跑得慢 / 没什么问题只是想看看 / 其他。

### 需求画像

| 字段 | 取值 | 来源 |
|---|---|---|
| purpose | 一句话 | 问题 1 |
| scale_tier | `personal` / `small_group` / `public` | 问题 2 |
| evolution_tier | `frozen` / `iterating` / `launching` / `collaborative` | 问题 3，多选时取最重的一档，顺序 frozen < iterating < launching < collaborative |
| pain_points | 列表 | 问题 4 |

默认档位（用户不答时）：`small_group` + `iterating`。

## 7. 问题清单 `checklist.md`

### 条目格式

每条固定包含：编号、名字、大白话解释、证据字段（JSON 路径）、判定阈值、基础严重程度、档位调整、放着不管的后果、一般改法。

### 严重程度

- **必须改**：放着会出事故或马上卡住开发。
- **建议改**：现在不疼，按用户的发展方向半年内会疼。
- **提示**：知道就行。

### 16 条清单

**A. 分层与职责**

| 编号 | 名字 | 证据 | 阈值 | 基础严重程度 |
|---|---|---|---|---|
| A1 | 巨型文件 | `largest_files` | 超过 500 行即报；501 到 1000 行建议改，超过 1000 行必须改 | 建议改；超过 1000 行为必须改 |
| A2 | 同一文件混合 UI、网络、数据中的两类以上 | `layer_mixing` | `layer_mixing` 非空 | 建议改 |
| A3 | 业务逻辑散在路由或页面里 | `largest_files` 中路径含 `page`、`route`、`views`、`api` 且超过 300 行 | 存在即报 | 建议改 |
| A4 | 万能 utils | `most_imported` | 单文件被超过 30% 的源文件引用且行数超过 300 | 存在即报 | 建议改 |

**B. 依赖与耦合**

| 编号 | 名字 | 证据 | 阈值 | 基础严重程度 |
|---|---|---|---|---|
| B1 | 循环依赖 | `cycles` | 非空 | 必须改 |
| B2 | 孤儿文件与死代码 | `orphans` | 非空 | 提示；超过 10 个为建议改 |
| B3 | 依赖方向混乱 | `edges` 中存在底层目录引用上层目录。层级顺序由 `reference-architectures.md` 中每个模板定义（通用顺序：`utils`/`lib`/`shared` < `services`/`db`/`models` < `components`/`hooks` < `pages`/`app`/`routes`/`api`），低层引用高层即为反向 | 存在即报 | 建议改 |

**C. 重复与一致性**

| 编号 | 名字 | 证据 | 阈值 | 基础严重程度 |
|---|---|---|---|---|
| C1 | 近似文件多份 | `similar_filenames` | 非空 | 建议改 |
| C2 | 同一逻辑多处复制 | `repeated_function_names` | 非空 | 提示；某个名字出现在超过 5 个文件为建议改 |
| C3 | 命名风格混乱 | `naming` | 同一类别中次多风格占比超过 20%，且该类别计数总和不少于 10 | 提示 |

**D. 工程卫生**

| 编号 | 名字 | 证据 | 阈值 | 基础严重程度 |
|---|---|---|---|---|
| D1 | 没有测试 | `has_tests` | false | 建议改 |
| D2 | 密钥硬编码 | `suspected_secrets` | 非空 | 必须改（任何档位都不降） |
| D3 | 缺 .env.example 或 .gitignore | `has_env_example`、`has_gitignore`、`config_files`、`suspected_secrets`、`committed_env_files` | `has_gitignore` 为 false；或 `has_env_example` 为 false 且 `config_files`、`suspected_secrets`、`committed_env_files` 任一非空 | 建议改 |
| D4 | 没有 lint 或 format | `has_lint_config`、`has_format_config` | 任一 false | 提示 |

**E. 可演进性**

| 编号 | 名字 | 证据 | 阈值 | 基础严重程度 |
|---|---|---|---|---|
| E1 | 目录按文件类型堆而不按功能分 | `tree` 中顶层或二层目录名是 `components`、`utils`、`hooks`、`types`、`helpers` 之一且单目录文件超过 20 | 存在即报 | 提示 |
| E2 | 配置和常量散落各处 | `config_files` | 超过 3 个且分布在不同目录 | 提示 |

### 档位调整规则

按顺序应用，每步最多调一级，最低为"提示"，最高为"必须改"：

1. `scale_tier == personal`：D 和 E 维度降一级，D2 除外。
2. `evolution_tier == collaborative`：C3、D1、E1 升一级。
3. `evolution_tier in (launching, collaborative)`：D1、D3 升一级。
4. `pain_points` 含"改一处坏一片"：A、B 维度升一级。
5. `pain_points` 含"AI 越来越改不动"：A1、A4、E1 升一级。
6. 最后封顶：`evolution_tier == frozen` 时 E 维度全部设为"提示"。
7. 被规则 4 或 5 命中的问题在各自严重程度分组内排最前。

## 8. 参考架构 `reference-architectures.md`

### 五个模板

1. **Next.js / React 前端应用**（识别：frameworks 含 next 或 react，无后端框架）
2. **Node 后端 API**（识别：frameworks 含 express、fastify、nest、koa、hono）
3. **Python 后端 API**（识别：frameworks 含 fastapi、flask、django）
4. **Python 脚本集或数据工具**（识别：languages 只有 python，无 Web 框架）
5. **全栈单仓**（识别：同时命中前端和后端模板，或 monorepo 为 true）

每个模板给出：目录骨架、每个目录一句话说明放什么、哪些目录在项目小的时候可以省略、以及一个从低到高的层级顺序（供清单 B3 判断依赖方向）。

### 使用规则

- 按 T5、T1、T2、T3、T4 的顺序匹配，取第一个命中的模板；T5 的条件是前端框架加任一后端框架，或 monorepo。识别不出类型时不给目标结构，只输出清单结果并说明。
- "建议的目标结构"只包含当前项目已暴露问题所涉及的部分。干净的部分不动，不为套模板要求用户重排。
- 目标结构里每个新增或移动的目录都要对应报告第 4 节的某个问题编号。

## 9. 报告 `report-template.md`

### 文件与语言

写到项目根目录 `ARCHITECTURE_REVIEW.md`。语言跟用户当前对话语言一致。已存在则覆盖，顶部标注生成时间和"基于默认假设"（如适用）。

### 五个章节

1. **一句话结论。** 三档之一：结构健康 / 有几处该改 / 需要系统整理。判定规则：无"必须改"且"建议改"不超过 2 条为健康；有"必须改"或"建议改"超过 5 条为需要系统整理；其余为有几处该改。后跟一句为什么。
2. **你的项目现在长什么样。** 大白话描述组织方式，配 ASCII 目录图（来自 `tree`，深度到 3 层），每个主要目录一句话说它在干嘛。
3. **需求画像。** 写回访谈结果，让用户确认判断前提。
4. **发现的问题。** 按必须改、建议改、提示分组，pain_points 命中的排最前。每条固定四行：是什么（大白话）、证据（具体文件与数字）、为什么对你的项目重要（结合需求画像）、放着不管会怎样。
5. **建议的改法。** 每条对应问题编号，含改动范围、风险（低/中/高）、工作量（小/中/大）、一段可直接复制给 agent 的任务描述。排序按收益高且风险低优先。若有目标结构，附图并标注每处改动对应的问题编号。

### 写法规则

- 不用术语；非用不可时第一次出现要括号解释。
- 每个问题必须引用脚本 JSON 里的具体证据，禁止"感觉有点乱"式的判断。
- 不虚构文件路径。所有路径必须来自 JSON。
- 对话里的总结不超过 5 句话，并给出报告路径。

## 10. 错误处理

| 情况 | 处理 |
|---|---|
| `out_of_scope` 为 true | 只做第 1、2、3 节和顶层结构层面的问题（E1、D 维度），明确写出"本版本未逐文件分析" |
| `out_of_scope` 为 true（脚本侧） | 脚本跳过逐文件部分：`dependency`、`duplication` 列表为空并带 `"skipped": "out_of_scope"`，`layer_mixing` 为空 |
| `scale.source_files` 为 0 | 告诉用户没有找到支持的源文件（不分析 notebook），停止，不写报告 |
| 语言不是 JS/TS 或 Python | 只评估 D3，报告里说明本语言无法检查测试、密钥和 lint，跳过参考架构 |
| 识别不出框架 | 跳过参考架构，只跑通用清单，报告里说明 |
| 项目无任何文档 | 访谈草稿改为"从代码看，这个项目像是……"，问题不变 |
| 用户不愿回答访谈 | 使用默认档位，报告顶部标注"以下判断基于默认假设" |
| 脚本运行失败 | 不降级成 agent 自行数文件，把脚本的具体错误告诉用户并停止 |
| `unresolved_imports` 占比超过 30% | 报告里说明依赖分析可能不完整，B 维度结论标为"待确认" |

## 11. 测试与评测

- **脚本**：`tests/test_collect_facts.py`，unittest，对 3 个 fixture 断言第 5 节列出的关键字段。
- **skill 整体**：`EVALS.md` 列出每个 fixture 在默认档位下应被报出的问题编号和不应被报出的编号。修改 SKILL.md 或 checklist.md 后在 3 个 fixture 上人工跑一遍对照。第一版不做自动化评测。

## 12. 第二阶段展望（不在本设计范围内）

- 移植为跨 agent 的 skill 格式（Cursor、Codex 等）。
- 超大项目的分批与摘要策略。
- 更多语言的参考架构。
- 报告历史对比。
