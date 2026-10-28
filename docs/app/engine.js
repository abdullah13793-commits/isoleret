/* Isoleret: browser port of physics.py, ds452.py, economy.py (parity-tested against Python). */
(function (root) {
  const SIGMA = 5.670374e-8;
  let KB = null;   // data/kb.json: materials, cladding, bare, table_6_4, pipe_k, carriers, cost, steps_mm, component_pipe_m
  function load(kb) { KB = kb; return kb; }

  function lam(material, theta) {
    const c = KB.materials[material].curve;
    if (theta <= c[0][0]) return c[0][1];
    for (let i = 0; i + 1 < c.length; i++) {
      const [t0, l0] = c[i], [t1, l1] = c[i + 1];
      if (theta <= t1) return l0 + (l1 - l0) * (theta - t0) / (t1 - t0);
    }
    return c[c.length - 1][1];
  }
  function hConv(D, dt, orientation, wind) {
    dt = Math.abs(dt) || 1e-6;
    if (wind && wind > 0) return 8.1e-3 / D + 3.14 * Math.sqrt(wind / D);
    if (orientation === 'vertical') return dt <= 10 ? 1.32 * Math.pow(dt, 0.25) : 1.74 * Math.cbrt(dt);
    return D ** 3 * dt <= 10 ? 1.25 * Math.pow(dt / D, 0.25) : 1.21 * Math.cbrt(dt);
  }
  function hRad(ts, ta, eps) {
    const Ts = ts + 273.15, Ta = ta + 273.15;
    if (Math.abs(Ts - Ta) < 1e-9) return 4 * eps * SIGMA * Ta ** 3;
    return eps * SIGMA * (Ts ** 4 - Ta ** 4) / (Ts - Ta);
  }
  const hSe = (D, ts, ta, eps, o, w) => hConv(D, ts - ta, o || 'horizontal', w || 0) + hRad(ts, ta, eps);

  function pipe(D, layers, tm, ta, cladding, opt) {
    opt = opt || {};
    const bare = opt.bare || 'steel', o = opt.orientation || 'horizontal', w = opt.wind || 0;
    layers = (layers || []).filter(([t]) => t && t > 0);
    if (!layers.length) {
      const e = opt.eps != null ? opt.eps : KB.bare[bare][1], h = hSe(D, tm, ta, e, o, w), q = h * Math.PI * D * (tm - ta);
      return { q, ts: tm, De: D, U: tm !== ta ? q / (tm - ta) : 0, R: [], lam: [], h_se: h };
    }
    const e = opt.eps != null ? opt.eps : KB.cladding[cladding || 'laerred'][1];
    const dia = [D]; for (const [t] of layers) dia.push(dia[dia.length - 1] + 2 * t);
    const De = dia[dia.length - 1];
    let ts = ta + 0.1 * (tm - ta);
    let temps = [tm]; for (let k = 0; k < layers.length; k++) temps.push(tm + (ta - tm) * (k + 1) / (layers.length + 1));
    let q = 0, R = [], lams = [], h = 0;
    for (let it = 0; it < 60; it++) {
      lams = layers.map(([t, m], k) => lam(m, ((k + 1 < temps.length ? temps[k] + temps[k + 1] : temps[k] + ts)) / 2));
      R = layers.map((_, k) => Math.log(dia[k + 1] / dia[k]) / (2 * Math.PI * lams[k]));
      h = hSe(De, ts, ta, e, o, w);
      const Rse = 1 / (Math.PI * De * h);
      q = (tm - ta) / (R.reduce((a, b) => a + b, 0) + Rse);
      const nw = [tm]; for (const r of R) nw.push(nw[nw.length - 1] - q * r);
      const tsNew = nw[nw.length - 1];
      if (Math.abs(tsNew - ts) < 1e-7) { ts = tsNew; temps = nw.slice(0, -1).concat([ts]); break; }
      ts = 0.5 * (ts + tsNew); temps = nw.slice(0, -1).concat([ts]);
    }
    return { q, ts, De, U: tm !== ta ? q / (tm - ta) : 0, R, lam: lams, h_se: h };
  }
  function dewPoint(ta, rh) { const g = Math.log(rh / 100) + 17.62 * ta / (243.12 + ta); return 243.12 * g / (17.62 - g); }
  function thicknessFor(D, material, tm, ta, target, cladding, f, steps, opt) {
    f = f || 1;
    const ok = t => f * pipe(D, [[t, material]], tm, ta, cladding, opt).U <= target;
    if (steps) { for (const t of [...steps].sort((a, b) => a - b)) if (ok(t)) return t; return null; }
    let lo = 0, hi = 0.3; if (!ok(hi)) return null;
    for (let i = 0; i < 40; i++) { const mid = (lo + hi) / 2; if (ok(mid)) hi = mid; else lo = mid; }
    return hi;
  }
  function condensationThickness(D, material, tm, ta, rh, cladding, margin, steps, opt) {
    const td = dewPoint(ta, rh) + (margin || 0);
    if (tm >= td) return 0;
    const ok = t => pipe(D, [[t, material]], tm, ta, cladding || 'elastomer', opt).ts >= td;
    if (steps) { for (const t of [...steps].sort((a, b) => a - b)) if (ok(t)) return t; return null; }
    let lo = 0, hi = 0.2; if (!ok(hi)) return null;
    for (let i = 0; i < 40; i++) { const mid = (lo + hi) / 2; if (ok(mid)) hi = mid; else lo = mid; }
    return hi;
  }
  /* DS 452 */
  const uLimit = (cls, D) => { const [a, b] = KB.pipe_k[cls]; return a * D + b; };
  function requiredClass(system, part, operation, ambient) {
    let row = KB.table_6_4.find(r => r.system === system && r.part === part && r.operation === (operation || null));
    if (!row) row = KB.table_6_4.find(r => r.system === system && r.part === part && r.operation === null);
    if (!row) return null;
    return { class: ambient <= 5 ? row.le5 : row.gt5, row, condensation: row.condensation, band: ambient <= 5 ? '≤ 5 °C' : '> 5 °C' };
  }
  const supportFactor = (s, outside) => s === 'insulated' ? 1 : (outside ? 1.25 : 1.15);
  /* economy */
  function upgradeCostPerM(D, t, cladding, replace) {
    const vol = Math.PI * ((D + 2 * t) ** 2 - D ** 2) / 4, c = KB.cost;
    return vol * c.insulation_dkk_m3 + (c.cladding_dkk_m[cladding] ?? 30) + c.labour_dkk_m + (replace ? c.removal_dkk_m : 0);
  }
  function npv(cost, kwh, price, years, rate, esc) {
    let pv = 0; for (let k = 1; k <= years; k++) pv += kwh * price * (1 + esc) ** k / (1 + rate) ** k;
    return pv - cost;
  }
  root.IEngine = { load, lam, hConv, hRad, pipe, dewPoint, thicknessFor, condensationThickness, uLimit, requiredClass, supportFactor, upgradeCostPerM, npv,
    kb: () => KB };
})(typeof window !== 'undefined' ? window : globalThis);
