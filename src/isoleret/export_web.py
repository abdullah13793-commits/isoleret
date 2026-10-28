"""Data for the browser app: audit, validation, materials, the 3D model (one node per pipe and insulation segment, named
by GlobalId, so the viewer can colour by status or heat loss) and downloads.

python -m isoleret.export_web
"""
import json
import multiprocessing
import shutil
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as ue
import numpy as np
import trimesh

from . import ds452, economy, materials

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"


def glb(model_path, out):
    m = ifcopenshell.open(str(model_path))
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    s.set("weld-vertices", True)
    classes = ["IfcSlab", "IfcWall", "IfcSpace", "IfcPipeSegment", "IfcCovering", "IfcValve", "IfcPump", "IfcFlowMeter"]
    elems = [e for c in classes for e in m.by_type(c)]
    it = ifcopenshell.geom.iterator(s, m, multiprocessing.cpu_count(), include=elems)
    scene = trimesh.Scene()
    shell = {}
    if it.initialize():
        while True:
            sh = it.get()
            v = np.array(sh.geometry.verts).reshape(-1, 3)
            fc = np.array(sh.geometry.faces).reshape(-1, 3)
            e = m.by_guid(sh.guid)
            mesh = trimesh.Trimesh(v, fc, process=False)
            if e.is_a("IfcSlab") or e.is_a("IfcWall"):
                shell.setdefault("H_" + ("slab" if e.is_a("IfcSlab") else "wall"), []).append(mesh)
            elif e.is_a("IfcSpace"):
                scene.add_geometry(mesh, node_name="Z_" + e.Name, geom_name="Z_" + e.Name)
            else:
                pre = {"IfcPipeSegment": "P_", "IfcCovering": "I_"}.get(e.is_a(), "C_")
                run = (ue.get_psets(e).get("Isoleret_Drift") or ue.get_psets(e).get("Isoleret_Komponent") or {}).get("RunId")
                if e.is_a("IfcCovering"):
                    rel = next((r for r in m.by_type("IfcRelCoversBldgElements") if e in (r.RelatedCoverings or [])), None)
                    run = ue.get_psets(rel.RelatingBuildingElement).get("Isoleret_Drift", {}).get("RunId") if rel else None
                name = f"{pre}{run}__{sh.guid}"
                scene.add_geometry(mesh, node_name=name, geom_name=name)
            if not it.next():
                break
    for k, ms in shell.items():
        scene.add_geometry(trimesh.util.concatenate(ms), node_name=k, geom_name=k)
    out.parent.mkdir(parents=True, exist_ok=True)
    scene.export(out)


def main():
    audit = json.loads((ROOT / "results" / "audit.json").read_text(encoding="utf-8"))
    val = json.loads((ROOT / "results" / "validation.json").read_text(encoding="utf-8"))
    (WEB / "data").mkdir(parents=True, exist_ok=True)
    kb = {"materials": materials.INSULATION, "cladding": materials.CLADDING, "bare": materials.BARE, "table_6_4": [
        {"system": k[0], "part": k[1], "operation": k[2], "le5": v[0], "gt5": v[1], "condensation": k in ds452.CONDENSATION_NOTE} for k, v in ds452.TABLE_6_4.items()],
        "labels": ds452.LABEL, "pipe_k": ds452.PIPE_K, "flat_u": ds452.FLAT_U, "carriers": economy.CARRIERS, "cost": economy.COST,
        "steps_mm": economy.STEPS_MM, "component_pipe_m": economy.COMPONENT_PIPE_M}
    for name, data in (("audit.json", audit), ("validation.json", val), ("kb.json", kb)):
        (WEB / "data" / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    glb(ROOT / "models" / audit["model"], WEB / "building.glb")
    dl = WEB / "downloads"
    if dl.exists():
        shutil.rmtree(dl)
    dl.mkdir(parents=True)
    for f in (ROOT / "out").glob("*"):
        if f.is_file():
            shutil.copy(f, dl / f.name)
    shutil.copy(ROOT / "models" / audit["model"], dl / audit["model"])
    files = sorted(p.name for p in dl.iterdir())
    (WEB / "data" / "downloads.json").write_text(json.dumps(files), encoding="utf-8")
    size = sum(f.stat().st_size for f in WEB.rglob("*") if f.is_file()) / 1e6
    print("web data:", len(audit["runs"]), "runs; downloads", files, "; web MB", round(size, 1))


if __name__ == "__main__":
    main()
