# Brocade Port Allocator Skill (POC) / 博科端口分配 Skill（POC）

A small, framework-agnostic Python skill that allocates Brocade FC switch ports for hosts with **dual-fabric redundancy** and **strict same port number** across Fabric A and Fabric B.

一个轻量、与框架无关的 Python skill，用于给主机分配博科（Brocade）光纤交换机端口，满足 **双 Fabric 冗余**，并且 **同一台主机在 Fabric A 与 Fabric B 上必须使用相同端口号**。

---

## Features / 功能特性

- **Dual-fabric redundancy**: allocate one port on Fabric A and one port on Fabric B for each host.  
  **双 Fabric 冗余**：每台主机在 Fabric A 与 Fabric B 各分配 1 个端口。

- **Same port number enforced**: Fabric A port number must equal Fabric B port number for the same host (e.g., A:10 and B:10).  
  **强制相同端口号**：同一主机在 A/B 上端口号必须一致（例如 A:10、B:10）。

- **Reserved port exclusion** (global): configured by `reserved_port_ranges` in `config.yaml`.  
  **全局预留端口规避**：通过 `config.yaml` 的 `reserved_port_ranges` 配置。

- **Simple used/free detection**: `connected_host` non-empty => used; empty/None => free.  
  **端口占用判定简单明确**：`connected_host` 非空表示已用；空字符串或 None 表示空闲。

- **Outputs only the allocation list**, no zoning/CLI commands.  
  **仅输出端口分配结果列表**，不做 zoning 或下发交换机命令。

---

## Quick Start / 快速开始

### Entrypoint / 入口函数

```python
from brocade_port_allocator.skill import run

result = run(input_json)
print(result)
```

`run(input: dict, context: dict | None = None) -> dict`

- `input` is the normalized request payload (already adapted from DCM upstream).  
  `input` 为标准化后的请求数据（由上游从 DCM 适配整理后传入）。
- `context` is optional and unused in the POC implementation.  
  `context` 可选，POC 版本不使用。

---

## Configuration / 配置

### Default config file / 默认配置文件
`brocade_port_allocator/config.yaml`

### Override config path / 覆盖配置路径
Set environment variable:

- `BROCADE_PORT_ALLOCATOR_CONFIG=/path/to/config.yaml`

### Default reserved port ranges / 默认预留端口范围（全局）
- 44-47
- 92-95

Example config:

```yaml
reserved_port_ranges:
  - [44, 47]
  - [92, 95]

defaults:
  port_pick: lowest   # lowest / highest
  atomic: auto        # auto / true / false
```

---

## Input Contract (Normalized) / 输入契约（标准化）

> The skill does NOT depend on raw DCM schema.  
> Skill 不依赖 DCM 原始字段结构，上游需整理成如下标准格式。

```json
{
  "request_id": "20260429-001",
  "hosts": ["host01", "host02"],
  "fabric_a_switch": {
    "switch_name": "brcd-a-sw01",
    "rack_location": "R1-U20",
    "ports": [
      {"port": 0, "connected_host": ""},
      {"port": 1, "connected_host": "oldhost01"}
    ]
  },
  "fabric_b_switch": {
    "switch_name": "brcd-b-sw01",
    "rack_location": "R2-U18",
    "ports": [
      {"port": 0, "connected_host": null},
      {"port": 1, "connected_host": ""}
    ]
  },
  "options": {
    "atomic": "auto",
    "port_pick": "lowest"
  }
}
```

### Field explanation / 字段说明
- `hosts`: list of host names to allocate.  
  `hosts`：需要分配端口的主机名列表。
- `ports[].port`: port number (int).  
  `ports[].port`：端口号（整数）。
- `ports[].connected_host`: host name if already connected; empty/None means free.  
  `ports[].connected_host`：已连接的主机名；为空/None 代表空闲。
- `options.port_pick`: `lowest` or `highest`.  
  `options.port_pick`：`lowest`（优先小端口）或 `highest`（优先大端口）。
- `options.atomic`: `auto/true/false`. In this POC, `auto` acts like strong-atomic.  
  `options.atomic`：`auto/true/false`；POC 中 `auto` 等价于强原子。

---

## Output / 输出

```json
{
  "request_id": "20260429-001",
  "assignments": [
    {"fabric": "A", "switch_name": "...", "rack_location": "...", "port": 0, "host_name": "host01"},
    {"fabric": "B", "switch_name": "...", "rack_location": "...", "port": 0, "host_name": "host01"}
  ],
  "unassigned": []
}
```

- `assignments`: flat list. Each host typically appears twice (A and B), with the same `port` number.  
  `assignments`：扁平列表。每台主机通常两条记录（A/B 各一条），且端口号相同。
- `unassigned`: reasons when allocation cannot be completed.  
  `unassigned`：无法完成分配时的原因说明。

---

## Notes on Same Port Number / 关于“必须相同端口号”的说明

The allocator computes:

- `FreeA`: free & non-reserved ports on Fabric A switch  
- `FreeB`: free & non-reserved ports on Fabric B switch  
- `Pairable = FreeA ∩ FreeB`

Only ports in `Pairable` can be assigned, ensuring the same port number on A and B.

分配器会计算：

- `FreeA`：A 侧空闲且非预留的端口集合  
- `FreeB`：B 侧空闲且非预留的端口集合  
- `Pairable = FreeA ∩ FreeB`（交集）

仅从 `Pairable` 中选择端口，从而保证 A/B 端口号一致。

---

## Development / 开发与测试

```bash
