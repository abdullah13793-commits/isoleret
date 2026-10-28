"""Insulation materials, claddings and bare-pipe surfaces.

λ(θ) curves are typical declared values for the material class at mean temperature θ (°C), the shape that product
data sheets give (λ rises with temperature). They are defaults: a project replaces them with the declared values of the
product actually used. Two reference materials reproduce published tables (see validate.py):
  "ref_ds452"  constant design λ that reproduces DS 452 Annex A, tables A.1/A.2 (fitted, stated as such)
  "ref_ens"    λ = 0.038 W/mK, the value Energistyrelsen's Energihåndbog states for its savings tables
"""

INSULATION = {
    "stenuld_roerskaal": {"name": "Stenuld rørskål (80-100 kg/m³)", "curve": [(10, 0.034), (50, 0.039), (100, 0.046), (150, 0.055), (250, 0.078)],
                          "max_temp": 250, "fire": "A2L-s1,d0", "kind": "stone_wool"},
    "stenuld_lamel": {"name": "Stenuld lamelmåtte (pap/lærred)", "curve": [(10, 0.037), (50, 0.043), (100, 0.051), (150, 0.061)],
                      "max_temp": 250, "fire": "A2L-s1,d0", "kind": "stone_wool"},
    "elastomer": {"name": "Elastomer (cellegummi)", "curve": [(-20, 0.031), (0, 0.033), (20, 0.035), (40, 0.037), (100, 0.044)],
                  "max_temp": 105, "fire": "BL-s3,d0", "kind": "elastomeric", "mu": 7000},
    "pe_skum": {"name": "PE-skum", "curve": [(0, 0.036), (10, 0.037), (40, 0.040), (70, 0.044)], "max_temp": 90, "fire": "EL", "kind": "pe_foam",
                "mu": 3000},
    "pir": {"name": "PIR-skål", "curve": [(10, 0.022), (50, 0.026), (100, 0.031)], "max_temp": 140, "fire": "CL-s3,d0", "kind": "pir", "mu": 60},
    "ref_ds452": {"name": "DS 452 anneks A, reference (tilpasset)", "curve": [(0, 0.0459), (200, 0.0459)], "max_temp": 400, "kind": "reference"},
    "ref_ens": {"name": "Energihåndbogen, reference λ 0,038", "curve": [(0, 0.038), (200, 0.038)], "max_temp": 400, "kind": "reference"},
}

# outer surface emissivity (typical values for the surface type)
CLADDING = {"laerred": ("Lærred / pap", 0.90), "pvc": ("PVC-kappe", 0.90), "alu_blank": ("Aluminium, blank", 0.05),
            "alu_oxid": ("Aluminium, oxideret", 0.13), "galv": ("Galvaniseret stål", 0.26), "elastomer": ("Elastomer, uden kappe", 0.90),
            "ref_ds452": ("Reference, ikke-metallisk", 0.90)}
BARE = {"steel": ("Stål, malet/oxideret", 0.94), "copper": ("Kobber, oxideret", 0.60), "copper_bright": ("Kobber, blank", 0.07),
        "plastic": ("Plast (PEX, PP)", 0.90), "composite": ("Alupex", 0.90)}


def lam(material, theta):
    """λ at mean temperature θ by linear interpolation in the curve (constant beyond the ends)."""
    c = INSULATION[material]["curve"]
    if theta <= c[0][0]:
        return c[0][1]
    for (t0, l0), (t1, l1) in zip(c, c[1:]):
        if theta <= t1:
            return l0 + (l1 - l0) * (theta - t0) / (t1 - t0)
    return c[-1][1]
