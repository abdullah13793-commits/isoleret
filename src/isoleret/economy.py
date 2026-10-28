"""Energy prices, CO2 factors, upgrade cost model and payback.

All numbers here are EXAMPLE defaults for the demonstration, editable per project (web: Beregner, API: parameters). They
are not a price list. Component losses follow Energihåndbogen's convention: a valve's surface = 0.2 m of pipe of the
same dimension, a pump = 1 m.
"""
import math

CARRIERS = {  # DKK per kWh delivered heat, kg CO2 per kWh (example values)
    "fjernvarme": {"name": "Fjernvarme", "price": 0.75, "co2": 0.066},
    "naturgas": {"name": "Naturgas (kedel 95 %)", "price": 10.11 / 11.0 / 0.95, "co2": 0.204 / 0.95},
    "varmepumpe": {"name": "Varmepumpe (el, SCOP 3)", "price": 2.40 / 3.0, "co2": 0.10 / 3.0},
}
COMPONENT_PIPE_M = {"ventil": 0.2, "energimåler": 0.2, "pumpe": 1.0}
COST = {"insulation_dkk_m3": 4500.0, "cladding_dkk_m": {"laerred": 18.0, "pvc": 32.0, "alu_oxid": 55.0, "alu_blank": 55.0, "elastomer": 0.0, "galv": 60.0},
        "labour_dkk_m": 95.0, "removal_dkk_m": 25.0, "jacket_dkk": {"ventil": 380.0, "energimåler": 380.0, "pumpe": 950.0}}
STEPS_MM = {"stenuld_roerskaal": [20, 30, 40, 50, 60, 70, 80, 100, 120, 140, 160], "stenuld_lamel": [30, 40, 50, 60, 80, 100, 120],
            "elastomer": [9, 13, 19, 25, 32, 40, 50], "pe_skum": [9, 13, 20, 30], "pir": [20, 30, 40, 50, 60, 80]}


def upgrade_cost_per_m(D, t, cladding="pvc", replace=True):
    vol = math.pi * ((D + 2 * t) ** 2 - D ** 2) / 4
    c = vol * COST["insulation_dkk_m3"] + COST["cladding_dkk_m"].get(cladding, 30.0) + COST["labour_dkk_m"]
    return c + (COST["removal_dkk_m"] if replace else 0.0)


def payback(cost, kwh, carrier="fjernvarme", prices=None):
    p = (prices or CARRIERS)[carrier]["price"]
    dkk = kwh * p
    return {"dkk_per_year": dkk, "years": cost / dkk if dkk > 0 else None}


def npv(cost, kwh, carrier="fjernvarme", years=20, rate=0.035, escalation=0.0):
    p = CARRIERS[carrier]["price"]
    pv = sum(kwh * p * (1 + escalation) ** k / (1 + rate) ** k for k in range(1, years + 1))
    return pv - cost
