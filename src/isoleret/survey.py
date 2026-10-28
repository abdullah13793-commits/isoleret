"""Survey (opmåling) as CSV, for existing buildings without a model: one row per run. Same fields as the IFC take-off,
so the audit is identical whichever way the data came in (tested by round trip).

Columns (semicolon-separated, UTF-8):
id; navn; system (heating|dhw|cold_water|...); del (distribution|connection_other_room|...); drift (season_le45|season_regulated|other|);
medie_C; timer; ydre_diameter_mm; godstykkelse_mm; materiale (Stål|Kobber|PEX); laengde_m; rum; omgivelse_C; rf_pct; zone;
isolering (stenuld_roerskaal|stenuld_lamel|elastomer|pe_skum|pir|); isolering_mm; kappe (laerred|pvc|alu_oxid|...); fabrikat;
baeringer (traditional|insulated); ventiler; pumper; maalere
"""
import csv
from pathlib import Path

COLS = ["id", "navn", "system", "del", "drift", "medie_C", "timer", "ydre_diameter_mm", "godstykkelse_mm", "materiale", "laengde_m", "rum",
        "omgivelse_C", "rf_pct", "zone", "isolering", "isolering_mm", "kappe", "fabrikat", "baeringer", "ventiler", "pumper", "maalere"]


def write(runs, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(COLS)
        for r in runs:
            ins = r.get("insulation") or {}
            n = lambda k: sum(1 for c in r["components"] if c["kind"] == k and not c["insulated"])
            w.writerow([r["id"], r["name"], r["system"], r["part"], r["operation"] or "", r["tm"], r["hours"], round(r["od"] * 1000, 1),
                        round(r["wall"] * 1000, 2) if r.get("wall") else "", r["material"], r["length"], r["space"], r["ambient"], r["rh"], r["zone"] or "",
                        ins.get("material") or "", round(ins["thickness"] * 1000) if ins.get("thickness") else "", ins.get("cladding") or "",
                        ins.get("product") or "", r["supports"], n("ventil"), n("pumpe"), n("energimåler")])


def read(path):
    runs = []
    with open(path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            f = lambda k: float(str(row[k]).replace(",", ".")) if row.get(k) not in (None, "") else None
            ins = None
            if row.get("isolering") and f("isolering_mm"):
                ins = {"material": row["isolering"], "thickness": f("isolering_mm") / 1000, "cladding": row.get("kappe") or "laerred",
                       "product": row.get("fabrikat") or None}
            comps = [{"kind": k, "insulated": False} for k, col in (("ventil", "ventiler"), ("pumpe", "pumper"), ("energimåler", "maalere"))
                     for _ in range(int(f(col) or 0))]
            runs.append({"id": row["id"], "name": row["navn"], "system": row["system"], "part": row["del"], "operation": row.get("drift") or None,
                         "tm": f("medie_C"), "hours": f("timer"), "od": f("ydre_diameter_mm") / 1000,
                         "wall": f("godstykkelse_mm") / 1000 if f("godstykkelse_mm") else None, "material": row["materiale"], "length": f("laengde_m"),
                         "space": row["rum"], "ambient": f("omgivelse_C"), "rh": f("rf_pct"), "zone": row.get("zone") or None, "insulation": ins,
                         "supports": row.get("baeringer") or "traditional", "components": comps, "segments": [], "penetrations": []})
    return runs


if __name__ == "__main__":
    import json
    from . import takeoff
    ROOT = Path(__file__).resolve().parents[2]
    runs, _ = takeoff.read(ROOT / "models" / "blok_c_isolering.ifc")
    (ROOT / "out").mkdir(exist_ok=True)
    write(runs, ROOT / "out" / "Opmaaling_blok_c.csv")
    write([], ROOT / "out" / "Opmaaling_skabelon.csv")
    print(len(read(ROOT / "out" / "Opmaaling_blok_c.csv")), "runs round-tripped")
