"""Agent 节点单元测试（Phase 4）。"""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from app.agent.nodes import (
    create_analyze_node,
    create_classify_node,
    create_execute_node,
    create_plan_node,
    create_report_node,
    format_knowledge,
    format_tool_results,
    parse_analysis,
    parse_category,
    parse_final_response,
    parse_generation,
    parse_plan,
)
from app.core.exceptions import LLMTimeoutError


def test_parse_generation() -> None:
    """解析结论与步骤。"""
    text = "结论：初步分析\n步骤：检查 DNS\n步骤：检查路由"
    answer, steps = parse_generation(text)
    assert answer == "初步分析"
    assert steps == ["检查 DNS", "检查路由"]


def test_parse_generation_halfwidth_colon() -> None:
    """兼容半角冒号格式。"""
    text = "结论:初步分析\n步骤:检查 DNS"
    answer, steps = parse_generation(text)
    assert answer == "初步分析"
    assert steps == ["检查 DNS"]


def test_parse_generation_fallback() -> None:
    """格式不符时保留原文，不伪造结构化结果。"""
    text = "没有固定格式的回复"
    answer, steps = parse_generation(text)
    assert answer == text
    assert steps == []


def test_parse_final_response_with_status() -> None:
    """解析最终回复中的诊断状态。"""
    text = "结论：DNS 解析故障\n步骤：检查 DNS 配置\n状态：suspected"
    answer, steps, status = parse_final_response(text)
    assert answer == "DNS 解析故障"
    assert steps == ["检查 DNS 配置"]
    assert status == "suspected"


def test_parse_final_response_invalid_status() -> None:
    """非法状态值不被采纳，返回 None。"""
    text = "结论：测试\n步骤：检查\n状态：made_up"
    _, _, status = parse_final_response(text)
    assert status is None


def test_parse_category_valid() -> None:
    """合法分类标识。"""
    assert parse_category("dns") == "dns"
    assert parse_category("connectivity。") == "connectivity"


def test_parse_category_invalid() -> None:
    """非法分类归入 unknown。"""
    assert parse_category("网络问题") == "unknown"
    assert parse_category("") == "unknown"


def test_parse_plan_extracts_valid_steps() -> None:
    """解析计划，剔除未知工具。"""
    text = (
        '工具：ping_host 参数:{"host": "127.0.0.1"} 理由：测连通性\n'
        '工具：ghost_tool 参数:{"x": 1} 理由：不存在\n'
        "无"
    )
    steps = parse_plan(text, {"ping_host"})
    assert len(steps) == 1
    assert steps[0]["tool"] == "ping_host"
    assert steps[0]["args"] == {"host": "127.0.0.1"}
    assert steps[0]["reason"] == "测连通性"


def test_parse_plan_rejects_bad_json() -> None:
    """非法 JSON 参数被剔除。"""
    text = '工具：ping_host 参数:{bad json} 理由：x'
    assert parse_plan(text, {"ping_host"}) == []


def test_parse_plan_none() -> None:
    """输出"无"时计划为空。"""
    assert parse_plan("无", {"ping_host"}) == []


def test_parse_analysis() -> None:
    """解析分析与证据充分标记。"""
    text = "[分析] DNS 问题\n[证据充分] 是"
    analysis, sufficient = parse_analysis(text)
    assert analysis == "DNS 问题"
    assert sufficient is True


def test_parse_analysis_insufficient() -> None:
    """证据不充分时返回 False。"""
    text = "[分析] 推测\n[证据充分] 否"
    _, sufficient = parse_analysis(text)
    assert sufficient is False


def test_format_tool_results_empty() -> None:
    """无工具结果时给出明确占位说明。"""
    assert "尚未执行" in format_tool_results([])


def test_format_tool_results_marks_source() -> None:
    """工具结果格式化后保留来源与成败标记。"""
    text = format_tool_results(
        [
            {
                "tool_name": "ping_host",
                "source": "local_diagnostic",
                "success": True,
                "summary": "可达",
                "args": {"host": "127.0.0.1"},
            },
            {
                "tool_name": "analyze_routing_table",
                "source": "simulation",
                "success": False,
                "error": "设备不存在",
                "args": {"device_id": "x"},
            },
        ]
    )
    assert "local_diagnostic" in text
    assert "simulation" in text
    assert "成功" in text
    assert "失败" in text


