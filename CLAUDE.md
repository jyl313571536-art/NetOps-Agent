# NetOps Agent 项目开发规范

版本：v1.2

## 1. 项目介绍

### 1.1 项目名称

**NetOps Agent**

英文名称：**AI Network Operations & Troubleshooting Agent**

### 1.2 项目定位

NetOps Agent 是一个基于大语言模型和 LangGraph
构建的智能网络运维与故障诊断 Agent。

项目通过自然语言接收网络故障描述，结合网络诊断工具、网络知识库和 Agent
工作流，实现网络故障识别、诊断规划、工具执行、结果分析和故障报告生成。

项目用于：

1.  AI Agent 技术学习。
2.  个人 GitHub 开源项目展示。
3.  AI Agent 工程师求职作品集。
4.  网络运维智能化应用实践。

项目目标是形成真实可运行、模块清晰、可测试、可扩展的工程项目，而不是简单的
LLM 聊天机器人。

**真实性要求：**
只描述已经实现并验证的功能。模拟数据必须明确标记为模拟数据；未经工具验证的诊断结论不得描述为已确认结果。

## 2. 当前技术选型

### 2.1 基础环境

-   Python：3.13.9
-   Agent Framework：LangGraph
-   LLM Integration：LangChain Core
-   LLM Provider：Xiaomi MiMo
-   Model Integration：langchain-openai
-   API Framework：FastAPI
-   Data Validation：Pydantic v2
-   Configuration：pydantic-settings
-   HTTP Client：HTTPX
-   Testing：Pytest
-   Code Quality：Ruff
-   Web UI：HTML5 / CSS3 / 原生 JavaScript
-   Template Engine：Jinja2（如有模板渲染需求）
-   Frontend HTTP：Fetch API

Web UI 不引入 Vue、React、Node.js，不增加不必要的依赖。

依赖版本以实际安装、兼容性测试和锁定结果为准，不盲目追求最新版本。若某个依赖与
Python 3.13.9 不兼容，应先分析并提出解决方案，不得擅自更换 Python 版本。

### 2.2 大模型配置

当前项目只接入 Xiaomi MiMo。

默认模型：

``` env
MIMO_MODEL=mimo-v2.6-pro
```

可选备用模型：

``` env
MIMO_MODEL=mimo-v2.6-flash
```

按TokenPlan付费 OpenAI 兼容接口 Base URL：

``` env
https://token-plan-cn.xiaomimimo.com/v1
```

环境变量：

``` env
MIMO_API_KEY=
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.6-pro
MIMO_TIMEOUT=60
```

注意：

1.  API Key 不能硬编码。
2.  不允许将 API Key 写入 GitHub。
3.  不允许在日志中输出 API Key。
4.  不允许将真实 API Key 提交到 `.env.example`。
5.  使用 Token Plan 时，以控制台提供的专属 Base URL 和 Key
    为准，不得默认套用按量付费地址。
6.  不允许使用已经下线的 MiMo 模型 ID。
7.  模型参数应根据 MiMo 官方接口能力配置。
8.  不得假设所有 OpenAI 兼容参数和功能都能被 MiMo 完全支持。
9.  第一阶段先验证普通对话；第二阶段单独验证 Function Calling
    和多轮工具调用。
10. 不得将普通聊天调用成功等同于 Tool Calling 已经兼容。

官方文档：

-   首次调用：https://mimo.mi.com/docs/zh-CN/quick-start/summary/first-api-call
-   OpenAI 兼容 API：https://mimo.mi.com/docs/zh-CN/api/chat/openai-api
-   模型列表：https://mimo.mi.com/docs/zh-CN/quick-start/summary/model

**模型创建设计：**

当前只有一个模型供应商 Xiaomi MiMo，Pro 和 Flash
属于同一供应商下的不同模型型号。

第一阶段只需要在独立模块中提供简单的模型创建函数，例如
`create_llm()`，负责读取配置并创建 `ChatOpenAI`
实例。暂不实现多供应商注册、动态发现或复杂工厂体系。

