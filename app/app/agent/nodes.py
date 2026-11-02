"""LangGraph 工作流节点实现（Phase 4 完整诊断工作流）。

节点通过依赖注入接收模型实例与工具注册表，不得自行创建模型。
复用 Phase 2/3 已验证的解析、格式化与异常映射函数。
"""

import json
import logging
import re
from collections.abc import Callable
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage

from app.agent.prompts import (
    ANALYZE_SYSTEM_PROMPT,
    ANALYZE_USER_TEMPLATE,
    CLASSIFY_SYSTEM_PROMPT,
    CLASSIFY_USER_TEMPLATE,
    PLAN_SYSTEM_PROMPT,
    PLAN_USER_TEMPLATE,
    REPORT_SYSTEM_PROMPT,
    REPORT_USER_TEMPLATE,
)
from app.agent.state import NetOpsState
from app.core.exceptions import (
    ModelResponseError,
    classify_llm_error,
)
from app.models.diagnosis import DiagnosisStatus, IssueCategory
from app.rag.service import format_marker
from app.tools.network_tools import TOOL_SPECS
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

CONCLUSION_PREFIX = "结论"
STEP_PREFIX = "步骤"
STATUS_PREFIX = "状态"
PLAN_LINE_RE = re.compile(
    r"^工具[：:]\s*(?P<tool>\S+)\s+参数[：:]\s*(?P<args>\{.*?\})\s+理由[：:]\s*(?P<reason>.*)$"
)


def _invoke_llm(llm: BaseChatModel, messages: list[AnyMessage]) -> AnyMessage:
    """调用模型，统一映射异常。"""
    try:
        return llm.invoke(messages)
    except Exception as exc:
        raise classify_llm_error(exc) from exc


def _call_llm(llm: BaseChatModel, system_prompt: str, user_prompt: str) -> str:
    """调用模型并返回文本内容，响应为空时抛出异常。"""
    response = _invoke_llm(
        llm,
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ],
    )
    text = getattr(response, "content", None)
    if not isinstance(text, str) or not text.strip():
        raise ModelResponseError("模型返回内容为空或格式异常")
    return text.strip()


def _extract_value(line: str, *tokens: str) -> str | None:
    """提取「<token><分隔符>值」行中的值。

    tokens 为可接受的前缀（含分隔符），返回第一个命中前缀之后的内容。
    """
    for token in tokens:
        if line.startswith(token):
            return line[len(token) :].strip()
    return None


def _field_tokens(prefix: str) -> tuple[str, ...]:
    """字段前缀的可接受写法：方括号式、全角冒号、半角冒号。"""
    return (f"[{prefix}]", f"{prefix}：", f"{prefix}:")


def _extract_after_prefix(line: str, prefix: str) -> str | None:
    """提取「前缀：值」行中的值，支持全角/半角冒号。"""
    return _extract_value(line, f"{prefix}：", f"{prefix}:")


def parse_generation(text: str) -> tuple[str, list[str]]:
    """解析生成节点输出，提取结论和后续步骤。

    格式要求：结论：<...>，步骤：<...>（可多行）。
    解析不出结论时返回原文作为结论，步骤为空列表，不伪造结构化结果。
    """
    conclusion = ""
    steps: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        value = _extract_after_prefix(stripped, CONCLUSION_PREFIX)
        if value is not None:
            conclusion = value
            continue
        value = _extract_after_prefix(stripped, STEP_PREFIX)
        if value:
            steps.append(value)
    if not conclusion:
        conclusion = text
    return conclusion, steps


def parse_final_response(text: str) -> tuple[str, list[str], str | None]:
    """解析最终回复：结论、步骤、诊断状态。"""
    conclusion, steps = parse_generation(text)
    status: str | None = None
    for line in text.splitlines():
        value = _extract_after_prefix(line.strip(), STATUS_PREFIX)
        if value and value.lower() in set(DiagnosisStatus):
            status = value.lower()
            break
    return conclusion, steps, status


def parse_category(text: str) -> str:
    """解析故障分类，非法值归入 unknown。"""
    candidate = text.strip().split()[0].lower() if text.strip() else ""
    candidate = candidate.strip("。.，,；;")
    if candidate in set(IssueCategory):
        return candidate
    return IssueCategory.UNKNOWN.value


