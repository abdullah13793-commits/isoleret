"""Provenance manifest: every delivered file with SHA-256, producer, inputs and the checks that cover it.

python -m isoleret.manifest  ->  web/data/manifest.json (+ out/MANIFEST.json)
"""
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web" if (ROOT / "web").exists() else ROOT / "docs" / "app"
RULES = {
    "Isoleringsrapport_blok_c.pdf": ("isoleret.report", "Isoleringsrapport (PDF)", "Hver strækning: klasse, U mod grænse, forslag; beregningstrin i bilag", ["test_i10_deliverables", "test_i6_audit_consistency"]),
    "Isoleringsaudit_blok_c.xlsx": ("isoleret.report", "Audit-regneark", "Samme tal som audit.json", ["test_i10_deliverables"]),
    "Opmaaling_blok_c.csv": ("isoleret.survey", "Opmåling (CSV) for demonstrationsbygningen", "Round trip: CSV giver samme audit som IFC", ["test_i8_survey_round_trip"]),
    "Opmaaling_skabelon.csv": ("isoleret.survey", "Tom opmålingsskabelon", "Kolonnerne er dokumenteret i survey.py", []),
    "blok_c_isolering.ifc": ("isoleret.model", "Demonstrationsmodel (IFC4)", "Kilde; facitliste i models/planted.json", ["test_i5_answer_key"]),
    "validering_ds452_anneks_a.csv": ("isoleret.validate", "Validering 1, celle for celle", "Publiceret mod model for 72 værdier", ["test_i3_ds452_annex_a"]),
    "validering_energihaandbogen.csv": ("isoleret.validate", "Validering 2, celle for celle", "Publiceret mod model for 96 værdier", ["test_i4_energihaandbogen"]),
}
DATA = {"audit.json": ("isoleret.audit", ["test_i5_answer_key", "test_i6_audit_consistency", "test_i7_fire_crosscheck"]),
        "validation.json": ("isoleret.validate", ["test_i3_ds452_annex_a", "test_i4_energihaandbogen"]),
        "kb.json": ("isoleret.export_web", ["test_i9_browser_parity"]), "downloads.json": ("isoleret.export_web", [])}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def code_version():
    h = hashlib.sha256()
    for p in sorted((ROOT / "src").rglob("*.py")):
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


def kb_version():
    h = hashlib.sha256()
    for p in sorted((ROOT / "data" / "fire_kb").glob("*.json")):
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def build():
    inputs = {"model": sha(ROOT / "models" / "blok_c_isolering.ifc")[:16], "fire_kb": kb_version(), "code": code_version()}
    files = []
    for p in sorted((WEB / "downloads").glob("*")):
        r = RULES.get(p.name, (None, None, None, []))
        files.append({"path": "downloads/" + p.name, "name": p.name, "bytes": p.stat().st_size, "sha256": sha(p), "producer": r[0], "what": r[1], "how": r[2], "tests": r[3]})
    for p in sorted((WEB / "data").glob("*.json")):
        if p.name in ("manifest.json", "reproduce.json"):
            continue
        prod, tests = DATA.get(p.name, (None, []))
        files.append({"path": "data/" + p.name, "name": p.name, "bytes": p.stat().st_size, "sha256": sha(p), "producer": prod, "what": "Data bag appen",
                      "how": "Samme tal som rapporten", "tests": tests})
    m = {"product": "Isoleret", "generated": datetime.date.today().isoformat(), "inputs": inputs, "files": files, "reproduce": "python -m isoleret.reproduce"}
    (WEB / "data" / "manifest.json").write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    if (ROOT / "out").exists():
        (ROOT / "out" / "MANIFEST.json").write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    return m


if __name__ == "__main__":
    m = build()
    print(len(m["files"]), "files;", m["inputs"])
