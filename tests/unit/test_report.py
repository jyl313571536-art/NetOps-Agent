"""故障报告组装单元测试。"""

from app.agent.service import build_report
from app.models.diagnosis import (
    Citation,
    DiagnosisStatus,
    to_tool_records,
)

determine_diagnosis_status = DiagnosisStatus.adjudicate


def test_determine_status_no_tools() -> None:
    """未执行工具时只能是 preliminary。"""
    assert determine_diagnosis_status([], "confirmed") == DiagnosisStatus.PRELIMINARY


def test_determine_status_all_failed() -> None:
    """工具全部失败时为 failed。"""
    failed = [{"success": False}, {"success": False}]
    assert determine_diagnosis_status(failed, None) == DiagnosisStatus.FAILED


def test_determine_status_with_evidence() -> None:
    """有工具成功时为 suspected / confirmed。"""
    ok = [{"success": True}]
    assert determine_diagnosis_status(ok, None) == DiagnosisStatus.SUSPECTED
    assert (
        determine_diagnosis_status(ok, "confirmed") == DiagnosisStatus.CONFIRMED
    )
    assert (
        determine_diagnosis_status(ok, "preliminary") == DiagnosisStatus.SUSPECTED
    )


def test_build_report_marks_unverified() -> None:
    """未充分验证的结论在报告中明确标记。"""
    report = build_report(
        issue_category="dns",
        analysis="DNS 解析故障",
        tool_records=to_tool_records(
            [
                {
                    "tool_name": "dns_lookup",
                    "source": "local_diagnostic",
                    "success": False,
                    "summary": "",
                    "error": "解析失败",
                    "args": {},
                }
            ]
        ),
        citations=[
            Citation(marker="[引用1]", source="a.md", snippet="片段", score=0.9)
        ],
        next_steps=["检查 DNS"],
        status=DiagnosisStatus.SUSPECTED,
    )
    assert report.issue_category == "dns"
    assert report.possible_causes[0].cause == "DNS 解析故障"
    assert report.possible_causes[0].status == DiagnosisStatus.SUSPECTED
    assert any("推测" in point for point in report.unverified_points)
    assert any("dns_lookup" in point for point in report.unverified_points)
    assert report.knowledge_citations[0].source == "a.md"
    assert report.recommendations == ["检查 DNS"]


def test_build_report_tracks_sources() -> None:
    """报告记录工具证据来源。"""
    report = build_report(
        issue_category="vlan",
        analysis="VLAN 配置问题",
        tool_records=to_tool_records(
            [
                {
                    "tool_name": "analyze_vlan_config",
                    "source": "simulation",
                    "success": True,
                    "summary": "2 个 VLAN",
                    "error": None,
                    "args": {"device_id": "switch-01"},
                }
            ]
        ),
        citations=[],
        next_steps=[],
        status=DiagnosisStatus.SUSPECTED,
    )
    assert report.tool_evidence[0].source == "simulation"
    assert "simulation" in report.possible_causes[0].source_types
