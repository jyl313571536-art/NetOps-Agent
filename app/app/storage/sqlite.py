"""SQLite 诊断记录存储。

使用标准库 sqlite3，无 ORM 依赖。
第一版只存不查（历史查询接口后续阶段再评估）。
"""

import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.models.diagnosis import AgentResult, DiagnosisReport

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS diagnosis_records (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    user_message TEXT NOT NULL,
    issue_category TEXT,
    diagnosis_status TEXT,
    answer TEXT,
    report_json TEXT,
    executed_tools_json TEXT,
    tool_results_json TEXT,
    citations_json TEXT,
    next_steps_json TEXT,
    duration_ms INTEGER
)
"""


class DiagnosisStorage:
    """SQLite 诊断记录存储。"""

    def __init__(self, db_path: str = "data/netops.db") -> None:
        self._db_path = db_path
        self._initialized = False
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """初始化数据表，进程内只执行一次。"""
        if self._initialized:
            return
        with self._connect() as conn:
            conn.execute(CREATE_TABLE_SQL)
        self._initialized = True

    def save_record(
        self,
        result: AgentResult,
        user_message: str,
        duration_ms: int = 0,
    ) -> str:
        """保存一次诊断记录，返回记录 ID。

        Args:
            result: Agent 执行结果。
            user_message: 用户原始故障描述。
            duration_ms: 本次诊断耗时（毫秒）。

        Returns:
            生成的诊断记录 ID。
        """
        self.init_db()
        record_id = uuid.uuid4().hex[:16]
        created_at = datetime.now(UTC).isoformat()
        report: DiagnosisReport | None = result.report
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO diagnosis_records (
                    id, thread_id, created_at, user_message,
                    issue_category, diagnosis_status, answer, report_json,
                    executed_tools_json, tool_results_json, citations_json,
                    next_steps_json, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    result.thread_id,
                    created_at,
                    user_message,
                    report.issue_category if report else "unknown",
                    result.diagnosis_status.value,
                    result.answer,
                    report.model_dump_json() if report else None,
                    json.dumps(result.executed_tools, ensure_ascii=False),
                    json.dumps(
                        [r.model_dump(mode="json") for r in result.tool_results],
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        [c.model_dump(mode="json") for c in result.citations],
                        ensure_ascii=False,
                    ),
                    json.dumps(result.next_steps, ensure_ascii=False),
                    duration_ms,
                ),
            )
        logger.info("诊断记录已保存: id=%s thread_id=%s", record_id, result.thread_id)
        return record_id

    def count(self) -> int:
        """返回诊断记录总数。"""
        self.init_db()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM diagnosis_records"
            ).fetchone()
        return int(row["n"]) if row else 0

    def list_records(self, limit: int = 20) -> list[dict]:
        """按时间倒序返回诊断记录摘要列表（只读）。"""
        self.init_db()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, thread_id, created_at, user_message,
                       issue_category, diagnosis_status, answer,
                       executed_tools_json, next_steps_json, duration_ms
                FROM diagnosis_records
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "thread_id": row["thread_id"],
                "created_at": row["created_at"],
                "user_message": row["user_message"],
                "issue_category": row["issue_category"],
                "diagnosis_status": row["diagnosis_status"],
                "answer": row["answer"],
                "executed_tools": json.loads(row["executed_tools_json"] or "[]"),
                "next_steps": json.loads(row["next_steps_json"] or "[]"),
                "duration_ms": row["duration_ms"],
            }
            for row in rows
        ]


_storage: DiagnosisStorage | None = None


def get_storage() -> DiagnosisStorage:
    """获取诊断存储单例。"""
    global _storage
    if _storage is None:
        from app.core.config import get_settings

        _storage = DiagnosisStorage(get_settings().storage_db_path)
    return _storage
