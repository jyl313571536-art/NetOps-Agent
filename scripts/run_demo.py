#!/usr/bin/env python
"""NetOps Agent 演示案例脚本。

真实执行完整诊断链路（真实 MiMo + 真实诊断工具 + 真实 RAG + SQLite 落库）。
模拟设备数据部分会在结果中明确标记 simulation，与本机真实检测区分。

用法：
    python scripts/run_demo.py            # 运行全部案例
    python scripts/run_demo.py 1 3        # 只运行案例 1 和 3
    python scripts/run_demo.py --save     # 同时把响应保存到 docs/demos/
    python scripts/run_demo.py --base-url http://127.0.0.1:8000
                                          # 对已运行的服务发起真实 HTTP 请求

前提：
    1. 已配置 MIMO_API_KEY（环境变量或 .env）。
    2. 首次运行需下载 BGE 模型；网络受限时设置 HF_ENDPOINT=https://hf-mirror.com。
"""

import argparse
import json
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DEMOS: list[dict] = [
    {
        "id": 1,
        "title": "本机连通性与 DNS 检测（local_diagnostic 实证）",
        "message": (
            "请帮我做本机网络诊断：Ping 127.0.0.1 测试本机回环，"
            "并查询 localhost 的 DNS 解析结果，告诉我是否正常。"
        ),
        "focus": "观察工具结果来源标记 local_diagnostic，这是本机真实执行的检测。",
    },
    {
        "id": 2,
        "title": "模拟交换机状态分析（simulation 数据演示）",
        "message": (
            "帮我分析模拟交换机 switch-01 的接口状态和 VLAN 配置，"
            "哪些接口是 down 的？属于哪个 VLAN？"
        ),
        "focus": "观察工具结果来源标记 simulation，这是虚构模拟数据，非真实设备。",
    },
    {
        "id": 3,
        "title": "综合故障诊断（多工具 + 知识引用 + 报告）",
        "message": (
            "我的电脑可以 Ping 通网关，但是无法访问互联网，"
            "帮我诊断可能原因并给出依据。"
        ),
        "focus": (
            "观察 citations 是否 verified、unverified_points 是否如实标记推测、"
            "报告是否区分工具证据/知识库/推断。"
        ),
    },
]


def run_via_httpx(base_url: str, message: str, thread_id: str) -> dict:
    """对已运行的服务发起真实 HTTP 请求。"""
    resp = httpx.post(
        f"{base_url.rstrip('/')}/api/v1/agent/chat",
        json={"message": message, "thread_id": thread_id},
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


def run_via_testclient(message: str, thread_id: str) -> dict:
    """通过 TestClient 驱动真实 FastAPI 应用（同一 ASGI 应用）。"""
    from fastapi.testclient import TestClient

    from app.main import app

    if not hasattr(run_via_testclient, "_client"):
        run_via_testclient._client = TestClient(app)
    resp = run_via_testclient._client.post(
        "/api/v1/agent/chat",
        json={"message": message, "thread_id": thread_id},
    )
    resp.raise_for_status()
    return resp.json()


def print_result(data: dict) -> None:
    """格式化打印诊断结果的关键字段。"""
    report = data.get("report") or {}
    print(f"  diagnosis_status : {data.get('diagnosis_status')}")
    print(f"  diagnosis_id     : {data.get('diagnosis_id')}")
    print(f"  issue_category   : {report.get('issue_category')}")
    print("  executed_tools   :")
    for record in data.get("tool_results", []):
        ok = "成功" if record.get("success") else "失败"
        print(
            f"    - {record.get('tool_name')} "
            f"[{record.get('source')}] {ok} | {record.get('summary', '')[:40]}"
        )
    print(f"  citations        : {len(data.get('citations', []))} 条")
    for citation in data.get("citations", []):
        print(
            f"    - {citation.get('marker')} {citation.get('source')} "
            f"verified={citation.get('verified')}"
        )
    unverified = report.get("unverified_points", [])
    print(f"  unverified_points: {unverified if unverified else '（无）'}")
    answer = data.get("answer", "")
    print(f"  answer（前 120 字）: {answer[:120]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="NetOps Agent 演示案例")
    parser.add_argument(
        "ids", nargs="*", type=int, help="要运行的案例编号（默认全部）"
    )
    parser.add_argument(
        "--save", action="store_true", help="把响应 JSON 保存到 docs/demos/"
    )
    parser.add_argument(
        "--base-url", help="对已运行的服务发起真实 HTTP 请求"
    )
    args = parser.parse_args()

    selected = [d for d in DEMOS if not args.ids or d["id"] in args.ids]
    if not selected:
        print("未匹配到任何案例，可用编号:", [d["id"] for d in DEMOS])
        return 1

    if args.save:
        (PROJECT_ROOT / "docs" / "demos").mkdir(parents=True, exist_ok=True)

    def runner(message: str, tid: str) -> dict:
        if args.base_url:
            return run_via_httpx(args.base_url, message, tid)
        return run_via_testclient(message, tid)

    for demo in selected:
        thread_id = f"demo-{demo['id']:03d}"
        print("=" * 60)
        print(f"案例 {demo['id']}：{demo['title']}")
        print(f"消息：{demo['message']}")
        print(f"观察点：{demo['focus']}")
        print("-" * 60)
        try:
            data = runner(demo["message"], thread_id)
        except Exception as exc:  # noqa: BLE001 - 演示脚本如实报告失败
            print(f"  [执行失败] {type(exc).__name__}: {exc}")
            continue
        print_result(data)
        if args.save:
            out_path = (
                PROJECT_ROOT / "docs" / "demos" / f"demo_{demo['id']:03d}.json"
            )
            out_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  已保存: {out_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
