"""测试共享配置。"""

from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

ANALYSIS_SUFFICIENT = "[分析] 初步判断为 DNS 问题\n[证据充分] 是"
ANALYSIS_INSUFFICIENT = "[分析] 初步判断为 DNS 问题\n[证据充分] 否"
REPORT_TEXT = (
    "结论：初步判断为 DNS 解析问题 [引用1]（推测）\n"
    "步骤：检查 DNS 配置\n"
    "步骤：检查默认路由\n"
    "状态：suspected"
)


def _plan_message() -> AIMessage:
    return AIMessage(
        content=(
            "工具：ping_host 参数:{\"host\": \"127.0.0.1\", \"count\": 2} "
            "理由：验证本机回环连通性\n"
            "工具：dns_lookup 参数:{\"hostname\": \"localhost\"} "
            "理由：验证 DNS 解析\n"
            "工具：not_a_tool 参数:{} 理由：应被剔除"
        )
    )


@pytest.fixture
def mock_llm() -> MagicMock:
    """构造返回固定内容的 Mock 模型（单轮诊断：证据充分直接出报告）。"""
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.side_effect = [
        AIMessage(content="dns"),
        _plan_message(),
        AIMessage(content=ANALYSIS_SUFFICIENT),
        AIMessage(content=REPORT_TEXT),
    ]
    return llm


@pytest.fixture
def mock_llm_multi_round() -> MagicMock:
    """构造多轮诊断 Mock 模型（第一轮证据不足，第二轮充分）。"""
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.side_effect = [
        AIMessage(content="connectivity"),
        _plan_message(),
        AIMessage(content=ANALYSIS_INSUFFICIENT),  # 第一轮：证据不足
        _plan_message(),  # 第二轮规划
        AIMessage(content=ANALYSIS_SUFFICIENT),
        AIMessage(content=REPORT_TEXT),
    ]
    return llm


@pytest.fixture
def mock_registry() -> MagicMock:
    """构造返回固定成功结果的工具注册表 Mock。"""
    registry = MagicMock()
    registry.names = ["ping_host", "dns_lookup"]
    registry.run_tool.return_value = MagicMock(
        model_dump=MagicMock(
            return_value={
                "tool_name": "ping_host",
                "source": "local_diagnostic",
                "success": True,
                "summary": "127.0.0.1 可达，丢包 0%",
                "detail": {"host": "127.0.0.1", "packet_loss": 0},
                "error": None,
            }
        )
    )
    return registry


@pytest.fixture
def mock_rag() -> MagicMock:
    """构造返回固定知识片段的 RAG 服务 Mock。"""
    from app.rag.models import RetrievedChunk

    rag = MagicMock()
    rag.search.return_value = [
        RetrievedChunk(
            chunk_id="dns#0",
            source="dns_troubleshooting.md",
            content="DNS 故障排查先确认本机 DNS 配置。",
            score=0.9,
            chunk_index=0,
        )
    ]
    return rag


@pytest.fixture
def mock_storage(tmp_path) -> MagicMock:
    """构造诊断记录存储 Mock（用临时文件真实写入，可验证）。"""
    from app.storage.sqlite import DiagnosisStorage

    return DiagnosisStorage(str(tmp_path / "test.db"))


__all__ = [
    "ANALYSIS_SUFFICIENT",
    "ANALYSIS_INSUFFICIENT",
    "REPORT_TEXT",
    "mock_llm",
    "mock_llm_multi_round",
    "mock_registry",
    "mock_rag",
    "mock_storage",
]
