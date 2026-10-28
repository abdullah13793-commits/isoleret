"""IFC -> survey runs: pipes grouped by run, length, diameter, insulation (from the IfcCovering that covers each pipe),
the space each run sits in (design temperature and humidity), components (valves, pumps, meters), and the fire-rated
decks and walls each pipe crosses (for the fire cross-check).

Works on any IFC4 with IfcPipeSegment + IfcCovering(INSULATION) via IfcRelCoversBldgElements. Operating data
(medium temperature, hours, DS 452 part) is read from the 'Isoleret_Drift' property set when present; a survey CSV
(survey.py) supplies the same fields for buildings without a model.
"""
import multiprocessing
from collections import defaultdict

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import numpy as np


def _bboxes(model, elems):
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    out = {}
    if not elems:
        return out
    it = ifcopenshell.geom.iterator(s, model, multiprocessing.cpu_count(), include=elems)
    if it.initialize():
        while True:
            sh = it.get()
            v = np.array(sh.geometry.verts).reshape(-1, 3)
            out[sh.guid] = (v.min(0), v.max(0))
            if not it.next():
                break
    return out


def _host_kind(e):
    if e.is_a("IfcSlab"):
        return "rigid_floor"
    mat = (getattr(ue.get_material(e), "Name", "") or "").lower()
    return "flexible_wall" if "gips" in mat else "rigid_wall"


def _ei(rating):
    import re
    m = re.search(r"(\d+)", rating or "")
    return int(m.group(1)) if m else None


def read(path):
    m = ifcopenshell.open(str(path))
    spaces = {}
    for sp in m.by_type("IfcSpace"):
        ps = ue.get_psets(sp).get("Isoleret_Rum", {})
        spaces[sp.Name] = {"ambient": ps.get("AmbientTemperature"), "rh": ps.get("RelativeHumidity"), "zone": ps.get("Zone"), "guid": sp.GlobalId}
    pipes = list(m.by_type("IfcPipeSegment"))
    hosts = [e for e in list(m.by_type("IfcSlab")) + list(m.by_type("IfcWall")) if (ue.get_psets(e).get("Pset_SlabCommon") or ue.get_psets(e).get("Pset_WallCommon") or {}).get("FireRating")]
    bb = _bboxes(m, pipes + hosts)
    runs = defaultdict(lambda: {"segments": [], "length": 0.0, "components": [], "penetrations": []})
    for p in pipes:
        ps = ue.get_psets(p)
        d = ps.get("Isoleret_Drift", {})
        rid = d.get("RunId") or p.GlobalId
        r = runs[rid]
        common = ps.get("Pset_PipeSegmentTypeCommon", {})
        od, idia = common.get("OuterDiameter"), common.get("InnerDiameter")
        lo, hi = bb[p.GlobalId]
        ext = hi - lo
        L = d.get("Length") or float(max(ext))
        r.update(id=rid, name=p.Name.split(" [")[0], od=od, wall=round((od - idia) / 2, 4) if od and idia else None,
                 material=getattr(ue.get_material(p), "Name", None), system=d.get("System"), part=d.get("Part"), operation=d.get("Operation") or None,
                 tm=d.get("MediumTemperature"), hours=d.get("OperatingHours"), supports=d.get("Supports", "traditional"), space=d.get("Space"),
                 ifc_system=next((a.RelatingGroup.Name for a in p.HasAssignments or [] if a.is_a("IfcRelAssignsToGroup")), None))
        r["length"] += L
        seg = {"guid": p.GlobalId, "length": round(L, 3), "a": [round(float(x), 3) for x in lo], "b": [round(float(x), 3) for x in hi]}
        cov = None
        for rel in m.by_type("IfcRelCoversBldgElements"):
            if rel.RelatingBuildingElement == p and rel.RelatedCoverings:
                cov = rel.RelatedCoverings[0]
                break
        if cov is not None:
            cp = ue.get_psets(cov).get("Isoleret_Isolering", {})
            seg["insulation"] = {"material": cp.get("MaterialKey"), "thickness": cp.get("Thickness"), "cladding": cp.get("Cladding"),
                                 "product": cp.get("Product"), "covering": cov.GlobalId}
        else:
            seg["insulation"] = None
        # crossings of fire-rated hosts: pipe box overlaps the host box and passes through its thin dimension
        for h in hosts:
            hl, hh = bb[h.GlobalId]
            if np.all(lo <= hh + 1e-6) and np.all(hi >= hl - 1e-6):
                thin = int(np.argmin(hh - hl))
                if lo[thin] < hl[thin] - 0.01 and hi[thin] > hh[thin] + 0.01:
                    hp = ue.get_psets(h)
                    rating = (hp.get("Pset_SlabCommon") or hp.get("Pset_WallCommon") or {}).get("FireRating")
                    r["penetrations"].append({"segment": p.GlobalId, "host": h.Name, "host_guid": h.GlobalId, "kind": _host_kind(h),
                                              "thickness_mm": round(float((hh - hl)[thin]) * 1000), "rating": rating, "ei_required": _ei(rating),
                                              "storey": getattr(ue.get_container(p), "Name", None), "point": [round(float(x), 3) for x in (lo + hi) / 2]})
        r["segments"].append(seg)
    for c in list(m.by_type("IfcValve")) + list(m.by_type("IfcPump")) + list(m.by_type("IfcFlowMeter")):
        cp = ue.get_psets(c).get("Isoleret_Komponent", {})
        if cp.get("RunId") in runs:
            runs[cp["RunId"]]["components"].append({"guid": c.GlobalId, "kind": cp.get("Kind"), "insulated": cp.get("Insulated", False)})
    out = []
    for r in runs.values():
        ins = [s["insulation"] for s in r["segments"] if s["insulation"]]
        r["insulation"] = ins[0] if ins and len(ins) == len(r["segments"]) else (ins[0] if ins else None)
        r["length"] = round(r["length"], 2)
        sp = spaces.get(r.get("space")) or {}
        r["ambient"], r["rh"], r["zone"] = sp.get("ambient"), sp.get("rh"), sp.get("zone")
        out.append(r)
    return sorted(out, key=lambda r: r["id"]), spaces
