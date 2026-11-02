"""完整性条件路由单元测试（Phase 4 多轮诊断）。"""

from app.agent.routing import NODE_PLAN, NODE_REPORT, create_completeness_check


def test_goes_report_when_evidence_sufficient() -> None:
    """证据充分时直接生成报告。"""
    check = create_completeness_check(max_rounds=3, timeout_seconds=120.0)
    assert check({"evidence_sufficient": True, "diagnosis_round": 1}) == NODE_REPORT


def test_loops_back_when_insufficient() -> None:
    """证据不足且未达上限时进入下一轮规划。"""
    check = create_completeness_check(max_rounds=3, timeout_seconds=120.0)
    assert check({"evidence_sufficient": False, "diagnosis_round": 1}) == NODE_PLAN


def test_stops_when_plan_empty() -> None:
    """本轮计划为空（模型认为无需再查）时直接收束，不空转。"""
    check = create_completeness_check(max_rounds=3, timeout_seconds=120.0)
    state = {"evidence_sufficient": False, "plan_empty": True, "diagnosis_round": 1}
    assert check(state) == NODE_REPORT


def test_stops_at_max_rounds() -> None:
    """达到最大诊断轮数后收束，避免无限循环。"""
    check = create_completeness_check(max_rounds=3, timeout_seconds=120.0)
    assert check({"evidence_sufficient": False, "diagnosis_round": 3}) == NODE_REPORT


def test_stops_on_timeout() -> None:
    """超过总超时后收束。"""
    import time

    check = create_completeness_check(max_rounds=5, timeout_seconds=60.0)
    state = {
        "evidence_sufficient": False,
        "diagnosis_round": 1,
        "started_at": time.time() - 999,
    }
    assert check(state) == NODE_REPORT
