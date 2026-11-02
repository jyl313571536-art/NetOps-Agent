"""数据模型单元测试。"""

from app.models.diagnosis import AgentResult, DiagnosisStatus


def test_diagnosis_status_values() -> None:
    """诊断状态枚举值符合规范。"""
    assert DiagnosisStatus.PRELIMINARY.value == "preliminary"
    assert DiagnosisStatus.SUSPECTED.value == "suspected"
    assert DiagnosisStatus.CONFIRMED.value == "confirmed"
    assert DiagnosisStatus.FAILED.value == "failed"


def test_agent_result_defaults() -> None:
    """AgentResult 默认不伪造工具执行结果。"""
    result = AgentResult(thread_id="t1")
    assert result.diagnosis_status == DiagnosisStatus.PRELIMINARY
    assert result.executed_tools == []
    assert result.next_steps == []
