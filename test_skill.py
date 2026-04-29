from brocade_port_allocator.skill import run


def test_allocate_same_port_success():
    req = {
        "request_id": "t1",
        "hosts": ["host01", "host02"],
        "fabric_a_switch": {
            "switch_name": "A",
            "rack_location": "R1-U1",
            "ports": [
                {"port": 0, "connected_host": ""},
                {"port": 1, "connected_host": "used"},
                {"port": 2, "connected_host": None},
                {"port": 44, "connected_host": ""},  # reserved
            ],
        },
        "fabric_b_switch": {
            "switch_name": "B",
            "rack_location": "R2-U1",
            "ports": [
                {"port": 0, "connected_host": ""},
                {"port": 2, "connected_host": ""},
                {"port": 92, "connected_host": ""},  # reserved
            ],
        },
        "options": {"atomic": "auto", "port_pick": "lowest"},
    }

    out = run(req)
    assert out["unassigned"] == []

    # pairable ports are {0,2}
    assert out["assignments"][0]["fabric"] == "A" and out["assignments"][0]["port"] == 0
    assert out["assignments"][1]["fabric"] == "B" and out["assignments"][1]["port"] == 0
    assert out["assignments"][2]["fabric"] == "A" and out["assignments"][2]["port"] == 2
    assert out["assignments"][3]["fabric"] == "B" and out["assignments"][3]["port"] == 2


def test_allocate_insufficient_pairable_ports():
    req = {
        "request_id": "t2",
        "hosts": ["host01", "host02"],
        "fabric_a_switch": {
            "switch_name": "A",
            "rack_location": "R1-U1",
            "ports": [{"port": 0, "connected_host": ""}],
        },
        "fabric_b_switch": {
            "switch_name": "B",
            "rack_location": "R2-U1",
            "ports": [{"port": 1, "connected_host": ""}],
        },
        "options": {"atomic": "auto"},
    }

    out = run(req)
    assert out["assignments"] == []
    assert out["unassigned"][0]["reason"] == "insufficient_pairable_ports"