"""LangGraph 工作流构建模块（Phase 4 完整诊断工作流）。"""

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes import (
    create_analyze_node,
    create_classify_node,
    create_execute_node,
    create_plan_node,
    create_report_node,
    create_retrieve_knowledge_node,
)
from app.agent.routing import (
    NODE_ANALYZE,
    NODE_CLASSIFY,
    NODE_EXECUTE,
    NODE_PLAN,
    NODE_REPORT,
    NODE_RETRIEVE,
    create_completeness_check,
)
from app.agent.state import NetOpsState
from app.tools.registry import ToolRegistry


def create_graph(
    llm: BaseChatModel,
    registry: ToolRegistry,
    rag_service=None,
    fast_llm: BaseChatModel | None = None,
    max_rounds: int = 3,
    timeout_seconds: float = 120.0,
) -> CompiledStateGraph:
    """构建并编译 Agent 工作流。

    模型分级：迭代节点（分类/规划/分析）用 fast_llm，
    最终报告用 llm（质量优先）；fast_llm 未传时统一用 llm。

    流程：
        START
        → classify_issue
        → plan_diagnosis
        → execute_diagnostics
        → retrieve_knowledge
        → analyze_results
        → check_completeness（条件：证据不足且未达轮数/超时上限 → plan_diagnosis）
        → generate_report
        → END
    """
    fast = fast_llm or llm
    workflow = StateGraph(NetOpsState)
    workflow.add_node(NODE_CLASSIFY, create_classify_node(fast))
    workflow.add_node(NODE_PLAN, create_plan_node(fast, registry))
    workflow.add_node(NODE_EXECUTE, create_execute_node(registry))
    workflow.add_node(NODE_RETRIEVE, create_retrieve_knowledge_node(rag_service))
    workflow.add_node(NODE_ANALYZE, create_analyze_node(fast))
    workflow.add_node(NODE_REPORT, create_report_node(llm))

    workflow.add_edge(START, NODE_CLASSIFY)
    workflow.add_edge(NODE_CLASSIFY, NODE_PLAN)
    workflow.add_edge(NODE_PLAN, NODE_EXECUTE)
    workflow.add_edge(NODE_EXECUTE, NODE_RETRIEVE)
    workflow.add_edge(NODE_RETRIEVE, NODE_ANALYZE)
    workflow.add_conditional_edges(
        NODE_ANALYZE,
        create_completeness_check(max_rounds, timeout_seconds),
        {
            NODE_PLAN: NODE_PLAN,
            NODE_REPORT: NODE_REPORT,
        },
    )
    workflow.add_edge(NODE_REPORT, END)
    return workflow.compile()