def parse_plan(text: str, known_tools: set[str]) -> list[dict]:
    """解析诊断计划，非法工具名与非法 JSON 参数一律剔除。

    格式：工具：<名> 参数:<JSON> 理由：<文本>，或输出"无"。
    返回合法步骤列表（dict：tool/args/reason），不伪造计划。
    """
    steps: list[dict] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped in {"无", "无。", "不需要"}:
            continue
        match = PLAN_LINE_RE.match(stripped)
        if not match:
            continue
        tool = match.group("tool")
        if tool not in known_tools:
            logger.warning("计划中的未知工具被剔除: %s", tool)
            continue
        try:
            args = json.loads(match.group("args"))
            if not isinstance(args, dict):
                raise ValueError("参数必须是 JSON 对象")
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("计划步骤参数非法被剔除: %s (%s)", tool, exc)
            continue
        steps.append(
            {"tool": tool, "args": args, "reason": match.group("reason").strip()}
        )
    return steps


def parse_analysis(text: str) -> tuple[str, bool]:
    """解析综合分析，返回 (分析文本, 证据是否充分)。

    兼容两种格式：
    - 方括号：[分析] xxx、[证据充分] 是/否
    - 冒号：分析：xxx、证据充分：是/否
    """
    analysis = ""
    sufficient = False
    for line in text.splitlines():
        stripped = line.strip()
        value = _extract_value(stripped, *_field_tokens("分析"))
        if value is not None:
            analysis = value
            continue
        value = _extract_value(stripped, *_field_tokens("证据充分"))
        if value is not None:
            sufficient = value.startswith("是")
    return analysis or text, sufficient


def format_tool_results(tool_results: list[dict]) -> str:
    """把工具执行记录格式化为提示词中的可读文本。"""
    if not tool_results:
        return "（尚未执行任何工具）"
    lines: list[str] = []
    for index, item in enumerate(tool_results, start=1):
        status = "成功" if item.get("success") else "失败"
        lines.append(
            f"{index}. {item.get('tool_name', '未知工具')} "
            f"[{item.get('source', '未知来源')}] {status}"
        )
        lines.append(f"   参数: {item.get('args', {})}")
        if item.get("summary"):
            lines.append(f"   结果: {item['summary']}")
        if item.get("error"):
            lines.append(f"   错误: {item['error']}")
    return "\n".join(lines)


def format_knowledge(chunks: list[dict]) -> str:
    """把检索到的知识片段格式化为带 [引用N] 编号的文本。"""
    if not chunks:
        return "（知识库中无相关内容）"
    lines: list[str] = []
    for index, item in enumerate(chunks, start=1):
        lines.append(f"{format_marker(index)} 来源: {item.get('source', 'unknown')}")
        lines.append(item.get("content", ""))
    return "\n\n".join(lines)


def build_tool_catalog(specs: list) -> str:
    """从工具规格生成紧凑的工具清单文本（单一来源，不再手抄）。

    格式：- 工具名(参数...)：说明 [来源]
    """
    lines: list[str] = []
    for spec in specs:
        fields = spec.args_schema.model_fields
        params = ", ".join(fields)
        lines.append(
            f"- {spec.name}({params})：{spec.description} [{spec.source.value}]"
        )
    return "\n".join(lines)


def create_classify_node(
    llm: BaseChatModel,
) -> Callable[[NetOpsState], dict[str, Any]]:
    """创建故障分类节点。"""

    def classify_issue(state: NetOpsState) -> dict[str, Any]:
        logger.info("故障分类, thread_id=%s", state.get("thread_id", ""))
        prompt = CLASSIFY_USER_TEMPLATE.format(
            user_message=state.get("user_message", "")
        )
        raw = _call_llm(llm, CLASSIFY_SYSTEM_PROMPT, prompt)
        return {"issue_category": parse_category(raw)}

    return classify_issue


