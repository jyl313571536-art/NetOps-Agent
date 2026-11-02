"""Agent 服务层。

封装 LangGraph 完整诊断工作流，组装故障报告并保存诊断记录。
"""

import logging
import time
import uuid

from langchain_core.language_models import BaseChatModel

from app.agent.graph import create_graph
from app.core.config import get_settings
from app.core.llm import create_llm
from app.models.diagnosis import (
    AgentResult,
    Citation,
    DiagnosisReport,
    DiagnosisStatus,
    PossibleCause,
    ToolRecord,
    to_tool_records,
)
from app.rag.models import RetrievedChunk
from app.rag.service import RagService, extract_citations
from app.storage.sqlite import DiagnosisStorage, get_storage
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# 确定性判定规则，提示词中的状态约束与之对应（见 prompts.py REPORT_SYSTEM_PROMPT）
determine_diagnosis_status = DiagnosisStatus.adjudicate


def build_report(
    issue_category: str,
    analysis: str,
    tool_records: list[ToolRecord],
    citations: list[Citation],
    next_steps: list[str],
    status: DiagnosisStatus,
) -> DiagnosisReport:
    """组装故障诊断报告。

    未验证的结论在 unverified_points 中明确列出，不与工具证据混淆。
    """
    cause = PossibleCause(
        cause=analysis or "（无分析结论）",
        status=status,
        evidence="; ".join(
            f"{r.tool_name}[{r.source or '未知'}]" for r in tool_records
        )
        or "无工具证据",
        source_types=sorted({r.source for r in tool_records if r.source}),
    )
    unverified: list[str] = []
    if status in (DiagnosisStatus.PRELIMINARY, DiagnosisStatus.SUSPECTED):
        unverified.append("结论尚未被工具检测充分验证，标记为推测")
    for record in tool_records:
        if not record.success:
            unverified.append(f"工具 {record.tool_name} 执行失败: {record.error}")
    return DiagnosisReport(
        issue_category=issue_category,
        summary=analysis,
        possible_causes=[cause],
        unverified_points=unverified,
        tool_evidence=tool_records,
        knowledge_citations=citations,
        recommendations=next_steps,
    )


