# NetOps Agent 演示案例

本文档的响应输出均为 **2026-11-01 真实运行捕获**（真实 MiMo 调用、真实工具执行、
真实 BGE 检索、SQLite 落库），非人工编造。复现命令见文末。

输出中的 `simulation` 表示模拟设备虚构数据，`local_diagnostic` 表示本机真实检测，
两类来源在结果中严格区分。

---

## 案例 1：本机连通性与 DNS 检测（local_diagnostic 实证）

**用户消息**：

> 请帮我做本机网络诊断：Ping 127.0.0.1 测试本机回环，并查询 localhost 的 DNS 解析结果，告诉我是否正常。

**观察点**：工具结果来源标记 `local_diagnostic`，这是本机真实执行的检测。

**真实运行输出**：

```text
diagnosis_status : confirmed
diagnosis_id     : d165fdd991ec47c7
issue_category   : connectivity
executed_tools   :
  - ping_host [local_diagnostic] 成功 | ping_host 目标 127.0.0.1 完成（returncode=0）
  - dns_lookup [local_diagnostic] 成功 | 主机 localhost 解析到 2 个地址
citations        : 4 条
  - [引用3] network_connectivity.md verified=True
  - [引用1] dns_troubleshooting.md verified=True
  - [引用2] dns_troubleshooting.md verified=True
  - [引用4] network_connectivity.md verified=True
unverified_points: （无）
answer（前 120 字）: 本机回环与 localhost 解析均正常，未发现故障。依据：local_diagnostic
的 ping_host 对 127.0.0.1 发起 4 次探测并成功返回（returncode=0），说明本机 TCP/IP
协议栈回环功能完
```

**说明**：本例工具检测直接证明"无故障"，证据充分，状态为 `confirmed`；
知识库引用仅用于解释排查方法，4 条引用均通过真实性校验。

---

## 案例 2：模拟交换机状态分析（simulation 数据演示）

**用户消息**：

> 帮我分析模拟交换机 switch-01 的接口状态和 VLAN 配置，哪些接口是 down 的？属于哪个 VLAN？

**观察点**：工具结果来源标记 `simulation`，这是虚构模拟数据，非真实设备。

**真实运行输出**：

```text
diagnosis_status : suspected
diagnosis_id     : 9cd986e7c3b84304
issue_category   : connectivity
executed_tools   :
  - analyze_interface_status [simulation] 成功 | 模拟设备 SW-CORE-01 共 4 个接口，其中 2 个状态为 up
  - analyze_vlan_config [simulation] 成功 | 模拟设备 SW-CORE-01 共配置 3 个 VLAN
  - analyze_network_logs [simulation] 成功 | 模拟设备日志共 1 条（级别 WARNING）
  - analyze_network_logs [simulation] 成功 | 模拟设备日志共 5 条（级别 INFO）
citations        : 3 条
  - [引用3] network_connectivity.md verified=True
  - [引用1] switch_vlan.md verified=True
  - [引用2] switch_vlan.md verified=True
unverified_points: ['结论尚未被工具检测充分验证，标记为推测']
answer（前 120 字）: 模拟交换机 SW-CORE-01（device_id: switch-01）共 4 个接口，其中 2 个为 up，
即存在 2 个非 up 状态接口（工具结果来源 simulation）；设备共配置 3 个 VLAN（来源 simulatio
```

**说明**：
1. 全部工具结果标记 `simulation`，回答中明确注明"（工具结果来源 simulation）"。
2. 状态为 `suspected` 而非 `confirmed`：模拟数据是虚构的，不能作为真实设备结论依据，
   `unverified_points` 如实标注"标记为推测"。
3. 运行中 `AGENT_TIMEOUT`（60s）触发，多轮诊断按保护规则收束，行为符合设计。

---

## 案例 3：综合故障诊断（多工具 + 知识引用 + 报告）

**用户消息**：

> 我的电脑可以 Ping 通网关，但是无法访问互联网，帮我诊断可能原因并给出依据。

**观察点**：citations 是否 verified、unverified_points 是否如实标记推测、
报告是否区分工具证据/知识库/推断。

**真实运行输出**：

```text
diagnosis_status : suspected
diagnosis_id     : b9b9e579ad7c4004
issue_category   : connectivity
executed_tools   :
  - dns_lookup [local_diagnostic] 成功 | 主机 www.baidu.com 解析到 2 个地址
  - analyze_routing_table [simulation] 成功 | 模拟设备 RTR-EDGE-01 共 3 条路由，其中 1 条默认路由
  - analyze_interface_status [simulation] 成功 | 模拟设备 RTR-EDGE-01 共 2 个接口，其中 2 个状态为 up
  - analyze_network_logs [simulation] 成功 | 模拟设备日志共 1 条（级别 ERROR）
citations        : 1 条
  - [引用2] network_connectivity.md verified=True
unverified_points: ['结论尚未被工具检测充分验证，标记为推测']
answer（前 120 字）: 用户"能 Ping 通网关但无法上网"属于典型场景，知识库列出的常见原因按可能性
排序为 DNS 解析故障、默认路由缺失或错误、出口 NAT 配置异常、上联链路或运营商故障、本机代理设置
错误 [引用2]。结合本次工具检测结果逐项排除：
```

**说明**：
1. 同一回答中混合了两类来源：DNS 解析是本机真实检测（`local_diagnostic`），
   路由/接口/日志来自模拟设备（`simulation`），回答逐项注明依据。
2. 知识库引用 `[引用2]` 对应 `network_connectivity.md` 的真实检索片段，verified=True。
3. 状态保持 `suspected`：`www.baidu.com` 解析正常只能排除本机 DNS 故障，
   出口/运营商方向未验证，`unverified_points` 如实标记为推测。

---

## 复现方式

```bash
# 前提：已配置 MIMO_API_KEY；国内网络建议设置 HF_ENDPOINT=https://hf-mirror.com

# 运行全部案例
python scripts/run_demo.py

# 只运行案例 1
python scripts/run_demo.py 1

# 同时保存响应 JSON 到 docs/demos/
python scripts/run_demo.py --save

# 对已运行的服务发起真实 HTTP 请求
uvicorn app.main:app --reload        # 另开终端
python scripts/run_demo.py --base-url http://127.0.0.1:8000
```

完整响应 JSON 见 `docs/demos/demo_00*.json`（由 `--save` 生成）。

**注意**：输出内容由模型生成，不同次运行的具体措辞与诊断 ID 会变化，
但数据来源标记、引用校验、状态判定规则是确定性的。
