"""Isoleret MCP server: technical insulation (DS 452, EN ISO 12241) for any MCP client.

Run (stdio):   python src/mcp_server.py
Client config: {"mcpServers": {"isoleret": {"command": "python", "args": ["<repo>/src/mcp_server.py"]}}}
"""
import json
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from isoleret import audit, ds452, economy, physics  # noqa: E402
from isoleret.materials import INSULATION  # noqa: E402

READ = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
server = MCPServer(
    name="isoleret", title="Isoleret",
    instructions=("Technical insulation of pipes: DS 452 class (table 6.4) and U-limit, heat loss after EN ISO 12241, required thickness, "
                  "condensation on cold pipes, savings and payback, and the fire cross-check (insulation in fire-rated penetrations must match "
                  "the tested ETA configuration). check_pipe for one pipe; audit_overview / list_runs / get_run for the demonstration building "
                  "(fictitious); fire_crosscheck for penetrations. Prices and CO2 factors are example values. Answer in the user's language."),
    version="1.0.0")


def _audit():
    return json.loads((ROOT / "results" / "audit.json").read_text(encoding="utf-8"))


@server.tool(annotations=READ)
def check_pipe(system: str, part: str, outer_diameter_mm: float, medium_temp_c: float, ambient_temp_c: float, operation: str | None = None,
               insulation_material: str = "stenuld_roerskaal", insulation_mm: float = 0, cladding: str = "pvc", supports: str = "traditional",
               relative_humidity_pct: float | None = None, length_m: float = 1.0, hours_per_year: float = 8760, carrier: str = "fjernvarme",
               bare_surface: str = "steel") -> dict:
    """One pipe against DS 452 and EN ISO 12241.
    system: heating | dhw | cold_water | solar | heat_pump | cooling | roof_drain. part: distribution | connection_other_room |
    connection_same_room | tank | pipes | ... operation (heating distribution): season_le45 | season_regulated | other.
    insulation_material: stenuld_roerskaal | stenuld_lamel | elastomer | pe_skum | pir. cladding: laerred | pvc | alu_blank | alu_oxid | galv | elastomer.
    supports: traditional (+15 % inside / +25 % outside) | insulated. Returns class, U vs limit, heat loss, surface temperature, required
    thickness (continuous and next standard size), condensation thickness for cold pipes, and savings vs bare pipe."""
    D, t = outer_diameter_mm / 1000, insulation_mm / 1000
    rc = ds452.required_class(system, part, operation, ambient_temp_c)
    cls = rc["class"]
    f = ds452.support_factor(supports, ambient_temp_c <= 5)
    lay = [(t, insulation_material)] if t else []
    r = physics.pipe(D, lay, medium_temp_c, ambient_temp_c, cladding, bare=bare_surface)
    q = r["q"] * (f if lay else 1)
    out = {"class": cls, "table_6_4_row": list(rc["row"]), "ambient_band": rc["ambient_band"], "support_factor": f if lay else 1.0,
           "heat_loss_w_per_m": round(q, 2), "U_w_per_mk": round(q / (medium_temp_c - ambient_temp_c), 4) if medium_temp_c != ambient_temp_c else None,
           "surface_temp_c": round(r["ts"], 1), "lambda_used": [round(x, 4) for x in r["lam"]]}
    if isinstance(cls, int) and cls > 0:
        lim = ds452.u_limit(cls, D)
        need = physics.thickness_for(D, insulation_material, medium_temp_c, ambient_temp_c, lim, cladding, f)
        std = physics.thickness_for(D, insulation_material, medium_temp_c, ambient_temp_c, lim, cladding, f,
                                    steps=[x / 1000 for x in economy.STEPS_MM.get(insulation_material, [20, 30, 40, 50, 60, 80, 100])])
        out.update(U_limit=round(lim, 4), meets_class=bool(lay) and out["U_w_per_mk"] is not None and out["U_w_per_mk"] <= lim + 1e-9,
                   required_mm=round(need * 1000, 1) if need else None, required_standard_mm=round(std * 1000) if std else None,
                   component_half_thickness_mm=round(need * 500, 1) if need else None)
    if relative_humidity_pct is not None and medium_temp_c < ambient_temp_c:
        dew = physics.dew_point(ambient_temp_c, relative_humidity_pct)
        tc = physics.condensation_thickness(D, insulation_material, medium_temp_c, ambient_temp_c, relative_humidity_pct, cladding)
        out.update(dew_point_c=round(dew, 1), condensation=r["ts"] < dew, condensation_free_mm=round(tc * 1000, 1) if tc is not None else None)
    if lay and medium_temp_c > ambient_temp_c:
        q0 = physics.pipe(D, [], medium_temp_c, ambient_temp_c, bare=bare_surface)["q"]
        kwh = (q0 - q) * length_m * hours_per_year / 1000
        out["savings_vs_bare"] = {"kwh_per_year": round(kwh), "dkk_per_year": round(kwh * economy.CARRIERS[carrier]["price"]),
                                  "co2_kg": round(kwh * economy.CARRIERS[carrier]["co2"]), "note": "example price and CO2 factor"}
    return out