class AgentService:
    """Agent 服务，负责执行完整诊断工作流并返回结构化结果。"""

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        registry: ToolRegistry | None = None,
        rag_service: RagService | None = None,
        storage: DiagnosisStorage | None = None,
        fast_llm: BaseChatModel | None = None,
    ) -> None:
        """各依赖由外部注入，测试时传入 Mock。

        模型分级：llm 用于最终报告，fast_llm 用于分类/规划/分析等迭代节点。
        测试只传 llm 时，所有节点统一用它（保持测试行为不变）。
        """
        settings = get_settings()
        self._llm = llm or create_llm()
        # 生产模式（未注入 llm）自动创建快速模型；测试注入时保持统一 Mock
        if fast_llm is None and llm is None:
            fast_llm = create_llm(model=settings.mimo_fast_model)
        self._registry = registry or ToolRegistry()
        self._rag = rag_service or RagService()
        self._storage = storage or get_storage()
        self._graph = create_graph(
            self._llm,
            self._registry,
            self._rag,
            fast_llm=fast_llm,
            max_rounds=settings.agent_max_steps,
            timeout_seconds=settings.agent_timeout,
        )

    def chat(self, message: str, thread_id: str | None = None) -> AgentResult:
        """执行一次完整故障诊断。

        thread_id 仅作请求关联标识，不保存跨请求历史
        （未配置 Checkpointer，不承诺跨请求恢复对话状态）。
        """
        tid = thread_id or uuid.uuid4().hex[:12]
        started = time.time()
        result = self._graph.invoke(_initial_state(message, tid, started))
        return self._finalize(result, message, tid, started)

    def chat_stream(self, message: str, thread_id: str | None = None):
        """流式执行诊断，按节点产出进度事件。

        Yields:
            dict 事件，形如：
            {"event": "node", "data": {"node": 节点名, "summary": 摘要}}
            {"event": "result", "data": {最终 ChatResponse 字段}}
            {"event": "error", "data": {"error_code": ..., "message": ...}}
        """
        tid = thread_id or uuid.uuid4().hex[:12]
        started = time.time()
        merged: dict = _initial_state(message, tid, started)
        try:
            # stream 默认产出 {节点名: 状态增量}，逐节点合并出全量终态
            for chunk in self._graph.stream(merged):
                node = next(iter(chunk), "unknown")
                delta = chunk.get(node) or {}
                merged.update(delta)
                yield {
                    "event": "node",
                    "data": {"node": node, "summary": _node_summary(node, delta)},
                }
            agent_result = self._finalize(merged, message, tid, started)
            yield {"event": "result", "data": agent_result.model_dump(mode="json")}
        except Exception as exc:  # noqa: BLE001 - 流式通道也要如实上报错误
            from app.core.exceptions import NetOpsError, sanitize

            logger.error("流式诊断失败: %s", sanitize(str(exc)))
            if isinstance(exc, NetOpsError):
                code, msg = exc.error_code, exc.safe_message
            else:
                code, msg = "internal_error", "服务器内部错误"
            yield {"event": "error", "data": {"error_code": code, "message": msg}}

    def _finalize(
        self, result: dict, message: str, tid: str, started: float
    ) -> AgentResult:
        """把工作流终态组装为 AgentResult 并落库（chat / chat_stream 共用）。"""
        tool_records = to_tool_records(result.get("tool_results", []))
        status = DiagnosisStatus.adjudicate(
            result.get("tool_results", []), result.get("diagnosis_status")
        )
        answer, citations = _extract_valid_citations(result)
        next_steps = result.get("next_steps", [])
        report = build_report(
            issue_category=result.get("issue_category", "unknown"),
            analysis=result.get("analysis", ""),
            tool_records=tool_records,
            citations=citations,
            next_steps=next_steps,
            status=status,
        )
        agent_result = AgentResult(
            thread_id=tid,
            answer=answer,
            diagnosis_status=status,
            executed_tools=[r.tool_name for r in tool_records],
            tool_results=tool_records,
            next_steps=next_steps,
            citations=citations,
            report=report,
        )
        self._save(agent_result, message, started)
        return agent_result

    def _save(self, agent_result: AgentResult, message: str, started: float) -> None:
        """保存诊断记录；存储失败不影响返回结果。"""
        try:
            agent_result.diagnosis_id = self._storage.save_record(
                agent_result,
                user_message=message,
                duration_ms=int((time.time() - started) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 - 存储失败不影响返回
            logger.error("保存诊断记录失败: %s", exc)


def _extract_valid_citations(state: dict) -> tuple[str, list[Citation]]:
    """校验模型引用，剔除编造引用（编号越界的标记）。"""
    retrieved = [
        RetrievedChunk(**item) for item in state.get("retrieved_chunks", [])
    ]
    cleaned_answer, citations, invalid = extract_citations(
        state.get("answer", ""), retrieved
    )
    if invalid:
        logger.warning("剔除无效引用 %s", invalid)
    return cleaned_answer, citations


def _initial_state(message: str, tid: str, started: float) -> dict:
    """构造工作流初始状态。"""
    return {
        "user_message": message,
        "thread_id": tid,
        "tool_results": [],
        "retrieved_chunks": [],
        "diagnosis_round": 0,
        "started_at": started,
    }


def _node_summary(node: str, state: dict) -> str:
    """为流式进度事件生成节点摘要（只含关键信息，不倒出全量状态）。"""
    if node == "classify_issue":
        return f"故障分类: {state.get('issue_category', '未知')}"
    if node == "plan_diagnosis":
        plan = state.get("diagnosis_plan", [])
        return f"诊断规划: {len(plan)} 个步骤"
    if node == "execute_diagnostics":
        tools = state.get("executed_tools", [])
        return f"工具执行: {', '.join(tools) if tools else '无'}"
    if node == "retrieve_knowledge":
        return f"知识检索: {len(state.get('retrieved_chunks', []))} 个片段"
    if node == "analyze_results":
        ok = "是" if state.get("evidence_sufficient") else "否"
        return f"结果分析: 证据充分={ok}"
    if node == "generate_report":
        return "故障报告已生成"
    return node


_service_instance: AgentService | None = None


def get_agent_service() -> AgentService:
    """获取 Agent 服务单例（FastAPI 依赖注入入口）。"""
    global _service_instance
    if _service_instance is None:
        _service_instance = AgentService()
    return _service_instance
