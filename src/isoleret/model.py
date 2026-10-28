"""Demonstration survey model: the heating, hot-water and cold-water network of the same fictitious Blok C as Gennemført,
as an IFC4 file an MEP consultant or a surveyor could hand over (pipes, insulation coverings with material and thickness,
valves and pumps, spaces with design temperature and humidity, operating data per run).

Each run is planted with the result a careful engineer would reach by hand: the DS 452 class from table 6.4, and a
status only where DS 452 Annex A (table A.2 for traditional supports, A.1 for insulated supports) leaves a clear margin.
The answer key is in models/planted.json and is never read by the audit.

python -m isoleret.model  ->  models/blok_c_isolering.ifc, models/planted.json
"""
import json
import uuid
from pathlib import Path

import ifcopenshell.api as api
import ifcopenshell.guid

from . import ifcw
from .ifcw import box_solid, cyl_solid, element

ROOT = Path(__file__).resolve().parents[2]
LEVELS = [("Kælder", -3.0), ("Stueetage", 0.0), ("1. sal", 3.0), ("2. sal", 6.0), ("Tagrum", 9.0)]
SLAB = 0.22
SPACES = {  # name: (storey, box, ambient °C, RH %, zone)
    "Teknikrum": ("Kælder", (0, 0, -3.0, 12, 12, -0.22), 22.0, 55, "opvarmet"),
    "Kældergang": ("Kælder", (12, 9.2, -3.0, 36, 12, -0.22), 12.0, 65, "uopvarmet, inden for klimaskærm"),
    "Skakt A1": ("Stueetage", (5.6, 5.6, -3.0, 6.8, 6.4, 9.0), 20.0, 50, "opvarmet"),
    "Skakt A2": ("Stueetage", (9.2, 5.6, -3.0, 10.4, 6.4, 9.0), 20.0, 50, "opvarmet"),
    "Skakt B1": ("Stueetage", (25.6, 5.6, -3.0, 26.8, 6.4, 9.0), 20.0, 50, "opvarmet"),
    "Skakt B2": ("Stueetage", (29.2, 5.6, -3.0, 30.4, 6.4, 9.0), 20.0, 50, "opvarmet"),
    "Lejligheder, stue": ("Stueetage", (10.6, 0.5, 0.0, 25.4, 5.4, 2.78), 20.0, 50, "opvarmet"),
    "Lejligheder, 1. sal": ("1. sal", (10.6, 0.5, 3.0, 25.4, 5.4, 5.78), 20.0, 50, "opvarmet"),
    "Lejligheder, 2. sal": ("2. sal", (10.6, 0.5, 6.0, 25.4, 5.4, 8.78), 20.0, 50, "opvarmet"),
    "Tagrum": ("Tagrum", (0, 0, 9.0, 36, 12, 11.0), 4.0, 80, "uden for klimaskærm"),
}
SYSTEMS = {"Varme": "HEATING", "Brugsvand varmt": "DOMESTICHOTWATER", "Brugsvand koldt": "DOMESTICCOLDWATER"}
INS_NAME = {"stenuld_roerskaal": "Stenuld rørskål 80 kg/m³", "stenuld_lamel": "Stenuld lamelmåtte", "elastomer": "Kaiflex ST",
            "elastomer_armaflex": "Armaflex AF"}

# id, name, ifc system, ds452 (system, part, operation), medium °C, hours, Ø mm, wall mm, pipe material, space, legs,
# insulation (material, mm, cladding) or None, supports, components [(kind, n)], expected
R = []


def run(id_, name, sysn, ds, tm, hours, od, wall, mat, space, legs, ins=None, supports="traditional", comps=(), exp=None, product=None):
    R.append(dict(id=id_, name=name, sys=sysn, ds=ds, tm=tm, hours=hours, od=od, wall=wall, mat=mat, space=space, legs=legs, ins=ins,
                  supports=supports, comps=list(comps), exp=exp or {}, product=product))


HEAT = ("heating", "distribution", "season_regulated")
DIST_OTHER = ("heating", "distribution", "other")
DHW = ("dhw", "distribution", None)
COLD = ("cold_water", "pipes", None)
CONN = ("heating", "connection_other_room", None)
Z0 = -0.5
# basement corridor (12 °C, inside the envelope -> column > 5 °C)
run("K1", "Varme fremløb stål 60,3", "Varme", HEAT, 60, 5800, 60.3, 2.9, "Stål", "Kældergang", [((6.0, 10.6, Z0), (22.0, 10.6, Z0))],
    ("stenuld_lamel", 30, "laerred"), comps=[("ventil", 2), ("pumpe", 1)], exp={"class": 3, "status": "UNDER"})