@server.tool(annotations=READ)
def ds452_class(system: str, part: str, ambient_temp_c: float, operation: str | None = None) -> dict:
    """Insulation class from DS 452 table 6.4 and whether condensation insulation is also required."""
    return ds452.required_class(system, part, operation, ambient_temp_c)


@server.tool(annotations=READ)
def audit_overview() -> dict:
    """The demonstration building (fictitious): runs, status counts, heat loss today, savings, cost, payback, CO2, fire conflicts."""
    a = _audit()
    return {"model": a["model"], **a["summary"], "note": "example prices; fictitious building"}


@server.tool(annotations=READ)
def list_runs(status: str | None = None, system: str | None = None) -> list[dict]:
    """Runs of the demonstration audit. status: OK | UNDER | MANGLER | KONDENS | DS439. system: heating | dhw | cold_water."""
    return [{"id": r["id"], "name": r["name"], "space": r["space"], "class": r["class"], "status": r["status"],
             "insulation": r["insulation"]["product"] + f" {round(r['insulation']['thickness'] * 1000)} mm" if r["insulation"] else "uisoleret",
             "proposal": f"{r['proposal']['product']} {r['proposal']['thickness_mm']} mm" if r["proposal"] else None,
             "kwh_saved": r["proposal"]["kwh"] if r["proposal"] else 0}
            for r in _audit()["runs"] if (not status or r["status"] == status.upper()) and (not system or r["system"] == system)]


@server.tool(annotations=READ)
def get_run(run_id: str) -> dict:
    """Everything about one run (e.g. 'K1'): conditions, class, U vs limit, proposal with savings and payback, components, fire crossings."""
    r = next((x for x in _audit()["runs"] if x["id"].lower() == run_id.lower()), None)
    return {k: v for k, v in r.items() if k != "segments"} if r else {"error": f"unknown run {run_id}"}


@server.tool(annotations=READ)
def fire_crosscheck(only_conflicts: bool = True) -> list[dict]:
    """Fire-rated penetrations crossed by insulated pipes: tested today, tested after the proposed upgrade, and the recommendation
    (keep the tested insulation locally where DS 452 table 6.2's half thickness allows)."""
    out = []
    for r in _audit()["runs"]:
        for x in r["fire"]:
            if only_conflicts and not x["conflict"]:
                continue
            out.append({"run": r["id"], "pipe": r["name"], "host": x["host"], "rating": x["rating"], "now": x["now"], "after": x["new"],
                        "half_thickness_mm": x["half_thickness_mm"], "recommendation": x["recommendation"]})
    return out


@server.tool(annotations=READ)
def materials() -> dict:
    """Insulation materials with λ(θ) curves (typical declared values; replace with the product data sheet) and maximum temperatures."""
    return {k: {"name": v["name"], "lambda_curve": v["curve"], "max_temp_c": v["max_temp"]} for k, v in INSULATION.items()}


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
def run_audit() -> dict:
    """Re-run the audit on the demonstration IFC and write results/audit.json."""
    o = audit.run()
    return {"summary": o["summary"], "answer_key": {k: o["evaluation"][k] for k in ("runs", "correct", "all_ok")} if o.get("evaluation") else None}


if __name__ == "__main__":
    server.run("stdio")
