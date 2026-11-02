"""LangGraph 工作流状态定义。"""

from typing import TypedDict


class NetOpsState(TypedDict, total=False):
    """Agent 工作流共享状态。

    Phase 4 完整诊断工作流：
    classify → plan → execute → retrieve → analyze → check → report
    thread_id 仅作请求关联标识，不保存跨请求历史（未配置 Checkpointer）。
    """

    user_message: str
    thread_id: str
    started_at: float
    # 诊断流程字段
    issue_category: str
    diagnosis_plan: list[dict]
    plan_empty: bool
    tool_results: list[dict]
    executed_tools: list[str]
    retrieved_chunks: list[dict]
    analysis: str
    evidence_sufficient: bool
    diagnosis_round: int
    # 输出字段
    answer: str
    next_steps: list[str]
    diagnosis_status: str
