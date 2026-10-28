/* Landing page behaviour: theme, scroll reveal, count-up, flow line, lightbox, copy. */
(function () {
  const root = document.documentElement, reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  try { const t = localStorage.getItem('landing-theme'); if (t) root.dataset.theme = t; } catch (e) { }
  const tb = document.getElementById('theme');
  if (tb) tb.onclick = () => { const dark = getComputedStyle(root).getPropertyValue('--bg').trim() === '#0b0d11'; root.dataset.theme = dark ? 'light' : 'dark';
    try { localStorage.setItem('landing-theme', root.dataset.theme); } catch (e) { } };
  const fmt = (n, src) => Math.round(n).toLocaleString('en-US');
  function countUp(el) {
    const end = +el.dataset.count, suf = el.dataset.suffix || '', dur = 1400, t0 = performance.now();
    if (reduce) { el.textContent = fmt(end) + suf; return; }
    (function step(t) { const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3); el.textContent = fmt(end * e) + suf; if (p < 1) requestAnimationFrame(step); })(t0);
  }
  const io = 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(e => {
    if (!e.isIntersecting) return; e.target.classList.add('in');
    e.target.querySelectorAll('[data-count]').forEach(countUp); if (e.target.matches('[data-count]')) countUp(e.target);
    io.unobserve(e.target); }), { threshold: 0.18, rootMargin: '0px 0px -40px 0px' }) : null;
  document.querySelectorAll('.reveal, .lane').forEach(el => io ? io.observe(el) : el.classList.add('in'));
  if (!io) document.querySelectorAll('[data-count]').forEach(el => el.textContent = fmt(+el.dataset.count) + (el.dataset.suffix || ''));
  const lb = document.getElementById('lb');
  if (lb) { document.querySelectorAll('.gallery img, .shot img').forEach(im => im.addEventListener('click', () => { lb.querySelector('img').src = im.src; lb.classList.add('on'); }));
    lb.addEventListener('click', () => lb.classList.remove('on')); addEventListener('keydown', e => { if (e.key === 'Escape') lb.classList.remove('on'); }); }
  document.querySelectorAll('.copy').forEach(b => b.onclick = async () => { try { await navigator.clipboard.writeText(document.getElementById(b.dataset.copy).textContent);
    b.textContent = 'Copied'; setTimeout(() => b.textContent = 'Copy', 1400); } catch (e) { } });
  // pause off-screen videos (battery, CPU)
  if (io) { const vo = new IntersectionObserver(es => es.forEach(e => { const v = e.target; if (e.isIntersecting) { if (v.autoplay) v.play().catch(() => { }); } else if (!v.paused && v.autoplay) v.pause(); }), { threshold: 0.1 });
    document.querySelectorAll('video[autoplay]').forEach(v => { if (reduce) { v.removeAttribute('autoplay'); v.pause(); } else vo.observe(v); }); }
})();