保留模块边界，未来确实接入多个供应商时，再考虑升级为多供应商
LLMFactory。Agent 节点不得自行创建模型实例。

### 2.3 网络诊断接入方式

网络诊断能力按阶段实现，不得提前把后续阶段的功能塞入第一阶段。

-   Phase 1：不执行网络诊断工具，只进行基于用户描述的初步分析。
-   Phase 2：实现模拟网络设备和受控的本机网络诊断工具。
-   后续阶段：根据需要扩展真实网络设备接入。

计划支持的能力：

**模拟设备：**

-   模拟交换机。
-   模拟路由器。
-   模拟防火墙。

**本机网络诊断：**

-   Ping。
-   DNS 查询。
-   TCP 端口检测。
-   Traceroute。

**后续真实设备接入：**

-   SSH。
-   Netmiko。
-   NAPALM。
-   SNMP。

模拟数据与本机真实检测结果必须明确区分。未连接真实网络设备时，不得声称已经读取真实设备配置或状态。

### 2.4 用户交互方式

提供两种交互方式：

1.  FastAPI REST API：供程序化调用、自动化测试和 Web UI 使用。
2.  Web 测试控制台（`app/web/`）：项目内置的 Web 管理和测试界面。

Web 测试控制台定位为开发与测试辅助界面，不是产品级前端：

-   使用 HTML5、CSS3、原生 JavaScript、Fetch API，按需使用 Jinja2。
-   只通过后端 API 与业务层交互。
-   不引入 Vue、React、Node.js。

后续可扩展：

-   SSE 流式输出。
-   诊断任务管理。
-   前端体验优化。

第一阶段采用同步 API，暂不引入 Redis、Celery 或复杂异步任务系统。

## 3. 系统架构

项目采用模块化分层架构，按实际开发阶段逐步实现。

### 3.1 API Layer

负责：

-   接收用户请求。
-   参数校验。
-   调用 Agent Service。
-   返回结构化结果。
-   统一错误响应。

API 层不能直接调用 LLM，也不能直接执行网络诊断命令。

### 3.2 Agent Layer

负责：

-   故障识别。
-   诊断任务规划。
-   工作流编排。
-   状态管理。
-   条件路由。
-   工具调用控制。
-   结果分析。
-   故障报告生成。

Agent 工作流使用 LangGraph `StateGraph`。

### 3.3 LLM Layer

负责：

-   Xiaomi MiMo 接入。
-   模型实例创建。
-   模型配置读取。
-   请求超时设置。
-   模型异常处理。

模型实例通过独立模块创建。Agent 节点不得直接创建 `ChatOpenAI` 对象。

### 3.4 Network Tools Layer

Phase 2 开始实现，负责：

-   网络诊断工具封装。
-   工具参数校验。
-   工具执行。
-   工具结果结构化。
-   工具异常处理。

工具不应该直接依赖大模型。工具的输入、输出应使用明确的数据结构，并可独立测试。

### 3.5 Network Adapter Layer

Phase 2 开始实现，负责隔离模拟网络设备和真实网络环境。

计划包含：

-   `NetworkAdapter`
-   `MockNetworkAdapter`
-   `LocalNetworkAdapter`

未来可增加真实设备适配器。模拟设备、真实本机网络检测和真实网络设备访问必须有清晰边界。

### 3.6 RAG Layer

Phase 3 开始实现，负责：

-   文档加载。
-   文本切分。
-   Embedding。
-   Chroma 向量存储。
-   相似度检索。
-   知识来源引用。

### 3.7 Storage Layer

Phase 4 开始按需实现，负责：

-   诊断记录。
-   历史任务。
-   会话状态。
-   执行日志。

第一版不强制引入复杂数据库。

### 3.8 Web UI Layer

Phase 5 开始实现。Web 测试控制台是项目内置的 Web 管理和测试界面，
不是独立前端产品。

负责：

-   展示服务、模型、知识库和存储状态。
-   提供 Agent 对话测试入口。
-   展示网络诊断、知识检索和诊断历史结果。
-   展示错误状态。

模块结构（允许根据实际项目结构适当调整，但必须保持前后端职责清晰）：

