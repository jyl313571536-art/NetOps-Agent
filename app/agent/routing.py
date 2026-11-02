"""LangGraph 条件路由（Phase 4 多轮诊断完整性判定）。"""

import logging
import time
from collections.abc import Callable

from app.agent.state import NetOpsState

logger = logging.getLogger(__name__)

NODE_CLASSIFY = "classify_issue"
NODE_PLAN = "plan_diagnosis"
NODE_EXECUTE = "execute_diagnostics"
NODE_RETRIEVE = "retrieve_knowledge"
NODE_ANALYZE = "analyze_results"
NODE_REPORT = "generate_report"


def create_completeness_check(
    max_rounds: int, timeout_seconds: float
) -> Callable[[NetOpsState], str]:
    """创建完整性条件路由：决定继续多轮诊断还是生成报告。

    出口条件（满足任一即生成报告，避免无限循环）：
    1. 分析判定证据已充分。
    2. 诊断轮数达到 AGENT_MAX_STEPS。
    3. Agent 总耗时超过 AGENT_TIMEOUT。
    """

    def check_completeness(state: NetOpsState) -> str:
        if state.get("evidence_sufficient"):
            return NODE_REPORT
        # 本轮计划为空（模型认为无需再查）：直接收束，不再空转一轮
        if state.get("plan_empty"):
            logger.info("本轮无诊断计划，停止多轮诊断")
            return NODE_REPORT
        round_no = state.get("diagnosis_round", 1)
        if round_no >= max_rounds:
            logger.warning("达到最大诊断轮数 %s，停止多轮诊断", max_rounds)
            return NODE_REPORT
        started_at = state.get("started_at")
        if started_at is not None:
            elapsed = time.time() - started_at
            if elapsed >= timeout_seconds:
                logger.warning("Agent 任务超时 %.1fs，停止多轮诊断", elapsed)
                return NODE_REPORT
        logger.info("证据不充分，进入第 %s 轮诊断", round_no + 1)
        return NODE_PLAN

    return check_completeness
