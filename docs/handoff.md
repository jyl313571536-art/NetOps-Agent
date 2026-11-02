# NetOps Agent 项目交接文档

更新时间：2026-11-02
适用范围：Phase 5 完成后的性能优化（B+C+D+E）交接

---

## 一、当前进度

### 已完成（全部验收通过）

| Phase | 内容 | 状态 |
|---|---|---|
| Phase 1 | 基础 Agent 工程（MiMo + LangGraph + FastAPI） | ✅ |
| Phase 2 | 8 个网络诊断工具 + Function Calling 兼容性验证 | ✅ |
| Phase 3 | RAG 知识库（BGE + Chroma + 引用校验防编造） | ✅ |
| Phase 4 | 完整诊断工作流（分类→规划→执行→检索→分析→多轮→报告）+ SQLite | ✅ |
| Phase 5 | Web 测试控制台（5 页面）+ tests/web/ | ✅ |

### Git 状态

- 初始提交：`f7641b3` "Initial commit: NetOps Agent v1.0 (Phase 1-5)"（95 文件）
- **未提交改动：15 个文件**（性能优化 B+C+D+E，见下）
- 远程仓库：无。从未执行 Push。

### 性能优化（已实施、已实测、未提交）

针对 "Agent Chat 回复慢" 的排查结论：95% 时间在 6 次串行 LLM 调用。

| 编号 | 优化 | 效果 |
|---|---|---|
| B | 收紧多轮判定（分析节点明确规则 + 空计划直接收束） | 简单问题少跑一轮 |
| C | 模型分级：分类/规划/分析用 `mimo-v2.6-flash`，报告用 `mimo-v2.6-pro` | 单次延迟大降 |
| D | 提示词瘦身 + 工具清单从 TOOL_SPECS 动态生成 | 上下文变短 |
| E | SSE 流式（`POST /api/v1/agent/chat/stream`），逐节点推送进度 | 体感不卡 |

**同口径实测**：简单问题 95.3s → **48.4s**（-49%）；复杂问题 128.3s → **108.8s**（-15%）。

---

## 二、验证基线（改动后必须保持）

```bash
source .venv/Scripts/activate
ruff check .                          # 必须 All checks passed
pytest -m "not real_api"              # 必须 148 passed
pytest -m real_api                    # 需 MIMO_API_KEY，必须 9 passed
```

当前状态：Ruff ✅ / 离线 148 ✅ / 真实 API 9 ✅ / 覆盖率 92%。

---

## 三、关键约束（摘自 CLAUDE.md v1.2，勿违反）

1. Python 固定 3.13.9；MiMo 单一供应商；不引入 Vue/React/Node.js。
2. 前端只经后端 API 交互，不直连 MiMo/SQLite/Chroma。
3. 诊断结果必须区分 `simulation` / `local_diagnostic`；未验证结论不得标 `confirmed`。
4. 诊断目标白名单默认仅本机回环（`DIAG_ALLOWED_TARGETS`）。
5. 不提交真实 API Key；`data/netops.db`、`data/chroma_db/`、`.coverage` 已被 .gitignore 排除。
6. 远程 Push / Docker / GitHub 发布属于 Phase 6，必须用户确认。
7. 真实性要求：只描述已实现并验证的功能，不得伪造数据、测试结果或功能状态。

---

## 四、下一步计划

### 待办 1：提交性能优化改动（优先）

15 个未提交文件，建议 commit message：

```
perf: 模型分级 + SSE 流式 + 多轮判定收紧

- 迭代节点用 mimo-v2.6-flash，报告用 pro（简单问题 -49%）
- 新增 POST /api/v1/agent/chat/stream（SSE 逐节点进度）
- 分析节点证据判定规则收紧，空计划直接收束
- 工具清单从 TOOL_SPECS 动态生成，提示词瘦身
```

### 待办 2：Phase 6 工程化和发布（未开始）

1. Docker（Dockerfile + docker-compose，注意 .env 与 data 目录挂载）
2. GitHub 发布（仓库创建、README 徽章、发布说明）
3. 发布前安全检查（CLAUDE.md 第 12 节清单逐项核对）
4. **远程 Push 需用户明确确认**

### 可选优化（已评估未做）

- 可选 A（合并 classify 进 plan 节点，-1 次调用）：用户未选
- 复杂问题仍受 `AGENT_TIMEOUT`（默认 120s）制约，如需可调 `AGENT_MAX_STEPS`/`AGENT_TIMEOUT`
- `reasoning_content` 被 langchain-openai 适配器丢弃（不影响多轮工具调用，README 已记录）
- LICENSE 文件（GitHub 开源惯例，规范未要求）

---

## 五、常用命令速查

```bash
# 启动服务（Web 控制台在 http://127.0.0.1:8000/）
uvicorn app.main:app --reload

# 真实诊断演示（3 个案例）
set HF_ENDPOINT=https://hf-mirror.com   # 国内下载 BGE 模型用
python scripts/run_demo.py

# API
GET  /health
GET  /api/v1/agent/providers
POST /api/v1/agent/chat          # 同步
POST /api/v1/agent/chat/stream   # SSE 流式
POST /api/v1/diagnostics/run     # 单工具执行
POST /api/v1/knowledge/search    # 知识检索
GET  /api/v1/history             # 诊断历史
```

环境变量见 `.env.example`（Key 在 Windows 环境变量中亦可生效）。

---

## 六、项目结构速览

```
app/
├── api/routes/     # 5 个路由模块（agent/health/diagnostics/knowledge/history）
├── agent/          # LangGraph 工作流（graph/nodes/routing/state/prompts/service）
├── core/           # config/llm/logging/exceptions
├── models/         # 诊断状态与报告模型
├── network/        # 适配层（mock/local + 白名单校验）
├── rag/            # loaders/splitter/embeddings/store/service
├── storage/        # SQLite 诊断记录（含 list_records 只读查询）
├── tools/          # TOOL_SPECS 唯一工具元数据源 + registry
└── web/            # Web 控制台（原生 HTML/CSS/JS）
tests/              # unit / integration / web（148 离线 + 9 真实 API）
docs/               # architecture.md / demo_cases.md / demos/ / handoff.md
data/               # knowledge_base / simulated_devices / sample_logs（源数据入库）
```

---

## 七、已知问题与注意事项

1. **复杂开放式问题**（如"全面诊断"）仍需约 2 分钟，受 LLM 延迟与 `AGENT_TIMEOUT` 制约，属预期行为。
2. 测试中的 `sk-*` 字符串为脱敏测试用假 key，非真实密钥。
3. MiMo `reasoning_content` 字段经 langchain-openai 适配器不保留（已验证不影响多轮工具调用）。
4. Windows 下 Git Bash 使用 `source .venv/Scripts/activate`；curl 引号易被转义，建议用 python httpx 发请求。
