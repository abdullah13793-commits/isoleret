"""Audit: every run checked against DS 452, heat loss now and after the proposed upgrade, savings, CO2, cost, payback,
condensation on cold pipes, components, and the fire cross-check at fire-rated penetrations.

Statuses:
  OK        meets the class from table 6.4 (U incl. heat-bridge allowance ≤ class limit)
  UNDER     insulated, but U above the limit: the missing thickness and the upgrade are given
  MANGLER   uninsulated where the class requires insulation
  KONDENS   cold pipe whose surface (or bare pipe) is below the dew point of the room air
  DS439     cold water outside the envelope: frost protection after DS 439, not an energy class
  INGEN_KRAV  class 0 / no requirement

python -m isoleret.audit  ->  results/audit.json (+ evaluation against models/planted.json)
"""
import json
import math
from pathlib import Path

from . import ds452, economy, fire_engine, physics, takeoff
from .materials import INSULATION

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "models" / "blok_c_isolering.ifc"
PIPE_MAT = {"Stål": "steel", "Kobber": "copper", "PEX": "plastic", "Alupex": "composite"}
FIRE_MAT = {"Stål": "Stål", "Kobber": "Kobber"}
CARRIER = {"heating": "fjernvarme", "dhw": "fjernvarme", "cold_water": None}


def layers_of(ins):
    return [(ins["thickness"], ins["material"])] if ins and ins.get("thickness") else []


def loss(run, layers, cladding, f):
    """Heat-bridge allowance (supports) applies to insulated pipes only."""
    r = physics.pipe(run["od"], layers, run["tm"], run["ambient"], cladding, bare=PIPE_MAT.get(run["material"], "steel"))
    return r["q"] * (f if layers else 1.0), r


def component_loss(run, kind, insulated_t=None, material="stenuld_roerskaal", f=1.0):
    L = economy.COMPONENT_PIPE_M.get(kind, 0.2)
    lay = [(insulated_t, material)] if insulated_t else []
    return physics.pipe(run["od"], lay, run["tm"], run["ambient"], "laerred", bare=PIPE_MAT.get(run["material"], "steel"))["q"] * L * f


def propose(run, cls, f, outside):
    cold = run["tm"] < run["ambient"]
    mat = "elastomer" if cold or run["system"] == "cold_water" else ("stenuld_roerskaal" if run["od"] <= 0.115 else "stenuld_lamel")
    clad = "elastomer" if mat == "elastomer" else "pvc"
    steps = [t / 1000 for t in economy.STEPS_MM[mat]]
    need = None
    if isinstance(cls, int) and cls > 0:
        need = physics.thickness_for(run["od"], mat, run["tm"], run["ambient"], ds452.u_limit(cls, run["od"]), clad, f, steps=steps)
    if cold and run.get("rh"):
        tc = physics.condensation_thickness(run["od"], mat, run["tm"], run["ambient"], run["rh"], clad, steps=steps)
        need = max(x for x in (need, tc) if x is not None) if (need or tc) else need
    return {"material": mat, "cladding": clad, "thickness": need, "product": INSULATION[mat]["name"]}


def fire_query(run, pen, ins):
    q = {"host_kind": pen["kind"], "thickness_mm": pen["thickness_mm"], "ei_required": pen["ei_required"], "hollow_core": pen["kind"] == "rigid_floor",
         "service_kind": "pipe", "material": fire_engine.norm_material(run["material"]), "od_mm": round(run["od"] * 1000, 1),
         "wall_mm": round(run["wall"] * 1000, 2) if run.get("wall") else None, "open_system": False,
         "insulation": fire_engine.norm_insulation(None if not ins else {"category": "stenuld" if "stenuld" in ins["material"] else "elastomer",
                                                                          "thickness_mm": round(ins["thickness"] * 1000), "product": ins.get("product")}),
         "configuration": "perpendicular"}
    return q


def _brief(v):
    m = (v["matches"] or v["nearest"] or [None])[0]
    if not m:
        return None
    return {"eta": m["eta"], "section": m["section"], "page": m["page"], "system": m.get("system"), "classification": m["classification"],
            "insulation": m.get("insulation"), "insulation_length": m.get("insulation_length"), "deviates": m.get("deviates", [])}