run("K2", "Varme retur stål 60,3", "Varme", HEAT, 35, 5800, 60.3, 2.9, "Stål", "Kældergang", [((6.0, 10.3, Z0), (33.0, 10.3, Z0))],
    ("stenuld_lamel", 30, "laerred"), comps=[("ventil", 2)], exp={"class": 3, "status": "UNDER"})
run("K3", "Brugsvand varmt stål 42,4 (galv.)", "Brugsvand varmt", DHW, 55, 8760, 42.4, 2.6, "Stål", "Kældergang",
    [((6.0, 10.0, Z0), (33.0, 10.0, Z0))], ("stenuld_lamel", 40, "laerred"), comps=[("ventil", 2)], exp={"class": 4, "status": "UNDER"})
run("K4", "Cirkulation kobber 28x1", "Brugsvand varmt", DHW, 50, 8760, 28, 1.0, "Kobber", "Kældergang", [((6.0, 9.75, Z0), (33.0, 9.75, Z0))],
    ("stenuld_roerskaal", 20, "pvc"), exp={"class": 4, "status": "UNDER"})
run("K5", "Koldt vand kobber 54x1,5", "Brugsvand koldt", COLD, 10, 8760, 54, 1.5, "Kobber", "Kældergang", [((6.0, 9.45, Z0), (33.0, 9.45, Z0))],
    None, exp={"class": 2, "status": "MANGLER"})
run("K6", "Varme fremløb stål 60,3, renoveret delstrækning", "Varme", HEAT, 60, 5800, 60.3, 2.9, "Stål", "Kældergang",
    [((22.0, 10.6, Z0), (33.0, 10.6, Z0))], ("stenuld_roerskaal", 80, "pvc"), exp={"class": 3, "status": "OK"})
# plant room (22 °C, 55 % RH)
run("T1", "Fjernvarmestik stål 60,3", "Varme", DIST_OTHER, 70, 8760, 60.3, 2.9, "Stål", "Teknikrum", [((0.5, 2.0, -0.7), (6.0, 2.0, -0.7)),
    ((6.0, 2.0, -0.7), (6.0, 10.6, -0.7))], ("stenuld_roerskaal", 40, "alu_oxid"), comps=[("ventil", 4), ("energimåler", 1)],
    exp={"class": 4, "status": "UNDER"})
run("T2", "Koldt vand kobber 54x1,5, teknikrum", "Brugsvand koldt", COLD, 10, 8760, 54, 1.5, "Kobber", "Teknikrum",
    [((0.5, 4.0, -0.9), (6.0, 4.0, -0.9)), ((6.0, 4.0, -0.9), (6.0, 9.45, -0.9))], None, comps=[("ventil", 2)],
    exp={"class": 2, "status": "KONDENS"})
# risers: from the corridor into each shaft and up through the decks (same pipes and insulation as the fire-seal register)
SHAFTS = {"A1": 6.2, "A2": 9.8, "B1": 26.2, "B2": 29.8}
for tag, sx in SHAFTS.items():
    xh, xc = sx + 0.45, sx
    legs_h = [((xh, 10.6, Z0), (xh, 6.0, Z0))] + [((xh, 6.0, z + 0.05), (xh, 6.0, z + 3.1 if z < 6 else z + 2.6)) for _, z in LEVELS[:4]]
    legs_c = [((xc, 9.45, Z0), (xc, 6.0, Z0))] + [((xc, 6.0, z + 0.05), (xc, 6.0, z + 3.1 if z < 6 else z + 2.6)) for _, z in LEVELS[:4]]
    if tag == "B1":
        run(f"S-{tag}-VV", f"Stigstreng varmt brugsvand kobber 28x1, skakt {tag}", "Brugsvand varmt", DHW, 55, 8760, 28, 1.0, "Kobber",
            f"Skakt {tag}", legs_h, ("stenuld_roerskaal", 30, "pvc"), exp={"class": 4, "status": "UNDER"})
        run(f"S-{tag}-K", f"Stigstreng koldt vand kobber 22x1, skakt {tag}", "Brugsvand koldt", COLD, 10, 8760, 22, 1.0, "Kobber",
            f"Skakt {tag}", legs_c, ("elastomer", 13, "elastomer"), exp={"class": 2}, product="Armaflex AF")
    else:
        run(f"S-{tag}-V", f"Varmestreng stål 42,4x2,6, skakt {tag}", "Varme", HEAT, 60, 5800, 42.4, 2.6, "Stål", f"Skakt {tag}", legs_h,
            ("stenuld_roerskaal", 30, "pvc"), exp={"class": 3, "status": "UNDER"})
        run(f"S-{tag}-K", f"Stigstreng koldt vand kobber 22x1, skakt {tag}", "Brugsvand koldt", COLD, 10, 8760, 22, 1.0, "Kobber",
            f"Skakt {tag}", legs_c, ("elastomer", 13, "elastomer"), exp={"class": 2}, product="Kaiflex ST")