``` text
app/web/
├── routes.py
├── templates/
│   └── index.html
└── static/
    ├── css/
    │   └── style.css
    ├── js/
    │   └── app.js
    └── images/
```

技术选型：HTML5、CSS3、原生 JavaScript、Fetch API，
模板渲染按需使用 Jinja2。不引入 Vue、React、Node.js。

架构约束：

1.  Web UI 只能通过后端 API 与业务层交互。
2.  前端不得直接调用 MiMo API。
3.  前端不得直接访问 SQLite 或 Chroma 数据库文件。
4.  优先复用已有 API 和 Service。
5.  不得重复实现 Agent、RAG 和网络诊断业务逻辑。
6.  不得伪造测试数据或虚构功能状态。
7.  未实现的功能必须明确标记为暂不可用。
8.  诊断结果必须区分 `simulation` 和 `local_diagnostic`。
9.  不得为了开发 Web UI 破坏已有核心模块。
10. 不得擅自删除或修改现有测试用例。

Web 页面规划：

| 页面 | 功能 | 数据来源 |
|---|---|---|
| Dashboard | 展示 API、MiMo、RAG、SQLite 状态 | 已有状态接口，如 `/health`、`/api/v1/agent/providers` |
| Agent Chat | 自然语言提问、模型回答、诊断状态、工具执行结果、下一步建议 | `POST /api/v1/agent/chat` |
| Network Diagnostics | 调用已经实现的网络诊断接口，展示诊断结果 | 已实现的诊断能力 |
| Knowledge Base | 调用已经实现的 RAG 接口，展示检索内容和文档来源 | 已实现的 RAG 能力 |
| History | 展示已有 API 提供的 SQLite 诊断历史 | 已实现的存储能力 |

页面功能必须根据当前实际代码确定，不能假设接口存在：

1.  开发前先确认目标接口和 Service 是否已经实现。
2.  只复用已经实现的接口；后端缺少读取接口时，可在 API Layer
    增加只读接口，优先复用已有 Service，不绕过 API 层直接访问数据。
3.  未实现的功能在页面明确标记为暂不可用，不得伪造数据或功能状态。

## 4. 项目目录规范

以下是项目逐步完成后的目标目录结构，不要求在 Phase 1
一次性创建所有目录和文件。

``` text
NetOps-Agent/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── routes/
│   │   │   ├── agent.py
│   │   │   └── health.py
│   │   └── schemas/
│   │       ├── request.py
│   │       └── response.py
│   ├── core/
│   │   ├── config.py
│   │   ├── llm.py
│   │   └── logging.py
│   ├── agent/
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── nodes.py
│   │   ├── routing.py
│   │   └── prompts.py
│   ├── tools/
│   │   ├── network_tools.py
│   │   └── registry.py
│   ├── network/
│   │   ├── base.py
│   │   ├── service.py
│   │   ├── mock_adapter.py
│   │   └── local_adapter.py
│   ├── web/
│   │   ├── routes.py
│   │   ├── templates/
│   │   │   └── index.html
│   │   └── static/
│   │       ├── css/
│   │       │   └── style.css
│   │       ├── js/
│   │       │   └── app.js
│   │       └── images/
│   ├── rag/
│   └── storage/
├── data/
│   ├── simulated_devices/
│   ├── sample_logs/
│   └── knowledge_base/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── web/
├── docs/
├── scripts/
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── CLAUDE.md
```

创建目录和文件的原则：

1.  只在当前阶段确实需要时创建。
2.  不创建没有实际用途的空文件。
3.  不为了提前匹配目标目录树而实现尚未进入阶段的模块。
4.  新增模块前先检查是否已有可复用实现。

## 5. LangGraph 工作流规范

### 5.1 Phase 1 工作流

第一阶段只实现：

``` text
START
  → analyze_network_issue
  → generate_response
  → END
```

要求：

1.  使用 `StateGraph`。
2.  定义明确的 State。
3.  节点职责清晰。
4.  通过 Agent Service 调用工作流。
5.  对模型异常和工作流异常进行处理。
6.  输出结构化结果。
7.  不执行网络诊断工具。
8.  诊断状态标记为 `preliminary`，不得声称故障已经得到验证。

