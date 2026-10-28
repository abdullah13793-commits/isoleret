"""Independent reference checks: reproduce two published tables with the physics in physics.py.

V1  DS 452 Annex A, tables A.1 (supports outside the insulation) and A.2 (traditional supports, +15 %): required thickness
    for classes 1-6, Ø18-60 mm, medium 60 °C, ambient 20 °C (72 cells). The standard does not state the λ behind the
    tables; one constant design λ is fitted (non-metallic cladding, ε 0.9) and every cell is compared.
V2  Energistyrelsen, Energihåndbogen 2019, Teknisk isolering, tables 11, 12, 15, 16 (large buildings, steel pipes
    Ø35-89): annual savings in kWh/m for 0/20/30 mm → 45/50 mm, heating 45 °C 6,000 h, hot water 55 °C 8,760 h,
    ambient 15 °C (basement) and 4 °C (loft), λ = 0.038 W/mK as stated. One parameter is fitted: the emissivity of
    the bare painted steel pipe. Finding: the basement tables say half the loss before is useful heat; the published
    numbers are reproduced only if that rule is NOT applied (with it, every basement value would halve).

python -m isoleret.validate  ->  results/validation.json
"""
import json
import math
from pathlib import Path

from . import ds452, materials, physics

ROOT = Path(__file__).resolve().parents[2]
A1 = {18: [12, 15, 20, 28, 40, 61], 22: [14, 18, 24, 32, 46, 71], 28: [17, 21, 28, 38, 55, 84], 35: [19, 25, 32, 44, 64, 97],
      42: [21, 27, 36, 49, 71, 107], 60: [25, 32, 43, 59, 84, 127]}
A2 = {18: [16, 20, 27, 38, 56, 88], 22: [18, 24, 32, 44, 65, 102], 28: [22, 28, 37, 52, 76, 119], 35: [24, 32, 42, 59, 87, 136],
      42: [27, 35, 47, 65, 95, 150], 60: [31, 40, 54, 76, 111, 174]}
# (medium, ambient, hours, existing mm, new mm, {D: values row-major existing x new}), halving stated in the text: T11, T15
ENS = {"T11 Centralvarme, kælder": (45, 15, 6000, [0, 20, 30], [45, 50], {35: [217, 220, 18, 21, 8, 11], 48: [290, 293, 23, 27, 10, 14],
                                                                         60: [355, 360, 29, 34, 13, 17], 89: [509, 515, 42, 49, 18, 25]}),
       "T12 Centralvarme, loft": (45, 4, 6000, [0, 20, 30], [45, 50], {35: [307, 311, 23, 28, 10, 14], 48: [409, 415, 32, 38, 13, 19],
                                                                      60: [501, 508, 39, 46, 17, 23], 89: [715, 725, 57, 67, 25, 34]}),
       "T15 Varmt brugsvand, kælder": (55, 15, 8760, [0, 20, 30], [45, 50], {35: [455, 461, 35, 41, 15, 21], 48: [607, 615, 46, 53, 19, 27],
                                                                            60: [745, 754, 56, 66, 25, 34], 89: [1065, 1079, 81, 95, 35, 49]}),
       "T16 Varmt brugsvand, loft": (55, 4, 8760, [0, 20, 30], [45, 50], {35: [596, 604, 44, 52, 19, 27], 48: [793, 803, 58, 68, 25, 35],
                                                                         60: [971, 982, 72, 83, 32, 43], 89: [1382, 1400, 103, 121, 44, 61]})}
STEPS_MM = None


def ds452_cells(lam_ref):
    out = []
    old = materials.INSULATION["ref_ds452"]["curve"]
    materials.INSULATION["ref_ds452"]["curve"] = [(0, lam_ref), (200, lam_ref)]
    try:
        for tab, f, name in ((A1, 1.0, "A.1"), (A2, 1.15, "A.2")):
            for d, row in tab.items():
                for c in range(1, 7):
                    t = physics.thickness_for(d / 1000, "ref_ds452", 60, 20, ds452.u_limit(c, d / 1000), "ref_ds452", f)
                    out.append({"table": name, "D": d, "class": c, "published": row[c - 1], "model": round(t * 1000, 1)})
    finally:
        materials.INSULATION["ref_ds452"]["curve"] = old
    return out