# apartments (20 °C): heating connection pipes in other rooms (class 2) and hot-water branches (class 4)
for n, (st, z) in enumerate(LEVELS[1:4]):
    run(f"L{n}-V", f"Radiatorforbindelse kobber 22x1, {st}", "Varme", CONN, 60, 5800, 22, 1.0, "Kobber", f"Lejligheder, {st.lower() if st != 'Stueetage' else 'stue'}",
        [((10.6, 4.0, z + 0.3), (25.4, 4.0, z + 0.3))], None, exp={"class": 2, "status": "MANGLER"})
    if n == 2:
        run(f"L{n}-VV", f"Brugsvandsgren kobber 22x1, {st} (bæringer uden på isoleringen)", "Brugsvand varmt", DHW, 55, 8760, 22, 1.0, "Kobber",
            "Lejligheder, 2. sal", [((10.6, 4.4, z + 2.4), (25.4, 4.4, z + 2.4))], ("stenuld_roerskaal", 50, "pvc"), supports="insulated",
            exp={"class": 4, "status": "OK"})
    else:
        run(f"L{n}-VV", f"Brugsvandsgren kobber 22x1, {st}", "Brugsvand varmt", DHW, 55, 8760, 22, 1.0, "Kobber",
            f"Lejligheder, {st.lower() if st != 'Stueetage' else 'stue'}", [((10.6, 4.4, z + 2.4), (25.4, 4.4, z + 2.4))],
            ("stenuld_roerskaal", 20, "pvc"), exp={"class": 4, "status": "UNDER"})
# loft, outside the climate envelope (≤ 5 °C column -> class 6)
run("R1", "Cirkulation kobber 28x1, tagrum", "Brugsvand varmt", DHW, 50, 8760, 28, 1.0, "Kobber", "Tagrum", [((6.6, 6.0, 9.4), (29.9, 6.0, 9.4))],
    ("stenuld_lamel", 30, "laerred"), exp={"class": 6, "status": "UNDER"})
run("R2", "Varme fremløb stål 33,7 til tagaggregat", "Varme", DIST_OTHER, 60, 5800, 33.7, 2.6, "Stål", "Tagrum", [((6.6, 6.5, 9.4), (20.0, 6.5, 9.4))],
    ("stenuld_lamel", 50, "laerred"), exp={"class": 6, "status": "UNDER"})
run("R3", "Koldt vand kobber 22x1 til tagaggregat", "Brugsvand koldt", COLD, 10, 8760, 22, 1.0, "Kobber", "Tagrum", [((6.2, 5.5, 9.4), (20.0, 5.5, 9.4))],
    ("elastomer", 13, "elastomer"), exp={"class": "DS 439", "status": "DS439"}, product="Kaiflex ST")


def gid(seed):
    return ifcopenshell.guid.compress(uuid.uuid5(uuid.NAMESPACE_URL, "blok-c-isolering/" + seed).hex)


