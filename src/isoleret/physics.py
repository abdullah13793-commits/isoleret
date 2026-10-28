"""Heat transfer of insulated and bare pipes, EN ISO 12241 method.

Linear heat loss of a pipe with n insulation layers (inner resistance and pipe wall neglected, surface = medium temperature):

    q = (θm − θa) / ( Σ ln(D_j+1 / D_j) / (2π λ_j(θ_mean,j)) + 1 / (π D_e h_se) )        [W/m]

λ_j is taken at the mean temperature of layer j; h_se = h_cv + h_r is the outer surface coefficient:
    h_cv  horizontal cylinder, still air, laminar (D³Δθ ≤ 10 m³K): 1.25 (Δθ/D)^¼ ; turbulent: 1.21 Δθ^⅓
          vertical cylinder / plane surface, laminar: 1.32 (Δθ/H)^¼ with H = 1 m ; turbulent 1.74 Δθ^⅓
          outdoors with wind v: 8.1e-3/D + 3.14 √(v/D)
    h_r   ε σ (Ts⁴ − Ta⁴) / (Ts − Ta)
The surface temperature, the layer temperatures and λ are solved together by fixed-point iteration.
Cold pipes use the same equations with Δθ < 0 (the surface is then colder than the air; condensation in condensation()).
"""
import math

from .materials import BARE, CLADDING, lam

SIGMA = 5.670374e-8


def h_conv(D, dt, orientation="horizontal", wind=0.0):
    dt = abs(dt) or 1e-6
    if wind and wind > 0:
        return 8.1e-3 / D + 3.14 * math.sqrt(wind / D)
    if orientation == "vertical":
        return 1.32 * dt ** 0.25 if dt <= 10 else 1.74 * dt ** (1 / 3)
    return 1.25 * (dt / D) ** 0.25 if D ** 3 * dt <= 10 else 1.21 * dt ** (1 / 3)


def h_rad(ts, ta, eps):
    Ts, Ta = ts + 273.15, ta + 273.15
    if abs(Ts - Ta) < 1e-9:
        return 4 * eps * SIGMA * Ta ** 3
    return eps * SIGMA * (Ts ** 4 - Ta ** 4) / (Ts - Ta)


def h_se(D, ts, ta, eps, orientation="horizontal", wind=0.0):
    return h_conv(D, ts - ta, orientation, wind) + h_rad(ts, ta, eps)


def pipe(D, layers, tm, ta, cladding="laerred", bare="steel", orientation="horizontal", wind=0.0, eps=None):
    """D outer pipe diameter (m); layers [(thickness m, material key), ...] from the pipe outwards.
    Returns dict(q W/m, ts °C, De m, U W/mK, R per layer, lam per layer, h_se)."""
    layers = [(t, m) for t, m in layers if t and t > 0]
    if not layers:
        e = eps if eps is not None else BARE[bare][1]
        h = h_se(D, tm, ta, e, orientation, wind)
        q = h * math.pi * D * (tm - ta)
        return {"q": q, "ts": tm, "De": D, "U": q / (tm - ta) if tm != ta else 0.0, "R": [], "lam": [], "h_se": h}
    e = eps if eps is not None else CLADDING[cladding][1]
    dia = [D]
    for t, _ in layers:
        dia.append(dia[-1] + 2 * t)
    De = dia[-1]
    ts = ta + 0.1 * (tm - ta)
    temps = [tm] + [tm + (ta - tm) * (k + 1) / (len(layers) + 1) for k in range(len(layers))]
    for _ in range(60):
        lams = [lam(m, (temps[k] + temps[k + 1] if k + 1 < len(temps) else temps[k] + ts) / 2) for k, (t, m) in enumerate(layers)]
        R = [math.log(dia[k + 1] / dia[k]) / (2 * math.pi * lams[k]) for k in range(len(layers))]
        h = h_se(De, ts, ta, e, orientation, wind)
        Rse = 1 / (math.pi * De * h)
        q = (tm - ta) / (sum(R) + Rse)
        new = [tm]
        for r in R:
            new.append(new[-1] - q * r)
        ts_new = new[-1]
        if abs(ts_new - ts) < 1e-7:
            ts = ts_new
            temps = new[:-1] + [ts]
            break
        ts = 0.5 * (ts + ts_new)
        temps = new[:-1] + [ts]
    return {"q": q, "ts": ts, "De": De, "U": q / (tm - ta) if tm != ta else 0.0, "R": R, "lam": lams, "h_se": h}


def flat(layers, tm, ta, cladding="laerred", orientation="vertical", wind=0.0):
    """Plane surface (tanks, ducts): q in W/m²."""
    layers = [(t, m) for t, m in layers if t and t > 0]
    e = CLADDING[cladding][1]
    ts = ta + 0.1 * (tm - ta)
    for _ in range(60):
        R, x = 0.0, tm
        for t, m in layers:
            R += t / lam(m, (tm + ts) / 2)
        h = h_conv(1.0, ts - ta, orientation, wind) + h_rad(ts, ta, e)
        q = (tm - ta) / (R + 1 / h)
        ts_new = tm - q * R
        if abs(ts_new - ts) < 1e-7:
            break
        ts = 0.5 * (ts + ts_new)
    return {"q": q, "ts": ts, "U": q / (tm - ta) if tm != ta else 0.0, "h_se": h}


def dew_point(ta, rh):
    """Magnus formula (Sonntag constants), °C."""
    g = math.log(rh / 100.0) + 17.62 * ta / (243.12 + ta)
    return 243.12 * g / (17.62 - g)


def thickness_for(D, material, tm, ta, target, cladding="laerred", f=1.0, steps=None, **kw):
    """Smallest insulation thickness (m) with f·U ≤ target (W/mK). steps: list of available thicknesses (m) or None for
    a continuous answer (bisection to 0.1 mm). Returns None if not reachable within 300 mm."""
    ok = lambda t: f * pipe(D, [(t, material)], tm, ta, cladding, **kw)["U"] <= target
    if steps:
        return next((t for t in sorted(steps) if ok(t)), None)
    lo, hi = 0.0, 0.3
    if not ok(hi):
        return None
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if ok(mid) else (mid, hi)
    return hi


def condensation_thickness(D, material, tm, ta, rh, cladding="elastomer", margin=0.0, steps=None, **kw):
    """Smallest thickness so the outer surface stays at or above the dew point (+ margin) of the ambient air."""
    td = dew_point(ta, rh) + margin
    if tm >= td:
        return 0.0
    ok = lambda t: pipe(D, [(t, material)], tm, ta, cladding, **kw)["ts"] >= td
    if steps:
        return next((t for t in sorted(steps) if ok(t)), None)
    lo, hi = 0.0, 0.2
    if not ok(hi):
        return None
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if ok(mid) else (mid, hi)
    return hi
