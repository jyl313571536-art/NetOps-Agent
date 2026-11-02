# 交换机与 VLAN 基础

## VLAN 的作用

VLAN（虚拟局域网）把一个物理交换机划分为多个逻辑广播域：

- 隔离广播流量，减少广播风暴。
- 提升安全性，不同部门/区域可做访问控制。
- 灵活组网，不依赖物理位置。

## 接口类型

### Access 接口

- 只属于一个 VLAN。
- 连接终端设备（PC、打印机、服务器）。
- 收发不带 VLAN 标签的帧。

### Trunk 接口

- 可承载多个 VLAN 的流量。
- 交换机之间互联常用。
- 帧中携带 802.1Q VLAN 标签。

## 常见 VLAN 故障

1. 终端接错接口：接口 VLAN 与预期不符，导致无法与同部门通信。
2. Trunk 未放行目标 VLAN：跨交换机同 VLAN 不通。
3. Native VLAN 不匹配：Trunk 两端 Native VLAN 不一致导致流量泄露或丢包。
4. VLAN 未创建：接口配置了 VLAN 但 VLAN 未创建。
5. STP 阻塞：环路导致部分接口被阻塞，表现为间歇性不通。

## 排查建议

1. 确认终端所在接口的 VLAN 归属（`show interfaces switchport`）。
2. 确认 Trunk 链路放行了哪些 VLAN（`show interfaces trunk`）。
3. 检查 VLAN 是否创建且命名正确（`show vlan brief`）。
4. 查看 STP 状态，排除阻塞接口（`show spanning-tree`）。
5. 结合 MAC 地址表判断终端实际接入位置（`show mac address-table`）。