### 5.2 后续目标工作流

Phase 2 至 Phase 4 逐步扩展为：

``` text
START
  → classify_issue
  → plan_diagnosis
  → execute_diagnostics
  → retrieve_knowledge
  → analyze_results
  → check_completeness
  → generate_report
  → END
```

要求：

1.  每个节点职责单一。
2.  使用明确的 State 定义。
3.  使用条件路由。
4.  工具结果必须写入 Agent State。
5.  支持多步骤诊断。
6.  设置最大执行步数和任务总超时。
7.  避免无限循环。
8.  对未验证的故障原因明确标记。
9.  工具执行失败时不得伪装成正常诊断结果。

`thread_id` 与会话持久化约定：

-   Phase 1 中，`thread_id` 仅作为请求关联标识。
-   Phase 1 不承诺跨请求保存对话历史。
-   未配置 Checkpointer 时，不得宣称 LangGraph 能够自动恢复历史状态。
-   Phase 4 再评估 SQLite 与 LangGraph
    Checkpointer，实现持久化会话状态。

## 6. 网络诊断工具规范

Phase 2 开始实现。

### 6.1 基础工具

-   `ping_host`
-   `dns_lookup`
-   `traceroute_host`
-   `check_tcp_port`

### 6.2 网络设备分析工具

-   `analyze_interface_status`
-   `analyze_routing_table`
-   `analyze_vlan_config`
-   `analyze_network_logs`

### 6.3 工具开发要求

1.  工具必须独立封装。
2.  使用 Pydantic 或等效明确的数据结构定义输入、输出。
3.  参数必须进行格式和范围校验。
4.  设置执行超时。
5.  捕获并分类异常。
6.  返回结构化结果。
7.  工具必须能够独立测试。
8.  不允许伪造检测结果。
9.  不允许任意执行用户提供的 Shell 命令。
10. 工具结果必须标记数据来源，例如 `simulation` 或 `local_diagnostic`。

### 6.4 网络工具安全规范

项目默认采用只读诊断策略。

**⚠️ 目标白名单当前默认已放开（`DIAG_ALLOW_ALL_TARGETS=true`）**，
允许对任意 IP 执行诊断工具，仅做输入格式校验。仅限受控测试环境使用；
如需恢复白名单防护，设置 `DIAG_ALLOW_ALL_TARGETS=false` 并配置
`DIAG_ALLOWED_TARGETS`。

禁止 Agent 自动执行：

-   修改交换机配置。
-   修改路由表。
-   修改 ACL。
-   修改 VLAN。
-   重启设备。
-   删除网络配置。
-   执行未经授权的系统命令。

命令执行要求：

1.  禁止使用 `shell=True` 执行用户输入。
2.  系统命令必须使用固定命令和参数列表，不得拼接用户输入形成 Shell
    命令。
3.  对 IP、域名、端口和其他参数进行严格校验（格式、范围、注入防护）。
4.  所有网络检测必须设置超时和合理的资源限制。
5.  目标范围限制通过 `DIAG_ALLOW_ALL_TARGETS` 控制：
    -   `true`（当前默认）：允许任意 IP，仅做输入格式校验。
    -   `false`：启用白名单，仅允许 `DIAG_ALLOWED_TARGETS` 列出的目标。
6.  禁止扫描或访问未经授权的网络、主机和设备（即使白名单已放开，
    使用者仍须遵守当地法律与授权范围）。
7.  工具执行前必须校验参数和权限。
8.  模型生成的参数不能直接视为可信输入。

未来若增加配置变更能力，必须采用显式权限控制、人工确认、审计日志和回滚策略。

## 7. Phase 开发规划

### Phase 1：基础 Agent 工程

目标：完成 Xiaomi MiMo + LangGraph + FastAPI 的基础工程，提供可运行的
Agent API。

任务：