def crosscheck(run, ins_now, ins_new, cls, f):
    """For each fire-rated crossing: is the seal tested with today's insulation, with the proposed insulation, and what to do."""
    out = []
    if not run["penetrations"]:
        return out
    half = None
    if isinstance(cls, int) and cls > 0 and ins_new:
        need = physics.thickness_for(run["od"], ins_new["material"], run["tm"], run["ambient"], ds452.u_limit(cls, run["od"]), ins_new["cladding"], f)
        half = need / 2 if need else None
    for pen in run["penetrations"]:
        v_now = fire_engine.evaluate(fire_query(run, pen, ins_now))
        v_new = fire_engine.evaluate(fire_query(run, pen, ins_new)) if ins_new else None
        rec, keep = None, None
        if v_new and v_new["status"] == "TESTET":
            rec = "Efterisoleringen kan føres gennem tætningen: opbygningen er testet."
        elif v_now["status"] == "TESTET" and not ins_now:
            keep = None
            rec = ("Gennemføringen er testet med uisoleret rør. Den nye isolering skal standse ved tætningen, eller der vælges en opbygning, "
                   "der er testet med isolering; ellers brandteknisk vurdering.")
        elif v_now and v_now["status"] == "TESTET":
            keep = ins_now
            ok_half = half is not None and ins_now["thickness"] >= half - 1e-4
            L = (_brief(v_now) or {}).get("insulation_length")
            rec = (f"Behold den testede isolering ({ins_now.get('product')} {ins_now['thickness'] * 1000:.0f} mm) gennem tætningen"
                   + (f" over {L:g} mm" if L else "") + "; efterisolér uden for den testede længde. "
                   + (f"DS 452 tabel 6.2 (halv tykkelse i gennemføringer, {half * 1000:.0f} mm) er opfyldt." if ok_half else
                      f"DS 452 tabel 6.2 kræver {half * 1000:.0f} mm i gennemføringen: brandteknisk vurdering eller andet testet system." if half else ""))
        else:
            alt = (v_new or v_now)["alternatives"][:1]
            rec = "Gennemføringen er ikke testet med hverken nuværende eller ny isolering: " + (
                f"testet alternativ {alt[0]['eta']} {alt[0]['section']} (s. {alt[0]['page']}) kræver ændring af {', '.join(alt[0]['deviates'])}; "
                f"ellers brandteknisk vurdering." if alt else "brandteknisk vurdering eller andet testet system.")
        out.append({**pen, "now": {"status": v_now["status"] if v_now else None, "ref": _brief(v_now) if v_now else None},
                    "new": {"status": v_new["status"] if v_new else None, "ref": _brief(v_new) if v_new else None},
                    "half_thickness_mm": round(half * 1000) if half else None, "keep_tested": bool(keep), "recommendation": rec,
                    "conflict": bool(v_now and v_now["status"] == "TESTET" and v_new and v_new["status"] != "TESTET")})
    return out


def audit_run(run, carrier_of=CARRIER):
    outside = run["ambient"] is not None and run["ambient"] <= 5
    rc = ds452.required_class(run["system"], run["part"], run["operation"], run["ambient"])
    cls = rc["class"]
    f = ds452.support_factor(run["supports"], outside)
    ins = run["insulation"]
    lay = layers_of(ins)
    clad = (ins or {}).get("cladding", "laerred")
    q_now, r_now = loss(run, lay, clad, f)
    res = {"id": run["id"], "name": run["name"], "system": run["system"], "part": run["part"], "operation": run["operation"], "space": run["space"],
           "zone": run["zone"], "ambient": run["ambient"], "rh": run["rh"], "tm": run["tm"], "hours": run["hours"], "od_mm": round(run["od"] * 1000, 1),
           "material": run["material"], "length": run["length"], "supports": run["supports"], "support_factor": f, "class": cls,
           "class_row": list(rc["row"]), "ambient_band": rc["ambient_band"], "insulation": ins, "q_now": round(q_now, 2), "ts_now": round(r_now["ts"], 1),
           "U_now": round(r_now["U"] * (f if lay else 1.0), 4)}
    cold = run["tm"] < run["ambient"]
    dew = physics.dew_point(run["ambient"], run["rh"]) if run.get("rh") else None
    res["dew_point"] = round(dew, 1) if dew is not None else None
    res["condensation_now"] = bool(cold and dew is not None and r_now["ts"] < dew)
    limit = ds452.u_limit(cls, run["od"]) if isinstance(cls, int) and cls > 0 else None
    res["U_limit"] = round(limit, 4) if limit else None
    if isinstance(cls, str):
        status = "DS439"
    elif res["condensation_now"]:
        status = "KONDENS"
    elif not cls:
        status = "INGEN_KRAV"
    elif not lay:
        status = "MANGLER"
    elif r_now["U"] * (f if lay else 1.0) > limit + 1e-9:
        status = "UNDER"
    else:
        status = "OK"
    res["status"] = status
    prop = propose(run, cls, f, outside) if status in ("UNDER", "MANGLER", "KONDENS") else None
    res["proposal"] = None
    carrier = carrier_of.get(run["system"])
    comp_now = sum(component_loss(run, c["kind"], f=1.0) for c in run["components"] if not c["insulated"])
    if prop and prop["thickness"]:
        same = ins and ins.get("material") == prop["material"] and ins.get("product")
        new = {"material": prop["material"], "thickness": prop["thickness"], "cladding": prop["cladding"], "product": ins["product"] if same else prop["product"]}
        q_new, r_new = loss(run, layers_of(new), prop["cladding"], f)
        half = prop["thickness"] / 2
        jacket_t = max(0.02, round(half, 2))
        comp_new = sum(component_loss(run, c["kind"], jacket_t, prop["material"]) for c in run["components"] if not c["insulated"])
        kwh_pipe = max(0.0, (q_now - q_new) * run["length"] * run["hours"] / 1000)
        kwh_comp = max(0.0, (comp_now - comp_new) * run["hours"] / 1000)
        cost = economy.upgrade_cost_per_m(run["od"], prop["thickness"], prop["cladding"], replace=bool(lay)) * run["length"] + \
            sum(economy.COST["jacket_dkk"].get(c["kind"], 400) for c in run["components"] if not c["insulated"])
        kwh = kwh_pipe + kwh_comp
        econ = economy.payback(cost, kwh, carrier) if carrier else {"dkk_per_year": 0.0, "years": None}
        res["proposal"] = {**new, "thickness_mm": round(prop["thickness"] * 1000), "q_new": round(q_new, 2), "ts_new": round(r_new["ts"], 1),
                           "U_new": round(r_new["U"] * f, 4), "kwh_pipe": round(kwh_pipe), "kwh_components": round(kwh_comp), "kwh": round(kwh),
                           "co2_kg": round(kwh * economy.CARRIERS[carrier]["co2"]) if carrier else 0, "cost_dkk": round(cost),
                           "dkk_per_year": round(econ["dkk_per_year"]), "payback_years": round(econ["years"], 1) if econ["years"] else None,
                           "jacket_mm": round(jacket_t * 1000), "carrier": carrier}
    else:
        new = None
    res["components"] = [{"kind": c["kind"], "insulated": c["insulated"], "loss_w": round(component_loss(run, c["kind"]), 1)} for c in run["components"]]
    res["kwh_now"] = round((q_now * run["length"] + comp_now) * run["hours"] / 1000)
    res["fire"] = crosscheck(run, ins, new, cls, f)
    res["segments"] = run["segments"]
    return res