def fit_ds452():
    best = None
    for k in range(400, 501):
        lam_ref = k / 10000
        cells = ds452_cells(lam_ref)
        rms = math.sqrt(sum((c["model"] - c["published"]) ** 2 for c in cells) / len(cells))
        if best is None or rms < best[0]:
            best = (rms, lam_ref, cells)
    return best


def ens_cells(eps_bare):
    out = []
    for name, (tm, ta, hrs, ex, new, rows) in ENS.items():
        for D, vals in rows.items():
            k = 0
            for e in ex:
                for n in new:
                    lay = lambda t: [(t / 1000, "ref_ens")] if t else []
                    q0 = physics.pipe(D / 1000, lay(e), tm, ta, "laerred", eps=None if e else eps_bare)["q"]
                    q1 = physics.pipe(D / 1000, lay(n), tm, ta, "laerred")["q"]
                    out.append({"table": name, "D": D, "from_mm": e, "to_mm": n, "published": vals[k], "model": round((q0 - q1) * hrs / 1000, 1),
                                "model_with_halving": round(0.5 * (q0 - q1) * hrs / 1000, 1) if "kælder" in name else None})
                    k += 1
    return out


def fit_ens():
    best = None
    for k in range(60, 101):
        eps = k / 100
        cells = ens_cells(eps)
        bare = [c for c in cells if c["from_mm"] == 0]
        rms = math.sqrt(sum(((c["model"] - c["published"]) / c["published"]) ** 2 for c in bare) / len(bare))
        if best is None or rms < best[0]:
            best = (rms, eps, cells)
    return best


def run():
    rms, lam_ref, cells = fit_ds452()
    err = [c["model"] - c["published"] for c in cells]
    v1 = {"fitted_lambda": lam_ref, "cells": len(cells), "rms_mm": round(rms, 2), "max_abs_mm": round(max(map(abs, err)), 1),
          "within_2mm": sum(abs(e) <= 2 for e in err), "within_3mm": sum(abs(e) <= 3 for e in err), "data": cells,
          "assumptions": "EN ISO 12241 cylinder, h_se = h_cv(horizontal, still air) + h_r(ε 0.9), supports A.1 ×1.00, A.2 ×1.15"}
    rms2, eps, cells2 = fit_ens()
    bare = [c for c in cells2 if c["from_mm"] == 0]
    ins = [c for c in cells2 if c["from_mm"] > 0]
    halving_bare = [c for c in bare if c["model_with_halving"] is not None]
    v2 = {"fitted_eps_bare_steel": eps, "cells": len(cells2), "bare_rms_rel_pct": round(100 * rms2, 1),
          "bare_max_rel_pct": round(100 * max(abs(c["model"] - c["published"]) / c["published"] for c in bare), 1),
          "insulated_max_abs_kwh": round(max(abs(c["model"] - c["published"]) for c in ins), 1),
          "insulated_mean_abs_kwh": round(sum(abs(c["model"] - c["published"]) for c in ins) / len(ins), 1),
          "halving_finding": {"basement_bare_cells": len(halving_bare),
                              "mean_rel_err_without_halving_pct": round(100 * sum((c["model"] - c["published"]) / c["published"] for c in halving_bare) / len(halving_bare), 1),
                              "mean_rel_err_with_halving_pct": round(100 * sum((c["model_with_halving"] - c["published"]) / c["published"] for c in halving_bare) / len(halving_bare), 1)},
          "data": cells2, "assumptions": "λ 0.038 (stated), cladding ε 0.9, bare steel ε fitted, h_cv EN ISO 12241 horizontal still air"}
    out = {"V1_DS452_annexA": v1, "V2_Energihaandbogen": v2}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "validation.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    o = run()
    for k, v in o.items():
        print(k, {a: b for a, b in v.items() if a != "data"})
