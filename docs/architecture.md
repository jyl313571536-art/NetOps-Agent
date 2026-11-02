# NetOps Agent 架构说明

## 1. 系统分层

项目采用模块化分层架构，各层职责单一、依赖方向自上而下：

| 层 | 目录 | 职责 | 禁止事项 |
|---|---|---|---|
| API Layer | `app/api/` | 接收请求、参数校验、调用 Agent Service、统一错误响应 | 不直接调用 LLM，不执行网络命令 |
| Agent Layer | `app/agent/` | 故障分类、诊断规划、工作流编排、结果分析、故障报告 | 节点不自行创建模型实例 |
| LLM Layer | `app/core/llm.py` | MiMo 模型实例创建、配置读取、超时与重试 | 不做多供应商工厂（当前仅一个供应商） |
| Network Tools Layer | `app/tools/` | 8 个诊断工具封装、入参校验、结果结构化 | 不依赖大模型，不执行写操作 |
| Network Adapter Layer | `app/network/` | 隔离模拟设备与本机真实检测、目标白名单 | 不访问未授权网络 |
| RAG Layer | `app/rag/` | 文档加载、切分、BGE 向量化、Chroma 检索、引用校验 | 不编造知识引用 |
| Storage Layer | `app/storage/` | SQLite 诊断记录写入 | 第一版只存不查 |
| Core | `app/core/` | 配置、日志、异常、脱敏 | 不记录 API Key |

## 2. 诊断工作流（LangGraph StateGraph）

```
START
  → classify_issue        故障分类（connectivity/dns/routing/vlan/firewall/unknown）
  → plan_diagnosis        诊断规划（结构化工具计划，非法工具名/参数剔除）
  → execute_diagnostics   多工具执行（结果写回 State，失败如实记录）
  → retrieve_knowledge    RAG Top-K 检索（片段+来源+分数）
  → analyze_results       结果分析（判定证据是否充分）
  → check_completeness    条件路由
  │     ├─ 证据不足 且 未达 AGENT_MAX_STEPS 且 未超 AGENT_TIMEOUT → plan_diagnosis
  │     └─ 其他情况 → generate_report
  → generate_report       故障报告（结论/步骤/状态）
  → END
```

## 3. 关键设计决策

### 3.1 诊断规划采用结构化计划而非自由工具调用

`plan_diagnosis` 输出固定格式的工具计划（工具名 + JSON 参数 + 理由），
执行前经 Pydantic 校验，未知工具名与非法参数一律剔除。
好处：计划可审计、可测试，避免模型生成的参数绕过校验直接执行。

### 3.2 引用真实性三层保障

| 层 | 机制 |
|---|---|
| 提示词层 | 要求 `[引用N]` 标记知识库依据，区分工具结果/知识库/推断 |
| 结构层 | `citations` 字段只含真实检索片段（来源+原文+分数） |
| 校验层 | `extract_citations` 逐条比对，编号越界的编造引用剔除 |

### 3.3 诊断状态判定规则

| 条件 | 状态 |
|---|---|
| 未执行任何工具 | `preliminary` |
| 工具全部失败 | `failed` |
| 有工具成功，模型未自称 confirmed | `suspected` |
| 模型自称 confirmed 且至少一个工具成功 | `confirmed` |

### 3.4 数据来源强制标记

所有工具结果必须带 `source` 字段：
- `local_diagnostic`：本机真实执行的检测（Ping/DNS/Traceroute/TCP）
- `simulation`：模拟设备虚构数据（接口/路由/VLAN/日志）

两类来源在提示词、报告、API 响应中全程保留，不得混淆。

## 4. 安全设计

| 措施 | 实现位置 |
|---|---|
| 诊断目标白名单（默认仅本机回环） | `app/network/validation.py` |
| 禁止 shell=True，固定命令参数列表 | `app/network/local_adapter.py` |
| 设备 ID 防路径穿越 | `app/network/validation.py` |
| 入参 Pydantic 校验 | `app/tools/network_tools.py` |
| 工具执行超时 | `DIAG_TIMEOUT` |
| 多轮循环上限 | `AGENT_MAX_STEPS` / `AGENT_TIMEOUT` |
| 日志脱敏（sk-* 遮蔽） | `app/core/exceptions.py:sanitize` |
| 错误响应不泄露内部细节 | `safe_message` 与 `detail` 分离 |

## 5. 依赖注入

`AgentService` 的 `llm`、`registry`、`rag_service`、`storage`
均由外部注入，测试可替换为 Mock，生产环境由 `get_agent_service()` 装配。
Agent 节点不自行创建模型实例（见 CLAUDE.md LLM Layer 规范）。
