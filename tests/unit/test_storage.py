"""SQLite 诊断记录存储单元测试。"""

from app.models.diagnosis import (
    AgentResult,
    DiagnosisReport,
    DiagnosisStatus,
    ToolRecord,
)
from app.storage.sqlite import DiagnosisStorage


def _sample_result() -> AgentResult:
    return AgentResult(
        thread_id="t-001",
        answer="结论：DNS 故障",
        diagnosis_status=DiagnosisStatus.SUSPECTED,
        executed_tools=["ping_host"],
        tool_results=[
            ToolRecord(
                tool_name="ping_host",
                args={"host": "127.0.0.1"},
                source="local_diagnostic",
                success=True,
                summary="可达",
            )
        ],
        next_steps=["检查 DNS"],
        report=DiagnosisReport(
            issue_category="dns",
            summary="DNS 故障",
        ),
    )


def test_save_and_count(tmp_path) -> None:
    """保存记录并计数。"""
    storage = DiagnosisStorage(str(tmp_path / "t.db"))
    assert storage.count() == 0
    record_id = storage.save_record(_sample_result(), "无法上网", duration_ms=1234)
    assert record_id
    assert storage.count() == 1
    record_id2 = storage.save_record(_sample_result(), "另一个问题", duration_ms=10)
    assert record_id2 != record_id
    assert storage.count() == 2


def test_save_record_persists_fields(tmp_path) -> None:
    """记录字段完整落库。"""
    import json
    import sqlite3

    db_path = str(tmp_path / "t.db")
    storage = DiagnosisStorage(db_path)
    record_id = storage.save_record(_sample_result(), "无法上网", duration_ms=500)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM diagnosis_records WHERE id = ?", (record_id,)
    ).fetchone()
    conn.close()
    assert row["thread_id"] == "t-001"
    assert row["user_message"] == "无法上网"
    assert row["issue_category"] == "dns"
    assert row["diagnosis_status"] == "suspected"
    assert row["answer"] == "结论：DNS 故障"
    assert row["duration_ms"] == 500
    tools = json.loads(row["executed_tools_json"])
    assert tools == ["ping_host"]
    results = json.loads(row["tool_results_json"])
    assert results[0]["source"] == "local_diagnostic"
    assert row["report_json"]


def test_init_db_idempotent(tmp_path) -> None:
    """重复初始化不报错。"""
    storage = DiagnosisStorage(str(tmp_path / "t.db"))
    storage.init_db()
    storage.init_db()
    assert storage.count() == 0
