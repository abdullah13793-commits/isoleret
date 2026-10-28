/* Isoleret — "Vis beregning": every step of one run's heat loss in numbers, so it can be checked by hand.
   Uses the browser engine, which is parity-tested against the Python audit (results/parity.json). */
(function (root) {
  const f = (v, d) => (v === null || v === undefined) ? '–' : Number(v).toLocaleString('da-DK', { maximumFractionDigits: d ?? 3, minimumFractionDigits: 0 });
  const BARE = { Stål: 'steel', Kobber: 'copper' };
  function steps(run, ins, label, expect) {
    const E = IEngine, KB = E.kb(), D = run.od_mm / 1000, tm = run.tm, ta = run.ambient;
    const lay = ins && ins.thickness ? [[ins.thickness, ins.material]] : [];
    const clad = (ins && ins.cladding) || 'laerred', bare = BARE[run.material] || 'steel';
    const r = E.pipe(D, lay, tm, ta, clad, { bare });
    const fac = lay.length ? run.support_factor : 1;
    const out = [];
    const L = (a, b, c) => out.push(`<tr><td>${a}</td><td class="mono">${b}</td><td class="num"><b>${c}</b></td></tr>`);
    L('Rørets udv. diameter D', 'Pset_PipeSegmentTypeCommon', `${f(D, 4)} m`);
    L('Medie θm / omgivelse θa', `rum: ${run.space}`, `${f(tm, 1)} / ${f(ta, 1)} °C`);
    if (!lay.length) {
      const eps = KB.bare[bare][1], dt = tm - ta;
      const hcv = E.hConv(D, dt), hr = E.hRad(tm, ta, eps);
      L('Uisoleret: overflade = medietemperatur', `ε (${KB.bare[bare][0]})`, f(eps, 2));
      L('h<sub>cv</sub> (vandret rør, stille luft)', D ** 3 * Math.abs(dt) <= 10 ? `1,25·(${f(Math.abs(dt), 1)}/${f(D, 4)})^(1/4)` : `1,21·${f(Math.abs(dt), 1)}^(1/3)`, `${f(hcv)} W/m²K`);
      L('h<sub>r</sub> = εσ(Ts⁴−Ta⁴)/(Ts−Ta)', '', `${f(hr)} W/m²K`);
      L('q = (h<sub>cv</sub>+h<sub>r</sub>)·π·D·(θm−θa)', `(${f(hcv)}+${f(hr)})·π·${f(D, 4)}·${f(dt, 1)}`, `${f(r.q, 2)} W/m`);
    } else {
      let Di = D, th = tm;
      const lyr = lay.map(([t, m], k) => { const Do = Di + 2 * t, tOut = th - r.q * r.R[k];
        const row = { t, m, Di, Do, tIn: th, tOut, mean: (th + tOut) / 2, lam: r.lam[k], R: r.R[k] }; Di = Do; th = tOut; return row; });
      lyr.forEach((x, k) => {
        L(`Lag ${k + 1}: ${KB.materials[x.m].name}, ${f(x.t * 1000, 0)} mm`, `D ${f(x.Di, 4)} → ${f(x.Do, 4)} m`, '');
        L('&nbsp;&nbsp;middeltemperatur i laget', `(${f(x.tIn, 1)} + ${f(x.tOut, 1)}) / 2`, `${f(x.mean, 1)} °C`);
        L('&nbsp;&nbsp;λ(θ) fra materialets kurve', 'lineær interpolation', `${f(x.lam, 4)} W/mK`);
        L('&nbsp;&nbsp;R = ln(Do/Di) / (2πλ)', `ln(${f(x.Do, 4)}/${f(x.Di, 4)}) / (2π·${f(x.lam, 4)})`, `${f(x.R, 4)} mK/W`);
      });
      const De = r.De, ts = r.ts, eps = KB.cladding[clad][1];
      const hcv = E.hConv(De, ts - ta), hr = E.hRad(ts, ta, eps), Rse = 1 / (Math.PI * De * r.h_se);
      L('Overfladetemperatur Ts (løst iterativt)', `kappe: ${KB.cladding[clad][0]}, ε ${f(eps, 2)}`, `${f(ts, 2)} °C`);
      L('h<sub>cv</sub> (vandret rør, stille luft)', De ** 3 * Math.abs(ts - ta) <= 10 ? `1,25·(${f(Math.abs(ts - ta), 2)}/${f(De, 4)})^(1/4)` : `1,21·Δθ^(1/3)`, `${f(hcv)} W/m²K`);
      L('h<sub>r</sub> = εσ(Ts⁴−Ta⁴)/(Ts−Ta)', '', `${f(hr)} W/m²K`);
      L('R<sub>se</sub> = 1 / (π·De·h<sub>se</sub>)', `1 / (π·${f(De, 4)}·${f(r.h_se)})`, `${f(Rse, 4)} mK/W`);
      L('q = (θm − θa) / (ΣR + R<sub>se</sub>)', `${f(tm - ta, 1)} / (${lyr.map(x => f(x.R, 4)).join(' + ')} + ${f(Rse, 4)})`, `${f(r.q, 2)} W/m`);
      L('Tillæg for bæringer (DS 452)', run.supports === 'insulated' ? 'uden på isoleringen' : (ta <= 5 ? 'gennem isoleringen, ude' : 'gennem isoleringen, inde'), `× ${f(fac, 2)}`);
    }
    const q = r.q * fac, U = q / (tm - ta);
    L('q inkl. tillæg', expect !== undefined ? `audit.json: ${f(expect, 2)} W/m` : '',
      `${f(q, 2)} W/m` + (expect !== undefined ? (Math.abs(q - expect) < 0.006 ? ' <span class="okline">✓</span>' : ' <span class="badline">✗</span>') : ''));
    L('U = q / (θm − θa)', `${f(q, 2)} / ${f(tm - ta, 1)}`, `${f(U, 4)} W/mK`);
    if (typeof run.class === 'number' && run.class > 0) {
      const [a, b] = KB.pipe_k[run.class];
      L(`Grænse, klasse ${run.class} (tabel 6.4: ${run.class_row.filter(Boolean).join(' / ')})`, `${f(a, 2)}·${f(D, 4)} + ${f(b, 2)}`, `${f(a * D + b, 4)} W/mK`);
      L('Opfylder klassen?', `${f(U, 4)} ≤ ${f(a * D + b, 4)}`, U <= a * D + b + 1e-9 ? '<span class="okline">ja</span>' : '<span class="badline">nej</span>');
    }
    L('Årligt tab', `${f(q, 2)} W/m · ${f(run.length, 1)} m · ${f(run.hours, 0)} h / 1000`, `${f(q * run.length * run.hours / 1000, 0)} kWh/år`);
    return `<h3 style="margin-top:12px">${label}</h3><div class="tablewrap"><table class="t calc">${out.join('')}</table></div>`;
  }
  function trace(run) {
    let h = steps(run, run.insulation, 'I dag', run.q_now);
    if (run.proposal) h += steps(run, run.proposal, `Forslag: ${run.proposal.product} ${run.proposal.thickness_mm} mm`, run.proposal.q_new);
    return h + '<p class="note">Samme beregning som rapporten og Python-motoren (paritet testet til 1e-9). σ = 5,670374·10⁻⁸ W/m²K⁴. Komponenter er ikke medregnet her.</p>';
  }
  root.IFCalc = { trace };
})(window);
