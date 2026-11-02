"""诊断状态与 Agent 结果数据模型。

本模块是诊断领域模型的唯一居所，RAG 层与 API 层均复用此处定义。
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DiagnosisStatus(StrEnum):
    """诊断结论状态。

    - preliminary：仅根据用户描述初步分析，尚未执行验证工具。
    - suspected：有一定依据的疑似原因，尚未充分验证。
    - confirmed：有实际工具检测结果或可靠证据支持的结论。
    - failed：诊断工具或诊断流程执行失败，无法得出结论。
    """

    PRELIMINARY = "preliminary"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    FAILED = "failed"

    @classmethod
    def adjudicate(
        cls, tool_results: list[dict], model_claim: str | None
    ) -> "DiagnosisStatus":
        """按工具执行情况与模型自报状态判定诊断状态。

        规则（对应 CLAUDE.md 第 10 节）：
        1. 未执行任何工具 → preliminary（模型不得自称已验证）。
        2. 工具全部失败 → failed。
        3. 有工具成功但模型未报 confirmed → suspected。
        4. 模型报 confirmed 且至少一个工具成功 → confirmed。
        """
        if not tool_results:
            return cls.PRELIMINARY
        if all(not item.get("success") for item in tool_results):
            return cls.FAILED
        if model_claim == cls.CONFIRMED:
            return cls.CONFIRMED
        return cls.SUSPECTED


class IssueCategory(StrEnum):
    """故障分类。"""

    CONNECTIVITY = "connectivity"
    DNS = "dns"
    ROUTING = "routing"
    VLAN = "vlan"
    FIREWALL = "firewall"
    UNKNOWN = "unknown"


class ToolRecord(BaseModel):
    """单个工具的执行记录，结果必须可追溯到真实执行。"""

    tool_name: str
    args: dict = Field(default_factory=dict)
    source: str | None = Field(
        default=None,
        description="数据来源：simulation 或 local_diagnostic",
    )
    success: bool = False
    summary: str = ""
    error: str | None = None

    @classmethod
    def from_result(cls, item: dict[str, Any]) -> "ToolRecord":
        """从工具执行结果 dict 构造记录。"""
        return cls(
            tool_name=item.get("tool_name", ""),
            args=item.get("args", {}),
            source=item.get("source"),
            success=bool(item.get("success")),
            summary=item.get("summary", ""),
            error=item.get("error"),
        )


def to_tool_records(tool_results: list[dict]) -> list[ToolRecord]:
    """把工作流中的工具结果 dict 列表一次性转为记录列表。"""
    return [ToolRecord.from_result(item) for item in tool_results]


class Citation(BaseModel):
    """知识库引用，必须对应真实检索到的文档片段。"""

    marker: str = Field(description="引用标记，如 [引用1]")
    source: str = Field(description="知识文档文件名")
    snippet: str = Field(description="检索到的片段原文")
    score: float | None = Field(default=None, description="相似度分数")
    verified: bool = Field(
        default=True,
        description="是否与真实检索片段比对通过",
    )


class PossibleCause(BaseModel):
    """可能原因，必须带状态标记与证据来源。"""

    cause: str
    status: DiagnosisStatus = DiagnosisStatus.PRELIMINARY
    evidence: str = ""
    source_types: list[str] = Field(default_factory=list)


class DiagnosisReport(BaseModel):
    """故障诊断报告，结论可追溯到工具结果与知识引用。"""

    issue_category: str = "unknown"
    summary: str = ""
    possible_causes: list[PossibleCause] = Field(default_factory=list)
    unverified_points: list[str] = Field(default_factory=list)
    tool_evidence: list[ToolRecord] = Field(default_factory=list)
    knowledge_citations: list[Citation] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    """Agent 工作流执行结果。"""

    thread_id: str
    diagnosis_id: str = ""
    answer: str = ""
    diagnosis_status: DiagnosisStatus = DiagnosisStatus.PRELIMINARY
    executed_tools: list[str] = Field(default_factory=list)
    tool_results: list[ToolRecord] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    report: DiagnosisReport | None = None
