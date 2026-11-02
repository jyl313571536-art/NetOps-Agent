"""LangGraph 完整诊断工作流集成测试（Phase 4）。"""

from app.agent.service import AgentService
from app.models.diagnosis import DiagnosisStatus


def test_full_workflow_single_round(
    mock_llm, mock_registry, mock_rag, mock_storage
) -> None:
    """完整工作流：分类→规划→执行→检索→分析→报告。"""
    service = AgentService(
        llm=mock_llm,
        registry=mock_registry,
        rag_service=mock_rag,
        storage=mock_storage,
    )
    result = service.chat("可以 Ping 通网关但无法上网", "t1")
    assert result.thread_id == "t1"
    assert result.answer == "初步判断为 DNS 解析问题 [引用1]（推测）"
    assert result.next_steps == ["检查 DNS 配置", "检查默认路由"]
    assert result.report is not None
    assert result.report.issue_category == "dns"
    # 4 次模型调用：分类/规划/分析/报告
    assert mock_llm.invoke.call_count == 4


def test_workflow_executes_planned_tools(
    mock_llm, mock_registry, mock_rag, mock_storage
) -> None:
    """规划中的工具被执行，未知工具被剔除。"""
    service = AgentService(
        llm=mock_llm,
        registry=mock_registry,
        rag_service=mock_rag,
        storage=mock_storage,
    )
    result = service.chat("无法上网", "t2")
    # 计划含 2 个合法工具（ping_host、dns_lookup），not_a_tool 被剔除
    assert len(result.executed_tools) == 2
    assert set(result.executed_tools) == {"ping_host", "dns_lookup"}
    assert result.tool_results[0].source == "local_diagnostic"
    assert mock_registry.run_tool.call_count == 2


def test_multi_round_diagnosis(
    mock_llm_multi_round, mock_registry, mock_rag, mock_storage
) -> None:
    """证据不足时进入第二轮诊断，证据充分后生成报告。"""
    service = AgentService(
        llm=mock_llm_multi_round,
        registry=mock_registry,
        rag_service=mock_rag,
        storage=mock_storage,
    )
    result = service.chat("间歇性断网", "t3")
    assert result.answer
    # 6 次模型调用：分类/规划/分析/规划/分析/报告
    assert mock_llm_multi_round.invoke.call_count == 6


def test_status_suspected_with_evidence(
    mock_llm, mock_registry, mock_rag, mock_storage
) -> None:
    """有工具证据时状态为 suspected。"""
    service = AgentService(
        llm=mock_llm,
        registry=mock_registry,
        rag_service=mock_rag,
        storage=mock_storage,
    )
    result = service.chat("无法上网")
    assert result.diagnosis_status == DiagnosisStatus.SUSPECTED


def test_status_failed_when_all_tools_fail(
    mock_llm, mock_rag, mock_storage
) -> None:
    """工具全部失败时状态为 failed，不伪装成正常结果。"""
    from unittest.mock import MagicMock

    registry = MagicMock()
    registry.names = ["ping_host"]
    registry.run_tool.return_value = MagicMock(
        model_dump=MagicMock(
            return_value={
                "tool_name": "ping_host",
                "source": "local_diagnostic",
                "success": False,
                "summary": "",
                "detail": {},
                "error": "白名单外",
            }
        )
    )
    service = AgentService(
        llm=mock_llm,
        registry=registry,
        rag_service=mock_rag,
        storage=mock_storage,
    )
    result = service.chat("无法上网")
    assert result.diagnosis_status == DiagnosisStatus.FAILED


def test_report_contains_citations_and_unverified(
    mock_llm, mock_registry, mock_rag, mock_storage
) -> None:
    """报告含知识引用与未验证标记。"""
    service = AgentService(
        llm=mock_llm,
        registry=mock_registry,
        rag_service=mock_rag,
        storage=mock_storage,
    )
    result = service.chat("无法上网", "t4")
    assert result.citations
    assert result.citations[0].verified is True
    assert result.report is not None
    assert result.report.unverified_points


def test_fabricated_citation_removed(
    mock_llm, mock_registry, mock_rag, mock_storage
) -> None:
    """编造引用被剔除。"""
    from unittest.mock import MagicMock

    from langchain_core.messages import AIMessage

    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.side_effect = [
        AIMessage(content="dns"),
        AIMessage(content="无"),
        AIMessage(content="[分析] 分析\n[证据充分] 是"),
        AIMessage(content="结论：参见 [引用9] 与 [引用1]\n步骤：x\n状态：suspected"),
    ]
    service = AgentService(
        llm=llm,
        registry=mock_registry,
        rag_service=mock_rag,
        storage=mock_storage,
    )
    result = service.chat("DNS 问题", "t5")
    assert "[引用9]" not in result.answer
    assert len(result.citations) == 1
    assert result.citations[0].marker == "[引用1]"


def test_diagnosis_record_saved(
    mock_llm, mock_registry, mock_rag, mock_storage
) -> None:
    """诊断记录写入存储。"""
    service = AgentService(
        llm=mock_llm,
        registry=mock_registry,
        rag_service=mock_rag,
        storage=mock_storage,
    )
    result = service.chat("无法上网", "t6")
    assert result.diagnosis_id
    assert mock_storage.count() == 1


def test_service_auto_thread_id(
    mock_llm, mock_registry, mock_rag, mock_storage
) -> None:
    """未提供 thread_id 时自动生成。"""
    service = AgentService(
        llm=mock_llm,
        registry=mock_registry,
        rag_service=mock_rag,
        storage=mock_storage,
    )
    result = service.chat("无法上网")
    assert len(result.thread_id) == 12


def test_rag_search_failure_does_not_block(
    mock_llm, mock_registry, mock_storage
) -> None:
    """知识检索失败不阻塞工作流。"""
    from unittest.mock import MagicMock

    rag = MagicMock()
    rag.search.side_effect = RuntimeError("向量库不可用")
    service = AgentService(
        llm=mock_llm,
        registry=mock_registry,
        rag_service=rag,
        storage=mock_storage,
    )
    result = service.chat("任意问题")
    assert result.answer
    assert result.citations == []