def build(out=ROOT / "models" / "blok_c_isolering.ifc"):
    ifcw._materials.clear()
    f, project, _ = ifcw.new_file("Blok C, varme- og brugsvandsanlæg (demonstration)")
    site = element(f, "IfcSite", "Grund", container=project)
    bldg = element(f, "IfcBuilding", "Blok C (demonstration)", container=site)
    st = {}
    for n, z in LEVELS:
        s = element(f, "IfcBuildingStorey", n, container=bldg)
        s.Elevation = z
        st[n] = s
    systems = {}
    for n, t in SYSTEMS.items():
        s = api.run("system.add_system", f, ifc_class="IfcDistributionSystem")
        s.Name, s.PredefinedType = n, t
        systems[n] = s
    # decks (hollow core 220 mm, REI 60) over each storey, plant-room wall (concrete 150, EI 60)
    for n, z in LEVELS[:4]:
        top = z + 3.0
        sl = element(f, "IfcSlab", f"Huldæk 220 over {n}", [box_solid(f, 0, 0, top - SLAB, 36, 12, top)], st[n],
                     psets={"Pset_SlabCommon": {"FireRating": "REI 60", "LoadBearing": True}}, predefined="FLOOR")
        ifcw.assign_material(f, sl, "Beton, huldæk 220 mm")
        sl.GlobalId = gid(f"slab/{n}")
    w = element(f, "IfcWall", "Teknikrumsvæg, beton 150", [box_solid(f, 11.925, 0, -3.0, 12.075, 12, -0.22)], st["Kælder"],
                psets={"Pset_WallCommon": {"FireRating": "EI 60", "LoadBearing": True}}, predefined="SOLIDWALL")
    ifcw.assign_material(f, w, "Beton")
    w.GlobalId = gid("wall/teknik")
    spaces = {}
    for name, (stn, (x0, y0, z0, x1, y1, z1), ta, rh, zone) in SPACES.items():
        sp = element(f, "IfcSpace", name, [box_solid(f, x0, y0, z0, x1, y1, z1)], st[stn] if stn != "Stueetage" or "Skakt" not in name else st["Stueetage"],
                     psets={"Pset_SpaceThermalDesign": {"HeatingDryBulb": ta}, "Isoleret_Rum": {"AmbientTemperature": ta, "RelativeHumidity": rh,
                            "Zone": zone, "AmbientBand": "≤ 5 °C" if ta <= 5 else "> 5 °C"}})
        sp.GlobalId = gid(f"space/{name}")
        spaces[name] = sp
    planted = []
    for r in R:
        storey_of = lambda zz: next(n for n, z in reversed(LEVELS) if zz >= z - 0.01)
        segs = []
        for k, (p0, p1) in enumerate(r["legs"]):
            vec = [b - a for a, b in zip(p0, p1)]
            L = sum(v * v for v in vec) ** 0.5
            axis = [v / L for v in vec]
            rad = r["od"] / 2000
            el = element(f, "IfcPipeSegment", f"{r['name']} [{r['id']}.{k + 1}]", [cyl_solid(f, p0, axis, L, rad, r["wall"] / 1000)],
                         st[storey_of(min(p0[2], p1[2]))], predefined="RIGIDSEGMENT")
            el.GlobalId = gid(f"run/{r['id']}/{k}")
            ifcw.add_pset(f, el, "Pset_PipeSegmentTypeCommon", {"OuterDiameter": r["od"] / 1000, "NominalDiameter": r["od"] / 1000,
                                                                 "InnerDiameter": round((r["od"] - 2 * r["wall"]) / 1000, 5)})
            sysk, part, op = r["ds"]
            ifcw.add_pset(f, el, "Isoleret_Drift", {"RunId": r["id"], "System": sysk, "Part": part, "Operation": op or "",
                                                    "MediumTemperature": float(r["tm"]), "OperatingHours": float(r["hours"]),
                                                    "Supports": r["supports"], "Space": r["space"], "Length": round(L, 3)})
            ifcw.assign_material(f, el, r["mat"])
            api.run("system.assign_system", f, products=[el], system=systems[r["sys"]])
            if r["ins"]:
                m, t, clad = r["ins"]
                prod = r.get("product") or INS_NAME.get(m, m)
                cov = element(f, "IfcCovering", f"Isolering {prod} {t} mm [{r['id']}.{k + 1}]", [cyl_solid(f, p0, axis, L, rad + t / 1000, t / 1000)],
                              el.ContainedInStructure[0].RelatingStructure, predefined="INSULATION")
                ifcw.layered(f, cov, prod, t / 1000, m)
                ifcw.add_pset(f, cov, "Isoleret_Isolering", {"MaterialKey": m, "Thickness": t / 1000, "Cladding": clad, "Product": prod})
                cov.GlobalId = gid(f"cov/{r['id']}/{k}")
                f.createIfcRelCoversBldgElements(gid(f"rel/{r['id']}/{k}"), None, "Isolering", None, el, [cov])
            segs.append(el.GlobalId)
        # components along the first leg
        p0, p1 = r["legs"][0]
        n_all = sum(n for _, n in r["comps"])
        i = 0
        for kind, n in r["comps"]:
            for _ in range(n):
                i += 1
                t_ = i / (n_all + 1)
                c = [a + (b - a) * t_ for a, b in zip(p0, p1)]
                rad = r["od"] / 2000 * 1.6
                cls = {"ventil": "IfcValve", "pumpe": "IfcPump", "energimåler": "IfcFlowMeter"}[kind]
                comp = element(f, cls, f"{kind.capitalize()} {r['id']}-{i}", [box_solid(f, c[0] - rad, c[1] - rad, c[2] - rad, c[0] + rad, c[1] + rad, c[2] + rad)],
                               st[storey_of(c[2])])
                comp.GlobalId = gid(f"comp/{r['id']}/{i}")
                ifcw.add_pset(f, comp, "Isoleret_Komponent", {"RunId": r["id"], "Kind": kind, "Insulated": False})
                api.run("system.assign_system", f, products=[comp], system=systems[r["sys"]])
        planted.append({"id": r["id"], "name": r["name"], "segments": segs, "components": n_all, **r["exp"]})
    out.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(out))
    (out.parent / "planted.json").write_text(json.dumps(planted, indent=1, ensure_ascii=False), encoding="utf-8")
    return f, planted


if __name__ == "__main__":
    f, p = build()
    from collections import Counter
    print(len(p), "runs;", sum(len(x["segments"]) for x in p), "segments;", Counter(x.get("status") for x in p))
