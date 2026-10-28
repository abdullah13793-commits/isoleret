"""DS 452:2013 (with Ret. 1:2018), Termisk isolering af tekniske installationer: classes, limits and the rule table.

Insulation classes (pipes, D = outer pipe diameter in m), U in W/mK per metre of pipe incl. heat bridges:
    class 1: 3.3 D + 0.22   class 2: 2.6 D + 0.20   class 3: 2.0 D + 0.18
    class 4: 1.5 D + 0.16   class 5: 1.1 D + 0.14   class 6: 0.85 D + 0.12
Plane surfaces (W/m²K): 1.17 / 0.88 / 0.66 / 0.49 / 0.35 / 0.22.

Heat bridges (supports): the standard's tables assume +15 % heat loss in buildings and +25 % outside for supports that
penetrate the insulation (traditional supports, Annex A table A.2); supports outside the insulation give no
addition (table A.1). Table 6.2: joints, flanges, valves, pumps, filters and pipes in a penetration need half the class
thickness.

Table 6.4 assigns a class by system, installation part, operating condition and ambient temperature (≤ 5 °C: outside,
in the ground, unheated rooms outside the climate envelope; > 5 °C: heated rooms and unheated rooms inside the envelope).
"""
from . import physics

PIPE_K = {1: (3.3, 0.22), 2: (2.6, 0.20), 3: (2.0, 0.18), 4: (1.5, 0.16), 5: (1.1, 0.14), 6: (0.85, 0.12)}
FLAT_U = {1: 1.17, 2: 0.88, 3: 0.66, 4: 0.49, 5: 0.35, 6: 0.22}

# (system, part, operation) -> (class at ambient ≤ 5 °C, class at > 5 °C); None = not required / see other rules
TABLE_6_4 = {
    ("heating", "connection_same_room", None): (None, 0),
    ("heating", "connection_other_room", None): (6, 2),
    ("heating", "distribution", "season_le45"): (6, 3),
    ("heating", "distribution", "season_regulated"): (6, 3),
    ("heating", "distribution", "other"): (6, 4),
    ("dhw", "connection_same_room", None): (6, 0),
    ("dhw", "connection_other_room", None): (6, 4),
    ("dhw", "distribution", None): (6, 4),
    ("dhw", "tank", None): (6, 5),
    ("solar", "pipes", None): (4, 4),
    ("solar", "tank", None): (6, 5),
    ("cold_water", "pipes", None): ("DS 439", 2),
    ("heat_pump", "warm_connection", None): (6, 5),
    ("heat_pump", "cold_connection", None): (0, 4),
    ("cooling", "beams_ge15", None): (2, 2),
    ("cooling", "coils_0_15", None): (2, 2),
    ("cooling", "server_0_15", None): (4, 4),
    ("roof_drain", "internal", None): (None, 2),
}
CONDENSATION_NOTE = {("cold_water", "pipes", None), ("heat_pump", "cold_connection", None), ("cooling", "coils_0_15", None),
                     ("cooling", "server_0_15", None), ("roof_drain", "internal", None)}
LABEL = {"heating": "Opvarmningsanlæg", "dhw": "Varmt brugsvand", "solar": "Solvarme", "cold_water": "Koldt brugsvand",
         "heat_pump": "Varmepumpe", "cooling": "Køling", "roof_drain": "Tagnedløb",
         "connection_same_room": "Koblingsledning i samme rum", "connection_other_room": "Koblingsledning i andre rum / indstøbt",
         "distribution": "Fordelings- og cirkulationsledning", "tank": "Beholder / veksler", "pipes": "Rør",
         "warm_connection": "Varme forbindelsesrør til udedel", "cold_connection": "Kolde forbindelsesrør til udedel",
         "beams_ge15": "Kølebafler/-lofter θ ≥ 15 °C", "coils_0_15": "Køleflader, fancoils 0-15 °C", "server_0_15": "Serverrum 0-15 °C",
         "internal": "Indvendige tagnedløb", "season_le45": "kun i fyringssæson, θ ≤ 45 °C",
         "season_regulated": "kun i fyringssæson, reguleret fremløb", "other": "andre tilfælde (fx fjernvarme)"}


def u_limit(cls, D):
    a, b = PIPE_K[cls]
    return a * D + b


def required_class(system, part, operation=None, ambient=20.0):
    """Class from table 6.4 and whether condensation insulation is also required ('kondensisoleres efter forholdene')."""
    key = (system, part, operation if (system, part, operation) in TABLE_6_4 else None)
    if key not in TABLE_6_4:
        raise KeyError(f"table 6.4 has no row for {system}/{part}/{operation}")
    le5, gt5 = TABLE_6_4[key]
    cls = le5 if ambient <= 5 else gt5
    return {"class": cls, "row": key, "condensation": key in CONDENSATION_NOTE, "ambient_band": "≤ 5 °C" if ambient <= 5 else "> 5 °C"}


def support_factor(supports="traditional", outside=False):
    if supports == "insulated":
        return 1.0
    return 1.25 if outside else 1.15


def check(D, layers, tm, ta, cls, supports="traditional", outside=False, component=False, cladding="laerred", **kw):
    """U (incl. heat bridges) vs the class limit. component=True: valves, flanges, pumps, penetrations (half thickness rule:
    checked as thickness ≥ half the thickness the class needs on the straight pipe)."""
    if not isinstance(cls, int) or cls == 0:
        return {"ok": True, "U": None, "limit": None, "note": "ingen energikrav" if cls in (0, None) else str(cls)}
    f = support_factor(supports, outside)
    r = physics.pipe(D, layers, tm, ta, cladding, **kw)
    lim = u_limit(cls, D)
    mat = layers[0][1] if layers else "stenuld_roerskaal"
    need = physics.thickness_for(D, mat, tm, ta, lim, cladding, f, **kw)
    have = sum(t for t, _ in layers)
    if component:
        ok = need is not None and have >= need / 2 - 1e-4
        return {"ok": ok, "U": r["U"] * f, "limit": lim, "need": need / 2 if need else None, "have": have, "rule": "tabel 6.2: halv tykkelse"}
    return {"ok": r["U"] * f <= lim + 1e-9, "U": r["U"] * f, "limit": lim, "need": need, "have": have, "q": r["q"] * f, "ts": r["ts"]}