1.  P1-01：检查项目目录，创建基础工程结构。
2.  P1-02：创建 `pyproject.toml`。
3.  P1-03：实现配置管理。
4.  P1-04：实现 Xiaomi MiMo 模型接入。
5.  P1-05：实现 `NetOpsState`。
6.  P1-06：实现 LangGraph 基础工作流。
7.  P1-07：实现 Agent Service。
8.  P1-08：实现 FastAPI 接口。
9.  P1-09：实现日志和异常处理。
10. P1-10：实现自动化测试。
11. P1-11：编写 README。

第一阶段 API：

  方法   路径                        作用
------ --------------------------- ----------------------
  GET    `/health`                   服务健康检查
  GET    `/api/v1/agent/providers`   查询当前模型配置状态
  POST   `/api/v1/agent/chat`        与 Agent 对话

`providers` 接口只返回当前配置的供应商、模型型号和配置状态，不得返回 API
Key 或其他敏感配置。

`POST /api/v1/agent/chat` 请求示例：

``` json
{
  "message": "我的电脑可以 Ping 通网关，但是无法访问互联网",
  "thread_id": "demo-001"
}
```

响应结构示例（仅表示字段格式，不代表真实诊断结果）：

``` json
{
  "success": true,
  "thread_id": "demo-001",
  "answer": "根据当前描述，建议优先检查 DNS 解析、默认路由和出口 NAT。",
  "diagnosis_status": "preliminary",
  "executed_tools": [],
  "next_steps": [
    "检查 DNS 解析",
    "检查默认路由",
    "检查出口 NAT"
  ]
}
```

Phase 1 验收标准：

-   MiMo API 普通对话调用成功。
-   Pro 和 Flash 能通过配置切换。
-   LangGraph 基础工作流正常运行。
-   FastAPI 正常运行。
-   API 返回符合 Schema 的结构化 JSON。
-   错误 Key、超时和模型服务异常有清晰处理。
-   默认 Pytest 不依赖真实 API Key。
-   使用 Mock 模型完成离线测试。
-   真实 MiMo API 测试单独运行。
-   README 能指导环境配置、启动和测试。

**Phase 1 不开发：**

-   Ping、DNS、Traceroute、TCP 等网络工具。
-   模拟交换机、路由器、防火墙。
-   Function Calling 工具执行流程。
-   RAG。
-   SQLite 和 Checkpointer。
-   Web 前端。
-   Docker。
-   多 Agent。
-   Redis、Celery 等任务系统。

### Phase 2：网络诊断工具与 Tool Calling

实现：

-   Ping。
-   DNS。
-   Traceroute。
-   TCP Port。
-   模拟交换机、路由器和防火墙。
-   接口状态分析。
-   路由表分析。
-   日志分析。
-   LangGraph 工具调用流程。

必须专门验证 Xiaomi MiMo 与 LangChain/LangGraph
的工具调用兼容性，至少覆盖：

1.  普通对话。
2.  单次工具调用。
3.  工具参数解析与校验。
4.  工具执行结果写回 Agent State。
5.  多轮工具调用。
6.  工具执行失败和异常恢复。
7.  思考模式下的多轮工具调用。

MiMo 思考模式可能涉及 `reasoning_content`
的多轮传递。必须使用真实接口验证所选模型、SDK
和适配器的行为；如果适配器无法正确保留或传递必要字段，应先定位兼容性问题，不得假定普通聊天成功就代表多轮工具调用成功。

### Phase 3：RAG 知识库

实现：

-   PDF 加载。
-   TXT 加载。
-   Markdown 加载。
-   文本切分。
-   BGE Embedding。
-   Chroma。
-   Top-K 检索。
-   知识来源引用。

要求：

1.  文档加载和切分过程可测试。
2.  检索结果保留来源信息。
3.  回答引用必须能对应实际检索到的文档片段。
4.  不得编造知识库中不存在的引用。
5.  区分知识库内容与模型推断。

### Phase 4：完整 Agent 故障诊断

实现：

-   故障分类。
-   诊断规划。
-   多工具调用。
-   RAG 检索。
-   多轮诊断。
-   结果分析。
-   故障报告。
-   SQLite 诊断记录。
-   根据需要引入 LangGraph Checkpointer。

