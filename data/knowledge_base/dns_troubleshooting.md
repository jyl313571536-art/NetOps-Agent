# DNS 故障排查指南

## 常见 DNS 故障现象

1. 能 Ping 通网关和公网 IP，但域名无法解析。
2. 域名解析缓慢，网页打开超时。
3. 部分域名可解析，部分域名失败。
4. DNS 解析结果与预期 IP 不一致。

## 排查步骤

### 第一步：确认本机 DNS 配置

使用 `ipconfig /all`（Windows）或 `cat /etc/resolv.conf`（Linux）
查看当前 DNS 服务器地址是否正确。

检查要点：

- DNS 服务器 IP 是否指向正确的内网 DNS 或公共 DNS。
- 是否存在多个 DNS 服务器且优先级错误。
- DHCP 下发的 DNS 是否符合预期。

### 第二步：验证 DNS 解析

使用 `nslookup` 或 `dig` 命令测试解析：

- 直接向指定 DNS 服务器查询，绕过本机缓存。
- 对比不同 DNS 服务器的解析结果。
- 检查是否存在解析超时或 SERVFAIL。

### 第三步：排查 DNS 缓存

本地 DNS 缓存可能保留过期记录：

- Windows：`ipconfig /flushdns` 清空缓存。
- Linux：`systemd-resolve --flush-caches`。

### 第四步：检查域名后缀与搜索域

内网裸主机名（如 `server01`）通常依赖 DNS 后缀补全，
需确认网卡属性中的 DNS 后缀配置是否正确。

## 常见原因

1. DNS 服务器地址配置错误或不可达。
2. 本地 DNS 缓存过期。
3. DNS 服务器本身故障或过载。
4. 防火墙拦截 UDP 53 端口。
5. 域名后缀/搜索域配置缺失。