def test_format_knowledge_numbers_citations() -> None:
    """知识片段带 [引用N] 编号。"""
    text = format_knowledge(
        [
            {"source": "a.md", "content": "内容 A"},
            {"source": "b.md", "content": "内容 B"},
        ]
    )
    assert "[引用1]" in text
    assert "[引用2]" in text
    assert "a.md" in text


def test_format_knowledge_empty() -> None:
    """无知识片段时给出占位。"""
    assert "无相关" in format_knowledge([])


def test_classify_node() -> None:
    """分类节点写入 issue_category。"""
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content="dns")
    node = create_classify_node(llm)
    result = node({"user_message": "域名解析不了", "thread_id": "t1"})
    assert result["issue_category"] == "dns"


def test_analyze_node() -> None:
    """分析节点写入分析文本与证据充分标记。"""
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(
        content="[分析] DNS 问题\n[证据充分] 否"
    )
    node = create_analyze_node(llm)
    result = node(
        {
            "user_message": "无法上网",
            "thread_id": "t1",
            "tool_results": [],
            "retrieved_chunks": [],
        }
    )
    assert result["analysis"] == "DNS 问题"
    assert result["evidence_sufficient"] is False


def test_plan_node_filters_unknown_tools() -> None:
    """规划节点剔除未知工具。"""
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(
        content=(
            '工具：ping_host 参数:{"host": "127.0.0.1"} 理由：测连通\n'
            '工具：evil_tool 参数:{"x": 1} 理由：不该出现'
        )
    )
    registry = MagicMock()
    registry.names = ["ping_host", "dns_lookup"]
    node = create_plan_node(llm, registry)
    result = node({"user_message": "无法上网", "thread_id": "t1"})
    steps = result["diagnosis_plan"]
    assert len(steps) == 1
    assert steps[0]["tool"] == "ping_host"
    assert result["diagnosis_round"] == 1


def test_execute_node_records_results() -> None:
    """执行节点按计划调用工具并写回结果。"""
    registry = MagicMock()
    registry.run_tool.return_value = MagicMock(
        model_dump=MagicMock(
            return_value={
                "tool_name": "ping_host",
                "source": "local_diagnostic",
                "success": True,
                "summary": "可达",
                "detail": {},
                "error": None,
            }
        )
    )
    node = create_execute_node(registry)
    result = node(
        {
            "diagnosis_plan": [{"tool": "ping_host", "args": {"host": "127.0.0.1"}}],
            "tool_results": [],
            "executed_tools": [],
        }
    )
    assert result["executed_tools"] == ["ping_host"]
    assert result["tool_results"][0]["args"] == {"host": "127.0.0.1"}


def test_execute_node_empty_plan() -> None:
    """空计划不执行任何工具。"""
    registry = MagicMock()
    node = create_execute_node(registry)
    result = node({"diagnosis_plan": [], "tool_results": [], "executed_tools": []})
    assert result == {}
    registry.run_tool.assert_not_called()


def test_report_node() -> None:
    """报告节点解析结论、步骤与状态。"""
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(
        content="结论：DNS 故障\n步骤：flushdns\n状态：suspected"
    )
    node = create_report_node(llm)
    result = node(
        {
            "user_message": "无法上网",
            "thread_id": "t1",
            "issue_category": "dns",
            "tool_results": [],
            "retrieved_chunks": [],
            "analysis": "分析",
        }
    )
    assert result["answer"] == "DNS 故障"
    assert result["next_steps"] == ["flushdns"]
    assert result["diagnosis_status"] == "suspected"


def test_node_maps_timeout_error() -> None:
    """超时异常映射为 LLMTimeoutError。"""
    llm = MagicMock()
    llm.invoke.side_effect = TimeoutError("Request timed out")
    node = create_classify_node(llm)
    try:
        node({"user_message": "无法上网", "thread_id": "t1"})
    except LLMTimeoutError:
        pass
    else:
        raise AssertionError("应抛出 LLMTimeoutError")