### Phase 5：Web UI + 项目测试与完善

目标：交付项目内置的 Web 测试控制台，并补齐项目测试与文档。

实现：

-   Web 测试控制台基础框架（`app/web/`，静态资源与模板）。
-   Dashboard 页面（服务、模型、知识库、存储状态）。
-   Agent Chat 页面（对话、诊断状态、工具执行结果、下一步建议）。
-   Network Diagnostics 页面（调用已有网络诊断能力）。
-   Knowledge Base 页面（调用已有 RAG 能力）。
-   History 页面（展示已有 SQLite 诊断历史）。
-   `tests/web/` 测试。
-   项目测试与完善。

要求：

1.  Web UI 只能通过后端 API 与业务层交互，不直连 MiMo、SQLite、Chroma。
2.  不重复实现 Agent、RAG 和网络诊断业务逻辑。
3.  页面功能以当前实际代码为准；未实现的功能明确标记为暂不可用。
4.  诊断结果必须区分 `simulation` 和 `local_diagnostic`。
5.  后端缺少只读接口时，在 API Layer 增加只读接口并复用已有 Service。
6.  不得为了开发 Web UI 破坏已有核心模块或删除、修改现有测试用例。

Phase 5 验收标准：

-   Web 首页可正常访问，静态资源可加载。
-   Agent 页面能调用真实后端接口。
-   请求参数和响应数据正确。
-   后端异常时页面能正确展示错误。
-   页面不泄露 API Key。
-   `tests/web/` 测试通过。
-   已有单元测试和集成测试继续通过。
-   README 能指导 Web 启动和使用。

### Phase 6：工程化和发布

实现：

-   Docker。
-   GitHub 发布。
-   发布前安全检查。

未经用户确认，不执行远程 Git Push。

## 8. 编码规范

必须遵守：

1.  使用当前 Python 3.13.9 环境。
2.  遵循 PEP 8。
3.  使用类型注解。
4.  重要函数提供 Docstring。
5.  模块职责清晰。
6.  避免循环依赖。
7.  避免重复代码。
8.  不滥用类和设计模式。
9.  优先使用稳定维护且兼容当前 Python 版本的依赖。
10. 使用 `pyproject.toml` 管理项目。
11. 使用 Ruff 检查代码。
12. 使用 Pytest 测试代码。
13. 不为了追求技术复杂度引入不必要的依赖。
14. 不随意修改已经通过测试的代码。

## 9. 异常处理规范

需要考虑：

-   API Key 缺失。
-   API Key 无效。
-   MiMo 服务不可用。
-   请求超时。
-   请求频率限制。
-   模型响应异常。
-   Agent 工作流异常。
-   工具执行失败。
-   网络连接失败。
-   参数校验失败。

异常处理要求：

1.  对外返回安全、明确且不泄露内部凭证的错误信息。
2.  日志记录必要的错误上下文，但不记录密钥、密码和敏感网络信息。
3.  只对超时、临时服务错误、限流等可恢复错误进行有限重试。
4.  对无效 API Key、参数错误等不可恢复错误不进行重试。
5.  重试采用指数退避，并设置最大重试次数。
6.  超过重试次数后返回明确错误。
7.  对不可恢复错误及时终止任务。
8.  不允许将异常伪装成正常诊断结果。
9.  区分单次模型请求超时与整个 Agent 任务超时。

超时配置约定：

-   `MIMO_TIMEOUT`：单次模型请求超时时间。
-   `AGENT_TIMEOUT`：整个 Agent 任务最大执行时间，后续阶段按需加入。
-   `AGENT_MAX_STEPS`：Agent 工具调用或诊断步骤的最大执行次数，Phase 2
    开始按需加入。

## 10. Agent 诊断结果真实性规范

Agent 必须区分推测、初步分析和实际检测结论。

建议统一使用以下状态：

  状态            含义
