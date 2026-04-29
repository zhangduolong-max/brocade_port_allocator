"""Brocade FC switch port allocation skill (POC).

Key requirements implemented:
- Dual-fabric redundancy (Fabric A + Fabric B)
- For the same host, Fabric A and Fabric B MUST allocate the SAME port number
- Exclude globally reserved port ranges (default: 44-47, 92-95)
- Port is considered USED if connected_host is non-empty, FREE otherwise
- Output: a flat list of assignments (A and B each as one row)

Entrypoint:
    run(input: dict, context: dict | None = None) -> dict

Config:
- By default reads config.yaml shipped with this module.
- Override with env var BROCADE_PORT_ALLOCATOR_CONFIG.

This module is intentionally framework-agnostic for easy embedding into internal agents.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


DEFAULT_CONFIG: Dict[str, Any] = {
    "reserved_port_ranges": [[44, 47], [92, 95]],
    "defaults": {"port_pick": "lowest", "atomic": "auto"},
}


def _load_yaml(path: str) -> Dict[str, Any]:
    if yaml is None:
        # Allow running without PyYAML in minimal environments.
        return DEFAULT_CONFIG.copy()

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    cfg = DEFAULT_CONFIG.copy()
    cfg.update(data)
    cfg["defaults"] = {**DEFAULT_CONFIG.get("defaults", {}), **cfg.get("defaults", {})}
    return cfg


def _load_config() -> Dict[str, Any]:
    env_path = os.getenv("BROCADE_PORT_ALLOCATOR_CONFIG")
    if env_path and os.path.exists(env_path):
        return _load_yaml(env_path)

    here = os.path.dirname(os.path.abspath(__file__))
    local_path = os.path.join(here, "config.yaml")
    if os.path.exists(local_path):
        return _load_yaml(local_path)

    return DEFAULT_CONFIG.copy()


def _is_free(connected_host: Optional[str]) -> bool:
    # DCM contract: non-empty => used; empty/None => free
    if connected_host is None:
        return True
    if isinstance(connected_host, str) and connected_host.strip() == "":
        return True
    return False


def _expand_ranges(ranges: List[List[int]]) -> Set[int]:
    out: Set[int] = set()
    for item in ranges:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError(f"Invalid reserved_port_ranges item: {item}")
        start, end = int(item[0]), int(item[1])
        if end < start:
            raise ValueError(f"Invalid range: {item}")
        out.update(range(start, end + 1))
    return out


def _free_ports_set(ports: List[Dict[str, Any]], reserved: Set[int]) -> Set[int]:
    free: Set[int] = set()
    for p in ports:
        port_no = int(p["port"])
        if port_no in reserved:
            continue
        if _is_free(p.get("connected_host")):
            free.add(port_no)
    return free


def _allocate(request: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    request_id = request.get("request_id")
    hosts: List[str] = request["hosts"]

    fa = request["fabric_a_switch"]
    fb = request["fabric_b_switch"]

    reserved_ranges = config.get("reserved_port_ranges", DEFAULT_CONFIG["reserved_port_ranges"])
    reserved_global = _expand_ranges(reserved_ranges)

    free_a = _free_ports_set(fa["ports"], reserved_global)
    free_b = _free_ports_set(fb["ports"], reserved_global)

    # Enforce same port number on A and B by taking intersection.
    pairable = sorted(free_a & free_b)

    options = request.get("options", {}) or {}
    port_pick = options.get("port_pick", config.get("defaults", {}).get("port_pick", "lowest"))
    if port_pick == "highest":
        pairable = list(reversed(pairable))

    atomic_opt = options.get("atomic", config.get("defaults", {}).get("atomic", "auto"))
    # POC: auto behaves as strong-atomic.
    atomic_effective = True if atomic_opt == "auto" else bool(atomic_opt)

    if atomic_effective and len(pairable) < len(hosts):
        return {
            "request_id": request_id,
            "assignments": [],
            "unassigned": [
                {
                    "reason": "insufficient_pairable_ports",
                    "needed": len(hosts),
                    "pairable": len(pairable),
                }
            ],
        }

    assignments: List[Dict[str, Any]] = []
    unassigned: List[Dict[str, Any]] = []

    for i, host in enumerate(hosts):
        if i >= len(pairable):
            unassigned.append({"host_name": host, "reason": "insufficient_pairable_ports"})
            if atomic_effective:
                return {"request_id": request_id, "assignments": [], "unassigned": unassigned}
            continue

        port_no = pairable[i]

        assignments.append(
            {
                "fabric": "A",
                "switch_name": fa["switch_name"],
                "rack_location": fa["rack_location"],
                "port": port_no,
                "host_name": host,
            }
        )
        assignments.append(
            {
                "fabric": "B",
                "switch_name": fb["switch_name"],
                "rack_location": fb["rack_location"],
                "port": port_no,
                "host_name": host,
            }
        )

    return {"request_id": request_id, "assignments": assignments, "unassigned": unassigned}


def run(input: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Skill entrypoint.

    Parameters
    ----------
    input:
        Normalized request JSON.
    context:
        Optional runtime context (unused in POC).
    """
    config = _load_config()
    return _allocate(input, config)