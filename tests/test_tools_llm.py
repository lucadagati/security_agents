"""Tool schema validation and Ollama JSON repair parsing."""

from coevsec.core.types import Role
from coevsec.environment.sim.tools import build_tool_registry
from coevsec.llm.ollama import _parse_tool_call


def test_tool_schema_accepts_valid_params():
    reg = build_tool_registry()
    exploit = reg.get("exploit")
    assert exploit is not None
    assert exploit.validate_params({"host": "gw", "vuln": "gw_v0"}) == []


def test_tool_schema_rejects_missing_host():
    reg = build_tool_registry()
    monitor = reg.get("monitor")
    assert monitor is not None
    errs = monitor.validate_params({})
    assert errs


def test_role_tool_split():
    reg = build_tool_registry()
    att = {t.name for t in reg.for_role(Role.ATTACKER)}
    dfn = {t.name for t in reg.for_role(Role.DEFENDER)}
    assert "exploit" in att and "exploit" not in dfn
    assert "isolate" in dfn and "isolate" not in att
    assert "wait" in att and "wait" in dfn
    assert "communicate" in att and "communicate" in dfn


def test_parse_tool_call_from_fenced_json():
    raw = """```json
    {"tool": "recon", "params": {}, "rationale": "look around", "strategy": "recon"}
    ```"""
    tc = _parse_tool_call(raw)
    assert tc is not None
    assert tc.tool == "recon"
    assert tc.rationale == "look around"


def test_parse_tool_call_embedded_object():
    raw = "Sure. {\"tool\": \"wait\", \"params\": {}} thanks"
    tc = _parse_tool_call(raw)
    assert tc is not None
    assert tc.tool == "wait"


def test_parse_tool_call_rejects_garbage():
    assert _parse_tool_call("no json here") is None
