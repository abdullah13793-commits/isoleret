"""Small IFC4 authoring helpers on top of IfcOpenShell (world-coordinate geometry, identity placements)."""
import numpy as np
import ifcopenshell.api as api
import ifcopenshell.util.element as ue


def new_file(project_name):
    f = api.run("project.create_file", version="IFC4")
    project = api.run("root.create_entity", f, ifc_class="IfcProject", name=project_name)
    units = [api.run("unit.add_si_unit", f, unit_type=t) for t in ("LENGTHUNIT", "AREAUNIT", "VOLUMEUNIT", "PLANEANGLEUNIT")]
    api.run("unit.assign_unit", f, units=units)
    model = api.run("context.add_context", f, context_type="Model")
    body = api.run("context.add_context", f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model)
    return f, project, body


def body_context(f):
    return next(c for c in f.by_type("IfcGeometricRepresentationSubContext") if c.ContextIdentifier == "Body")


def box_solid(f, x0, y0, z0, x1, y1, z1):
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    line = f.createIfcPolyline([f.createIfcCartesianPoint((float(x), float(y))) for x, y in pts])
    prof = f.createIfcArbitraryClosedProfileDef("AREA", None, line)
    pos = f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, float(z0))))
    return f.createIfcExtrudedAreaSolid(prof, pos, f.createIfcDirection((0.0, 0.0, 1.0)), float(z1 - z0))


def cyl_solid(f, p0, axis, length, radius, inner=None):
    """Circular (hollow if inner) extrusion from p0 along the unit vector axis."""
    a = np.asarray(axis, float)
    a /= np.linalg.norm(a)
    ref = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
    ref = ref - a * ref.dot(a)
    ref /= np.linalg.norm(ref)
    pos = f.createIfcAxis2Placement3D(f.createIfcCartesianPoint(tuple(float(v) for v in p0)),
                                      f.createIfcDirection(tuple(float(v) for v in a)), f.createIfcDirection(tuple(float(v) for v in ref)))
    if inner:
        prof = f.createIfcCircleHollowProfileDef("AREA", None, None, float(radius), float(radius - inner))
    else:
        prof = f.createIfcCircleProfileDef("AREA", None, None, float(radius))
    return f.createIfcExtrudedAreaSolid(prof, pos, f.createIfcDirection((0.0, 0.0, 1.0)), float(length))


def set_shape(f, product, solids):
    rep = f.createIfcShapeRepresentation(body_context(f), "Body", "SweptSolid", solids)
    api.run("geometry.assign_representation", f, product=product, representation=rep)
    if product.ObjectPlacement is None:
        api.run("geometry.edit_object_placement", f, product=product, matrix=np.eye(4))
    return rep


def add_pset(f, e, name, props):
    existing = ue.get_pset(e, name)
    ps = f.by_id(existing["id"]) if existing else api.run("pset.add_pset", f, product=e, name=name)
    api.run("pset.edit_pset", f, pset=ps, properties=dict(props))   # edit_pset consumes the dict
    return ps


def element(f, ifc_class, name, solids=None, container=None, psets=None, predefined=None, **attrs):
    e = api.run("root.create_entity", f, ifc_class=ifc_class, name=name, **({"predefined_type": predefined} if predefined else {}))
    for k, v in attrs.items():
        setattr(e, k, v)
    if solids:
        set_shape(f, e, solids)
    if container is not None:
        if e.is_a("IfcSpatialElement"):
            api.run("aggregate.assign_object", f, relating_object=container, products=[e])
        else:
            api.run("spatial.assign_container", f, relating_structure=container, products=[e])
    for pset, props in (psets or {}).items():
        add_pset(f, e, pset, props)
    return e


_materials = {}


def material(f, name, category=None):
    if name not in _materials:
        _materials[name] = api.run("material.add_material", f, name=name, category=category)
    return _materials[name]


def assign_material(f, e, name, category=None):
    api.run("material.assign_material", f, products=[e], type="IfcMaterial", material=material(f, name, category))


def layered(f, e, name, thickness, category=None):
    """Single-layer material set: how a covering carries its thickness."""
    ls = api.run("material.add_material_set", f, name=f"{name} {thickness * 1000:.0f} mm", set_type="IfcMaterialLayerSet")
    layer = api.run("material.add_layer", f, layer_set=ls, material=material(f, name, category))
    layer.LayerThickness = float(thickness)
    api.run("material.assign_material", f, products=[e], type="IfcMaterialLayerSet", material=ls)


def opening(f, host, solids, name="Udsparing"):
    op = api.run("root.create_entity", f, ifc_class="IfcOpeningElement", name=name, predefined_type="OPENING")
    set_shape(f, op, solids)
    api.run("feature.add_feature", f, feature=op, element=host)
    return op