def create_plan_node(
    llm: BaseChatModel, registry: ToolRegistry
) -> Callable[[NetOpsState], dict[str, Any]]:
    """创建诊断规划节点：输出结构化工具调用计划。"""
    known_tools = set(registry.names)
    system_prompt = PLAN_SYSTEM_PROMPT.format(
        tool_catalog=build_tool_catalog(TOOL_SPECS)
    )

    def plan_diagnosis(state: NetOpsState) -> dict[str, Any]:
        logger.info("诊断规划, round=%s", state.get("diagnosis_round", 1))
        prompt = PLAN_USER_TEMPLATE.format(
            user_message=state.get("user_message", ""),
            issue_category=state.get("issue_category", "unknown"),
            analysis=state.get("analysis", "（暂无）"),
            tool_results=format_tool_results(state.get("tool_results", [])),
        )
        raw = _call_llm(llm, system_prompt, prompt)
        steps = parse_plan(raw, known_tools)
        return {
            "diagnosis_plan": steps,
            "plan_empty": not steps,
            "diagnosis_round": state.get("diagnosis_round", 0) + 1,
        }

    return plan_diagnosis


def create_execute_node(
    registry: ToolRegistry,
) -> Callable[[NetOpsState], dict[str, Any]]:
    """创建诊断执行节点：按计划执行多个工具并写回 State。"""

    def execute_diagnostics(state: NetOpsState) -> dict[str, Any]:
        plan = state.get("diagnosis_plan", [])
        if not plan:
            logger.info("本轮无诊断计划，跳过执行")
            return {}
        executed = list(state.get("executed_tools", []))
        results = list(state.get("tool_results", []))
        for step in plan:
            name = step.get("tool", "")
            args = step.get("args", {}) or {}
            logger.info("执行工具 %s(%s)", name, args)
            result = registry.run_tool(name, args)
            # 构造新记录而非修改依赖返回的 dict
            record = {
                **result.model_dump(mode="json"),
                "tool_name": name,
                "args": args,
            }
            results.append(record)
            executed.append(name)
        return {"tool_results": results, "executed_tools": executed}

    return execute_diagnostics


def create_retrieve_knowledge_node(
    rag_service: Any,
) -> Callable[[NetOpsState], dict[str, Any]]:
    """创建知识检索节点：检索 Top-K 知识片段写入 State。"""

    def retrieve_knowledge(state: NetOpsState) -> dict[str, Any]:
        logger.info("检索知识库, thread_id=%s", state.get("thread_id", ""))
        query = (
            f"{state.get('user_message', '')}\n"
            f"{state.get('analysis', '')}"
        ).strip()
        try:
            chunks = rag_service.search(query)
        except Exception as exc:  # noqa: BLE001 - 检索失败不阻塞工作流
            logger.warning("知识检索失败: %s", exc)
            return {"retrieved_chunks": []}
        return {"retrieved_chunks": [c.model_dump() for c in chunks]}

    return retrieve_knowledge


def create_analyze_node(
    llm: BaseChatModel,
) -> Callable[[NetOpsState], dict[str, Any]]:
    """创建结果分析节点：综合工具与知识证据给出判断。"""

    def analyze_results(state: NetOpsState) -> dict[str, Any]:
        logger.info("结果分析, thread_id=%s", state.get("thread_id", ""))
        prompt = ANALYZE_USER_TEMPLATE.format(
            user_message=state.get("user_message", ""),
            tool_results=format_tool_results(state.get("tool_results", [])),
            knowledge=format_knowledge(state.get("retrieved_chunks", [])),
        )
        raw = _call_llm(llm, ANALYZE_SYSTEM_PROMPT, prompt)
        analysis, sufficient = parse_analysis(raw)
        return {"analysis": analysis, "evidence_sufficient": sufficient}

    return analyze_results


def create_report_node(
    llm: BaseChatModel,
) -> Callable[[NetOpsState], dict[str, Any]]:
    """创建故障报告节点：生成最终报告。"""

    def generate_report(state: NetOpsState) -> dict[str, Any]:
        logger.info("生成故障报告, thread_id=%s", state.get("thread_id", ""))
        prompt = REPORT_USER_TEMPLATE.format(
            user_message=state.get("user_message", ""),
            issue_category=state.get("issue_category", "unknown"),
            tool_results=format_tool_results(state.get("tool_results", [])),
            knowledge=format_knowledge(state.get("retrieved_chunks", [])),
            analysis=state.get("analysis", ""),
        )
        raw = _call_llm(llm, REPORT_SYSTEM_PROMPT, prompt)
        answer, next_steps, status = parse_final_response(raw)
        update: dict[str, Any] = {"answer": answer, "next_steps": next_steps}
        if status:
            update["diagnosis_status"] = status
        return update

    return generate_report