def summary(results):
    st = {}
    for r in results:
        st[r["status"]] = st.get(r["status"], 0) + 1
    props = [r["proposal"] for r in results if r["proposal"]]
    kwh = sum(p["kwh"] for p in props)
    cost = sum(p["cost_dkk"] for p in props)
    dkk = sum(p["dkk_per_year"] for p in props)
    return {"runs": len(results), "metres": round(sum(r["length"] for r in results), 1), "status": st, "kwh_now": sum(r["kwh_now"] for r in results),
            "kwh_saved": kwh, "co2_kg": sum(p["co2_kg"] for p in props), "cost_dkk": cost, "dkk_per_year": dkk,
            "payback_years": round(cost / dkk, 1) if dkk else None, "penetrations": sum(len(r["fire"]) for r in results),
            "fire_conflicts": sum(1 for r in results for p in r["fire"] if p["conflict"]),
            "components_uninsulated": sum(1 for r in results for c in r["components"] if not c["insulated"])}


def bom(results):
    lines = {}
    for r in results:
        p = r["proposal"]
        if not p:
            continue
        k = (p["product"], r["od_mm"], p["thickness_mm"], p["cladding"])
        lines[k] = lines.get(k, 0) + r["length"]
    out = [{"product": k[0], "pipe_od_mm": k[1], "thickness_mm": k[2], "cladding": k[3], "metres": round(v, 1), "order_m": math.ceil(v * 1.05)}
           for k, v in sorted(lines.items())]
    jackets = {}
    for r in results:
        if r["proposal"]:
            for c in r["components"]:
                if not c["insulated"]:
                    k = (c["kind"], r["od_mm"], r["proposal"]["jacket_mm"])
                    jackets[k] = jackets.get(k, 0) + 1
    out += [{"product": f"Isoleringskappe til {k[0]}", "pipe_od_mm": k[1], "thickness_mm": k[2], "cladding": "-", "pieces": n} for k, n in sorted(jackets.items())]
    return out


def evaluate_against(results, planted):
    by = {r["id"]: r for r in results}
    rows, ok_all = [], True
    for e in planted:
        r = by.get(e["id"])
        ok = r is not None and r["class"] == e.get("class") and (e.get("status") is None or r["status"] == e["status"])
        rows.append({"id": e["id"], "expected": {"class": e.get("class"), "status": e.get("status")},
                     "got": {"class": r["class"], "status": r["status"]} if r else None, "ok": ok})
        ok_all &= ok
    return {"runs": len(planted), "correct": sum(x["ok"] for x in rows), "all_ok": ok_all, "rows": rows}


def run(model=MODEL):
    runs, spaces = takeoff.read(model)
    results = [audit_run(r) for r in runs]
    s = summary(results)
    out = {"model": Path(model).name, "summary": s, "runs": results, "bom": bom(results), "spaces": spaces}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "audit.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    planted = ROOT / "models" / "planted.json"
    if planted.exists():
        ev = evaluate_against(results, json.loads(planted.read_text(encoding="utf-8")))
        (ROOT / "results" / "evaluation.json").write_text(json.dumps(ev, indent=1, ensure_ascii=False), encoding="utf-8")
        out["evaluation"] = ev
    return out


if __name__ == "__main__":
    o = run()
    print(json.dumps(o["summary"], ensure_ascii=False))
    ev = o.get("evaluation")
    if ev:
        print("answer key:", ev["correct"], "/", ev["runs"], "all_ok", ev["all_ok"])
        for r in ev["rows"]:
            if not r["ok"]:
                print("  MISMATCH", r)