--------------- ----------------------------------------------
  `preliminary`   仅根据用户描述进行初步分析，尚未执行验证工具
  `suspected`     有一定依据的疑似原因，但尚未得到充分验证
  `confirmed`     有实际工具检测结果或可靠证据支持的结论
  `failed`        诊断工具或诊断流程执行失败，无法得出对应结论

要求：

1.  只有实际执行了相应工具并获得有效证据，才能将对应检测结果标记为已执行。
2.  模拟设备返回的结果必须标记为 `simulation`。
3.  本机实际执行的检测必须标记为 `local_diagnostic`。
4.  不得把模型推断写成实际检测结果。
5.  工具执行失败时，明确说明失败原因和未完成的检查。
6.  报告中的结论应能追溯到用户描述、工具结果或知识库来源。

## 11. 测试规范

使用 Pytest。

### 11.1 单元测试

测试：

-   配置管理。
-   模型创建模块。
-   Agent 节点。
-   网络工具（Phase 2 开始）。
-   数据结构。
-   参数校验。
-   异常处理。

### 11.2 集成测试

测试：

-   LangGraph 工作流。
-   FastAPI 接口。
-   Agent Service。
-   工具调用流程（Phase 2 开始）。
-   RAG 检索流程（Phase 3 开始）。

### 11.3 Web 测试

测试目录：`tests/web/`（Phase 5 开始）。

至少验证：

-   Web 首页正常访问。
-   静态资源正常加载。
-   Agent 页面能调用真实后端接口。
-   请求参数和响应数据正确。
-   后端异常时页面能够正确展示错误。
-   页面不能泄露 API Key。

### 11.4 测试原则

1.  默认测试不能依赖真实 API Key。
2.  使用 Mock 模型进行自动化测试。
3.  真实 MiMo API 测试单独运行，并明确标记。
4.  不允许伪造测试通过结果。
5.  没有执行的测试不能标记为通过。
6.  每个 Phase 完成后必须执行对应测试。
7.  测试失败时先分析原因，不得通过删除测试或弱化断言掩盖问题。
8.  不得擅自删除或修改已经通过的测试用例；Web 开发不得影响已有测试。

## 12. GitHub 安全规范

项目计划公开发布。

发布前检查：

-   `.env` 文件。
-   API Key。
-   密码。
-   数据库凭证。
-   真实设备配置。
-   个人信息。
-   企业敏感网络信息。
-   日志和测试数据中的敏感内容。

要求：

1.  `.env` 必须加入 `.gitignore`。
2.  提供 `.env.example`，只包含示例配置和空密钥。
3.  不提交真实 API Key。
4.  演示设备数据使用虚构信息。
5.  不提交真实企业网络拓扑和设备配置。
6.  不未经用户确认执行远程 Push。
7.  不未经用户确认删除远程仓库内容。
8.  发布前检查 Git 暂存区和提交内容，避免误提交敏感文件。

## 13. Claude Code 工作方式

你是本项目的高级 Python / AI Agent 工程师和开发负责人。

必须遵循：

1.  开发前先阅读本文件和现有项目代码。
2.  修改前检查目录、文件内容和当前 Git 状态。
3.  不覆盖已有文件；如需修改，先说明修改原因和范围。
4.  开始编码前先给出当前任务的实现计划。
5.  按 Phase 和任务编号逐步开发。
6.  每次修改范围尽量明确，避免一次性生成整个项目。
7.  完成后列出新增和修改文件。
8.  解释关键设计和取舍。
9.  提供可复制的运行命令。
10. 执行相关测试并如实报告结果。
11. 没有执行的测试不得标记为通过。
12. 遇到架构问题主动指出，不得擅自大规模重构。
13. 不得伪造项目数据、测试结果或功能完成状态。
14. 不得擅自进入下一 Phase，等待用户确认。
15. 不执行未经用户确认的远程 Git Push 或破坏性操作。

每个任务完成时输出：

-   完成内容。
-   新增文件。
-   修改文件。
-   核心实现说明。
-   运行命令。
-   测试结果。
-   遗留问题。
-   下一步建议。

每个 Phase
结束时，还需汇总阶段验收情况，并等待用户确认后再进入下一阶段。

