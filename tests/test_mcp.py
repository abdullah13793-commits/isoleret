"""End-to-end MCP test over stdio with the official client."""
import json
import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def _calls():
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "src" / "mcp_server.py")])
    out = {}
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            out["server"] = init.server_info.name
            out["tools"] = sorted(t.name for t in (await s.list_tools()).tools)

            async def call(name, args=None):
                res = await s.call_tool(name, args or {})
                assert not res.is_error, (name, res)
                sc = res.structured_content
                if sc is not None:
                    return sc["result"] if set(sc) == {"result"} else sc
                return json.loads(res.content[0].text)
            out["pipe"] = await call("check_pipe", {"system": "dhw", "part": "distribution", "outer_diameter_mm": 28, "medium_temp_c": 55,
                                                    "ambient_temp_c": 20, "insulation_mm": 20, "length_m": 10})
            out["cold"] = await call("check_pipe", {"system": "cold_water", "part": "pipes", "outer_diameter_mm": 54, "medium_temp_c": 10,
                                                    "ambient_temp_c": 22, "relative_humidity_pct": 55, "insulation_material": "elastomer"})
            out["cls"] = await call("ds452_class", {"system": "heating", "part": "distribution", "operation": "other", "ambient_temp_c": 4})
            out["overview"] = await call("audit_overview")
            out["under"] = await call("list_runs", {"status": "UNDER"})
            out["run"] = await call("get_run", {"run_id": "K1"})
            out["fire"] = await call("fire_crosscheck")
            out["mats"] = await call("materials")
    return out


def test_mcp_end_to_end():
    o = anyio.run(_calls)
    assert o["server"] == "isoleret"
    assert {"check_pipe", "ds452_class", "audit_overview", "list_runs", "get_run", "fire_crosscheck", "materials", "run_audit"} <= set(o["tools"])
    assert o["pipe"]["class"] == 4 and o["pipe"]["meets_class"] is False and o["pipe"]["required_standard_mm"] >= 30
    assert o["cold"]["condensation"] is True and o["cold"]["condensation_free_mm"] > 0
    assert o["cls"]["class"] == 6
    assert o["overview"]["runs"] == 25 and len(o["under"]) == 17 and o["run"]["status"] == "UNDER"
    assert o["fire"] and all(x["now"]["status"] == "TESTET" for x in o["fire"])
    (ROOT / "results" / "mcp_session.json").write_text(json.dumps(o, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
