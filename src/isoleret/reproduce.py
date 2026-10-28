"""Reproduce and compare: re-run validation and audit from the source model and compare with the published data; re-hash the manifest.

python -m isoleret.reproduce   (exit code 1 on any mismatch)
"""
import json
import sys
from pathlib import Path

from . import audit, manifest, takeoff, validate

ROOT = Path(__file__).resolve().parents[2]
WEB = manifest.WEB


def _key(r):
    p = r["proposal"] or {}
    return (r["id"], r["class"], r["status"], round(r["q_now"], 2), p.get("thickness_mm"), p.get("kwh"), p.get("cost_dkk"),
            [(x["host_guid"], x["now"]["status"], x["new"]["status"]) for x in r["fire"]])


def run():
    checks = []
    add = lambda n, ok, d="": checks.append({"check": n, "ok": bool(ok), "detail": d})
    pub_val = json.loads((WEB / "data" / "validation.json").read_text(encoding="utf-8"))
    v = validate.run()
    add("Validering 1: DS 452 anneks A genberegnet (72 værdier)", v["V1_DS452_annexA"]["data"] == pub_val["V1_DS452_annexA"]["data"],
        f"RMS {v['V1_DS452_annexA']['rms_mm']} mm, max {v['V1_DS452_annexA']['max_abs_mm']} mm")
    add("Validering 2: Energihåndbogen genberegnet (96 værdier)", v["V2_Energihaandbogen"]["data"] == pub_val["V2_Energihaandbogen"]["data"],
        f"uisolerede inden for {v['V2_Energihaandbogen']['bare_max_rel_pct']} %")
    runs, _ = takeoff.read(ROOT / "models" / "blok_c_isolering.ifc")
    res = [audit.audit_run(r) for r in runs]
    pub = json.loads((WEB / "data" / "audit.json").read_text(encoding="utf-8"))
    diff = [a[0] for a, b in zip(map(_key, res), map(_key, pub["runs"])) if a != b]
    add("Audit: klasse, status, varmetab, forslag, besparelse, pris, brandkrydstjek pr. strækning", len(res) == len(pub["runs"]) and not diff,
        f"{len(res)} strækninger, {len(diff)} forskelle {diff[:3]}")
    planted = ROOT / "models" / "planted.json"
    if planted.exists():
        ev = audit.evaluate_against(res, json.loads(planted.read_text(encoding="utf-8")))
        add("Facitliste (klasse fra tabel 6.4, status med klar margin til anneks A)", ev["all_ok"], f"{ev['correct']}/{ev['runs']}")
    s = audit.summary(res)
    add("Opsummering", s == pub["summary"], f"{s['kwh_saved']} kWh/år, {s['cost_dkk']} kr.")
    m = json.loads((WEB / "data" / "manifest.json").read_text(encoding="utf-8"))
    changed = [f["path"] for f in m["files"] if not (WEB / f["path"]).exists() or manifest.sha(WEB / f["path"]) != f["sha256"]]
    add("Manifest: SHA-256 for hver leveret fil", not changed, f"{len(m['files'])} filer, {len(changed)} ændret {changed[:3]}")
    out = {"ok": all(c["ok"] for c in checks), "checks": checks, "inputs": m["inputs"]}
    (WEB / "data" / "reproduce.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    if (ROOT / "results").exists():
        (ROOT / "results" / "reproduce.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    o = run()
    for c in o["checks"]:
        print("PASS" if c["ok"] else "FAIL", "|", c["check"], "|", c["detail"])
    sys.exit(0 if o["ok"] else 1)
