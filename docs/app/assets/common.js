/* Isoleret — shared page code: navigation, theme, data, labels. */
(function (root) {
  const $ = (s, el) => (el || document).querySelector(s);
  const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const num = (v, d) => (v === null || v === undefined || v === '' || Number.isNaN(v)) ? '–' : (Math.abs(Number(v)) < 1e-9 ? 0 : Number(v)).toLocaleString('da-DK', { maximumFractionDigits: d ?? 0, minimumFractionDigits: 0 });
  const NAV = [['index.html', 'Varmetabskort'], ['audit.html', 'Audit og materialer'], ['beregner.html', 'Beregner'], ['brand.html', 'Brandkrydstjek'], ['metode.html', 'Metode og validering'], ['verify.html', 'Verificér']];
  const STATUS = { OK: ['Opfylder DS 452', '--ok'], UNDER: ['For tynd', '--dev'], MANGLER: ['Uisoleret', '--bad'], KONDENS: ['Kondensrisiko', '--other'],
    DS439: ['Frostsikring (DS 439)', '--miss'], INGEN_KRAV: ['Intet krav', '--miss'] };
  const ORDER = ['MANGLER', 'KONDENS', 'UNDER', 'OK', 'DS439'];
  const SYS = { heating: 'Varme', dhw: 'Varmt brugsvand', cold_water: 'Koldt vand' };
  const store = {
    get(k, d) { try { const v = localStorage.getItem('iso-' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem('iso-' + k, JSON.stringify(v)); } catch (e) { } }
  };
  const t0 = store.get('theme', null); if (t0) document.documentElement.dataset.theme = t0;
  const isDark = () => css('--bg') === '#0c0e12';
  function nav() {
    const page = location.pathname.split('/').pop() || 'index.html';
    const el = document.createElement('header'); el.className = 'top';
    el.innerHTML = `<a class="brand" href="index.html"><i></i><span>Isoleret</span></a>
      <nav class="nav">${NAV.map(([h, l]) => `<a href="${h}" class="${h === page ? 'on' : ''}">${l}</a>`).join('')}</nav>
      <button class="iconbtn" id="themebtn" title="Lys / mørk" aria-label="Skift lys/mørk">◐</button>`;
    document.body.prepend(el);
    $('#themebtn').onclick = () => { const r = document.documentElement; r.dataset.theme = isDark() ? 'light' : 'dark'; store.set('theme', r.dataset.theme);
      document.dispatchEvent(new Event('themechange')); };
    const on = $('.nav a.on'); if (on) on.scrollIntoView({ block: 'nearest', inline: 'center' });
  }
  const cache = {};
  const load = (...n) => Promise.all(n.map(x => cache[x] || (cache[x] = fetch('data/' + x + '.json').then(r => r.json()))));
  async function ready() { const [kb] = await load('kb'); IEngine.load(kb); return kb; }
  const badge = s => { const [l, c] = STATUS[s] || [s, '--miss']; return `<span class="badge" style="background:var(${c})">${esc(l)}</span>`; };
  let tipEl = null;
  function tip(html, e) {
    if (!tipEl) { tipEl = document.createElement('div'); tipEl.className = 'tip'; document.body.appendChild(tipEl); }
    if (!html) { tipEl.style.display = 'none'; return; }
    tipEl.innerHTML = html; tipEl.style.display = 'block';
    tipEl.style.left = Math.min(e.clientX + 14, innerWidth - tipEl.offsetWidth - 8) + 'px'; tipEl.style.top = Math.min(e.clientY + 14, innerHeight - tipEl.offsetHeight - 8) + 'px';
  }
  function download(name, text, type) {
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type: type || 'text/plain' })); a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  const insText = i => i ? `${i.product || i.material} ${Math.round(i.thickness * 1000)} mm` : 'uisoleret';
  root.IF = { $, $$, esc, css, num, nav, load, ready, store, isDark, badge, tip, download, STATUS, ORDER, SYS, insText };
  document.addEventListener('DOMContentLoaded', nav);
})(window);
